# Preprocessor Module

> **Module**: `hsl_runtime/preprocessor.py` (305 lines)  
> **Phase**: 1 of 4  
> **Input**: HSL file path  
> **Output**: Flattened source string with all includes resolved and macros substituted

---

## Table of Contents

1. [Purpose](#purpose)
2. [Public API](#public-api)
3. [Class: Preprocessor](#class-preprocessor)
4. [Directive Reference](#directive-reference)
5. [Include Resolution](#include-resolution)
6. [Macro Substitution](#macro-substitution)
7. [Conditional Compilation](#conditional-compilation)
8. [Configuration](#configuration)
9. [Error Handling](#error-handling)

---

## Purpose

The preprocessor transforms one or more HSL source files into a single, flattened source string. It handles:

- **`#include`** -- Resolves file paths and recursively inlines included files
- **`#define` / `#undef`** -- Stores macro definitions and performs textual substitution
- **`#ifdef` / `#ifndef` / `#else` / `#endif`** -- Conditional compilation blocks
- **`#pragma once`** -- Include-once file guards
- **`#if defined(...)`** -- Alternative conditional syntax

The output is a plain text string suitable for tokenization by the lexer.

---

## Public API

### Constructor

```python
Preprocessor(hamilton_dir: str = r"C:\Program Files (x86)\Hamilton")
```

Creates a preprocessor instance with Hamilton search paths configured.

**Parameters:**
- `hamilton_dir`: Path to the Hamilton installation directory. Used to construct search paths for `Library\` and `Methods\` subdirectories.

**Initial State:**
- `HSL_RUNTIME` is always defined with value `"1"`
- Search paths include `Hamilton\Library\` and `Hamilton\Methods\`
- `included_files` set is empty
- `pragma_once_files` set is empty

### Methods

#### `add_search_path(path: str) → None`

Add a directory to the include search path list.

```python
pp = Preprocessor()
pp.add_search_path(r"C:\MyProject\includes")
```

#### `preprocess_file(filepath: str) → str`

Preprocess an HSL file and return the flattened source code.

```python
pp = Preprocessor()
source = pp.preprocess_file(r"C:\Hamilton\Methods\MyMethod.hsl")
```

This is the main entry point. It:
1. Adds the file's directory to the search paths
2. Reads the file
3. Calls `preprocess()` on the content
4. Returns the flattened result

---

## Class: Preprocessor

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `defines` | `dict[str, str]` | Macro name → value mapping. Pre-populated with `HSL_RUNTIME = "1"` |
| `search_paths` | `list[str]` | Ordered list of directories to search for includes |
| `included_files` | `set[str]` | Normalized paths of files already included (prevents duplicates) |
| `pragma_once_files` | `set[str]` | Files marked with `#pragma once` |
| `source_map` | `dict[int, tuple]` | Output line → (source file, original line) mapping |
| `max_include_depth` | `int` | Maximum recursive include depth (default: 50) |

### Internal Methods

#### `preprocess(content: str, filename: str, depth: int) → str`

Core preprocessing loop. Processes each line of `content`:

1. Checks the condition stack -- if a false condition is active, only `#else`, `#endif`, and nested `#ifdef`/`#ifndef` are processed
2. Handles directives via `_handle_directive()`
3. Performs macro substitution via `_substitute_defines()`
4. Handles inline includes (`#include` appearing mid-line)

#### `_handle_directive(line: str, filename: str, depth: int) → str | None`

Dispatches preprocessor directives:

| Directive | Action |
|-----------|--------|
| `#pragma once` | Add file to pragma_once set |
| `#define NAME VALUE` | Store in defines dict |
| `#undef NAME` | Remove from defines dict |
| `#ifdef NAME` | Push `True` if NAME is defined |
| `#ifndef NAME` | Push `True` if NAME is not defined |
| `#if defined(NAME)` | Push `True` if NAME is defined |
| `#else` | Invert top of condition stack |
| `#endif` | Pop condition stack |
| `#include "path"` | Resolve and recursively preprocess |

Returns `None` for directives (consumed), or the processed line for non-directives.

#### `_resolve_and_read_include(path: str, current_file: str, depth: int) → str`

1. Resolves the include path against search paths
2. Checks `pragma_once_files` and `included_files`
3. Reads the file
4. Recursively preprocesses with `depth + 1`

#### `resolve_include(include_path: str, current_file: str) → str | None`

Resolves an include path in this order:
1. Relative to the directory of the current file
2. Absolute path (if the include path is absolute)
3. Each directory in `search_paths`

Handles the `__filename__` token by replacing it with the directory of the current file.

Returns the resolved absolute path, or `None` if not found.

#### `_substitute_defines(line: str) → str`

Replaces all defined macros in a line using **whole-word matching** (word boundaries with `\b`). This prevents partial replacements inside identifiers.

```python
# Given: defines = {"VERSION": "2"}
# Input:  "variable VERSION_NUMBER(VERSION);"
# Output: "variable VERSION_NUMBER(2);"
# Note: VERSION_NUMBER is NOT replaced (word boundary check)
```

---

## Directive Reference

### `#include`

```csharp
#include "HSLStrLib.hsl"                        // relative path
#include "C:\\Program Files (x86)\\Hamilton\\Library\\HSLMthLib.hsl"  // absolute
```

- Paths are resolved using the search path list
- Circular includes are prevented by tracking `included_files`
- Maximum depth: 50 levels
- The included file's directory is temporarily added to search paths

### `#define` / `#undef`

```csharp
#define DEBUG_MODE 1
#define PLATE_COUNT 96
#define MY_STRING "hello"
#undef DEBUG_MODE
```

- Value is optional (defaults to `"1"` if omitted)
- Substitution is whole-word only
- Macros are not recursive (no expansion within values)

### `#ifdef` / `#ifndef` / `#else` / `#endif`

```csharp
#ifndef __MY_GUARD__
#define __MY_GUARD__ 1

// This content is included only once

#ifdef HSL_RUNTIME
    // Runtime implementation
#else
    // Edit-time stub
#endif

#endif // __MY_GUARD__
```

- Nesting is supported to arbitrary depth
- The condition stack tracks active/inactive states
- Inside a false condition, only `#ifdef`, `#ifndef`, `#else`, and `#endif` are processed (to track nesting depth)

### `#pragma once`

```csharp
#pragma once
```

- Marks the current file as "include once"
- Subsequent `#include` directives for this file are skipped
- Alternative to `#ifndef` / `#define` include guards

### `#if defined(...)`

```csharp
#if defined(HSL_RUNTIME)
    // equivalent to #ifdef HSL_RUNTIME
#endif
```

---

## Include Resolution

### Search Order

When resolving `#include "path"`, the preprocessor searches in this order:

1. **Relative to current file**: `dirname(current_file) / path`
2. **Absolute path**: If `path` is already absolute
3. **Hamilton Library**: `hamilton_dir\Library\path`
4. **Hamilton Methods**: `hamilton_dir\Methods\path`
5. **Additional search paths**: Any paths added via `add_search_path()`

### Path Normalization

All file paths are normalized with `os.path.normcase()` and `os.path.abspath()` before comparison. This ensures:
- Case-insensitive matching on Windows
- Forward/backslash equivalence
- Consistent deduplication in `included_files` and `pragma_once_files`

### The `__filename__` Token

Some Hamilton libraries use `__filename__` in include paths:

```csharp
#include "__filename__\\..\\SubDir\\helper.hsl"
```

The preprocessor replaces `__filename__` with the directory of the current file being processed.

---

## Macro Substitution

### Behavior

- Substitution occurs on every non-directive line
- Uses Python `re.sub()` with `\b` word boundaries
- Only whole-word matches are replaced
- Multiple macros can be substituted in a single line
- Substitution is single-pass (no recursive expansion)

### Example

```python
defines = {
    "HSL_RUNTIME": "1",
    "MAX_CHANNELS": "96",
    "PLATE_TYPE": "\"96-well\""
}

# Input line:
"variable channels(MAX_CHANNELS);  // PLATE_TYPE"

# After substitution:
"variable channels(96);  // \"96-well\""
```

---

## Conditional Compilation

### Condition Stack

The preprocessor maintains a `condition_stack` (list of booleans) to track nested conditional blocks:

```
#ifdef A          → push(A is defined?)
  #ifdef B        → push(B is defined?)
    // ...
  #else           → invert top: top = !top
    // ...
  #endif          → pop
#endif            → pop
```

A line is output only when:
1. The condition stack is empty (unconditional), OR
2. ALL values in the condition stack are `True`

### Active State

```python
is_active = len(condition_stack) == 0 or all(condition_stack)
```

When inactive, the preprocessor still processes `#ifdef`, `#ifndef`, `#else`, and `#endif` to maintain correct nesting, but all other lines and directives are skipped.

---

## Configuration

### Default Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Hamilton directory | `C:\Program Files (x86)\Hamilton` | Root of Hamilton installation |
| Max include depth | 50 | Prevents infinite recursion |
| Initial defines | `HSL_RUNTIME = "1"` | Always defined for simulation |

### Customization

```python
pp = Preprocessor(hamilton_dir=r"D:\Hamilton")
pp.add_search_path(r"C:\MyLibraries")
pp.defines["MY_FEATURE"] = "1"
pp.max_include_depth = 100
```

---

## Error Handling

### PreprocessorError

The `PreprocessorError` exception is raised for fatal preprocessing errors:

```python
class PreprocessorError(Exception):
    pass
```

### Error Scenarios

| Scenario | Behavior |
|----------|----------|
| Include file not found | Warning printed; include skipped |
| Max include depth exceeded | `PreprocessorError` raised |
| Malformed `#define` | Warning printed; directive ignored |
| Unmatched `#endif` | Silently ignored |
| Unmatched `#else` | Behavior undefined (stack mismatch) |
| File read error (encoding) | Falls back to `latin-1` encoding after `utf-8` failure |

### File Encoding

The preprocessor attempts to read files with UTF-8 encoding first. If that fails, it falls back to Latin-1 (ISO-8859-1), which can read any byte sequence. This handles Hamilton library files that may use Windows-1252 encoding.
