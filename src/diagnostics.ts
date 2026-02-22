import * as vscode from "vscode";

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
function refreshDiagnostics(
  document: vscode.TextDocument,
  collection: vscode.DiagnosticCollection
): void {
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

  collection.set(document.uri, diagnostics);
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
    if (trimmed === "" || PREPROCESSOR_LINE.test(trimmed)) {
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
