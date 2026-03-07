# HSL Debugger -- Simulation Runtime for Hamilton Standard Language

> **SIMULATION ONLY** -- This tool never connects to Hamilton hardware. It replaces `HXRun.exe` and `HxHSLMetEd.exe` for offline testing, debugging, and method validation.

## Overview

The HSL Debugger is a complete **simulation-only** runtime for [Hamilton Standard Language (HSL)](docs/HSL_LANGUAGE_REFERENCE.md) files. It preprocesses, tokenizes, parses, and interprets HSL source code entirely in Python, producing trace output and validating program logic -- without requiring a Hamilton instrument or the VENUS software environment.

### Key Features

- **Full HSL pipeline**: Preprocessor → Lexer → Parser → Interpreter
- **No hardware dependency**: Every device, timer, dialog, and COM object is stubbed for simulation
- **Real Hamilton library support**: Resolves `#include` directives against the Hamilton installation directory
- **Trace output**: Captures all `Trace()` and `FormatTrace()` calls for offline analysis
- **AST / token dump modes**: Inspect internal representations for debugging
- **Debugger hook**: Step callback support for future VS Code integration

---

## Quick Start

### Prerequisites

- Python 3.10+ (tested on 3.13)
- Hamilton software installed at `C:\Program Files (x86)\Hamilton` (for library includes)

### Run a Method

```powershell
cd "c:\Users\admin\Desktop\HSL Debugger"
python -m hsl_runtime.main "C:\Program Files (x86)\Hamilton\Methods\MyMethod.hsl"
```

### Common Options

| Flag | Description |
|------|-------------|
| `--verbose` | Show detailed trace output (default) |
| `--quiet` | Suppress trace output |
| `--dump-tokens` | Print token stream and exit |
| `--dump-ast` | Print abstract syntax tree and exit |
| `--dump-preprocessed` | Print preprocessed source and exit |
| `--max-iterations N` | Safety limit for loops (default: 100,000) |
| `--hamilton-dir PATH` | Override Hamilton installation path |

### Example

```powershell
python -m hsl_runtime.main "C:\Program Files (x86)\Hamilton\Methods\Library Demo Methods\TraceLevel Demo.hsl" --quiet
```

Output:

```
============================================================
  HSL Debugger - Simulation Runtime v0.1
  SIMULATION ONLY - No hardware interaction
============================================================
  File:    C:\...\TraceLevel Demo.hsl
  Hamilton: C:\Program Files (x86)\Hamilton

[1/4] Preprocessing...
  Done (0.XXXs)
[2/4] Tokenizing...
  Tokens: 186,927
[3/4] Parsing...
  Declarations: XXX
[4/4] Executing (SIMULATION)...
  ...
============================================================
  Simulation finished successfully
============================================================
```

---

## Architecture

The runtime is a four-phase pipeline. Each phase is a self-contained module:

```
┌─────────────┐    ┌───────┐    ┌────────┐    ┌─────────────┐
│ Preprocessor │───▶│ Lexer │───▶│ Parser │───▶│ Interpreter │
│   (.hsl)     │    │       │    │  (AST) │    │ (Simulation)│
└─────────────┘    └───────┘    └────────┘    └─────────────┘
```

| Phase | Module | Input | Output |
|-------|--------|-------|--------|
| 1. Preprocess | [`preprocessor.py`](docs/PREPROCESSOR.md) | HSL file path | Flattened source string |
| 2. Tokenize | [`lexer.py`](docs/LEXER.md) | Source string | List of `Token` objects |
| 3. Parse | [`parser.py`](docs/PARSER.md) | Token list | `Program` AST node |
| 4. Execute | [`interpreter.py`](docs/INTERPRETER.md) | AST | Trace output + simulation results |

For detailed architecture documentation, see [Compiler Architecture](docs/COMPILER_ARCHITECTURE.md).

---

## Documentation

| Document | Description |
|----------|-------------|
| [HSL Language Reference](docs/HSL_LANGUAGE_REFERENCE.md) | Complete guide to HSL syntax, types, operators, and built-in functions |
| [Compiler Architecture](docs/COMPILER_ARCHITECTURE.md) | Pipeline design, data flow, and design decisions |
| [Preprocessor](docs/PREPROCESSOR.md) | `#include`, `#define`, `#ifdef/#ifndef`, `#pragma once` |
| [Lexer / Tokenizer](docs/LEXER.md) | Token types, keyword map, tokenization rules |
| [AST Node Reference](docs/AST_NODES.md) | All 25+ AST node types with fields and hierarchy |
| [Parser](docs/PARSER.md) | Recursive descent, operator precedence, error recovery |
| [Interpreter / Runtime](docs/INTERPRETER.md) | Type system, built-in functions, simulation stubs |
| [CLI Entry Point](docs/MAIN.md) | Command-line interface and pipeline orchestration |

---

## Project Structure

```
HSL Debugger/
├── README.md                    # This file
├── docs/
│   ├── HSL_LANGUAGE_REFERENCE.md
│   ├── COMPILER_ARCHITECTURE.md
│   ├── PREPROCESSOR.md
│   ├── LEXER.md
│   ├── AST_NODES.md
│   ├── PARSER.md
│   ├── INTERPRETER.md
│   └── MAIN.md
└── hsl_runtime/
    ├── __init__.py              # Package init (v0.1.0)
    ├── preprocessor.py          # Phase 1: Include/define/ifdef resolution
    ├── lexer.py                 # Phase 2: Tokenization
    ├── ast_nodes.py             # AST node type definitions
    ├── parser.py                # Phase 3: Recursive-descent parser
    ├── interpreter.py           # Phase 4: Simulation interpreter
    └── main.py                  # CLI entry point
```

---

## Simulation Behavior

All hardware-facing operations are stubbed:

| HSL Feature | Simulation Behavior |
|-------------|-------------------|
| `device` declarations | Creates `HslDevice` stub; logs layout info |
| Device step calls (e.g., `ML_STAR.Aspirate()`) | Logged; returns success |
| `Trace()` / `FormatTrace()` | Captured in `TraceOutput`; optionally printed |
| `MessageBox()` | Logged; returns `hslOK` (1) |
| `InputBox()` | Logged; returns empty string |
| `Shell()` | Logged; **never executed** |
| `timer.WaitTimer()` | Returns immediately (no delay) |
| `dialog.ShowCustomDialog()` | Returns OK automatically |
| `object.CreateObject()` | Creates stub; logs ProgID |
| `file.Open()` / `file.ReadString()` | File reads work; writes are stubbed |
| `Fork()` / `Join()` | Not implemented (single-threaded simulation) |
| `onerror goto` / `resume next` | Error handler labels tracked; `resume next` is a no-op |

---

## Test Results

Tested against Hamilton demo methods:

| File | Tokens | Functions | Parse Warnings | Result |
|------|--------|-----------|----------------|--------|
| TraceLevel Demo.hsl | 186,927 | 648 | ~100 | Executes `main()`, hits intentional `abort` |
| CustomDialogs.hsl | 213,969 | 704 | ~123 | Executes through full dialog simulation |

Parse warnings are mostly in Hamilton library code (unsupported `^` operator, path edge cases) and do not affect execution.

---

## Limitations

- **No real hardware**: By design. All device calls are simulation stubs.
- **No COM interop**: `object.CreateObject()` creates a property bag, not a real COM object.
- **No threading**: `Fork()` / `Join()` are not simulated.
- **No `struct`**: Structure types (`struct { ... }`) are not parsed.
- **No `loop` keyword**: The `loop(N)` construct is not yet implemented.
- **No `^` operator**: Power operator (`^`) is not yet supported in the parser/interpreter.
- **Partial error recovery**: ~100-123 parse warnings on complex Hamilton libraries; these do not prevent execution.

---

## License

This project is an independent simulation tool and is not affiliated with, endorsed by, or supported by Hamilton Company. Hamilton Standard Language and VENUS are trademarks of Hamilton Company.
