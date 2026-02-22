# HSL (Hamilton) Language Support for VS Code

> **📥 Download**: Get the latest release and `.vsix` file from the [Releases Page](https://github.com/zdmilot/VS-Code-Extension-for-HSL/releases)

---

A VS Code extension providing comprehensive language support for **HSL (Hamilton Standard Language)** — the programming language used for Hamilton liquid handling robots. This extension brings modern IDE features to HSL development, including syntax highlighting, intelligent code completion, diagnostics, and code snippets.

> **⚠️ Beta Notice**: This extension is currently in beta and is not yet available on the VS Code Marketplace. Please follow the manual installation instructions below.

---

## Manual Installation

Since this extension is in beta, you need to install it manually using the `.vsix` file:

### Step 1: Download the Extension
1. Go to the [Releases Page](https://github.com/zdmilot/VS-Code-Extension-for-HSL/releases)
2. Download the latest `.vsix` file (e.g., `hsl-language-support-x.x.x.vsix`)

### Step 2: Install in VS Code

**Option A: Using the VS Code UI**
1. Open VS Code
2. Press `Ctrl+Shift+X` to open the Extensions view
3. Click the `...` (More Actions) button in the top-right of the Extensions pane
4. Select **Install from VSIX...**
5. Navigate to the downloaded `.vsix` file and select it
6. Reload VS Code when prompted

**Option B: Using the Command Line**
```powershell
code --install-extension path\to\hsl-language-support-x.x.x.vsix
```

**Option C: Using the Command Palette**
1. Press `Ctrl+Shift+P` to open the Command Palette
2. Type `Extensions: Install from VSIX...` and select it
3. Navigate to the downloaded `.vsix` file and select it

---

## Features

### Syntax Highlighting
Full HSL syntax highlighting with support for:
- Keywords and control flow statements
- Data types and modifiers
- Operators and punctuation
- Single-line (`//`) and block (`/* */`) comments
- String literals and numeric constants

### Intelligent Code Completion
- **Built-in Functions**: Auto-complete for HSL's extensive library of built-in functions including math, string manipulation, file I/O, and more
- **Element Methods**: Context-aware completion for object methods (sequence, device, file, timer, etc.)
- **Documentation**: Inline documentation and parameter hints for all completions

### Real-Time Diagnostics
The extension analyzes your code as you type and flags common errors:
- Invalid operator combinations (`=+` and `=-` which don't exist in HSL)
- Variable declarations not at the top of their code block (HSL requirement)
- Syntax validation with clear error messages and suggestions

### Variable Declaration Scope Rule
In HSL, local variables must be declared at the beginning of a **code block** (`{ ... }`).

- A function/namespace body is a code block.
- A nested `{ ... }` inside a function is also a new code block.
- Declarations are valid at the top of that nested block, even if they appear later in the outer function.
- Declarations after executable statements in the **same** block are invalid.

Valid pattern (nested block scope, as used in `CSVToArrayTable`):

```hsl
ArrayTable::Build::Create(strDescription, arrColumnNames, o_tblValues);

{
	variable intReadResult;
	variable blnSkipRow;
	variable strCheck;

	strLine = f.ReadString();
	intReadResult = strLine.GetLength();
	// ... processing logic
}
```

Invalid pattern (declaration after statements in the same block):

```hsl
strLine = f.ReadString();
variable intReadResult;   // Invalid in this block
```

### Code Snippets
Pre-built templates for common HSL patterns — just type the prefix and press `Tab`:

| Prefix | Description |
|--------|-------------|
| `hslfunc` | Function template |
| `hslmethod` | Method template |
| `hslns` | Namespace block |
| `hslguard` | Include guard for library files |
| `for` | For loop |
| `while` | While loop |
| `loop` | Loop statement (fixed iterations) |
| `ifelse` | If/else conditional |
| `onerror` | Error handling pattern |
| `raise` | Error raising statement (`err.Raise`) |
| `trace` | Trace output |
| `struct` | Struct definition |
| `hslevents` | CreateObject with event support |
| `hsleventhandler` | Event handler function |
| `hslfork` | Fork/Join parallel execution |
| `hsllock` | Lock/unlock critical section |

### Bracket Matching & Auto-Closing
- Automatic bracket pairing for `{}`, `[]`, `()`, and quotes
- Smart closing of brackets and strings

### Code Folding
- Support for region-based code folding using `// #region` and `// #endregion` markers
- Automatic folding for functions, namespaces, and code blocks

---

## Supported File Extensions

| Extension | Description |
|-----------|-------------|
| `.hsl` | Standard HSL source files |
| `.hs_` | HSL library/header files |
| `.sub` | HSL submethod files |

---

## Language Reference

### Keywords
- **Control Flow**: `if`, `else`, `for`, `while`, `do`, `loop`, `switch`, `case`, `default`, `break`, `continue`, `return`
- **Exception Handling**: `onerror`, `goto`, `abort`, `throw`, `try`, `catch`
- **Declarations**: `namespace`, `function`, `method`, `dialog`, `class`, `struct`
- **Modifiers**: `private`, `public`, `protected`, `static`, `const`, `global`, `synchronized`
- **Parallel Execution**: `fork`, `join`, `lock`, `unlock`
- **HSL Scheduler**: `activity`, `actionblock`, `executoronly`, `oncancelaction`, `oncanceltask`, `resource`, `reschedule`, `schedule`, `scheduleronly`, `schedulerprompt`, `workflow`

### Data Types
- **Primitives**: `variable`, `string`, `integer`, `float`, `char`, `short`, `long`
- **Objects**: `object`, `sequence`, `device`, `resource`, `dialog`, `timer`, `event`, `file`
- **Constants**: `hslTrue`, `hslFalse`

### Built-in Function Categories
The extension provides auto-completion for 100+ built-in HSL functions:
- **Math**: `Sin`, `Cos`, `Tan`, `Exp`, `Log`, `Sqrt`, `Abs`, `Round`, `Floor`, `Ceiling`
- **String**: `StrGetLength`, `StrMid`, `StrFind`, `StrReplace`, `StrTrimLeft`, `StrTrimRight`
- **Conversion**: `IStr`, `FStr`, `IVal`, `FVal`, `StrConcat`
- **Sequence**: `GetTotal`, `SetTotal`, `Add`, `Remove`, `GetAt`, `SetAt`
- **File I/O**: `Open`, `Close`, `Read`, `Write`, `ReadString`, `WriteString`
- **System**: `Trace`, `Sleep`, `Wait`, `MessageBox`, `GetFunctionName`, `GetTime`
- **Error Handling**: `err.Raise`, `err.Clear`, `err.GetId`, `err.GetDescription`

---

## Requirements

- VS Code 1.85.0 or later
- Windows (Hamilton VENUS software environment)

---

## Getting Started

1. **Install** the extension using the manual installation steps above
2. **Open** or create a file with `.hsl`, `.hs_`, or `.sub` extension
3. **Start coding** — syntax highlighting activates automatically
4. **Use snippets** by typing a prefix (e.g., `hslfunc`) and pressing `Tab`
5. **Explore completions** by pressing `Ctrl+Space` to see available functions

---

## Known Issues

This is a beta release. Please report any issues on the [GitHub Issues](https://github.com/zdmilot/VS-Code-Extension-for-HSL/issues) page.

---

## Contributing

Contributions are welcome! Visit the [GitHub Repository](https://github.com/zdmilot/VS-Code-Extension-for-HSL) to:
- Report bugs or request features
- Submit pull requests
- View the source code

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

