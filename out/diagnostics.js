"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.createHslDiagnostics = createHslDiagnostics;
const vscode = __importStar(require("vscode"));
/**
 * Creates and returns a DiagnosticCollection that validates HSL syntax.
 * Currently checks for:
 *   - `=+` which should be `= ++` (pre-increment) or `+=` (compound add)
 *   - `=-` which should be `= --` (pre-decrement) or `-=` (compound subtract)
 */
function createHslDiagnostics(context) {
    const diagnosticCollection = vscode.languages.createDiagnosticCollection("hsl");
    // Run diagnostics on the active editor when the extension activates
    if (vscode.window.activeTextEditor?.document.languageId === "hsl") {
        refreshDiagnostics(vscode.window.activeTextEditor.document, diagnosticCollection);
    }
    // Re-run when a document is opened or its content changes
    context.subscriptions.push(vscode.workspace.onDidChangeTextDocument((e) => {
        if (e.document.languageId === "hsl") {
            refreshDiagnostics(e.document, diagnosticCollection);
        }
    }), vscode.workspace.onDidOpenTextDocument((doc) => {
        if (doc.languageId === "hsl") {
            refreshDiagnostics(doc, diagnosticCollection);
        }
    }), vscode.workspace.onDidCloseTextDocument((doc) => {
        diagnosticCollection.delete(doc.uri);
    }), diagnosticCollection);
    return diagnosticCollection;
}
/**
 * Analyse the full document and publish diagnostics.
 */
function refreshDiagnostics(document, collection) {
    const diagnostics = [];
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
        let match;
        // Check for =+
        equalsPlusPattern.lastIndex = 0;
        while ((match = equalsPlusPattern.exec(lineText)) !== null) {
            const absoluteOffset = lineOffset + match.index;
            if (isInsideIgnoredRange(absoluteOffset, ignoredRanges)) {
                continue;
            }
            const range = new vscode.Range(lineIndex, match.index, lineIndex, match.index + match[0].length);
            const diag = new vscode.Diagnostic(range, "'=+' is not valid HSL. Did you mean '+=' (compound addition) or '= ++' (assign pre-increment)?", vscode.DiagnosticSeverity.Error);
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
            const range = new vscode.Range(lineIndex, match.index, lineIndex, match.index + match[0].length);
            const diag = new vscode.Diagnostic(range, "'=-' is not valid HSL. Did you mean '-=' (compound subtraction) or '= --' (assign pre-decrement)?", vscode.DiagnosticSeverity.Error);
            diag.source = "hsl";
            diag.code = "invalid-equals-minus";
            diagnostics.push(diag);
        }
    }
    collection.set(document.uri, diagnostics);
}
/**
 * Returns an array of [start, end) offset ranges that cover string literals
 * and comments so diagnostics can avoid false positives inside them.
 */
function getIgnoredRanges(text) {
    const ranges = [];
    // Matches:  // line comment  |  /* block comment */  |  "string"
    const pattern = /\/\/[^\n]*|\/\*[\s\S]*?\*\/|"(?:[^"\\]|\\.)*"/g;
    let m;
    while ((m = pattern.exec(text)) !== null) {
        ranges.push({ start: m.index, end: m.index + m[0].length });
    }
    return ranges;
}
function isInsideIgnoredRange(offset, ranges) {
    for (const r of ranges) {
        if (offset >= r.start && offset < r.end) {
            return true;
        }
    }
    return false;
}
//# sourceMappingURL=diagnostics.js.map