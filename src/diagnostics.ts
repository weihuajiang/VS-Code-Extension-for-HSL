import * as vscode from "vscode";
import { BUILTIN_FUNCTIONS, ELEMENT_FUNCTIONS } from "./builtins";
import { getHslIndexService } from "./hslIntellisense";

/**
 * Creates and returns a DiagnosticCollection that validates HSL syntax.
 * Currently checks for:
 *   - `=+` which should be `= +` (assign positive) or `= ++` (assign pre-increment)
 *   - `=-` which should be `= -` (assign negative) or `= --` (assign pre-decrement)
 *   - Variable declarations that are not at the top of their code block
 */
export function createHslDiagnostics(
  context: vscode.ExtensionContext
): vscode.DiagnosticCollection {
  const diagnosticCollection =
    vscode.languages.createDiagnosticCollection("hsl");

  // Run diagnostics on the active editor when the extension activates
  if (vscode.window.activeTextEditor?.document.languageId === "hsl") {
    refreshDiagnostics(
      vscode.window.activeTextEditor.document,
      diagnosticCollection
    );
  }

  // Re-run when a document is opened or its content changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.document.languageId === "hsl") {
        refreshDiagnostics(e.document, diagnosticCollection);
      }
    }),
    vscode.workspace.onDidOpenTextDocument((doc) => {
      if (doc.languageId === "hsl") {
        refreshDiagnostics(doc, diagnosticCollection);
      }
    }),
    vscode.workspace.onDidCloseTextDocument((doc) => {
      diagnosticCollection.delete(doc.uri);
    }),
    diagnosticCollection
  );

  return diagnosticCollection;
}

/**
 * Analyse the full document and publish diagnostics.
 */
async function refreshDiagnostics(
  document: vscode.TextDocument,
  collection: vscode.DiagnosticCollection
): Promise<void> {
  const diagnostics: vscode.Diagnostic[] = [];

  // Patterns: match `=+` or `=-` that are NOT part of `+=`, `-=`, `=++`, `=--`, `==`, `!=`, `<=`, `>=`
  //   (?<![+\-!=<>])   — `=` must NOT be preceded by another operator character
  //   =                — the literal `=`
  //   \+(?!\+|=)       — a `+` NOT followed by another `+` or `=`  (avoids `=++` and `+=`)
  //   -(?!-|=)         — a `-` NOT followed by another `-` or `=`  (avoids `=--` and `-=`)
  const equalsPlusPattern = /(?<![+\-!=<>])=\+(?!\+|=)/g;
  const equalsMinusPattern = /(?<![+\-!=<>])=-(?!-|=)/g;

  const fullText = document.getText();

  // Build a set of ranges that are inside strings or comments so we can skip them
  const ignoredRanges = getIgnoredRanges(fullText);

  for (let lineIndex = 0; lineIndex < document.lineCount; lineIndex++) {
    const line = document.lineAt(lineIndex);
    const lineText = line.text;
    const lineOffset = document.offsetAt(line.range.start);

    let match: RegExpExecArray | null;

    // Check for =+
    equalsPlusPattern.lastIndex = 0;
    while ((match = equalsPlusPattern.exec(lineText)) !== null) {
      const absoluteOffset = lineOffset + match.index;
      if (isInsideIgnoredRange(absoluteOffset, ignoredRanges)) {
        continue;
      }
      const range = new vscode.Range(
        lineIndex,
        match.index,
        lineIndex,
        match.index + match[0].length
      );
      const diag = new vscode.Diagnostic(
        range,
        "'=+' is not valid HSL. Did you mean '= +' (assign positive value) or '= ++' (assign pre-increment)? Note: HSL does not have compound assignment operators like '+='.",
        vscode.DiagnosticSeverity.Error
      );
      diag.source = "hsl";
      diag.code = "invalid-equals-plus";
      diagnostics.push(diag);
    }

    // Check for =-
    equalsMinusPattern.lastIndex = 0;
    while ((match = equalsMinusPattern.exec(lineText)) !== null) {
      const absoluteOffset = lineOffset + match.index;
      if (isInsideIgnoredRange(absoluteOffset, ignoredRanges)) {
        continue;
      }
      const range = new vscode.Range(
        lineIndex,
        match.index,
        lineIndex,
        match.index + match[0].length
      );
      const diag = new vscode.Diagnostic(
        range,
        "'=-' is not valid HSL. Did you mean '= -' (assign negative value) or '= --' (assign pre-decrement)? Note: HSL does not have compound assignment operators like '-='.",
        vscode.DiagnosticSeverity.Error
      );
      diag.source = "hsl";
      diag.code = "invalid-equals-minus";
      diagnostics.push(diag);
    }
  }

  // Check that all variable declarations are at the top of their scope
  checkVariableDeclarationPlacement(document, ignoredRanges, diagnostics);

  // Check function call argument counts against known signatures
  await checkFunctionCallArity(document, ignoredRanges, diagnostics);

  collection.set(document.uri, diagnostics);
}

// ── Function call arity enforcement ──────────────────────────────────────

interface ArityRule {
  minArgs: number;
  maxArgs: number;
  variadic: boolean;
}

function buildBuiltinArityMap(): Map<string, ArityRule> {
  const map = new Map<string, ArityRule>();
  for (const fn of BUILTIN_FUNCTIONS) {
    map.set(fn.name.toLowerCase(), parseSignatureArity(fn.signature));
  }
  return map;
}

const BUILTIN_ARITY_MAP = buildBuiltinArityMap();

function buildElementMethodArityMap(): Map<string, ArityRule[]> {
  const map = new Map<string, ArityRule[]>();
  for (const fn of ELEMENT_FUNCTIONS) {
    const key = fn.name.toLowerCase();
    const rule = parseSignatureArity(fn.signature);
    const existing = map.get(key);
    if (existing) {
      if (!existing.some((entry) => areArityRulesEqual(entry, rule))) {
        existing.push(rule);
      }
      continue;
    }
    map.set(key, [rule]);
  }
  return map;
}

const ELEMENT_METHOD_ARITY_MAP = buildElementMethodArityMap();

async function checkFunctionCallArity(
  document: vscode.TextDocument,
  ignoredRanges: OffsetRange[],
  diagnostics: vscode.Diagnostic[]
): Promise<void> {
  const fullText = document.getText();
  const cleanText = buildMaskedText(fullText, ignoredRanges);

  const localArity = extractLocalFunctionArity(cleanText);

  // Extend arity map with symbols from included library files
  const indexService = getHslIndexService();
  if (indexService) {
    try {
      const visible = await indexService.getVisibleSymbolContext(document);
      for (const symbol of visible.symbols) {
        const arity: ArityRule = {
          minArgs: symbol.parameters.length,
          maxArgs: symbol.parameters.length,
          variadic: false,
        };
        const qualifiedKey = symbol.qualifiedName.toLowerCase();
        if (!localArity.has(qualifiedKey)) {
          localArity.set(qualifiedKey, arity);
        }
        const simpleKey = symbol.name.toLowerCase();
        if (!localArity.has(simpleKey) && !BUILTIN_ARITY_MAP.has(simpleKey)) {
          localArity.set(simpleKey, arity);
        }
      }
    } catch {
      // index not ready yet — continue with local-only checking
    }
  }

  const callPattern = /\b([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*\(/g;
  let match: RegExpExecArray | null;

  while ((match = callPattern.exec(cleanText)) !== null) {
    const qualifiedName = match[1];
    const nameStart = match.index;
    const openParenIndex = callPattern.lastIndex - 1;

    if (isLikelyDeclarationContext(cleanText, nameStart)) {
      continue;
    }

    if (nameStart > 0 && cleanText[nameStart - 1] === ".") {
      continue;
    }

    const closeParenIndex = findMatchingParen(cleanText, openParenIndex);
    if (closeParenIndex < 0) {
      continue;
    }

    const argCount = countTopLevelArguments(
      cleanText.slice(openParenIndex + 1, closeParenIndex)
    );

    const fnName = qualifiedName.split("::").pop() ?? qualifiedName;
    const qualifiedKey = qualifiedName.toLowerCase();
    const simpleKey = fnName.toLowerCase();
    const rule =
      localArity.get(qualifiedKey) ??
      localArity.get(simpleKey) ??
      BUILTIN_ARITY_MAP.get(simpleKey);
    if (!rule) {
      continue;
    }

    if (argCount < rule.minArgs || (!rule.variadic && argCount > rule.maxArgs)) {
      const linePos = document.positionAt(nameStart);
      const range = new vscode.Range(
        linePos.line,
        linePos.character,
        linePos.line,
        linePos.character + qualifiedName.length
      );

      const expected = formatExpectedArity(rule);
      const diagnostic = new vscode.Diagnostic(
        range,
        `Function '${qualifiedName}' expects ${expected}, but ${argCount} argument${argCount === 1 ? "" : "s"} ${argCount === 1 ? "was" : "were"} provided.`,
        vscode.DiagnosticSeverity.Error
      );
      diagnostic.source = "hsl";
      diagnostic.code = "invalid-function-arity";
      diagnostics.push(diagnostic);
      continue;
    }

    if (simpleKey === "gettime" || simpleKey === "getdate") {
      const args = splitTopLevelArguments(
        cleanText.slice(openParenIndex + 1, closeParenIndex)
      );
      if (args.length === 1 && isObviouslyNonStringLiteral(args[0])) {
        const linePos = document.positionAt(nameStart);
        const range = new vscode.Range(
          linePos.line,
          linePos.character,
          linePos.line,
          linePos.character + qualifiedName.length
        );

        const diagnostic = new vscode.Diagnostic(
          range,
          `Function '${qualifiedName}' requires a string 'format' argument.`,
          vscode.DiagnosticSeverity.Error
        );
        diagnostic.source = "hsl";
        diagnostic.code = "invalid-format-argument";
        diagnostics.push(diagnostic);
      }
    }
  }

  const methodCallPattern = /\b[A-Za-z_]\w*(?:\[[^\]]+\])?\s*\.\s*([A-Za-z_]\w*)\s*\(/g;
  while ((match = methodCallPattern.exec(cleanText)) !== null) {
    const methodName = match[1];
    const methodNameIndex = methodCallPattern.lastIndex - 1 - methodName.length;
    const openParenIndex = methodCallPattern.lastIndex - 1;
    const closeParenIndex = findMatchingParen(cleanText, openParenIndex);
    if (closeParenIndex < 0) {
      continue;
    }

    const argCount = countTopLevelArguments(
      cleanText.slice(openParenIndex + 1, closeParenIndex)
    );

    const rules = ELEMENT_METHOD_ARITY_MAP.get(methodName.toLowerCase());
    if (!rules || rules.length === 0) {
      continue;
    }

    const hasMatch = rules.some((rule) => isArityValid(rule, argCount));
    if (hasMatch) {
      continue;
    }

    const linePos = document.positionAt(methodNameIndex);
    const range = new vscode.Range(
      linePos.line,
      linePos.character,
      linePos.line,
      linePos.character + methodName.length
    );

    const expected = formatExpectedArityOptions(rules);
    const diagnostic = new vscode.Diagnostic(
      range,
      `Method '${methodName}' expects ${expected}, but ${argCount} argument${argCount === 1 ? "" : "s"} ${argCount === 1 ? "was" : "were"} provided.`,
      vscode.DiagnosticSeverity.Error
    );
    diagnostic.source = "hsl";
    diagnostic.code = "invalid-method-arity";
    diagnostics.push(diagnostic);
  }
}

function parseSignatureArity(signature: string): ArityRule {
  const trimmed = signature.trim();
  const openParen = trimmed.indexOf("(");
  const closeParen = trimmed.lastIndexOf(")");
  const inner =
    openParen >= 0 && closeParen > openParen
      ? trimmed.slice(openParen + 1, closeParen)
      : trimmed;

  const outsideText = removeBracketGroups(inner);
  const insideGroups = extractBracketGroups(inner);

  const outside = parseArityText(outsideText);
  let optionalCount = 0;
  let variadic = outside.variadic;

  for (const group of insideGroups) {
    const parsed = parseArityText(group);
    optionalCount += parsed.count;
    variadic = variadic || parsed.variadic;
  }

  return {
    minArgs: outside.count,
    maxArgs: variadic ? Number.POSITIVE_INFINITY : outside.count + optionalCount,
    variadic,
  };
}

function removeBracketGroups(text: string): string {
  let result = "";
  let bracketDepth = 0;
  for (const ch of text) {
    if (ch === "[") {
      bracketDepth++;
      continue;
    }
    if (ch === "]") {
      bracketDepth = Math.max(0, bracketDepth - 1);
      continue;
    }
    if (bracketDepth === 0) {
      result += ch;
    }
  }
  return result;
}

function extractBracketGroups(text: string): string[] {
  const groups: string[] = [];
  let bracketDepth = 0;
  let current = "";

  for (const ch of text) {
    if (ch === "[") {
      if (bracketDepth === 0) {
        current = "";
      } else {
        current += ch;
      }
      bracketDepth++;
      continue;
    }

    if (ch === "]") {
      if (bracketDepth > 1) {
        current += ch;
      }
      bracketDepth = Math.max(0, bracketDepth - 1);
      if (bracketDepth === 0) {
        groups.push(current);
      }
      continue;
    }

    if (bracketDepth > 0) {
      current += ch;
    }
  }

  return groups;
}

function parseArityText(text: string): { count: number; variadic: boolean } {
  const parts = text
    .split(",")
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  let count = 0;
  let variadic = false;

  for (const token of parts) {
    if (token.includes("...")) {
      variadic = true;
      continue;
    }
    count++;
  }

  return { count, variadic };
}

function areArityRulesEqual(left: ArityRule, right: ArityRule): boolean {
  return (
    left.minArgs === right.minArgs &&
    left.maxArgs === right.maxArgs &&
    left.variadic === right.variadic
  );
}

function extractLocalFunctionArity(cleanText: string): Map<string, ArityRule> {
  const map = new Map<string, ArityRule>();
  const pattern =
    /(^|\n)\s*(?:(?:private|public|static|global|const|synchronized)\s+)*function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*[A-Za-z_]\w*\s*(?:;|\{)/g;

  let match: RegExpExecArray | null;
  while ((match = pattern.exec(cleanText)) !== null) {
    const name = match[2].toLowerCase();
    const params = match[3]
      .split(",")
      .map((p) => p.trim())
      .filter((p) => p.length > 0 && p !== "void");

    map.set(name, {
      minArgs: params.length,
      maxArgs: params.length,
      variadic: false,
    });
  }

  return map;
}

function isLikelyDeclarationContext(cleanText: string, nameStart: number): boolean {
  const contextStart = Math.max(0, nameStart - 80);
  const prefix = cleanText.slice(contextStart, nameStart);
  return /\b(function|method|namespace)\s+$/.test(prefix);
}

function findMatchingParen(text: string, openParenIndex: number): number {
  let depth = 0;
  for (let i = openParenIndex; i < text.length; i++) {
    const ch = text[i];
    if (ch === "(") {
      depth++;
      continue;
    }
    if (ch === ")") {
      depth--;
      if (depth === 0) {
        return i;
      }
    }
  }
  return -1;
}

function countTopLevelArguments(innerArgs: string): number {
  if (innerArgs.trim() === "") {
    return 0;
  }

  let depthParen = 0;
  let depthBracket = 0;
  let depthBrace = 0;
  let commas = 0;

  for (const ch of innerArgs) {
    if (ch === "(") {
      depthParen++;
      continue;
    }
    if (ch === ")") {
      depthParen = Math.max(0, depthParen - 1);
      continue;
    }
    if (ch === "[") {
      depthBracket++;
      continue;
    }
    if (ch === "]") {
      depthBracket = Math.max(0, depthBracket - 1);
      continue;
    }
    if (ch === "{") {
      depthBrace++;
      continue;
    }
    if (ch === "}") {
      depthBrace = Math.max(0, depthBrace - 1);
      continue;
    }
    if (ch === "," && depthParen === 0 && depthBracket === 0 && depthBrace === 0) {
      commas++;
    }
  }

  return commas + 1;
}

function formatExpectedArity(rule: ArityRule): string {
  if (rule.variadic) {
    if (rule.minArgs === 0) {
      return "zero or more arguments";
    }
    return `${rule.minArgs} or more arguments`;
  }

  if (rule.minArgs === rule.maxArgs) {
    if (rule.minArgs === 1) {
      return "exactly 1 argument";
    }
    return `exactly ${rule.minArgs} arguments`;
  }

  return `${rule.minArgs} to ${rule.maxArgs} arguments`;
}

function isArityValid(rule: ArityRule, argCount: number): boolean {
  if (argCount < rule.minArgs) {
    return false;
  }
  if (!rule.variadic && argCount > rule.maxArgs) {
    return false;
  }
  return true;
}

function formatExpectedArityOptions(rules: ArityRule[]): string {
  const uniqueLabels = Array.from(
    new Set(rules.map((rule) => formatExpectedArity(rule)))
  );

  if (uniqueLabels.length === 1) {
    return uniqueLabels[0];
  }

  return `one of: ${uniqueLabels.join("; ")}`;
}

function splitTopLevelArguments(innerArgs: string): string[] {
  if (innerArgs.trim() === "") {
    return [];
  }

  const args: string[] = [];
  let depthParen = 0;
  let depthBracket = 0;
  let depthBrace = 0;
  let current = "";

  for (const ch of innerArgs) {
    if (ch === "(") {
      depthParen++;
      current += ch;
      continue;
    }
    if (ch === ")") {
      depthParen = Math.max(0, depthParen - 1);
      current += ch;
      continue;
    }
    if (ch === "[") {
      depthBracket++;
      current += ch;
      continue;
    }
    if (ch === "]") {
      depthBracket = Math.max(0, depthBracket - 1);
      current += ch;
      continue;
    }
    if (ch === "{") {
      depthBrace++;
      current += ch;
      continue;
    }
    if (ch === "}") {
      depthBrace = Math.max(0, depthBrace - 1);
      current += ch;
      continue;
    }

    if (ch === "," && depthParen === 0 && depthBracket === 0 && depthBrace === 0) {
      args.push(current.trim());
      current = "";
      continue;
    }

    current += ch;
  }

  if (current.trim().length > 0) {
    args.push(current.trim());
  }

  return args;
}

function isObviouslyNonStringLiteral(argumentText: string): boolean {
  const arg = argumentText.trim();
  if (arg.length === 0) {
    return false;
  }

  if (/^"(?:[^"\\]|\\.)*"$/.test(arg)) {
    return false;
  }

  if (/^[+-]?(?:\d+\.\d*|\d*\.\d+|\d+)$/.test(arg)) {
    return true;
  }

  if (/^(hslTrue|hslFalse)$/i.test(arg)) {
    return true;
  }

  return false;
}

function buildMaskedText(text: string, ranges: OffsetRange[]): string {
  if (ranges.length === 0) {
    return text;
  }

  const chars = [...text];
  for (const range of ranges) {
    for (let i = range.start; i < range.end && i < chars.length; i++) {
      if (chars[i] !== "\n" && chars[i] !== "\r") {
        chars[i] = " ";
      }
    }
  }
  return chars.join("");
}

// ── Variable-declaration-at-top enforcement ─────────────────────────────

/**
 * Matches a variable declaration line: optional HSL storage modifiers
 * followed by a type keyword and the start of an identifier.
 */
const DECL_PATTERN = new RegExp(
  "^\\s*(?:(?:private|static|const|global|synchronized)\\s+)*" +
    "(?:variable|string|sequence|device|resource|dialog|object|" +
    "timer|event|file|char|short|long|float)\\s+\\w"
);

/** Matches a function or method header (with optional leading modifiers). */
const FUNC_METHOD_HEADER =
  /^\s*(?:(?:private|static|const|global|synchronized)\s+)*(?:function|method)\b/;

/** Matches a namespace header (with optional leading modifiers). */
const NAMESPACE_HEADER =
  /^\s*(?:(?:private|static|const|global|synchronized)\s+)*namespace\b/;

/** Matches a struct header (with optional leading modifiers). */
const STRUCT_HEADER =
  /^\s*(?:(?:private|static|const|global|synchronized)\s+)*struct\b/;

/** Matches a preprocessor directive. */
const PREPROCESSOR_LINE = /^\s*#/;

/**
 * Matches a one-line namespace wrapper used purely for `#include` preamble,
 * e.g. `namespace _Method { #include "Lib\\File.hsl" }`.
 */
const INLINE_INCLUDE_NAMESPACE =
  /^\s*(?:(?:private|static|const|global|synchronized)\s+)*namespace\b[^{}]*\{\s*#\s*include\b[^{}]*\}\s*;?\s*$/i;

type ScopeKind =
  | "file"
  | "function"
  | "method"
  | "namespace"
  | "struct"
  | "block";

interface ScopeState {
  /** Brace depth at which this scope's opening `{` was counted. */
  braceDepth: number;
  /** True once a non-declaration statement has been seen at this scope level. */
  sawCode: boolean;
  /** Human-readable scope kind (used in diagnostic messages). */
  kind: ScopeKind;
}

/**
 * Ensures every variable declaration sits at the **top** of its enclosing
 * code block (`{ ... }`, function/method/namespace/struct body, or file scope).
 * A declaration is flagged only when it appears *after* executable code in the
 * same block.
 */
function checkVariableDeclarationPlacement(
  document: vscode.TextDocument,
  ignoredRanges: OffsetRange[],
  diagnostics: vscode.Diagnostic[]
): void {
  // The file itself is the outermost declaration scope.
  const scopeStack: ScopeState[] = [
    { braceDepth: 0, sawCode: false, kind: "file" },
  ];
  let braceDepth = 0;
  let pendingKind: ScopeKind | null = null;

  for (let lineIdx = 0; lineIdx < document.lineCount; lineIdx++) {
    const line = document.lineAt(lineIdx);
    const lineOffset = document.offsetAt(line.range.start);
    const lineStartDepth = braceDepth;
    const scopeAtLineStart = scopeStack[scopeStack.length - 1];

    // Build a version of the line with comments / strings blanked out so
    // that keywords inside literals don't trigger false positives.
    let clean = "";
    for (let ci = 0; ci < line.text.length; ci++) {
      clean += isInsideIgnoredRange(lineOffset + ci, ignoredRanges)
        ? " "
        : line.text[ci];
    }

    const trimmed = clean.trim();
    if (
      trimmed === "" ||
      PREPROCESSOR_LINE.test(trimmed) ||
      INLINE_INCLUDE_NAMESPACE.test(trimmed)
    ) {
      continue;
    }

    // ── Phase 1: detect scope-opening headers ──────────────────────
    let isScopeHeader = false;

    if (FUNC_METHOD_HEADER.test(trimmed)) {
      pendingKind = /\bfunction\b/.test(trimmed) ? "function" : "method";
      isScopeHeader = true;
    } else if (NAMESPACE_HEADER.test(trimmed)) {
      pendingKind = "namespace";
      isScopeHeader = true;
    } else if (STRUCT_HEADER.test(trimmed)) {
      pendingKind = "struct";
      isScopeHeader = true;
    }

    if (isScopeHeader) {
      // A scope-level definition counts as "code" in the enclosing scope,
      // so later declarations in that enclosing scope are invalid.
      const enclosing = scopeStack[scopeStack.length - 1];
      if (enclosing && braceDepth === enclosing.braceDepth) {
        enclosing.sawCode = true;
      }
    }

    // ── Phase 2: track braces ──────────────────────────────────────
    for (let ci = 0; ci < clean.length; ci++) {
      if (clean[ci] === "{") {
        braceDepth++;
        scopeStack.push({
          braceDepth,
          sawCode: false,
          kind: pendingKind ?? "block",
        });
        pendingKind = null;
      } else if (clean[ci] === "}") {
        const top = scopeStack[scopeStack.length - 1];
        if (top && braceDepth === top.braceDepth) {
          scopeStack.pop();
        }
        braceDepth--;
      }
    }

    // Skip lines that are purely headers or structural braces / semicolons
    if (isScopeHeader || /^[{}\s;]*$/.test(trimmed)) {
      continue;
    }

    // ── Phase 3: check variable declarations ───────────────────────
    const scope = scopeStack[scopeStack.length - 1];
    if (!scope) {
      continue;
    }

    // Between a function / method header and its opening '{',
    // declarations are parameters — not local variables.
    if (
      (pendingKind === "function" || pendingKind === "method") &&
      DECL_PATTERN.test(trimmed)
    ) {
      continue;
    }

    if (DECL_PATTERN.test(trimmed)) {
      if (scope.sawCode) {
        const startCol = line.firstNonWhitespaceCharacterIndex;
        const endCol = line.text.trimEnd().length;
        const range = new vscode.Range(lineIdx, startCol, lineIdx, endCol);

        const scopeLabel =
          scope.kind === "block" ? "code block" : `${scope.kind} scope`;

        const reason =
          `Variable declarations must appear at the top of the ${scopeLabel}, before any executable code. ` +
          `In HSL, variables must be declared at the beginning of each code block.`;

        const diag = new vscode.Diagnostic(
          range,
          reason,
          vscode.DiagnosticSeverity.Error
        );
        diag.source = "hsl";
        diag.code = "declaration-not-at-top";
        diagnostics.push(diag);
      }
      // A valid top-of-scope declaration does NOT flip sawCode.
      continue;
    }

    // ── Phase 4: executable statement → mark scope as having code ──
    if (scopeAtLineStart && lineStartDepth === scopeAtLineStart.braceDepth) {
      scopeAtLineStart.sawCode = true;
    }
  }
}

// ── Helpers to skip strings / comments ──────────────────────────────────

interface OffsetRange {
  start: number;
  end: number;
}

/**
 * Returns an array of [start, end) offset ranges that cover string literals
 * and comments so diagnostics can avoid false positives inside them.
 */
function getIgnoredRanges(text: string): OffsetRange[] {
  const ranges: OffsetRange[] = [];
  // Matches:  // line comment  |  /* block comment */  |  "string"
  const pattern = /\/\/[^\n]*|\/\*[\s\S]*?\*\/|"(?:[^"\\]|\\.)*"/g;
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    ranges.push({ start: m.index, end: m.index + m[0].length });
  }
  return ranges;
}

function isInsideIgnoredRange(offset: number, ranges: OffsetRange[]): boolean {
  for (const r of ranges) {
    if (offset >= r.start && offset < r.end) {
      return true;
    }
  }
  return false;
}
