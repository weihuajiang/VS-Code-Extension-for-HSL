# CLI Entry Point

> **Module**: `hsl_runtime/main.py` (218 lines)  
> **Purpose**: Command-line interface for the HSL Debugger simulation runtime

---

## Table of Contents

1. [Usage](#usage)
2. [Arguments](#arguments)
3. [Pipeline Phases](#pipeline-phases)
4. [Output Format](#output-format)
5. [Diagnostic Modes](#diagnostic-modes)
6. [Exit Codes](#exit-codes)

---

## Usage

```powershell
python -m hsl_runtime.main <hsl_file> [options]
```

### Basic Examples

```powershell
# Run a method file
python -m hsl_runtime.main "C:\Hamilton\Methods\MyMethod.hsl"

# Run quietly (no trace output)
python -m hsl_runtime.main "C:\Hamilton\Methods\MyMethod.hsl" --quiet

# Dump tokens only
python -m hsl_runtime.main "C:\Hamilton\Methods\MyMethod.hsl" --dump-tokens

# Dump AST only
python -m hsl_runtime.main "C:\Hamilton\Methods\MyMethod.hsl" --dump-ast

# Dump preprocessed source
python -m hsl_runtime.main "C:\Hamilton\Methods\MyMethod.hsl" --dump-preprocessed

# Custom Hamilton path and iteration limit
python -m hsl_runtime.main "MyMethod.hsl" --hamilton-dir "D:\Hamilton" --max-iterations 500000
```

---

## Arguments

### Positional

| Argument | Description |
|----------|-------------|
| `hsl_file` | Path to the HSL file to process |

### Optional Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--verbose` | `True` | Show detailed trace output |
| `--quiet` | `False` | Suppress trace output (sets verbose to False) |
| `--dump-tokens` | `False` | Print token stream and exit after Phase 2 |
| `--dump-ast` | `False` | Print AST tree and exit after Phase 3 |
| `--dump-preprocessed` | `False` | Print preprocessed source and exit after Phase 1 |
| `--max-iterations` | `100000` | Safety limit for loop iterations |
| `--hamilton-dir` | `C:\Program Files (x86)\Hamilton` | Hamilton installation directory |

---

## Pipeline Phases

The main module orchestrates the four-phase pipeline with timing and status output:

### Phase 1: Preprocessing

```
[1/4] Preprocessing...
  Defines: 42
  Included files: 15
  Done (0.234s)
```

- Calls `Preprocessor.preprocess_file()`
- Reports the number of defined macros
- Reports the number of included files
- Optionally dumps the preprocessed source (`--dump-preprocessed`)

### Phase 2: Tokenization

```
[2/4] Tokenizing...
  Tokens: 186,927
  Done (0.567s)
```

- Calls `Lexer.tokenize()`
- Reports the total token count
- Optionally dumps all tokens (`--dump-tokens`)

### Phase 3: Parsing

```
[3/4] Parsing...
  Declarations: 648
  Parser warnings: 100
    Line 1234: Expected SEMICOLON
    Line 2345: Unexpected token '^'
    ...
  Done (0.345s)
```

- Calls `Parser.parse()`
- Reports the number of top-level declarations
- Reports parser warnings (first 10 shown)
- Optionally dumps the AST tree (`--dump-ast`)

### Phase 4: Execution

```
[4/4] Executing (SIMULATION)...
  ----------------------------------------
  [TRACE] Hello from main
  [TRACE] Processing plate 1
  ----------------------------------------
  Trace messages: 42
  Functions found: 648
  Namespaces: _Method, HSLStrLib, HSLTrcLib, ...
  Done (0.123s)
```

- Creates `Interpreter` and calls `execute()`
- Prints trace output (unless `--quiet`)
- Reports execution statistics
- Handles `AbortException` (intentional program abort)

---

## Output Format

### Header

```
============================================================
  HSL Debugger - Simulation Runtime v0.1
  SIMULATION ONLY - No hardware interaction
============================================================
  File:    C:\Hamilton\Methods\MyMethod.hsl
  Hamilton: C:\Program Files (x86)\Hamilton
```

### Footer (Success)

```
============================================================
  Simulation finished successfully
============================================================
```

### Footer (Abort)

```
============================================================
  Program aborted (intentional abort statement)
============================================================
```

### Footer (Error)

```
============================================================
  Simulation failed: <error message>
============================================================
```

---

## Diagnostic Modes

### `--dump-preprocessed`

Prints the entire preprocessed source code and exits. Useful for:
- Verifying `#include` resolution
- Checking `#ifdef` / `#ifndef` conditional compilation
- Inspecting macro substitution results

```powershell
python -m hsl_runtime.main MyMethod.hsl --dump-preprocessed > preprocessed.hsl
```

### `--dump-tokens`

Prints every token with its type, value, line, and column:

```
Token(type=VARIABLE, value='variable', line=1, col=1)
Token(type=IDENTIFIER, value='x', line=1, col=10)
Token(type=LPAREN, value='(', line=1, col=11)
Token(type=INTEGER, value=42, line=1, col=12)
Token(type=RPAREN, value=')', line=1, col=14)
Token(type=SEMICOLON, value=';', line=1, col=15)
```

### `--dump-ast`

Prints the AST tree with indentation showing the hierarchy:

```
Program
  NamespaceDeclaration: _Method
    FunctionDeclaration: Main (method)
      Parameters: []
      Block
        VariableDeclaration: x (variable)
          Initializer: IntegerLiteral(42)
        ExpressionStatement
          FunctionCall: Trace
            Arguments:
              StringLiteral("Hello")
```

The `_dump_ast()` utility function recursively traverses the AST, printing each node with its key attributes.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Simulation completed successfully (including intentional `abort`) |
| `1` | Error during preprocessing, parsing, or execution |
| `2` | Invalid arguments |

---

## Error Handling

Each phase is wrapped in try/except blocks with descriptive error output:

```python
try:
    # Phase 1: Preprocess
    source = preprocessor.preprocess_file(args.hsl_file)
except PreprocessorError as e:
    print(f"Preprocessing error: {e}")
    if args.verbose:
        traceback.print_exc()
    sys.exit(1)
```

When `--verbose` is active, full Python tracebacks are shown for internal errors, aiding in debugging the runtime itself.

---

## Module Structure

```python
# main.py layout
import argparse
import sys
import time
import traceback

from .preprocessor import Preprocessor
from .lexer import Lexer
from .parser import Parser
from .interpreter import Interpreter, TraceOutput, AbortException

def _dump_ast(node, indent=0):
    """Recursively print AST tree for --dump-ast mode."""
    ...

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="HSL Debugger - Simulation Runtime")
    # ... argument definitions ...
    args = parser.parse_args()
    
    # Phase 1: Preprocess
    # Phase 2: Tokenize
    # Phase 3: Parse
    # Phase 4: Execute
    
if __name__ == "__main__":
    main()
```

---

## Integration Notes

### Running from VS Code

The module can be run directly from a VS Code terminal:

```powershell
cd "c:\Users\admin\Desktop\HSL Debugger"
python -m hsl_runtime.main "path\to\method.hsl"
```

### Future Extension

The `main.py` module is designed to be extended with:
- **DAP (Debug Adapter Protocol)** integration for VS Code breakpoint debugging
- **Language Server Protocol** for syntax checking and code completion
- **Watch mode** for automatic re-execution on file changes
- **JSON output mode** for programmatic consumption of results
