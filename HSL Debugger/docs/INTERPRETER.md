# Interpreter Module

> **Module**: `hsl_runtime/interpreter.py` (1,666 lines)  
> **Phase**: 4 of 4  
> **Input**: `Program` AST node  
> **Output**: Trace messages, simulation results

---

## Table of Contents

1. [Purpose](#purpose)
2. [Public API](#public-api)
3. [Type System](#type-system)
4. [Scope and Variable Resolution](#scope-and-variable-resolution)
5. [Execution Model](#execution-model)
6. [Built-in Functions](#built-in-functions)
7. [Data Element Functions](#data-element-functions)
8. [Control Flow Implementation](#control-flow-implementation)
9. [Error Handling](#error-handling)
10. [Simulation Stubs](#simulation-stubs)
11. [Debugger Integration](#debugger-integration)
12. [Safety Limits](#safety-limits)

---

## Purpose

The interpreter executes the AST produced by the parser in a simulation environment. Its core responsibilities:

1. **Type system**: Variant values (`HslValue`) with automatic type coercion
2. **Scope management**: Lexical scoping with parent chain lookup
3. **Function dispatch**: ~120+ built-in functions + user-defined functions from the AST
4. **Simulation stubs**: Every hardware operation is stubbed (devices, timers, dialogs, COM objects)
5. **Error handling**: `onerror goto` / `resume next` semantics
6. **Trace capture**: All `Trace()` / `FormatTrace()` output collected for analysis

---

## Public API

### Class: Interpreter

```python
interp = Interpreter(
    program: Program,
    trace: TraceOutput,
    verbose: bool = True,
    hamilton_dir: str = r"C:\Program Files (x86)\Hamilton"
)
interp.execute() → None
```

**Parameters:**
- `program`: The `Program` AST node from the parser
- `trace`: A `TraceOutput` instance to collect trace messages
- `verbose`: Whether to print trace messages to console
- `hamilton_dir`: Hamilton installation path (for `GetBinPath()` etc.)

### Class: TraceOutput

```python
trace = TraceOutput(verbose: bool = True)
trace.trace(message: str) → None
trace.warn(message: str) → None
trace.error(message: str) → None
trace.messages  # List[str] of all collected messages
```

Collects trace output from the simulation. When `verbose=True`, messages are also printed to the console.

### Execution

```python
interp = Interpreter(program, trace)
try:
    interp.execute()
except AbortException:
    print("Program aborted (intentional)")
```

The `execute()` method:
1. Initializes built-in constants and functions
2. Collects all declarations from the AST (Pass 1)
3. Finds and calls the `Main` entry point (Pass 2)

---

## Type System

### HslValue -- The Variant Type

The core runtime type wrapping Python values:

```python
class HslValue:
    def __init__(self, value=0):
        self.value = value  # int, float, str, or None
```

#### Type Coercion Methods

| Method | Behavior |
|--------|----------|
| `to_int()` | `int(value)`, truncates floats, parses strings, `0` on failure |
| `to_float()` | `float(value)`, parses strings, `0.0` on failure |
| `to_string()` | `str(value)`, integers formatted without decimals |
| `to_bool()` | `False` for `0`, `0.0`, `""`, `None`; `True` otherwise |

### Automation Type Classes

Each HSL automation type has a corresponding Python class:

#### HslArray

```python
class HslArray:
    def __init__(self):
        self.elements = []    # List of HslValue
```

Element functions:
- `SetSize(n)` -- resize to `n` elements
- `GetSize()` -- return current size
- `SetAt(index, value)` -- set element at index
- `GetAt(index)` -- get element at index
- `ElementAt(index)` -- get element reference at index
- `AddAsLast(value)` -- append element

#### HslSequence

```python
class HslSequence:
    def __init__(self):
        self.current_pos = 0
        self.max_pos = 0
        self.count = 0
        self.name = ""
        self.labware_id = ""
        self.position_ids = []
        self.used_positions = 0
```

Simulates Hamilton deck sequences with position tracking.

#### HslDevice

```python
class HslDevice:
    def __init__(self, layout="", name="", sim=True):
        self.layout_file = layout
        self.device_name = name
        self._is_simulation = True  # ALWAYS True
        self.sequences = {}
```

Dynamic attribute access creates sequences on the fly:

```python
def __getattr__(self, name):
    # ML_STAR.mySequence → creates HslSequence named "mySequence"
    if name not in self.sequences:
        self.sequences[name] = HslSequence()
        self.sequences[name].name = name
    return self.sequences[name]
```

#### HslFile

```python
class HslFile:
    def __init__(self):
        self.handle = None
        self.filepath = ""
        self.mode = ""
        self.is_open = False
        self.delimiter = ","
        self.fields = []
```

File reads actually work (opens real files). Writes are stubbed.

#### HslObject

```python
class HslObject:
    def __init__(self):
        self.prog_id = ""
        self.properties = {}  # Dynamic property store
```

COM objects are simulated as property bags. `CreateObject()` logs the ProgID but doesn't create a real COM object.

#### HslTimer

```python
class HslTimer:
    def __init__(self):
        self.duration = 0
        self.elapsed = 0
        self.started = False
```

Timer operations return immediately -- no real delays.

#### HslDialog

```python
class HslDialog:
    def __init__(self):
        self.title = ""
        self.properties = {}
```

Dialogs auto-accept with OK. Properties are tracked for inspection.

#### HslEvent

```python
class HslEvent:
    def __init__(self):
        pass  # Pure stub
```

---

## Scope and Variable Resolution

### Scope Class

```python
class Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.variables = {}  # name → HslValue or automation type
```

Methods:
- `get(name)` -- look up variable in this scope and all parents
- `set(name, value)` -- set variable in the nearest scope that contains it
- `set_local(name, value)` -- set variable in this scope only (for declarations)
- `has(name)` -- check if variable exists in this scope or parents

### Scope Chain

```
Global Scope
└── Namespace "MyLib"
    └── Function "DoWork" (local scope)
        └── Block scope (for loop body, if body, etc.)
```

Variable lookup walks from the innermost scope to the global scope. The first match wins.

### Interpreter Scope Attributes

| Attribute | Description |
|-----------|-------------|
| `global_scope` | Top-level scope for global variables and constants |
| `current_scope` | Currently active scope (changes during execution) |
| `functions` | `dict[str, FunctionDeclaration]` -- all declared functions |
| `namespaces` | `dict[str, dict]` -- namespace contents |

---

## Execution Model

### Two-Pass Execution

```
Pass 1: _collect_declarations(program)
  For each top-level declaration:
    FunctionDeclaration → register in self.functions
    NamespaceDeclaration → register in self.namespaces, recurse
    VariableDeclaration → declare in global scope
    Block → recurse into contents

Pass 2: execute()
  Search for entry point in order:
    1. "main"
    2. "_Method::main"
    3. "Main"
    4. "_Method::Main"
  Call the found function
```

### Node Dispatch

The `_execute_node()` method dispatches based on AST node type:

```python
def _execute_node(self, node):
    if isinstance(node, Block):
        return self._execute_block(node)
    elif isinstance(node, ExpressionStatement):
        return self._eval_expr(node.expression)
    elif isinstance(node, IfStatement):
        return self._execute_if(node)
    elif isinstance(node, ForLoop):
        return self._execute_for(node)
    # ... 20+ node types handled
```

Before each node execution:
1. Iteration counter is checked against `_max_iterations`
2. Step callback is invoked (if set) for debugger support

### Expression Evaluation

`_eval_expr()` handles all expression node types:

```python
def _eval_expr(self, node):
    if isinstance(node, IntegerLiteral):
        return HslValue(node.value)
    elif isinstance(node, FloatLiteral):
        return HslValue(node.value)
    elif isinstance(node, StringLiteral):
        return HslValue(node.value)
    elif isinstance(node, Identifier):
        return self._resolve_identifier(node)
    elif isinstance(node, BinaryOp):
        return self._eval_binary_op(node)
    # ... etc
```

### Binary Operations

The `_eval_binary_op()` method handles arithmetic, comparison, and logical operators:

| Operator | Behavior |
|----------|----------|
| `+` | Numeric addition OR string concatenation (if either operand is string) |
| `-`, `*` | Standard arithmetic |
| `/` | Integer division (`//`) when both operands are int; float division otherwise |
| `%` | Modulo |
| `==`, `!=` | Value equality with type coercion |
| `<`, `<=`, `>`, `>=` | Comparison with type coercion fallback (str↔int) |
| `&&` | Short-circuit logical AND |
| `\|\|` | Short-circuit logical OR |
| `\|` | Bitwise OR (integer operands) |

### Unary Operations

| Operator | Behavior |
|----------|----------|
| `-` | Numeric negation |
| `!` | Logical NOT |
| `++` (prefix/postfix) | Increment by 1; postfix returns original value |
| `--` (prefix/postfix) | Decrement by 1; postfix returns original value |
| `++` on sequence | `sequence.Increment(1)` |
| `--` on sequence | `sequence.Increment(-1)` |

---

## Built-in Functions

The interpreter implements ~120+ built-in functions. They are registered during `_init_builtins()` and dispatched via `_call_builtin()`.

### Registration

```python
def _init_builtins(self):
    scope = self.global_scope
    
    # Boolean constants
    scope.set_local("hslTrue", HslValue(1))
    scope.set_local("hslFalse", HslValue(0))
    scope.set_local("hslInfinite", HslValue(2147483647))
    
    # Type constants
    scope.set_local("hslInteger", HslValue("hslInteger"))
    scope.set_local("hslFloat", HslValue("hslFloat"))
    scope.set_local("hslString", HslValue("hslString"))
    
    # File I/O constants
    scope.set_local("hslRead", HslValue(1))
    scope.set_local("hslWrite", HslValue(2))
    scope.set_local("hslAppend", HslValue(3))
    # ... many more constants
```

### Built-in Function Categories

#### Trace Functions

| Function | Implementation |
|----------|---------------|
| `Trace(...)` | Concatenates all arguments as strings; sends to `TraceOutput` |
| `FormatTrace(cat, level, ...)` | Same with category/level prefix |

#### Type Conversion

| Function | Implementation |
|----------|---------------|
| `IStr(n)` | `str(int(value))` |
| `FStr(n)` | `f"{float(value):f}"` |
| `IVal(s)` | `int(str_value)` with error handling |
| `FVal(s)` | `float(str_value)` with error handling |
| `IVal2(s)` | Variant of `IVal` |
| `FVal2(s)` | Variant of `FVal` |
| `GetType(v)` | Returns `"i"` for int, `"f"` for float, `"s"` for string |

#### String Functions (20+)

| Function | Implementation |
|----------|---------------|
| `StrGetLength(s)` | `len(str_value)` |
| `StrFind(s, sub)` | `str.find(sub)` → returns -1 if not found |
| `StrLeft(s, n)` | `str[:n]` |
| `StrRight(s, n)` | `str[-n:]` |
| `StrMid(s, start, len)` | `str[start:start+len]` |
| `StrMakeUpper(s)` | `str.upper()` |
| `StrMakeLower(s)` | `str.lower()` |
| `StrConcat2/4/8/12(...)` | Concatenate N strings |
| `StrReplace(s, old, new)` | `str.replace(old, new)` |
| `StrTrimLeft(s)` | `str.lstrip()` |
| `StrTrimRight(s)` | `str.rstrip()` |
| `StrIsDigit(s)` | `str.isdigit()` → 1 or 0 |
| `StrFillLeft(s, n, ch)` | Right-justify with fill character |
| `StrFillRight(s, n, ch)` | Left-justify with fill character |

#### Math Functions

| Function | Implementation |
|----------|---------------|
| `MthAbs(n)` | `abs(value)` |
| `MthSqrt(n)` | `math.sqrt(value)` |
| `MthPow(b, e)` | `math.pow(base, exp)` |
| `MthMin(a, b)` | `min(a, b)` |
| `MthMax(a, b)` | `max(a, b)` |
| `MthRound(n)` | `round(value)` |

#### System Path Functions

| Function | Returns |
|----------|---------|
| `GetBinPath()` | `hamilton_dir\Bin\` |
| `GetLibraryPath()` | `hamilton_dir\Library\` |
| `GetMethodsPath()` | `hamilton_dir\Methods\` |
| `GetLogFilesPath()` | `hamilton_dir\Logfiles\` |
| `GetConfigPath()` | `hamilton_dir\Config\` |
| `GetLabwarePath()` | `hamilton_dir\Labware\` |
| `GetSystemPath()` | `hamilton_dir\System\` |

#### I/O Functions

| Function | Simulation Behavior |
|----------|-------------------|
| `InputBox(prompt, ...)` | Returns empty string `""` |
| `MessageBox(msg, flags)` | Returns `hslOK` (1) |
| `Shell(cmd)` | Logs command; **never executes** |

#### Miscellaneous

| Function | Behavior |
|----------|----------|
| `SearchPath(file)` | Searches Hamilton dir; returns path or `""` |
| `GetFileName()` | Returns current source file path |
| `GetFunctionName()` | Returns current function name from call stack |
| `GetMethodFileName()` | Returns method file path |
| `GetLineNumber()` | Returns `0` (stub) |
| `RegisterAbortHandler(f)` | Logs; no-op in simulation |
| `Translate(s)` | Returns input unchanged |
| `AddCheckSum()` | No-op |
| `IsDBNull(v)` | Returns `0` (never null in simulation) |
| `GetExecutorObject()` | Returns `HslObject()` stub |

#### Library Stubs

Large blocks of stubs for Hamilton-specific libraries:

| Category | Functions |
|----------|-----------|
| PTL (Plate Transport) | `PTL::StartTransport`, `PTL::WaitForCompletion`, etc. |
| TRACELEVEL | `TRACELEVEL::...` trace configuration functions |
| MECC (Maintenance) | `MECC::...` stubs |
| ASWGLOBAL | `ASWGLOBAL::...` application constants |
| PDF Report | Report generator stubs |

---

## Data Element Functions

Element functions are called via dot notation on automation type instances. The interpreter dispatches to type-specific handlers.

### Dispatch

```python
def _eval_method_call(self, node):
    obj = self._eval_expr(node.object)
    method = node.method
    args = [self._eval_expr(a) for a in node.arguments]
    
    if isinstance(obj, HslArray):
        return self._call_array_method(obj, method, args)
    elif isinstance(obj, HslSequence):
        return self._call_sequence_method(obj, method, args)
    elif isinstance(obj, HslFile):
        return self._call_file_method(obj, method, args)
    # ... etc for each type
```

### Array Methods

| Method | Implementation |
|--------|---------------|
| `SetSize(n)` | Resize elements list (pad with `HslValue(0)` or truncate) |
| `GetSize()` | Return `len(elements)` |
| `SetAt(idx, val)` | `elements[idx] = val` (auto-extend if needed) |
| `GetAt(idx)` | `elements[idx]` (returns `HslValue(0)` if out of bounds) |
| `ElementAt(idx)` | Same as `GetAt` (reference semantics not fully modeled) |
| `AddAsLast(val)` | `elements.append(val)` |

### Sequence Methods

| Method | Implementation |
|--------|---------------|
| `GetCurrentPosition()` | Return `current_pos` |
| `SetCurrentPosition(n)` | Set `current_pos = n` |
| `GetCount()` | Return `count` |
| `SetCount(n)` | Set `count = n` |
| `GetTotal()` | Return `count` |
| `GetMax()` | Return `max_pos` |
| `SetMax(n)` | Set `max_pos = n` |
| `GetName()` | Return `name` |
| `Increment(n)` | `current_pos += n` |
| `GetLabwareId()` | Return `labware_id` or `""` |
| `GetPositionId()` | Return `""` (stub) |
| `Add(labId, posId)` | Append to positions; increment count |
| `SetUsedPositions(n)` | Set `used_positions = n` |
| `GetUsedPositions()` | Return `used_positions` |

### String Methods

| Method | Implementation |
|--------|---------------|
| `Find(sub)` | `str.find(sub)` |
| `Left(n)` | `str[:n]` |
| `Right(n)` | `str[-n:]` |
| `Mid(start, len)` | `str[start:start+len]` |
| `GetLength()` | `len(str)` |
| `MakeUpper()` | `str.upper()` |
| `MakeLower()` | `str.lower()` |
| `SpanExcluding(chars)` | Characters before first occurrence of any char in `chars` |
| `Compare(other)` | Case-sensitive string comparison |

### File Methods

| Method | Implementation |
|--------|---------------|
| `Open(path, mode)` | Opens real file for reading; stubs write modes |
| `Close()` | Closes file handle |
| `Eof()` | Returns `1` if at end of file |
| `ReadString(var)` | Reads one line from file (actual I/O) |
| `WriteString(s)` | Logged; no actual write |
| `AddField(...)` | Stub |
| `RemoveFields()` | Stub |
| `SetDelimiter(d)` | Stores delimiter value |
| `ReadRecord()` | Stub |
| `WriteRecord()` | Stub |
| `Seek(pos)` | Stub |
| `UpdateRecord()` | Stub |

### Dialog Methods

| Method | Implementation |
|--------|---------------|
| `InitCustomDialog(name)` | Sets dialog title |
| `SetCustomDialogProperty(k,v)` | Stores in properties dict |
| `GetCustomDialogProperty(k)` | Retrieves from properties dict |
| `SetCustomDialogArrayProperty(k,arr)` | Stores array property |
| `ShowCustomDialog()` | Returns OK (1) immediately |
| `SetOutput(msg)` | Logged |
| `ShowOutput()` | Logged |

### Object Methods

| Method | Implementation |
|--------|---------------|
| `CreateObject(progId)` | Stores ProgID; logs |
| `GetObject()` | Returns self |

### Timer Methods

| Method | Implementation |
|--------|---------------|
| `SetTimer(seconds)` | Stores duration |
| `WaitTimer(stoppable)` | Returns immediately (no delay) |
| `SetTimerViewName(name)` | Logged |
| `ReadElapsed()` | Returns stored duration |
| `Restart()` | Resets elapsed |
| `Stop()` | Sets stopped flag |

---

## Control Flow Implementation

### Python Exceptions as Control Flow

| HSL Statement | Python Exception | Caught By |
|---------------|-----------------|-----------|
| `break` | `BreakException` | For/while loop handlers |
| `continue` | `ContinueException` | For/while loop handlers |
| `return(value)` | `ReturnException(value)` | Function call handler |
| `abort` | `AbortException` | Top-level execute() |

### For Loop Execution

```python
def _execute_for(self, node):
    if node.initializer:
        self._execute_node(node.initializer)
    iterations = 0
    while True:
        if iterations >= self._max_iterations:
            break
        if node.condition:
            cond = self._eval_expr(node.condition)
            if not self._is_truthy(cond):
                break
        try:
            self._execute_node(node.body)
        except BreakException:
            break
        except ContinueException:
            pass  # fall through to increment
        if node.increment:
            self._eval_expr(node.increment)
        iterations += 1
```

### Function Call Dispatch

```python
def _call_function(self, name, args):
    # 1. Try exact name
    if name in self.functions:
        return self._execute_user_function(name, args)
    
    # 2. Try _Method:: prefix
    method_name = f"_Method::{name}"
    if method_name in self.functions:
        return self._execute_user_function(method_name, args)
    
    # 3. Try stripping namespace prefix
    if "::" in name:
        base = name.split("::")[-1]
        if base in self.functions:
            return self._execute_user_function(base, args)
    
    # 4. Try built-in
    result = self._call_builtin(name, args)
    if result is not None:
        return result
    
    # 5. Unknown function -- log warning, return 0
    self.trace.warn(f"Unknown function: {name}")
    return HslValue(0)
```

---

## Error Handling

### onerror goto

When `onerror goto label` is encountered, the interpreter stores the label name in `self.error_handler`. When an error occurs during execution:

1. If `error_handler` is set → jump to the label
2. If `error_handler` is `None` → propagate the exception

### onerror resume next

When `onerror resume next` is active, errors are caught and execution continues with the next statement. The `err` object properties are set with the error details.

### The `err` Object

The global `err` object is simulated as built-in function calls:

| Call | Behavior |
|------|----------|
| `err.GetId()` | Returns error code (0 if no error) |
| `err.GetDescription()` | Returns error message ("" if no error) |
| `err.Clear()` | Resets error state |
| `err.Raise(id, desc, src)` | Sets error state (doesn't actually throw in simulation) |

---

## Simulation Stubs

### Design Principle

Every hardware-facing operation returns a "success" value without performing any real action:

```python
# Device method calls
def _eval_method_call_on_device(self, device, method, args):
    self.trace.trace(f"[SIMULATION] {device.device_name}.{method}()")
    return HslValue(0)  # success
```

### Stub Categories

| Category | Approach |
|----------|----------|
| Device operations | Log and return success |
| COM objects | Property bag (get/set arbitrary properties) |
| Shell commands | Log command text; never execute |
| Message boxes | Return OK |
| Input boxes | Return empty string |
| Timers | Track duration; no real delay |
| Dialogs | Store properties; auto-accept |
| Events | No-op |
| File writes | Log; no actual output |
| File reads | **Actually read** the file |

### Why File Reads Work

File reads are the one operation that performs actual I/O. This is safe because:
- Reading files doesn't modify anything
- Many HSL methods read configuration/worklist files
- Without real file reads, many methods would fail trivially

---

## Debugger Integration

### Step Callback

```python
interp._step_callback = lambda node, interp: ...
```

Called before each AST node is executed. The callback receives:
- `node`: The AST node about to be executed
- `interp`: The interpreter instance (for reading state)

### Inspectable State

| Property | Access | Content |
|----------|--------|---------|
| `current_scope.variables` | `interp.current_scope.variables` | Current local variables |
| `global_scope.variables` | `interp.global_scope.variables` | Global variables |
| `call_stack` | `interp.call_stack` | Function call history |
| `functions` | `interp.functions` | All declared functions |
| `namespaces` | `interp.namespaces` | All namespace contents |
| `trace.messages` | `interp.trace.messages` | All trace output |

---

## Safety Limits

### Maximum Iterations

Each loop is limited to `_max_iterations` iterations (default: 100,000):

```python
if iterations >= self._max_iterations:
    self.trace.warn(f"Loop iteration limit reached ({self._max_iterations})")
    break
```

Configurable via `--max-iterations` CLI flag.

### Unknown Function Handling

Unknown functions are logged and return `HslValue(0)`:

```python
self.trace.warn(f"Unknown function: {name}")
return HslValue(0)
```

This prevents execution from halting on unsupported library calls while making the gaps visible in the trace output.

### Type Error Recovery

Binary operations catch `TypeError` and attempt type coercion:

```python
try:
    result = left_val + right_val
except TypeError:
    # Try string concatenation
    result = str(left_val) + str(right_val)
```

This handles HSL's loose typing where `"hello" + 42` produces `"hello42"`.
