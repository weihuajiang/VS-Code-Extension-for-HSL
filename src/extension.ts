import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as cp from "child_process";
import { buildCompletionItems } from "./builtins";
import { createHslDiagnostics } from "./diagnostics";
import { registerHslIntelliSense } from "./hslIntellisense";
import { registerStpHoverProvider } from "./stpHoverProvider";
import {
  HslDebugAdapterFactory,
  HslDebugConfigurationProvider,
} from "./hslDebugAdapter";

const HAMILTON_EDITOR_PATH = "C:\\Program Files (x86)\\Hamilton\\Bin\\HxHSLMetEd.exe";

/**
 * Called once when the extension is activated.
 * Registers all language-feature providers for HSL files.
 */
export function activate(context: vscode.ExtensionContext): void {
  // Build the static list of completion items from builtins.ts
  const completionItems = buildCompletionItems();

  // Register an inline completion provider for the "hsl" language
  const completionProvider = vscode.languages.registerCompletionItemProvider(
    { language: "hsl", scheme: "file" },
    {
      provideCompletionItems(
        _document: vscode.TextDocument,
        _position: vscode.Position,
        _token: vscode.CancellationToken,
        _ctx: vscode.CompletionContext
      ): vscode.CompletionItem[] {
        return completionItems;
      },
    }
  );

  context.subscriptions.push(completionProvider);

  registerHslIntelliSense(context);

  // Register HSL diagnostics (syntax validation)
  createHslDiagnostics(context);

  // Register STP hover provider (pipetting step tooltips)
  registerStpHoverProvider(context);

  // Register the HSL debug adapter so Run/Debug (F5) works from the Run menu
  const debugAdapterFactory = new HslDebugAdapterFactory();
  context.subscriptions.push(
    vscode.debug.registerDebugAdapterDescriptorFactory("hsl", debugAdapterFactory)
  );

  const debugConfigProvider = new HslDebugConfigurationProvider();
  context.subscriptions.push(
    vscode.debug.registerDebugConfigurationProvider("hsl", debugConfigProvider)
  );

  // Helper to resolve the target file from either a URI arg or the active editor
  function resolveHslFile(uri?: vscode.Uri): string | undefined {
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

  function validateHslExtension(filePath: string): boolean {
    const validExtensions = [".hsl", ".hs_", ".sub", ".med"];
    const ext = path.extname(filePath).toLowerCase();
    if (!validExtensions.includes(ext)) {
      vscode.window.showErrorMessage(
        `Cannot run file with extension '${ext}'. Valid HSL extensions: ${validExtensions.join(", ")}`
      );
      return false;
    }
    return true;
  }

  function saveAndLaunch(filePath: string, noDebug: boolean): void {
    const doc = vscode.workspace.textDocuments.find(d => d.fileName === filePath);
    const savePromise = doc?.isDirty ? doc.save() : Promise.resolve(true);
    savePromise.then(() => {
      vscode.debug.startDebugging(undefined, {
        type: "hsl",
        name: noDebug ? "Run HSL Method" : "Debug HSL Method",
        request: "launch",
        program: filePath,
        noDebug,
      });
    });
  }

  // Run Without Debugging (Ctrl+F5 equivalent -- launches HxRun.exe)
  const runMethodCommand = vscode.commands.registerCommand(
    "hsl.runMethod",
    (uri?: vscode.Uri) => {
      const filePath = resolveHslFile(uri);
      if (!filePath || !validateHslExtension(filePath)) {
        return;
      }
      saveAndLaunch(filePath, true);
    }
  );
  context.subscriptions.push(runMethodCommand);

  // Start Debugging (F5 equivalent -- launches Python simulation)
  const debugMethodCommand = vscode.commands.registerCommand(
    "hsl.debugMethod",
    (uri?: vscode.Uri) => {
      const filePath = resolveHslFile(uri);
      if (!filePath || !validateHslExtension(filePath)) {
        return;
      }
      saveAndLaunch(filePath, false);
    }
  );
  context.subscriptions.push(debugMethodCommand);

  // Register the Open in Hamilton HSL Editor command (only if editor executable exists)
  const hamiltonEditorAvailable = fs.existsSync(HAMILTON_EDITOR_PATH);
  vscode.commands.executeCommand("setContext", "hsl.hamiltonEditorAvailable", hamiltonEditorAvailable);

  const openInHamiltonEditorCommand = vscode.commands.registerCommand(
    "hsl.openInHamiltonEditor",
    (uri?: vscode.Uri) => {
      let filePath: string;
      if (uri) {
        filePath = uri.fsPath;
      } else {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
          vscode.window.showErrorMessage("No active file to open.");
          return;
        }
        filePath = editor.document.fileName;
      }

      cp.execFile(HAMILTON_EDITOR_PATH, [filePath], (err) => {
        if (err) {
          vscode.window.showErrorMessage(
            `Failed to open Hamilton HSL Editor: ${err.message}`
          );
        }
      });
    }
  );
  context.subscriptions.push(openInHamiltonEditorCommand);
}

/**
 * Called when the extension is deactivated.
 */
export function deactivate(): void {
  // nothing to dispose beyond what is in context.subscriptions
}
