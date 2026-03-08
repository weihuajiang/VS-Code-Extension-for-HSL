import * as vscode from "vscode";
import * as path from "path";
import * as cp from "child_process";

// --- Debug Adapter Protocol message types ---

interface DapMessage {
  seq: number;
  type: string;
}

interface DapRequest extends DapMessage {
  type: "request";
  command: string;
  arguments?: unknown;
}

interface DapResponse extends DapMessage {
  type: "response";
  request_seq: number;
  command: string;
  success: boolean;
  body?: unknown;
  message?: string;
}

interface DapEvent extends DapMessage {
  type: "event";
  event: string;
  body?: unknown;
}

/**
 * Minimal inline Debug Adapter that runs the Python HSL debugger
 * in a child process and forwards output to VS Code's Debug Console.
 */
export class HslInlineDebugAdapter implements vscode.DebugAdapter {
  private _seq = 1;
  private _process: cp.ChildProcess | undefined;
  private readonly _onDidSendMessage = new vscode.EventEmitter<DapResponse | DapEvent>();
  readonly onDidSendMessage: vscode.Event<DapResponse | DapEvent> = this._onDidSendMessage.event;

  handleMessage(message: DapRequest): void {
    switch (message.command) {
      case "initialize":
        this._sendResponse(message, {
          supportsConfigurationDoneRequest: false,
        });
        this._sendEvent("initialized");
        break;

      case "launch":
        this._handleLaunch(message);
        break;

      case "disconnect":
        this._handleDisconnect(message);
        break;

      case "configurationDone":
        this._sendResponse(message, {});
        break;

      case "threads":
        this._sendResponse(message, { threads: [{ id: 1, name: "main" }] });
        break;

      default:
        // Respond to unknown requests to prevent hangs
        this._sendResponse(message, {});
        break;
    }
  }

  private async _handleLaunch(request: DapRequest): Promise<void> {
    const args = request.arguments as {
      program?: string;
      hamiltonDir?: string;
      pythonPath?: string;
      verbose?: boolean;
      noDebug?: boolean;
    };

    const program = args?.program;
    if (!program) {
      this._sendErrorResponse(request, "No HSL file specified in launch configuration.");
      this._sendEvent("terminated");
      return;
    }

    const ext = path.extname(program).toLowerCase();
    if (![".hsl", ".hs_", ".sub"].includes(ext)) {
      this._sendErrorResponse(request, `Cannot run file with extension '${ext}'. Valid: .hsl, .hs_, .sub`);
      this._sendEvent("terminated");
      return;
    }

    // Find the HSL Debugger directory relative to the extension
    const extensionRoot = this._findExtensionRoot();
    const debuggerDir = path.join(extensionRoot, "HSL Debugger");

    const pythonPath = args?.pythonPath || "python";
    const hamiltonDir = args?.hamiltonDir || "C:\\Program Files (x86)\\Hamilton";
    const verbose = args?.verbose !== false;

    const spawnArgs = [
      "-m", "hsl_runtime.main",
      program,
      "--hamilton-dir", hamiltonDir,
    ];
    if (!verbose) {
      spawnArgs.push("--quiet");
    }

    this._outputLine(`Running HSL method: ${path.basename(program)}`);
    this._outputLine(`Python: ${pythonPath}`);
    this._outputLine(`Hamilton dir: ${hamiltonDir}`);
    this._outputLine("");

    // Acknowledge the launch request before starting the process
    this._sendResponse(request, {});

    try {
      this._process = cp.spawn(pythonPath, spawnArgs, {
        cwd: debuggerDir,
        shell: true,
      });

      this._process.stdout?.on("data", (data: Buffer) => {
        const text = data.toString();
        for (const line of text.split(/\r?\n/)) {
          if (line.length > 0) {
            this._outputLine(line);
          }
        }
      });

      this._process.stderr?.on("data", (data: Buffer) => {
        const text = data.toString();
        for (const line of text.split(/\r?\n/)) {
          if (line.length > 0) {
            this._outputLine(line, "stderr");
          }
        }
      });

      this._process.on("close", (code) => {
        this._outputLine("");
        if (code === 0) {
          this._outputLine("HSL method completed successfully.");
        } else {
          this._outputLine(`HSL method exited with code ${code}.`, "stderr");
        }
        this._sendEvent("terminated");
      });

      this._process.on("error", (err) => {
        this._outputLine(`Failed to start Python: ${err.message}`, "stderr");
        this._outputLine("Make sure Python is installed and on your PATH.", "stderr");
        this._sendEvent("terminated");
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this._outputLine(`Error launching HSL debugger: ${msg}`, "stderr");
      this._sendEvent("terminated");
    }
  }

  private _handleDisconnect(request: DapRequest): void {
    if (this._process && !this._process.killed) {
      this._process.kill();
    }
    this._sendResponse(request, {});
    this._sendEvent("terminated");
  }

  private _findExtensionRoot(): string {
    // The compiled extension lives in <root>/out/hslDebugAdapter.js
    // so the extension root is one level up from __dirname
    return path.resolve(__dirname, "..");
  }

  private _outputLine(text: string, category: string = "stdout"): void {
    this._sendEvent("output", {
      category,
      output: text + "\n",
    });
  }

  private _sendResponse(request: DapRequest, body: unknown): void {
    const response: DapResponse = {
      seq: this._seq++,
      type: "response",
      request_seq: request.seq,
      command: request.command,
      success: true,
      body,
    };
    this._onDidSendMessage.fire(response);
  }

  private _sendErrorResponse(request: DapRequest, message: string): void {
    const response: DapResponse = {
      seq: this._seq++,
      type: "response",
      request_seq: request.seq,
      command: request.command,
      success: false,
      message,
    };
    this._onDidSendMessage.fire(response);
  }

  private _sendEvent(event: string, body?: unknown): void {
    const evt: DapEvent = {
      seq: this._seq++,
      type: "event",
      event,
      body,
    };
    this._onDidSendMessage.fire(evt);
  }

  dispose(): void {
    if (this._process && !this._process.killed) {
      this._process.kill();
    }
    this._onDidSendMessage.dispose();
  }
}

/**
 * Factory that creates our inline debug adapter instances.
 */
export class HslDebugAdapterFactory implements vscode.DebugAdapterDescriptorFactory {
  createDebugAdapterDescriptor(
    _session: vscode.DebugSession
  ): vscode.ProviderResult<vscode.DebugAdapterDescriptor> {
    return new vscode.DebugAdapterInlineImplementation(new HslInlineDebugAdapter());
  }
}

/**
 * Provides automatic debug configurations for HSL files so F5 works
 * without requiring a launch.json.
 */
export class HslDebugConfigurationProvider implements vscode.DebugConfigurationProvider {
  resolveDebugConfiguration(
    _folder: vscode.WorkspaceFolder | undefined,
    config: vscode.DebugConfiguration,
    _token?: vscode.CancellationToken
  ): vscode.ProviderResult<vscode.DebugConfiguration> {
    // If the user pressed F5 without any launch.json or with an empty config
    if (!config.type && !config.request && !config.name) {
      const editor = vscode.window.activeTextEditor;
      if (editor && editor.document.languageId === "hsl") {
        config.type = "hsl";
        config.name = "Run HSL Method";
        config.request = "launch";
        config.program = "${file}";
      }
    }

    if (!config.program) {
      config.program = "${file}";
    }

    return config;
  }
}
