import * as vscode from "vscode";

/**
 * Creates and returns a DiagnosticCollection that validates HSL syntax.
 * Currently checks for:
 *   - `=+` which should be `= ++` (pre-increment) or `+=` (compound add)
 *   - `=-` which should be `= --` (pre-decrement) or `-=` (compound subtract)
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
        "'=+' is not valid HSL. Did you mean '+=' (compound addition) or '= ++' (assign pre-increment)?",
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
        "'=-' is not valid HSL. Did you mean '-=' (compound subtraction) or '= --' (assign pre-decrement)?",
        vscode.DiagnosticSeverity.Error
      );
      diag.source = "hsl";
      diag.code = "invalid-equals-minus";
      diagnostics.push(diag);
    }
  }

  collection.set(document.uri, diagnostics);
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
