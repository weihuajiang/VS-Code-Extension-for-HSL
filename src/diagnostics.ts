import * as vscode from "vscode";
import { BUILTIN_FUNCTIONS, ELEMENT_FUNCTIONS } from "./builtins";
import { getHslIndexService } from "./hslIntellisense";
import { execFile } from "child_process";
import * as path from "path";
import * as fs from "fs";
/**
 * Creates and returns a DiagnosticCollection that validates HSL syntax.
 * Currently checks for:
 *   - `=+` which should be `= +` (assign positive) or `= ++` (assign pre-increment)
 *   - `=-` which should be `= -` (assign negative) or `= --` (assign pre-decrement)
 *   - Variable declarations that are not at the top of their code block
 *   - `continue` keyword usage (not supported in HSL)
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
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (doc.languageId === "hsl") {
        // Use the compiled AddCheckSum.exe (.NET wrapper around
        // IHxSecurityFileCom2::SetFileValidation).  The exe ships in
        // the extension's out/ directory and targets x86/.NET 4.8 so
        // it can instantiate the 32-bit Hamilton COM object.
        const addCheckSumExe = path.join(
          context.extensionPath, "out", "AddCheckSum.exe"
        );
        if (!fs.existsSync(addCheckSumExe)) {
          vscode.window.showWarningMessage(
            `HSL Checksum update skipped: AddCheckSum.exe not found at ${addCheckSumExe}`
          );
          return;
        }
        execFile(addCheckSumExe, [doc.fileName], (err) => {
          if (err) {
            vscode.window.showWarningMessage(
              `HSL Checksum update failed: ${err.message}`
            );
          }
        });
      }
    }),
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

  // Check for unsupported 'continue' keyword
  checkContinueKeyword(document, ignoredRanges, diagnostics);

  // Check that all variable declarations are at the top of their scope
  checkVariableDeclarationPlacement(document, ignoredRanges, diagnostics);

  // Check function call argument counts against known signatures
  await checkFunctionCallArity(document, diagnostics);

  // Check that every function has both a declaration (prototype) and definition (implementation)
  checkFunctionDeclarationDefinitionPairing(document, ignoredRanges, diagnostics);

  // Check that ML_STAR is initialized before use
  checkInitializeBeforeDeviceUse(document, ignoredRanges, diagnostics);

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
  diagnostics: vscode.Diagnostic[]
): Promise<void> {
  const fullText = document.getText();
  const cleanText = buildArityMaskedText(fullText);

  const localArity = extractLocalFunctionArity(cleanText);

  // Collect ALL library arity rules per simple function name so that method
  // calls can be validated against every known overload, not just the first.
  const libraryArityByName = new Map<string, ArityRule[]>();

  // Extend arity map with symbols from included library files.
  // IMPORTANT: system-defined names (builtins + element methods) must NOT be
  // overridden by library-parsed symbols.  Library files sometimes re-declare
  // wrappers with fewer parameters than the real system function accepts.
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
        const simpleKey = symbol.name.toLowerCase();

        // Skip library symbols whose simple name collides with a system-
        // defined element method (e.g. CreateObject, Open, ReleaseObject).
        // The ELEMENT_METHOD_ARITY_MAP already contains the correct, more
        // permissive arity for these — letting the library override it is
        // the root cause of false-positive diagnostics.
        const isSystemElementMethod = ELEMENT_METHOD_ARITY_MAP.has(simpleKey);

        if (!isSystemElementMethod) {
          if (!localArity.has(qualifiedKey)) {
            localArity.set(qualifiedKey, arity);
          }
          if (!localArity.has(simpleKey) && !BUILTIN_ARITY_MAP.has(simpleKey)) {
            localArity.set(simpleKey, arity);
          }
        }

        // Always accumulate every unique arity rule per simple name so
        // the method-call fallback has the most complete picture.
        const existing = libraryArityByName.get(simpleKey);
        if (existing) {
          if (!existing.some((e) => areArityRulesEqual(e, arity))) {
            existing.push(arity);
          }
        } else {
          libraryArityByName.set(simpleKey, [arity]);
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

    const innerArgsText = fullText.slice(openParenIndex + 1, closeParenIndex);
    const argCount = countTopLevelArguments(
      innerArgsText
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
      // Before flagging, check whether a system element function with the
      // same simple name would accept this arg count.  Library files can
      // define wrappers like Object::CreateObject(programId) with fewer
      // params than the real system function (which also takes withEvents).
      const elementRules = ELEMENT_METHOD_ARITY_MAP.get(simpleKey);
      if (elementRules && elementRules.some((r) => isArityValid(r, argCount))) {
        continue;
      }

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
      const args = splitTopLevelArguments(innerArgsText);
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
    // Find the actual start of the captured method name in the matched text
    const fullMatchText = match[0];
    const capturedOffset = fullMatchText.lastIndexOf(methodName);
    const methodNameIndex = match.index + capturedOffset;
    const openParenIndex = methodCallPattern.lastIndex - 1;
    const closeParenIndex = findMatchingParen(cleanText, openParenIndex);
    if (closeParenIndex < 0) {
      continue;
    }

    const innerArgsText = fullText.slice(openParenIndex + 1, closeParenIndex);
    const argCount = countTopLevelArguments(
      innerArgsText
    );

    const methodKey = methodName.toLowerCase();
    const rules = ELEMENT_METHOD_ARITY_MAP.get(methodKey);
    if (!rules || rules.length === 0) {
      // Method is not a known element method — skip; we cannot validate it.
      continue;
    }

    const hasMatch = rules.some((rule) => isArityValid(rule, argCount));
    if (hasMatch) {
      continue;
    }

    // Also check library-defined functions with the same simple name.
    // The extension cannot determine the receiver type on a `.Method()` call,
    // so if any known function with this name accepts this arg count, allow it.
    const libraryRules = libraryArityByName.get(methodKey);
    if (libraryRules && libraryRules.some((rule) => isArityValid(rule, argCount))) {
      continue;
    }

    // Because this arity mismatch can prevent execution, report it as an
    // Error even though unresolved receiver typing can still cause
    // occasional false positives.
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
      `Method '${methodName}' expects ${expected}, but ${argCount} argument${argCount === 1 ? "" : "s"} ${argCount === 1 ? "was" : "were"} provided. Note: the receiver's object type could not be determined; this may be a false positive if the object defines its own '${methodName}' method.`,
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
  if (/\b(function|method|namespace)\s+$/.test(prefix)) {
    return true;
  }
  // If the line starts with "variable " or "variable& ", this is a variable
  // declaration — parentheses are used for initialisation, not function calls.
  const lineStart = cleanText.lastIndexOf("\n", nameStart - 1) + 1;
  const linePrefix = cleanText.slice(lineStart, nameStart).trimStart();
  if (/^variable&?\s/i.test(linePrefix)) {
    return true;
  }
  return false;
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
  return splitTopLevelArguments(innerArgs).length;
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

  let inString = false;
  let inLineComment = false;
  let inBlockComment = false;
  let escaped = false;

  for (let i = 0; i < innerArgs.length; i++) {
    const ch = innerArgs[i];
    const next = i + 1 < innerArgs.length ? innerArgs[i + 1] : "";

    if (inLineComment) {
      current += ch;
      if (ch === "\n") {
        inLineComment = false;
      }
      continue;
    }

    if (inBlockComment) {
      current += ch;
      if (ch === "*" && next === "/") {
        current += next;
        i++;
        inBlockComment = false;
      }
      continue;
    }

    if (inString) {
      current += ch;
      if (escaped) {
        escaped = false;
        continue;
      }
      if (ch === "\\") {
        escaped = true;
        continue;
      }
      if (ch === '"') {
        inString = false;
      }
      continue;
    }

    if (ch === '"') {
      current += ch;
      inString = true;
      escaped = false;
      continue;
    }

    if (ch === "/" && next === "/") {
      current += ch + next;
      i++;
      inLineComment = true;
      continue;
    }

    if (ch === "/" && next === "*") {
      current += ch + next;
      i++;
      inBlockComment = true;
      continue;
    }

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
 * Flags any use of the `continue` keyword as a syntax error.
 * HSL does not support `continue` in loops or conditionals.
 */
function checkContinueKeyword(
  document: vscode.TextDocument,
  ignoredRanges: OffsetRange[],
  diagnostics: vscode.Diagnostic[]
): void {
  const continuePattern = /\bcontinue\b/gi;

  for (let lineIndex = 0; lineIndex < document.lineCount; lineIndex++) {
    const line = document.lineAt(lineIndex);
    const lineText = line.text;
    const lineOffset = document.offsetAt(line.range.start);

    continuePattern.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = continuePattern.exec(lineText)) !== null) {
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
        "'continue' is not a valid HSL keyword. HSL does not support 'continue' in loops or conditionals.",
        vscode.DiagnosticSeverity.Error
      );
      diag.source = "hsl";
      diag.code = "invalid-continue";
      diagnostics.push(diag);
    }
  }
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
  const includePreambleLines = collectIncludePreambleNamespaceLines(
    document,
    ignoredRanges
  );

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

    if (includePreambleLines.has(lineIdx)) {
      for (let ci = 0; ci < clean.length; ci++) {
        if (clean[ci] === "{") {
          braceDepth++;
          continue;
        }
        if (clean[ci] === "}") {
          braceDepth = Math.max(0, braceDepth - 1);
        }
      }
      continue;
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
      // A function or method definition counts as "code" in the enclosing
      // scope, so later declarations in that enclosing scope are invalid.
      // Namespace (and struct) headers do NOT — variables may still appear
      // after namespace blocks as long as no functions have been defined.
      const enclosing = scopeStack[scopeStack.length - 1];
      if (
        enclosing &&
        braceDepth === enclosing.braceDepth &&
        pendingKind !== "namespace" &&
        pendingKind !== "struct"
      ) {
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

function collectIncludePreambleNamespaceLines(
  document: vscode.TextDocument,
  ignoredRanges: OffsetRange[]
): Set<number> {
  const lines: string[] = [];

  for (let lineIdx = 0; lineIdx < document.lineCount; lineIdx++) {
    const line = document.lineAt(lineIdx);
    const lineOffset = document.offsetAt(line.range.start);

    let clean = "";
    for (let ci = 0; ci < line.text.length; ci++) {
      clean += isInsideIgnoredRange(lineOffset + ci, ignoredRanges)
        ? " "
        : line.text[ci];
    }

    lines.push(clean);
  }

  const includePreambleLines = new Set<number>();

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const trimmed = lines[lineIdx].trim();
    if (!NAMESPACE_HEADER.test(trimmed)) {
      continue;
    }

    let openFound = false;
    let localDepth = 0;
    let endLine = -1;

    for (let scanLine = lineIdx; scanLine < lines.length; scanLine++) {
      const lineText = lines[scanLine];

      for (let ci = 0; ci < lineText.length; ci++) {
        const ch = lineText[ci];
        if (ch === "{") {
          openFound = true;
          localDepth++;
          continue;
        }

        if (ch === "}" && openFound) {
          localDepth = Math.max(0, localDepth - 1);
          if (localDepth === 0) {
            endLine = scanLine;
            break;
          }
        }
      }

      if (endLine >= 0) {
        break;
      }

      if (!openFound && /;/.test(lineText)) {
        break;
      }
    }

    if (!openFound || endLine < 0) {
      continue;
    }

    let hasInclude = false;
    let hasNonPreambleContent = false;

    for (let evalLine = lineIdx; evalLine <= endLine; evalLine++) {
      const text = lines[evalLine].trim();
      if (text === "" || /^[{}\s;]*$/.test(text)) {
        continue;
      }

      if (/#\s*include\b/i.test(text)) {
        hasInclude = true;
      }

      if (NAMESPACE_HEADER.test(text) || /^#/.test(text)) {
        continue;
      }

      hasNonPreambleContent = true;
      break;
    }

    if (!hasInclude || hasNonPreambleContent) {
      continue;
    }

    for (let markLine = lineIdx; markLine <= endLine; markLine++) {
      includePreambleLines.add(markLine);
    }

    lineIdx = endLine;
  }

  return includePreambleLines;
}

// ── Helpers to skip strings / comments ──────────────────────────────────

interface OffsetRange {
  start: number;
  end: number;
}

interface IgnoredSegment extends OffsetRange {
  kind: "string" | "comment";
}

/**
 * Returns an array of [start, end) offset ranges that cover string literals
 * and comments so diagnostics can avoid false positives inside them.
 */
function getIgnoredRanges(text: string): OffsetRange[] {
  return getIgnoredSegments(text).map(({ start, end }) => ({ start, end }));
}

function getIgnoredSegments(text: string): IgnoredSegment[] {
  const ranges: IgnoredSegment[] = [];
  // Matches:  // line comment  |  /* block comment */  |  "string"
  const pattern = /\/\/[^\n]*|\/\*[\s\S]*?\*\/|"(?:[^"\\]|\\.)*"/g;
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    ranges.push({
      start: m.index,
      end: m.index + m[0].length,
      kind: m[0].startsWith('"') ? "string" : "comment",
    });
  }
  return ranges;
}


function buildArityMaskedText(text: string): string {
  const segments = getIgnoredSegments(text);
  if (segments.length === 0) {
    return text;
  }

  const ranges: OffsetRange[] = [];
  const chars = [...text];

  for (const segment of segments) {
    if (segment.kind === "comment") {
      ranges.push(segment);
      continue;
    }

    const stringInnerStart = segment.start + 1;
    const stringInnerEnd = Math.max(stringInnerStart, segment.end - 1);
    ranges.push({ start: stringInnerStart, end: stringInnerEnd });
  }

  for (const range of ranges) {
    for (let i = range.start; i < range.end && i < chars.length; i++) {
      if (chars[i] !== "\n" && chars[i] !== "\r") {
        chars[i] = " ";
      }
    }
  }

  return chars.join("");
}

function isInsideIgnoredRange(offset: number, ranges: OffsetRange[]): boolean {
  for (const r of ranges) {
    if (offset >= r.start && offset < r.end) {
      return true;
    }
  }
  return false;
}

// ── Function declaration / definition pairing enforcement ───────────────

interface FunctionRecord {
  /** Normalised key that identifies identical signatures. */
  signatureKey: string;
  /** Human-readable display name for diagnostic messages. */
  displayName: string;
  /** Whether this is a prototype (`;`) or an implementation (`{ … }`). */
  kind: "declaration" | "definition";
  /** Line index where the function header starts. */
  lineIndex: number;
  /** Column of the function name within that line. */
  nameCol: number;
  /** Length of the function name. */
  nameLen: number;
}

/**
 * Ensure that every function within the document has both a declaration
 * (prototype ending with `;`) and a definition (implementation with `{ … }`).
 */
function checkFunctionDeclarationDefinitionPairing(
  document: vscode.TextDocument,
  ignoredRanges: OffsetRange[],
  diagnostics: vscode.Diagnostic[]
): void {
  const fullText = document.getText();
  const cleanText = buildMaskedText(fullText, ignoredRanges);
  const records = collectFunctionRecords(cleanText);

  // Group records by signature key
  const byKey = new Map<string, FunctionRecord[]>();
  for (const rec of records) {
    const group = byKey.get(rec.signatureKey) ?? [];
    group.push(rec);
    byKey.set(rec.signatureKey, group);
  }

  // Build a secondary index by namespace-agnostic key so that declarations
  // at the top level can match definitions inside a namespace (and vice
  // versa).  Key format: `modKey||name|paramSig|returnType` (namespace
  // portion is always empty).
  const stripNamespace = (key: string): string => {
    const parts = key.split("|");
    // parts: [modKey, nsPrefix, name, paramSig, returnType]
    return `${parts[0]}||${parts[2]}|${parts.slice(3).join("|")}`;
  };

  const byNameKey = new Map<string, FunctionRecord[]>();
  for (const rec of records) {
    const nameKey = stripNamespace(rec.signatureKey);
    const group = byNameKey.get(nameKey) ?? [];
    group.push(rec);
    byNameKey.set(nameKey, group);
  }

  for (const [_key, group] of byKey) {
    const declarations = group.filter((r) => r.kind === "declaration");
    const definitions = group.filter((r) => r.kind === "definition");

    if (declarations.length > 0 && definitions.length === 0) {
      // Check if a definition exists in another namespace
      // (e.g. private helper declared at top level, defined in a namespace).
      const nameKey = stripNamespace(declarations[0].signatureKey);
      const crossNs = byNameKey.get(nameKey) ?? [];
      const crossNsDef = crossNs.find((r) => r.kind === "definition");

      if (crossNsDef) {
        // Definition exists but in a different namespace — warn, not error
        for (const decl of declarations) {
          const range = new vscode.Range(
            decl.lineIndex,
            decl.nameCol,
            decl.lineIndex,
            decl.nameCol + decl.nameLen
          );
          const diag = new vscode.Diagnostic(
            range,
            `Declaration of '${decl.displayName}' and its definition '${crossNsDef.displayName}' are in different namespaces. Best practice: keep declaration and definition in the same namespace.`,
            vscode.DiagnosticSeverity.Warning
          );
          diag.source = "hsl";
          diag.code = "cross-namespace-function-definition";
          diagnostics.push(diag);
        }
      } else {
        for (const decl of declarations) {
          const range = new vscode.Range(
            decl.lineIndex,
            decl.nameCol,
            decl.lineIndex,
            decl.nameCol + decl.nameLen
          );
          const diag = new vscode.Diagnostic(
            range,
            `Missing definition for function '${decl.displayName}'.`,
            vscode.DiagnosticSeverity.Error
          );
          diag.source = "hsl";
          diag.code = "missing-function-definition";
          diagnostics.push(diag);
        }
      }
    }

    if (definitions.length > 0 && declarations.length === 0) {
      // Check if a declaration exists in another namespace.
      const nameKey = stripNamespace(definitions[0].signatureKey);
      const crossNs = byNameKey.get(nameKey) ?? [];
      const crossNsDecl = crossNs.find((r) => r.kind === "declaration");

      if (crossNsDecl) {
        // Declaration exists but in a different namespace — warn, not error
        for (const def of definitions) {
          const range = new vscode.Range(
            def.lineIndex,
            def.nameCol,
            def.lineIndex,
            def.nameCol + def.nameLen
          );
          const diag = new vscode.Diagnostic(
            range,
            `Definition of '${def.displayName}' and its declaration '${crossNsDecl.displayName}' are in different namespaces. Best practice: keep declaration and definition in the same namespace.`,
            vscode.DiagnosticSeverity.Warning
          );
          diag.source = "hsl";
          diag.code = "cross-namespace-function-declaration";
          diagnostics.push(diag);
        }
      } else {
        for (const def of definitions) {
          const range = new vscode.Range(
            def.lineIndex,
            def.nameCol,
            def.lineIndex,
            def.nameCol + def.nameLen
          );
          const diag = new vscode.Diagnostic(
            range,
            `Missing declaration for function '${def.displayName}'.`,
            vscode.DiagnosticSeverity.Error
          );
          diag.source = "hsl";
          diag.code = "missing-function-declaration";
          diagnostics.push(diag);
        }
      }
    }

    if (definitions.length > 1) {
      for (const def of definitions) {
        const range = new vscode.Range(
          def.lineIndex,
          def.nameCol,
          def.lineIndex,
          def.nameCol + def.nameLen
        );
        const diag = new vscode.Diagnostic(
          range,
          `Duplicate definition for function '${def.displayName}'.`,
          vscode.DiagnosticSeverity.Error
        );
        diag.source = "hsl";
        diag.code = "duplicate-function-definition";
        diagnostics.push(diag);
      }
    }
  }
}

/**
 * Walk through the comment/string-masked source text and collect every
 * function header, classifying each as either a declaration or definition.
 */
function collectFunctionRecords(cleanText: string): FunctionRecord[] {
  const records: FunctionRecord[] = [];
  const cleanLines = cleanText.split(/\r?\n/);

  const namespaceStack: Array<{ name: string; depth: number }> = [];
  let braceDepth = 0;
  let pendingNamespace: string | null = null;

  let collectingFunction = false;
  let functionStartLine = -1;
  let functionHeaderParts: string[] = [];

  for (let lineIndex = 0; lineIndex < cleanLines.length; lineIndex++) {
    const cleanLine = cleanLines[lineIndex];

    if (!collectingFunction) {
      // Detect namespace header
      const nsMatch =
        /^\s*(?:(?:private|public|static|global|const|synchronized)\s+)*namespace\s+([A-Za-z_]\w*)\b/.exec(
          cleanLine
        );
      if (nsMatch) {
        pendingNamespace = nsMatch[1];
      }

      // Detect function header start
      if (
        /^\s*(?:(?:private|public|static|global|const|synchronized)\s+)*function\b/.test(
          cleanLine
        )
      ) {
        collectingFunction = true;
        functionStartLine = lineIndex;
        functionHeaderParts = [cleanLine];
      }
    } else {
      functionHeaderParts.push(cleanLine);
    }

    if (collectingFunction) {
      const joinedClean = functionHeaderParts.join("\n");
      const openParens = (joinedClean.match(/\(/g) || []).length;
      const closeParens = (joinedClean.match(/\)/g) || []).length;
      const parenDelta = openParens - closeParens;

      if (parenDelta <= 0 && /[;{]/.test(joinedClean)) {
        // Extract function components
        const fnMatch =
          /^\s*((?:(?:private|public|static|global|const|synchronized)\s+)*)function\s+([A-Za-z_]\w*)\s*\(([\s\S]*?)\)\s*([A-Za-z_]\w*)\s*(;|\{)/m.exec(
            joinedClean
          );

        if (fnMatch) {
          const modifiers = fnMatch[1] ?? "";
          const name = fnMatch[2];
          const paramsRaw = fnMatch[3] ?? "";
          const returnTypeText = fnMatch[4] ?? "variable";
          const terminator = fnMatch[5];

          const kind: "declaration" | "definition" =
            terminator === ";" ? "declaration" : "definition";

          // Compute fully-qualified namespace prefix
          const nsPrefix = namespaceStack.map((n) => n.name).join("::");
          const qualifiedName =
            nsPrefix.length > 0 ? `${nsPrefix}::${name}` : name;

          // Normalise parameter signature (types only, no names)
          const paramSig = buildNormalizedParamSignature(paramsRaw);

          // Include private / static in the key so mismatches are caught
          const modParts: string[] = [];
          if (/\bprivate\b/i.test(modifiers)) {
            modParts.push("private");
          }
          if (/\bstatic\b/i.test(modifiers)) {
            modParts.push("static");
          }
          const modKey = modParts.join(" ");

          const signatureKey =
            `${modKey}|${nsPrefix.toLowerCase()}|${name.toLowerCase()}|${paramSig}|${returnTypeText.toLowerCase()}`;

          // Locate the function name within the starting line for a precise range
          const startLineText = cleanLines[functionStartLine];
          const funcKwIdx = startLineText.indexOf("function");
          const nameIdx =
            funcKwIdx >= 0
              ? startLineText.indexOf(name, funcKwIdx + 8)
              : startLineText.indexOf(name);
          const nameCol = nameIdx >= 0 ? nameIdx : 0;

          records.push({
            signatureKey,
            displayName: qualifiedName,
            kind,
            lineIndex: functionStartLine,
            nameCol,
            nameLen: name.length,
          });
        }

        collectingFunction = false;
        functionStartLine = -1;
        functionHeaderParts = [];
      }
    }

    // ── Track braces for namespace management ──────────────────────
    for (const ch of cleanLine) {
      if (ch === "{") {
        braceDepth++;
        if (pendingNamespace) {
          namespaceStack.push({
            name: pendingNamespace,
            depth: braceDepth,
          });
          pendingNamespace = null;
        }
      } else if (ch === "}") {
        while (
          namespaceStack.length > 0 &&
          namespaceStack[namespaceStack.length - 1].depth >= braceDepth
        ) {
          namespaceStack.pop();
        }
        braceDepth = Math.max(0, braceDepth - 1);
      }
    }
  }

  return records;
}

/**
 * Normalise a raw parameter list into a canonical form that only retains
 * the type, by-ref marker `&`, and array marker `[]` for each parameter.
 * Parameter names and default values are discarded.
 *
 * Example input:  `variable i_tblValues[], variable& o_x, string s`
 * Example output: `variable[],variable&,string`
 */
function buildNormalizedParamSignature(paramsRaw: string): string {
  const parts = splitArgsForSignature(paramsRaw).filter(
    (p) => p.toLowerCase() !== "void"
  );

  return parts
    .map((p) => {
      // Strip default value
      const noDefault = p.includes("=")
        ? p.slice(0, p.indexOf("=")).trim()
        : p.trim();
      // Detect array suffix
      const isArray = /\[\]\s*$/.test(noDefault);
      const noArray = noDefault.replace(/\[\]\s*$/, "").trim();
      // Detect by-ref
      const isByRef = noArray.includes("&");
      const noRef = noArray.replace(/&/g, "").trim();
      // Type is the first token
      const tokens = noRef.split(/\s+/).filter((t) => t.length > 0);
      const typeText = tokens.length > 0 ? tokens[0].toLowerCase() : "";
      return `${typeText}${isByRef ? "&" : ""}${isArray ? "[]" : ""}`;
    })
    .join(",");
}

/**
 * Split a parameter list by commas, respecting nested parentheses and brackets.
 */
function splitArgsForSignature(paramList: string): string[] {
  const parts: string[] = [];
  let current = "";
  let depth = 0;
  for (const c of paramList) {
    if (c === "(" || c === "[") {
      depth++;
      current += c;
      continue;
    }
    if (c === ")" || c === "]") {
      depth = Math.max(0, depth - 1);
      current += c;
      continue;
    }
    if (c === "," && depth === 0) {
      parts.push(current.trim());
      current = "";
      continue;
    }
    current += c;
  }
  if (current.trim().length > 0) {
    parts.push(current.trim());
  }
  return parts.filter((p) => p.length > 0);
}

// ── Initialize step enforcement ─────────────────────────────────────────

/** The Initialize CLSID (underscore format) used in ML_STAR._<CLSID>() calls. */
const INITIALIZE_CLSID = "1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2";

/**
 * Detects when ML_STAR (or any device object) is used in a `method main()`
 * body without a preceding Initialize step.  The Initialize step
 * (`ML_STAR._1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2(...)`) must be called
 * before any other device commands can execute.
 *
 * Reports an error on the first device usage line that appears before
 * (or without) the Initialize call.
 */
function checkInitializeBeforeDeviceUse(
  document: vscode.TextDocument,
  ignoredRanges: OffsetRange[],
  diagnostics: vscode.Diagnostic[]
): void {
  const fullText = document.getText();

  // Find `method main()` body — we only enforce this in main since that is
  // the entry point where Initialize must be called.  Library functions
  // receive an already-initialised device reference.
  const mainMethodPattern = /\bmethod\s+main\s*\(/g;
  const mainMatch = mainMethodPattern.exec(fullText);
  if (!mainMatch) {
    return;
  }

  // Find the opening brace of main()
  let mainBodyStart = -1;
  for (let i = mainMatch.index + mainMatch[0].length; i < fullText.length; i++) {
    if (fullText[i] === "{") {
      mainBodyStart = i;
      break;
    }
  }
  if (mainBodyStart < 0) {
    return;
  }

  // Find the matching closing brace
  let depth = 0;
  let mainBodyEnd = -1;
  for (let i = mainBodyStart; i < fullText.length; i++) {
    if (isInsideIgnoredRange(i, ignoredRanges)) {
      continue;
    }
    if (fullText[i] === "{") {
      depth++;
    } else if (fullText[i] === "}") {
      depth--;
      if (depth === 0) {
        mainBodyEnd = i;
        break;
      }
    }
  }
  if (mainBodyEnd < 0) {
    mainBodyEnd = fullText.length;
  }

  const mainBody = fullText.slice(mainBodyStart, mainBodyEnd + 1);
  const mainBodyOffset = mainBodyStart;

  // Detect `global device` declarations to learn device variable names.
  // Default to ML_STAR if none found.
  const deviceNames = new Set<string>();
  const globalDevicePattern = /\bglobal\s+device\s+([A-Za-z_]\w*)/g;
  let devMatch: RegExpExecArray | null;
  while ((devMatch = globalDevicePattern.exec(fullText)) !== null) {
    deviceNames.add(devMatch[1]);
  }
  if (deviceNames.size === 0) {
    deviceNames.add("ML_STAR");
  }

  // Build a pattern that matches:
  //   DEVICE._<any CLSID>( ... )   — device step calls
  // We check for the Initialize CLSID specifically.
  const deviceNamesEscaped = Array.from(deviceNames)
    .map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");

  // Find the Initialize call within main body
  const initPattern = new RegExp(
    `\\b(?:${deviceNamesEscaped})\\._${INITIALIZE_CLSID}\\s*\\(`,
    "i"
  );
  const initMatch = initPattern.exec(mainBody);
  const initOffset = initMatch
    ? mainBodyOffset + initMatch.index
    : -1;

  // Find ALL device step calls (DEVICE._CLSID(...)) in main body
  const deviceStepPattern = new RegExp(
    `\\b(${deviceNamesEscaped})\\._([0-9A-Fa-f_]+)\\s*\\(`,
    "gi"
  );
  let stepMatch: RegExpExecArray | null;

  while ((stepMatch = deviceStepPattern.exec(mainBody)) !== null) {
    const absoluteOffset = mainBodyOffset + stepMatch.index;

    // Skip if inside a comment or string
    if (isInsideIgnoredRange(absoluteOffset, ignoredRanges)) {
      continue;
    }

    const clsid = stepMatch[2];

    // Skip the Initialize call itself
    if (clsid.toUpperCase() === INITIALIZE_CLSID) {
      continue;
    }

    // If Initialize was never found, or this call appears before it
    if (initOffset < 0 || absoluteOffset < initOffset) {
      const pos = document.positionAt(absoluteOffset);
      const endPos = document.positionAt(
        absoluteOffset + stepMatch[0].length - 1
      );
      const range = new vscode.Range(pos, endPos);

      const deviceName = stepMatch[1];
      const diag = new vscode.Diagnostic(
        range,
        `Device '${deviceName}' is used before the Initialize step. ` +
          `The Initialize step (${deviceName}._${INITIALIZE_CLSID}(...)) ` +
          `must be called before any other instrument commands. Without it, ` +
          `the instrument hardware is not initialised and all subsequent ` +
          `device commands will fail at runtime.`,
        vscode.DiagnosticSeverity.Error
      );
      diag.source = "hsl";
      diag.code = "missing-initialize-step";
      diagnostics.push(diag);

      // Only flag the first occurrence — one error is enough
      return;
    }
  }
}
