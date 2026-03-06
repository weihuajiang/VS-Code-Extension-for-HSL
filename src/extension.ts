import * as vscode from "vscode";
import * as path from "path";
import { buildCompletionItems } from "./builtins";
import { createHslDiagnostics } from "./diagnostics";
import { registerHslIntelliSense } from "./hslIntellisense";
import { registerStpHoverProvider } from "./stpHoverProvider";

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

  // Register the Run HSL Method command
  const runMethodCommand = vscode.commands.registerCommand(
    "hsl.runMethod",
    () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showErrorMessage("No active file to run.");
        return;
      }

      const filePath = editor.document.fileName;
      const validExtensions = [".hsl", ".hs_", ".sub"];
      const ext = path.extname(filePath).toLowerCase();

      if (!validExtensions.includes(ext)) {
        vscode.window.showErrorMessage(
          `Cannot run file with extension '${ext}'. Valid HSL extensions: ${validExtensions.join(", ")}`
        );
        return;
      }

      // Save the file before running
      editor.document.save().then(() => {
        const terminal = vscode.window.createTerminal("HxRun");
        terminal.show();
        terminal.sendText(
          `& "HxRun.exe" "${filePath}" -t -c`
        );
      });
    }
  );
  context.subscriptions.push(runMethodCommand);
}

/**
 * Called when the extension is deactivated.
 */
export function deactivate(): void {
  // nothing to dispose beyond what is in context.subscriptions
}
