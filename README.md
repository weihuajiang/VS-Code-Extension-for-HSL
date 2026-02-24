# HSL (Hamilton) Language Support for VS Code

A VS Code extension providing comprehensive language support for **HSL (Hamilton Standard Language)** — the programming language used for Hamilton liquid handling robots (VANTAGE, STAR, STAR-V, Nimbus, etc.).
This extension brings modern IDE features to HSL development, including syntax highlighting, intelligent code completion, diagnostics, and snippets.

---

## Contributors

- **Huajiang Wei** — [GitHub](https://github.com/weihuajiang) · [Lab Automation Forum](https://labautomation.io/u/huajiang/summary)

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
- **Built-in Functions**: Auto-complete for VENUS's extensive built-in function set (math, string manipulation, file I/O, and more)
- **Library Functions**: Auto-complete for functions found in installed HSL libraries
- **Element Methods**: Context-aware completion for object methods (sequence, device, file, timer, etc.)
- **Inline Docs & Signature Help**: Hover documentation and parameter hints for completions and function calls

### Real-Time Diagnostics
The extension analyzes your code as you type and flags common issues:
- Invalid operator combinations (e.g., `=+` and `=-`, which do not exist in HSL)
- Function call argument-count validation with clear, descriptive messaging
- Variable declarations not at the top of their code block (HSL requirement)
- General syntax validation with clear error messages and suggestions

### Variable Declaration Scope Rule
In HSL, local variables must be declared at the beginning of a **code block** (`{ ... }`).

- A function or namespace body is a code block.
- Declarations may appear after `#include` directives and/or namespace wrappers, as long as declarations are the first executable statements within that specific code block.
- A nested `{ ... }` inside a function is also a new code block.
- Declarations are valid at the top of that nested block, even if they appear later in the outer function.
- Declarations after executable statements in the **same** block are invalid.

### Automatic Checksum Generation
When you save an HSL file, the extension automatically updates the Hamilton file validation checksum. This uses the Hamilton `HxSecurityCom` COM object to call `SetFileValidation`, so there is no need to manually fix checksums after editing — files are always kept in a valid state for the VENUS runtime.

> **Note:** Requires Hamilton VENUS installed to have access to the COM Objects needed to generate the checksum.

### Code Snippets
Pre-built templates for common HSL patterns — type a prefix and press `Tab`:

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
| `hslevents` | `CreateObject` with event support |
| `hsleventhandler` | Event handler function |
| `hslfork` | Fork/Join parallel execution |
| `hsllock` | Lock/unlock critical section |

---

## Supported File Extensions

| Extension | Description |
|-----------|-------------|
| `.hsl` | HSL source file (commonly used for declarations and/or headers, depending on library structure) |
| `.hs_` | HSL source file (commonly used for implementation/source, depending on library structure) |
| `.sub` | HSL submethod file |

---

## Library Discovery and Search Paths

This extension mirrors the standard HSL/VENUS library discovery model. Because library locations are governed by the Hamilton installation and HSL runtime conventions, **the extension does not provide a setting to change library roots**.

The extension discovers HSL libraries using the typical Hamilton installation library locations, such as:

- `C:\Program Files (x86)\Hamilton\Library\...`

It also resolves `#include "..."` directives commonly used in HSL libraries, including:
- Absolute paths
- UNC paths
- Library-root-relative includes under the Hamilton library directory

> Note: IntelliSense for library functions depends on the libraries being present on the machine where VS Code is running.

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
The extension provides auto-completion for 100+ built-in HSL functions, including:
- **Math**: `Sin`, `Cos`, `Tan`, `Exp`, `Log`, `Sqrt`, `Abs`, `Round`, `Floor`, `Ceiling`
- **String**: `StrGetLength`, `StrMid`, `StrFind`, `StrReplace`, `StrTrimLeft`, `StrTrimRight`
- **Conversion**: `IStr`, `FStr`, `IVal`, `FVal`, `StrConcat`
- **Sequence**: `GetTotal`, `SetTotal`, `Add`, `Remove`, `GetAt`, `SetAt`
- **File I/O**: `Open`, `Close`, `Read`, `Write`, `ReadString`, `WriteString`
- **System**: `Trace`, `Sleep`, `Wait`, `MessageBox`, `GetFunctionName`, `GetTime`
- **Error Handling**: `err.Raise`, `err.Clear`, `err.GetId`, `err.GetDescription`

---

# Code Map

<p align="center">
  <img width="700" height="3000" alt="NotebookLM Mind Map-2" src="https://github.com/user-attachments/assets/d3a73baa-9e59-4e31-b5ed-a9c6df687288" />
</p>

---

## Requirements

- VS Code 1.85.0 or later
- Hamilton VENUS 4 or later

You can download and install Hamilton VENUS 4 from [Hamilton's official post on the forum](https://labautomation.io/t/download-hamilton-method-manager-2/727), or download it directly [here](https://download.hamiltonsupport.com/wl/?id=7kDYflsz630Vp9uLwYjGvCVb4Gp0i8sG).

---

## Getting Started

1. **Install** the extension from the VS Code Marketplace
2. **Open** (or create) a file with a `.hsl`, `.hs_`, or `.sub` extension
3. **Start coding** — syntax highlighting activates automatically
4. **Use snippets** by typing a prefix (e.g., `hslfunc`) and pressing `Tab`
5. **Explore completions** by pressing `Ctrl+Space`

---

## Known Limitations / Non-Goals

- This extension is not a full HSL compiler; parsing and analysis are heuristic and best-effort.
- Diagnostics may not perfectly match every VENUS translator edge case.
- Some IntelliSense and discovery features depend on HSL libraries being installed locally in expected system paths.
- Initial indexing/discovery may take longer on first run; subsequent runs are typically faster due to caching.
- There is currently no debugger or Run Control integration in VS Code; programs must be executed using Hamilton Run Control (`HxRun.exe`).

---

## Help & Support

For additional help and support, check out the following resources:

- **Wiki**: Visit the [GitHub Wiki](https://github.com/zdmilot/VS-Code-Extension-for-HSL/wiki) for documentation and guides.
- **Forum**: Learn more about Hamilton HSL programming on the [Lab Automation Forum](https://labautomation.io/t/ways-to-learn-hamilton-hsl-code/1156/7).
- **Issues**: Report bugs or request features on the [Issues page](https://github.com/zdmilot/VS-Code-Extension-for-HSL/issues).

---

## Contributing

Contributions are welcome. Visit the GitHub repository to:
- Report bugs or request features
- Submit pull requests
- View the source code

GitHub: https://github.com/zdmilot/VS-Code-Extension-for-HSL

