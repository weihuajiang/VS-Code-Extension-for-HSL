# HSL (Hamilton) Language Support for VS Code

***Get the latest release and `.vsix` file from the [Releases Page](https://github.com/zdmilot/VS-Code-Extension-for-HSL/releases)***

---

A VS Code extension providing comprehensive language support for **HSL (Hamilton Standard Language)** — the programming language used for Hamilton liquid handling robots (VANTAGE, STAR, STAR-V, Nibus, etc). 
This extension brings modern IDE features to HSL development, including syntax highlighting, intelligent code completion, diagnostics, and code snippets.

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
- **Built-in Functions**: Auto-complete for VENUS's extensive library of built-in functions including math, string manipulation, file I/O, and more
- **Library Functions**: Auto-complete for library functions when additional libraries are installed or created within the `Hamilton/Libraries` directory
- **Element Methods**: Context-aware completion for object methods (sequence, device, file, timer, etc.)
- **Documentation**: Inline documentation and parameter hints for all completions

### Real-Time Diagnostics
The extension analyzes your code as you type and flags common errors:
- Invalid operator combinations (`=+` and `=-` which don't exist in HSL)
- Function parameter validation with clear and descriptive variable definition requirment messaging
- Variable declarations not at the top of their code block (HSL requirement)
- Syntax validation with clear error messages and suggestions

### Variable Declaration Scope Rule
In HSL, local variables must be declared at the beginning of a **code block** (`{ ... }`).

- A function/namespace body is a code block.
- Can be after any `#include` or namespace declarations as long as the declaration happens as the first translation unit used within that particular code block
- A nested `{ ... }` inside a function is also a new code block.
- Declarations are valid at the top of that nested block, even if they appear later in the outer function.
- Declarations after executable statements in the **same** block are invalid.


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
- Hamilton VENUS 4 or later

---

## Getting Started

1. **Install** the extension
2. **Open** or create a file with `.hsl`, `.hs_`, or `.sub` extension
3. **Start coding** — syntax highlighting activates automatically
4. **Use snippets** by typing a prefix (e.g., `hslfunc`) and pressing `Tab`
5. **Explore completions** by pressing `Ctrl+Space` to see available functions

---

## Contributing

Contributions are welcome! Visit the [GitHub Repository](https://github.com/zdmilot/VS-Code-Extension-for-HSL) to:
- Report bugs or request features
- Submit pull requests
- View the source code

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

