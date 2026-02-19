import * as vscode from "vscode";
import { buildCompletionItems } from "./builtins";
import { createHslDiagnostics } from "./diagnostics";

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

  // Register HSL diagnostics (syntax validation)
  createHslDiagnostics(context);
}

/**
 * Called when the extension is deactivated.
 */
export function deactivate(): void {
  // nothing to dispose beyond what is in context.subscriptions
}
