# AST Node Reference

> **Module**: `hsl_runtime/ast_nodes.py` (233 lines)  
> **Purpose**: Defines all Abstract Syntax Tree node types used by the parser and interpreter

---

## Table of Contents

1. [Overview](#overview)
2. [Base Class](#base-class)
3. [Expression Nodes](#expression-nodes)
4. [Statement Nodes](#statement-nodes)
5. [Declaration Nodes](#declaration-nodes)
6. [Top-Level Nodes](#top-level-nodes)
7. [Node Hierarchy Diagram](#node-hierarchy-diagram)

---

## Overview

The AST is the intermediate representation between the parser (Phase 3) and the interpreter (Phase 4). Every syntactic construct in HSL is represented as a subclass of `ASTNode`. The tree structure mirrors the nesting of the source code.

All node classes are Python dataclasses with positional tracking (line, column, file) for error reporting.

---

## Base Class

### ASTNode

```python
class ASTNode:
    line: int = 0       # Source line number (1-based)
    column: int = 0     # Source column number (1-based)
    file: str = ""      # Source filename
```

All AST nodes inherit from `ASTNode` and carry position information.

---

## Expression Nodes

### IntegerLiteral

```python
class IntegerLiteral(ASTNode):
    value: int          # e.g., 42, 255 (from 0xFF)
```

Represents integer constants, including hexadecimal values (converted at parse time).

### FloatLiteral

```python
class FloatLiteral(ASTNode):
    value: float        # e.g., 3.14, 1e-3
```

Represents floating-point constants, including scientific notation.

### StringLiteral

```python
class StringLiteral(ASTNode):
    value: str          # e.g., "hello" (escapes already processed by lexer)
```

Represents string constants. Escape sequences are resolved during lexing.

### BoolLiteral

```python
class BoolLiteral(ASTNode):
    value: bool         # True or False
```

Represents boolean literal values.

### Identifier

```python
class Identifier(ASTNode):
    name: str           # e.g., "myVar", "ML_STAR"
```

Represents a simple (unqualified) variable or function name.

### ScopedName

```python
class ScopedName(ASTNode):
    namespace: str      # e.g., "MyNamespace"
    name: str           # e.g., "MyFunction"
```

Represents a namespace-qualified name like `MyNamespace::MyFunction`.

### ArrayAccess

```python
class ArrayAccess(ASTNode):
    array: ASTNode      # Expression evaluating to an array
    index: ASTNode      # Expression evaluating to an index
```

Represents array element access: `arr[i]`.

### MemberAccess

```python
class MemberAccess(ASTNode):
    object: ASTNode     # Expression evaluating to an object/device/sequence
    member: str         # Member name
```

Represents dot-notation access: `obj.Property`, `ML_STAR.Aspirate`.

### FunctionCall

```python
class FunctionCall(ASTNode):
    name: str           # Function name (simple or qualified)
    arguments: list[ASTNode]  # Argument expressions
```

Represents a function call like `Trace("hello")` or `IStr(42)`.

### MethodCall

```python
class MethodCall(ASTNode):
    object: ASTNode     # Expression evaluating to the receiver
    method: str         # Method name
    arguments: list[ASTNode]  # Argument expressions
```

Represents a method call on an object: `arr.SetAt(0, value)`, `f.Open("file.txt", hslRead)`.

### UnaryOp

```python
class UnaryOp(ASTNode):
    operator: str       # "-", "!", "++", "--"
    operand: ASTNode    # Expression
    prefix: bool = True # True for prefix, False for postfix (++/--)
```

Represents unary operations:
- `-x` (negation)
- `!x` (logical NOT)
- `++x` / `x++` (increment)
- `--x` / `x--` (decrement)

### BinaryOp

```python
class BinaryOp(ASTNode):
    operator: str       # "+", "-", "*", "/", "%", "==", "!=", "<", ">",
                        # "<=", ">=", "&&", "||", "|"
    left: ASTNode       # Left operand expression
    right: ASTNode      # Right operand expression
```

Represents binary operations including arithmetic, comparison, and logical operators.

### Assignment

```python
class Assignment(ASTNode):
    target: ASTNode     # Left-hand side (Identifier, ArrayAccess, MemberAccess)
    value: ASTNode      # Right-hand side expression
```

Represents assignment: `x = 42`, `arr[i] = value`, `obj.prop = "hello"`.

Assignment can also be used as an expression (returns the assigned value), which is necessary for `for` loop initializers like `for (i = 0; ...)`.

---

## Statement Nodes

### ExpressionStatement

```python
class ExpressionStatement(ASTNode):
    expression: ASTNode  # Any expression (usually a function call)
```

Wraps an expression used as a statement: `Trace("hello");`

### Block

```python
class Block(ASTNode):
    statements: list[ASTNode]  # List of contained statements/declarations
```

Represents a brace-enclosed `{ ... }` block of statements.

### IfStatement

```python
class IfStatement(ASTNode):
    condition: ASTNode       # Boolean expression
    then_branch: ASTNode     # Statement/block for true case
    else_branch: ASTNode = None  # Optional statement/block for false case
```

Represents `if (cond) { ... } else { ... }`. The `else_branch` is `None` when there's no `else` clause. Chained `else if` is represented as an `IfStatement` in the `else_branch`.

### ForLoop

```python
class ForLoop(ASTNode):
    initializer: ASTNode = None  # Init statement (declaration or assignment)
    condition: ASTNode = None    # Loop condition expression
    increment: ASTNode = None    # Post-iteration expression
    body: ASTNode               # Loop body statement/block
```

Represents `for (init; cond; incr) { ... }`. All three header parts are optional (an empty `for(;;)` is an infinite loop).

### WhileLoop

```python
class WhileLoop(ASTNode):
    condition: ASTNode    # Loop condition expression
    body: ASTNode         # Loop body statement/block
```

Represents `while (cond) { ... }`.

### BreakStatement

```python
class BreakStatement(ASTNode):
    pass  # No additional fields
```

Represents `break;` — exits the innermost loop.

### ContinueStatement

```python
class ContinueStatement(ASTNode):
    pass  # No additional fields
```

Represents `continue;` — skips to the next loop iteration.

### ReturnStatement

```python
class ReturnStatement(ASTNode):
    value: ASTNode = None  # Optional return value expression
```

Represents `return;` or `return(expr);`. The parentheses around the return value in HSL are syntactic, handled by the parser.

### AbortStatement

```python
class AbortStatement(ASTNode):
    pass  # No additional fields
```

Represents `abort;` — terminates the entire program.

### PauseStatement

```python
class PauseStatement(ASTNode):
    pass  # No additional fields
```

Represents `pause;` — pauses execution (logged in simulation).

### OnErrorGoto

```python
class OnErrorGoto(ASTNode):
    label: str = None    # Target label name, or None for "onerror goto 0"
```

Represents `onerror goto ErrorHandler;` or `onerror goto 0;` (disable handler). When `label` is `None`, the error handler is disabled.

### ResumeNext

```python
class ResumeNext(ASTNode):
    pass  # No additional fields
```

Represents either `onerror resume next;` (enable silent error suppression) or `resume next;` (continue after error handler).

### Label

```python
class Label(ASTNode):
    name: str           # Label name (e.g., "ErrorHandler")
```

Represents a label destination: `ErrorHandler:`. Labels are targets for `onerror goto`.

---

## Declaration Nodes

### VariableDeclaration

```python
class VariableDeclaration(ASTNode):
    var_type: str           # "variable", "string", "device", "sequence", etc.
    name: str               # Variable name
    initializer: ASTNode = None  # Initial value expression
    is_array: bool = False  # Whether declared as array (name[])
    array_size: ASTNode = None   # Fixed array size expression, if any
    qualifiers: list[str] = []   # ["static", "private", "global", "const"]
    device_args: list[ASTNode] = []  # Device constructor arguments
```

Represents all variable declarations:
```csharp
variable x;                    // var_type="variable", name="x"
variable y(42);                // initializer=IntegerLiteral(42)
variable arr[];                // is_array=True
variable fixed[10];            // is_array=True, array_size=IntegerLiteral(10)
string s("hello");             // var_type="string"
device d("a.lay", "ML", 1);   // var_type="device", device_args=[...]
global variable g;             // qualifiers=["global"]
static variable count(0);     // qualifiers=["static"]
```

### Parameter

```python
class Parameter(ASTNode):
    param_type: str     # "variable", "device", "sequence", etc.
    name: str           # Parameter name
    is_reference: bool = False  # True if declared with &
```

Represents a function/method parameter:
```csharp
function f(variable x, variable& y, device& d)
//         ^param_type  ^is_reference=True
```

### FunctionDeclaration

```python
class FunctionDeclaration(ASTNode):
    name: str               # Function or method name
    parameters: list[Parameter]  # Parameter list
    body: Block             # Function body
    return_type: str = None # Return type (if specified)
    is_method: bool = False # True for 'method', False for 'function'
    qualifiers: list[str] = []  # ["static", "private"]
```

Represents both function and method declarations:
```csharp
function add(variable a, variable b) variable { return(a+b); }
// name="add", return_type="variable", is_method=False

method Main() { ... }
// name="Main", is_method=True
```

### NamespaceDeclaration

```python
class NamespaceDeclaration(ASTNode):
    name: str                    # Namespace name
    declarations: list[ASTNode]  # Contained declarations
```

Represents `namespace Name { ... }` blocks containing functions, variables, and nested declarations.

### SchedulerOnlyBlock

```python
class SchedulerOnlyBlock(ASTNode):
    body: Block          # Block of statements
```

Represents `scheduleronly { ... }` — skipped during simulation execution.

### ExecutorOnlyBlock

```python
class ExecutorOnlyBlock(ASTNode):
    body: Block          # Block of statements
```

Represents `executoronly { ... }` — executed during simulation.

---

## Top-Level Nodes

### Program

```python
class Program(ASTNode):
    declarations: list[ASTNode]  # Top-level declarations
    source_file: str = ""        # Original source file path
```

The root node of the AST. Contains all top-level declarations (namespaces, functions, methods, global variables).

---

## Node Hierarchy Diagram

```
ASTNode
├── Program
├── Expressions
│   ├── IntegerLiteral
│   ├── FloatLiteral
│   ├── StringLiteral
│   ├── BoolLiteral
│   ├── Identifier
│   ├── ScopedName
│   ├── ArrayAccess
│   ├── MemberAccess
│   ├── FunctionCall
│   ├── MethodCall
│   ├── UnaryOp
│   ├── BinaryOp
│   └── Assignment
├── Statements
│   ├── ExpressionStatement
│   ├── Block
│   ├── IfStatement
│   ├── ForLoop
│   ├── WhileLoop
│   ├── BreakStatement
│   ├── ContinueStatement
│   ├── ReturnStatement
│   ├── AbortStatement
│   ├── PauseStatement
│   ├── OnErrorGoto
│   ├── ResumeNext
│   └── Label
└── Declarations
    ├── VariableDeclaration
    ├── Parameter
    ├── FunctionDeclaration
    ├── NamespaceDeclaration
    ├── SchedulerOnlyBlock
    └── ExecutorOnlyBlock
```

---

## Usage in the Pipeline

### Parser → AST

The parser constructs AST nodes as it recognizes syntactic constructs:

```python
# Parser recognizes: variable x(42);
node = VariableDeclaration(
    var_type="variable",
    name="x",
    initializer=IntegerLiteral(value=42, line=1, column=12),
    line=1,
    column=1,
    file="example.hsl"
)
```

### AST → Interpreter

The interpreter dispatches on node type to execute:

```python
def _execute_node(self, node):
    if isinstance(node, Block):
        return self._execute_block(node)
    elif isinstance(node, IfStatement):
        return self._execute_if(node)
    elif isinstance(node, VariableDeclaration):
        return self._execute_var_decl(node)
    elif isinstance(node, FunctionCall):
        return self._eval_function_call(node)
    # ... etc for all node types
```

---

## Design Notes

### Why Dataclasses?

Python dataclasses provide:
- Automatic `__init__` generation with default values
- Clean attribute access (`node.name`, `node.value`)
- Easy debugging with `__repr__`
- No boilerplate constructors

### Why Separate Expression and Statement Nodes?

Expressions produce values; statements do not. This distinction is important for:
- `ExpressionStatement` wrapping: `Trace("hello")` is an expression used as a statement
- Assignment as expression: `for (i = 0; ...)` uses assignment in an expression context
- Return values: `return(expr)` expects an expression

### Why a Single FunctionDeclaration for Both?

Functions and methods in HSL are syntactically identical except for the keyword. The `is_method` flag distinguishes them, which the interpreter uses to identify the program entry point.
