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
const fs = __importStar(require("fs"));
const cp = __importStar(require("child_process"));
const builtins_1 = require("./builtins");
const diagnostics_1 = require("./diagnostics");
const hslIntellisense_1 = require("./hslIntellisense");
const stpHoverProvider_1 = require("./stpHoverProvider");
const traceLanguageSupport_1 = require("./traceLanguageSupport");
const hslDebugAdapter_1 = require("./hslDebugAdapter");
const HAMILTON_EDITOR_PATH = "C:\\Program Files (x86)\\Hamilton\\Bin\\HxHSLMetEd.exe";
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
    // Register trace log language support (syntax highlighting + firmware IntelliSense)
    (0, traceLanguageSupport_1.registerTraceLanguageSupport)(context);
    // Register the HSL debug adapter so Run/Debug (F5) works from the Run menu
    const debugAdapterFactory = new hslDebugAdapter_1.HslDebugAdapterFactory();
    context.subscriptions.push(vscode.debug.registerDebugAdapterDescriptorFactory("hsl", debugAdapterFactory));
    const debugConfigProvider = new hslDebugAdapter_1.HslDebugConfigurationProvider();
    context.subscriptions.push(vscode.debug.registerDebugConfigurationProvider("hsl", debugConfigProvider));
    // Helper to resolve the target file from either a URI arg or the active editor
    function resolveHslFile(uri) {
        if (uri) {
            return uri.fsPath;
        }
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage("No active file to run.");
            return undefined;
        }
        return editor.document.fileName;
    }
    function validateHslExtension(filePath) {
        const validExtensions = [".hsl", ".hs_", ".hsi", ".sub", ".med"];
        const ext = path.extname(filePath).toLowerCase();
        if (!validExtensions.includes(ext)) {
            vscode.window.showErrorMessage(`Cannot run file with extension '${ext}'. Valid HSL extensions: ${validExtensions.join(", ")}`);
            return false;
        }
        return true;
    }
    function saveAndLaunch(filePath, noDebug) {
        const doc = vscode.workspace.textDocuments.find(d => d.fileName === filePath);
        const savePromise = doc?.isDirty ? doc.save() : Promise.resolve(true);
        savePromise.then(() => {
            vscode.debug.startDebugging(undefined, {
                type: "hsl",
                name: noDebug ? "Run HSL Method" : "Debug HSL Method",
                request: "launch",
                program: filePath,
                noDebug,
                internalConsoleOptions: "openOnSessionStart",
            });
        });
    }
    // Run Without Debugging (Ctrl+F5 equivalent -- launches HxRun.exe)
    const runMethodCommand = vscode.commands.registerCommand("hsl.runMethod", (uri) => {
        const filePath = resolveHslFile(uri);
        if (!filePath || !validateHslExtension(filePath)) {
            return;
        }
        saveAndLaunch(filePath, true);
    });
    context.subscriptions.push(runMethodCommand);
    // Start Debugging (F5 equivalent -- launches Python simulation)
    const debugMethodCommand = vscode.commands.registerCommand("hsl.debugMethod", (uri) => {
        const filePath = resolveHslFile(uri);
        if (!filePath || !validateHslExtension(filePath)) {
            return;
        }
        saveAndLaunch(filePath, false);
    });
    context.subscriptions.push(debugMethodCommand);
    // Register the Open in Hamilton HSL Editor command (only if editor executable exists)
    const hamiltonEditorAvailable = fs.existsSync(HAMILTON_EDITOR_PATH);
    vscode.commands.executeCommand("setContext", "hsl.hamiltonEditorAvailable", hamiltonEditorAvailable);
    const openInHamiltonEditorCommand = vscode.commands.registerCommand("hsl.openInHamiltonEditor", (uri) => {
        let filePath;
        if (uri) {
            filePath = uri.fsPath;
        }
        else {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage("No active file to open.");
                return;
            }
            filePath = editor.document.fileName;
        }
        cp.execFile(HAMILTON_EDITOR_PATH, [filePath], (err) => {
            if (err) {
                vscode.window.showErrorMessage(`Failed to open Hamilton HSL Editor: ${err.message}`);
            }
        });
    });
    context.subscriptions.push(openInHamiltonEditorCommand);
}
/**
 * Called when the extension is deactivated.
 */
function deactivate() {
    // nothing to dispose beyond what is in context.subscriptions
}
//# sourceMappingURL=extension.js.map