# Parser Module

> **Module**: `hsl_runtime/parser.py` (938 lines)  
> **Phase**: 3 of 4  
> **Input**: `List[Token]` from the lexer  
> **Output**: `Program` AST node (tree of declarations and statements)

---

## Table of Contents

1. [Purpose](#purpose)
2. [Public API](#public-api)
3. [Parsing Strategy](#parsing-strategy)
4. [Grammar Reference](#grammar-reference)
5. [Expression Parsing](#expression-parsing)
6. [Statement Parsing](#statement-parsing)
7. [Declaration Parsing](#declaration-parsing)
8. [Error Recovery](#error-recovery)
9. [Special Cases](#special-cases)
10. [ParseError Details](#parseerror-details)

---

## Purpose

The parser transforms a flat list of tokens into a hierarchical Abstract Syntax Tree (AST) that represents the program's structure. It implements:

- Recursive descent parsing for statements and declarations
- Precedence climbing (Pratt-style) for expression parsing
- Error recovery to produce partial ASTs from files with syntax errors
- Special handling for HSL-specific constructs (device declarations, editor markers, runtime includes)

---

## Public API

### Class: Parser

```python
parser = Parser(tokens: List[Token])
program = parser.parse() → Program
errors = parser.errors   → List[ParseError]
```

**Parameters:**
- `tokens`: List of `Token` objects from the lexer (should end with EOF)

**Returns:** A `Program` AST node containing all parsed declarations.

**Errors:** Non-fatal parse errors are collected in `parser.errors`. The parser continues after each error, producing as complete an AST as possible.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `tokens` | `List[Token]` | Input token stream |
| `pos` | `int` | Current position in token stream |
| `errors` | `List[ParseError]` | Accumulated parse errors |
| `current_namespace` | `str` | Name of the namespace currently being parsed |

---

## Parsing Strategy

### Recursive Descent

Top-level parsing and statement parsing use recursive descent: each grammar rule is implemented as a method that recognizes its construct and calls sub-methods for nested constructs.

```python
def _parse_if_statement(self) → IfStatement:
    self._expect(TokenType.IF)
    self._expect(TokenType.LPAREN)
    condition = self._parse_expression()
    self._expect(TokenType.RPAREN)
    then_branch = self._parse_statement()
    else_branch = None
    if self._match(TokenType.ELSE):
        else_branch = self._parse_statement()
    return IfStatement(condition, then_branch, else_branch)
```

### Precedence Climbing

Expression parsing uses precedence climbing to handle operator precedence and associativity without deep recursion:

```
_parse_expression()          → Assignment level
_parse_or_expression()       → || level
_parse_and_expression()      → && level
_parse_bitwise_or()          → | level
_parse_equality()            → == != level
_parse_comparison()          → < <= > >= level
_parse_additive()            → + - level
_parse_multiplicative()      → * / % level
_parse_unary()               → - ! ++ -- level
_parse_postfix()             → () [] . :: ++ -- level
_parse_primary()             → literals, identifiers, parenthesized expressions
```

Each level handles its operators and delegates to the next higher-precedence level for operands.

### Lookahead

The parser uses one token of lookahead via the helper methods:

| Method | Description |
|--------|-------------|
| `_peek()` | Return current token without consuming |
| `_advance()` | Consume and return current token |
| `_match(type)` | If current matches type, consume and return `True` |
| `_expect(type)` | Consume and assert type; raise `ParseError` if mismatch |
| `_check(type)` | Return `True` if current matches type (no consume) |

---

## Grammar Reference

### Program Structure

```
Program        → Declaration* EOF

Declaration    → NamespaceDecl
               | QualifiedDecl
               | VarDecl
               | RuntimeInclude
               | BackslashSkip
               | Statement

QualifiedDecl  → Qualifier* (FunctionDecl | MethodDecl | VarDecl)

Qualifier      → 'static' | 'private' | 'global' | 'const'
```

### Namespace Declaration

```
NamespaceDecl  → 'namespace' IDENTIFIER '{' Declaration* '}'
```

### Function / Method Declaration

```
FunctionDecl   → 'function' IDENTIFIER '(' ParamList ')' [ReturnType] Block
MethodDecl     → 'method' IDENTIFIER '(' ParamList ')' [ReturnType] Block

ParamList      → ε
               | Parameter (',' Parameter)*

Parameter      → TypeKeyword ['&'] IDENTIFIER

ReturnType     → TypeKeyword

TypeKeyword    → 'variable' | 'string' | 'sequence' | 'device'
               | 'file' | 'object' | 'timer' | 'event' | 'dialog' | 'void'
```

### Variable Declaration

```
VarDecl        → TypeKeyword DeclItem (',' DeclItem)* ';'

DeclItem       → IDENTIFIER ['(' ExprList ')'] ['[' [Expr] ']'] ['=' Expr]
```

The parser supports comma-separated declarations with individual initializers:

```csharp
variable a, b(1), c("hello"), d[10], e;
// Produces 5 separate VariableDeclaration AST nodes
```

### Statements

```
Statement      → Block
               | IfStmt
               | ForStmt
               | WhileStmt
               | ReturnStmt
               | BreakStmt
               | AbortStmt
               | PauseStmt
               | OnErrorStmt
               | ResumeNextStmt
               | LabelStmt
               | SchedulerOnlyBlock
               | ExecutorOnlyBlock
               | ExpressionStmt

Block          → '{' Statement* '}'

IfStmt         → 'if' '(' Expr ')' Statement ['else' Statement]

ForStmt        → 'for' '(' [ForInit] ';' [Expr] ';' [Expr] ')' Statement
ForInit        → VarDecl | Expr

WhileStmt      → 'while' '(' Expr ')' Statement

ReturnStmt     → 'return' ['(' Expr ')'] ';'

BreakStmt      → 'break' ';'
AbortStmt      → 'abort' ';'
PauseStmt      → 'pause' ';'

OnErrorStmt    → 'onerror' 'goto' (IDENTIFIER | '0') ';'
               | 'onerror' 'resume' 'next' ';'

ResumeNextStmt → 'resume' 'next' ';'

LabelStmt      → IDENTIFIER ':'

SchedulerOnly  → 'scheduleronly' Block
ExecutorOnly   → 'executoronly' Block

ExpressionStmt → Expr ';'
```

### Expressions

```
Expr           → Assignment

Assignment     → PostfixExpr '=' Expr
               | OrExpr

OrExpr         → AndExpr ('||' AndExpr)*
AndExpr        → BitwiseOrExpr ('&&' BitwiseOrExpr)*
BitwiseOrExpr  → EqualityExpr ('|' EqualityExpr)*
EqualityExpr   → CompareExpr (('==' | '!=') CompareExpr)*
CompareExpr    → AddExpr (('<' | '<=' | '>' | '>=') AddExpr)*
AddExpr        → MulExpr (('+' | '-') MulExpr)*
MulExpr        → UnaryExpr (('*' | '/' | '%') UnaryExpr)*

UnaryExpr      → ('-' | '!' | '++' | '--') UnaryExpr
               | PostfixExpr

PostfixExpr    → PrimaryExpr (Postfix)*
Postfix        → '(' ArgList ')'           // function call
               | '[' Expr ']'              // array access
               | '.' IDENTIFIER ['(' ArgList ')']  // member/method
               | '::' IDENTIFIER           // scope resolution
               | '++'                      // post-increment
               | '--'                      // post-decrement

PrimaryExpr    → INTEGER | FLOAT | STRING
               | IDENTIFIER
               | '(' Expr ')'
```

---

## Expression Parsing

### Precedence Levels

The parser implements these precedence levels from lowest to highest:

| Level | Method | Operators | Associativity |
|-------|--------|-----------|---------------|
| 1 | `_parse_expression` | `=` | Right |
| 2 | `_parse_or_expression` | `\|\|` | Left |
| 3 | `_parse_and_expression` | `&&` | Left |
| 4 | `_parse_bitwise_or` | `\|` | Left |
| 5 | `_parse_equality` | `==` `!=` | Left |
| 6 | `_parse_comparison` | `<` `<=` `>` `>=` | Left |
| 7 | `_parse_additive` | `+` `-` | Left |
| 8 | `_parse_multiplicative` | `*` `/` `%` | Left |
| 9 | `_parse_unary` | `-` `!` `++` `--` (prefix) | Right |
| 10 | `_parse_postfix` | `()` `[]` `.` `::` `++` `--` | Left |
| 11 | `_parse_primary` | Literals, identifiers, groups | -- |

### Assignment as Expression

Assignment is parsed at the expression level, returning the assigned value. This is necessary for `for` loop initializers:

```csharp
for (i = 0; i < 10; i++)
//   ^^^^^ assignment expression, not a declaration
```

The parser detects assignment by checking if the left side is a valid l-value (identifier, array access, or member access) followed by `=`.

### Postfix Chaining

Postfix operations can be chained arbitrarily:

```csharp
obj.GetArray().SetAt(0, value);
// Parsed as: MethodCall(MemberAccess(obj, "GetArray"), "SetAt", [0, value])

namespace::function(arg).member;
// Parsed as: MemberAccess(FunctionCall(ScopedName("namespace", "function"), [arg]), "member")
```

### Scope Resolution

The `::` operator creates a `ScopedName` node:

```csharp
MyLib::DoWork(x)
// Parsed as: FunctionCall(name="MyLib::DoWork", arguments=[Identifier("x")])
```

If the scoped name is followed by `(`, it becomes a function call with the full qualified name.

---

## Statement Parsing

### If Statement

Parses `if (condition) then_branch [else else_branch]`:

```csharp
if (x > 0)
{
    Trace("positive");
}
else if (x < 0)
{
    Trace("negative");
}
else
{
    Trace("zero");
}
```

Chained `else if` is represented as nested `IfStatement` nodes in the `else_branch`.

### For Loop

Parses `for (init; condition; increment) body`:

- **Initializer**: Can be a variable declaration (`variable i(0)`) or an assignment expression (`i = 0`)
- **Condition**: Any expression; optional (empty = infinite)
- **Increment**: Any expression; optional (typically `i++`)

```csharp
for (variable i(0); i < 10; i++)    // declaration initializer
for (i = 0; i < 10; i++)            // assignment initializer
for (;;)                             // infinite loop
```

### While Loop

Parses `while (condition) body`:

```csharp
while (!done)
{
    process();
    done = checkComplete();
}
```

### Return Statement

HSL `return` uses parentheses around the return value:

```csharp
return;           // void return
return(42);       // return with value
return(a + b);    // return with expression
```

The parser handles both forms, consuming optional parentheses around the value.

### Error Handling Statements

```csharp
onerror goto ErrorHandler;   → OnErrorGoto(label="ErrorHandler")
onerror goto 0;              → OnErrorGoto(label=None)
onerror resume next;         → ResumeNext()
resume next;                 → ResumeNext()
```

### Label Detection

A label is an identifier followed by `:` at the statement level:

```csharp
ErrorHandler:
{
    // error handling code
}
```

The parser distinguishes labels from other uses of `:` (which don't exist in HSL except `::` for scope resolution).

---

## Declaration Parsing

### Variable Declarations

The parser handles complex variable declaration forms:

```csharp
// Simple
variable x;

// With initializer
variable x(42);

// String initializer
string s("hello");

// Comma-separated with mixed initializers
variable a, b(1), c("test"), d;

// Array declarations
variable arr[];        // dynamic array
variable fixed[10];    // fixed-size array

// Device with constructor arguments
device ML_STAR("layout.lay", "ML_STAR", hslTrue);

// Qualified
global variable sharedVar(0);
static variable counter(0);
```

Each comma-separated item produces a separate `VariableDeclaration` node.

### Function Declarations

```csharp
function add(variable a, variable b) variable
{
    return(a + b);
}

static function _helper(variable& ref) void
{
    ref = ref + 1;
}

method Main()
{
    // entry point
}
```

Parameters support pass-by-reference with `&`:

```csharp
function process(device& d, sequence& s, variable count)
```

### Namespace Declarations

```csharp
namespace MyLib
{
    variable version("1.0");
    
    function DoWork(variable x) variable
    {
        return(x * 2);
    }
}
```

The parser sets `current_namespace` during namespace parsing, which is used for error reporting.

---

## Error Recovery

The parser uses two error recovery strategies to continue parsing after syntax errors:

### Top-Level Recovery (`_recover`)

Used when an error occurs while parsing a top-level declaration:

```python
def _recover(self):
    """Skip tokens until we find a '}' at the top level."""
    depth = 0
    while not self._check(TokenType.EOF):
        if self._check(TokenType.LBRACE):
            depth += 1
        elif self._check(TokenType.RBRACE):
            if depth == 0:
                self._advance()  # consume the '}'
                return
            depth -= 1
        self._advance()
```

This strategy skips to the end of the current declaration block, allowing the parser to continue with the next declaration.

### Block-Level Recovery (`_recover_in_block`)

Used when an error occurs inside a function/method body:

```python
def _recover_in_block(self):
    """Skip to the next statement boundary without consuming '}'."""
    while not self._check(TokenType.EOF):
        if self._check(TokenType.RBRACE):
            return  # DON'T consume -- let the block parser handle it
        if self._check(TokenType.SEMICOLON):
            self._advance()
            return
        # Check for statement-starting keywords
        if self._peek().type in (TokenType.IF, TokenType.FOR, TokenType.WHILE, ...):
            return
        self._advance()
```

This strategy preserves the block structure by not consuming `}`, allowing the enclosing block parser to properly close.

### Error Collection

Parse errors are collected but do not halt parsing:

```python
try:
    decl = self._parse_declaration()
    declarations.append(decl)
except ParseError as e:
    self.errors.append(e)
    self._recover()
```

Typical error counts:
- Small files (< 1000 tokens): 0-5 errors
- Large Hamilton library files (100k+ tokens): 100-123 errors (mostly from unsupported constructs like `^`, `struct`, `loop`)

---

## Special Cases

### Runtime Include (`<< "file"`)

The `<<` (LSHIFT) token followed by a string literal is parsed as a runtime include:

```csharp
<< "helpers.hsl";
```

This is logged but does not produce an AST node -- the preprocessor handles actual file inclusion.

### Backslash Skipping

A standalone `\` token (common in Windows file paths within macro definitions) is consumed and skipped:

```csharp
#define PATH "C:\Hamilton\Library"
// After preprocessing, the backslash may appear as a stray token
```

### Comma-Separated Variable Declarations

HSL allows declaring multiple variables in a single statement:

```csharp
variable a, b(1), c("str"), d[];
```

The parser produces a separate `VariableDeclaration` node for each item, all sharing the same `var_type` and `qualifiers`.

### Device Constructor Arguments

Device declarations have a unique syntax with multiple constructor arguments:

```csharp
device ML_STAR("SystemLayout.lay", "ML_STAR", hslTrue);
```

These are stored in `device_args` on the `VariableDeclaration` node.

### For Loop Initializer Ambiguity

The `for` initializer can be either a declaration or an expression:

```csharp
for (variable i(0); i < 10; i++)    // declaration
for (i = 0; i < 10; i++)            // assignment expression
```

The parser checks if the first token is a type keyword to disambiguate.

---

## ParseError Details

```python
class ParseError(Exception):
    pass
```

Parse errors include the token position and a descriptive message:

```
ParseError: Expected RPAREN at line 42, column 15 in file "method.hsl", got SEMICOLON
```

Common parse errors in Hamilton library files:

| Error | Cause |
|-------|-------|
| `Unexpected token '^'` | Power operator not yet implemented |
| `Expected SEMICOLON` | Missing semicolon after statement |
| `Expected RPAREN` | Mismatched parentheses |
| `Expected IDENTIFIER` | Missing identifier after type keyword |
| `Unexpected token 'struct'` | Structure types not yet implemented |
| `Unexpected token 'loop'` | Loop construct not yet implemented |

These errors are logged as warnings and do not prevent execution of the successfully parsed portions of the program.
