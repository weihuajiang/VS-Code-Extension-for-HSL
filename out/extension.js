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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const builtins_1 = require("./builtins");
const diagnostics_1 = require("./diagnostics");
const hslIntellisense_1 = require("./hslIntellisense");
const stpHoverProvider_1 = require("./stpHoverProvider");
/**
 * Called once when the extension is activated.
 * Registers all language-feature providers for HSL files.
 */
function activate(context) {
    // Build the static list of completion items from builtins.ts
    const completionItems = (0, builtins_1.buildCompletionItems)();
    // Register an inline completion provider for the "hsl" language
    const completionProvider = vscode.languages.registerCompletionItemProvider({ language: "hsl", scheme: "file" }, {
        provideCompletionItems(_document, _position, _token, _ctx) {
            return completionItems;
        },
    });
    context.subscriptions.push(completionProvider);
    (0, hslIntellisense_1.registerHslIntelliSense)(context);
    // Register HSL diagnostics (syntax validation)
    (0, diagnostics_1.createHslDiagnostics)(context);
    // Register STP hover provider (pipetting step tooltips)
    (0, stpHoverProvider_1.registerStpHoverProvider)(context);
    // Register the Run HSL Method command
    const runMethodCommand = vscode.commands.registerCommand("hsl.runMethod", () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage("No active file to run.");
            return;
        }
        const filePath = editor.document.fileName;
        const validExtensions = [".hsl", ".hs_", ".sub"];
        const ext = path.extname(filePath).toLowerCase();
        if (!validExtensions.includes(ext)) {
            vscode.window.showErrorMessage(`Cannot run file with extension '${ext}'. Valid HSL extensions: ${validExtensions.join(", ")}`);
            return;
        }
        // Save the file before running
        editor.document.save().then(() => {
            const terminal = vscode.window.createTerminal("HxRun");
            terminal.show();
            terminal.sendText(`& "HxRun.exe" "${filePath}" -t -c`);
        });
    });
    context.subscriptions.push(runMethodCommand);
}
/**
 * Called when the extension is deactivated.
 */
function deactivate() {
    // nothing to dispose beyond what is in context.subscriptions
}
//# sourceMappingURL=extension.js.map