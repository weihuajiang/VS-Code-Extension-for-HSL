# Hamilton HSL -- Pipetting Step Reference

This VS Code extension supports Hamilton Standard Language (HSL) files for Hamilton liquid-handling robots. This document explains how pipetting steps are encoded in HSL code and companion `.stp` files so that an LLM can interpret, validate, and explain them.

---

## ABSOLUTE RULE: No Em Dashes or En Dashes (Zero Tolerance)

**NEVER** use em dashes (`U+2014` --) or en dashes (`U+2013` --) in **any** file touched by this extension or workspace. This applies to **every** file type: `.hsl`, `.sub`, `.stp`, `.med`, `.json`, `.ts`, `.js`, `.md`, `.py`, `.ps1`, `.csv`, `.txt`, or any other format. No exceptions.

- Use **two hyphens** (`--`) where you would use an em dash.
- Use a **single hyphen** (`-`) where you would use an en dash.
- This rule applies to code, comments, strings, documentation, commit messages, and any generated or modified text.

HSL and the VENUS toolchain do **not** handle Unicode dashes correctly. Inserting an em dash or en dash into any file can cause silent corruption, compile failures, or runtime errors. **There is no valid use case for these characters in this workspace.**

More broadly, **all non-ASCII characters** (smart quotes, arrows, non-breaking spaces, accented letters, etc.) should be avoided in `.hsl`, `.sub`, and related files. The VENUS compiler is a Win32 application that reads source files as ANSI/Windows-1252. UTF-8 multi-byte sequences (e.g., em dash U+2014 = bytes `E2 80 94`) are misinterpreted: byte `0x94` becomes a right double quotation mark in Windows-1252, corrupting the parser state and producing cascading syntax errors far from the actual offending character.

The VS Code extension enforces this rule with diagnostic code `non-ascii-character`. Any character outside printable ASCII (`0x20`-`0x7E`), tab, carriage return, or line feed is flagged as an error -- even inside comments and strings, because VENUS processes the raw bytes before parsing.

---

## How Pipetting Steps Appear in HSL Code

Device steps appear as function calls on a device object (typically `ML_STAR`). The format is:

```
ML_STAR._<CLSID>("stepInstanceGuid"); // StepName
```

- **CLSID**: A COM class identifier (underscore-formatted GUID) that identifies the **step type** (e.g., Aspirate, Dispense).
- **stepInstanceGuid**: A unique instance identifier that maps to the step's parameters stored in the companion `.stp` file.

The HSL code itself does **not** contain the pipetting parameters (volume, liquid class, LLD settings, etc.). All parameters are stored in the binary `.stp` file, keyed by the `stepInstanceGuid`.

### Step Type CLSIDs

| CLSID (underscore format) | Step Type |
|---|---|
| `1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2` | Initialize |
| `541143F5_7FA2_11D3_AD85_0004ACB1DCB2` | Aspirate (single channel) |
| `541143F8_7FA2_11D3_AD85_0004ACB1DCB2` | Dispense (single channel) |
| `541143FA_7FA2_11D3_AD85_0004ACB1DCB2` | TipPickUp (single channel) |
| `541143FC_7FA2_11D3_AD85_0004ACB1DCB2` | TipEject (single channel) |
| `54114400_7FA2_11D3_AD85_0004ACB1DCB2` | UnloadCarrier |
| `54114402_7FA2_11D3_AD85_0004ACB1DCB2` | LoadCarrier |
| `827392A0_B7E8_4472_9ED3_B45B71B5D27A` | Head96Aspirate (CO-RE 96) |
| `A48573A5_62ED_4951_9EF9_03207EFE34FB` | Head96Dispense (CO-RE 96) |
| `BD0D210B_0816_4C86_A903_D6B2DF73F78B` | Head96TipPickUp (CO-RE 96) |
| `2880E77A_3D6D_40FE_AF57_1BD1FE13960C` | Head96TipEject (CO-RE 96) |
| `EA251BFB_66DE_48D1_83E5_6884B4DD8D11` | MoveAutoLoad |

---

## .stp File Structure

The `.stp` file is a binary HxCfgFile v3 container. Each step instance has a section keyed by its GUID containing token pairs (key, value). Parameters fall into two categories:

### Named String/Integer Fields

| Key | Type | Description |
|---|---|---|
| `1StepName` | string | Step type name (e.g., "Aspirate", "Head96Aspirate") |
| `1SequenceObject` | string | Target sequence (e.g., "ML_STAR.Cells") |
| `1SequenceName` | string | Sequence name (usually same as SequenceObject) |
| `1LiquidName` | string | Liquid class name. Empty on dispense means "same as aspirate" |
| `1ChannelPattern` | string | Channel enable mask (e.g., "11111111" for 8 channels) |
| `3SequenceCounting` | int | 0 = Manually, 1 = Automatic |
| `3LiquidFollowing` | int | 0 = Off, 1 = On (pipette tip follows liquid surface) |
| `3TipType` | int | Tip type identifier |
| `3DispenseMode` | int | 3 = Jet, 4 = Surface Empty, 5 = Drain Tip |
| `3UsePickUpPosition` | int | TipEject: 0 = Default, 1 = Pick-up position, 2 = Default waste |
| `3SameLiquid` | int | 1 = Use same liquid class as aspirate |

### Numeric Field IDs (inside parameter groups)

These fields are in a parenthesized group: `(-534183935 ...)` for CO-RE 96 head steps, or `(-534183936 ...)` for single-channel steps (repeated per channel).

| Field ID | Type | Parameter | Unit |
|---|---|---|---|
| `-534183924` | float | **Aspirate Volume** | µL |
| `-534183908` | float | **Dispense Volume** | µL |
| `-534183915` | float | **Mix Volume** | µL |
| `-534183914` | int | **Mix Cycles** | count |
| `-534183925` | float | **Mix Position from Liquid Surface** | mm |
| `-534183913` | float | **Submerge Depth** (position relative to liquid surface) | mm |
| `-534183919` | int | **LLD Mode**: 0 = Off, 1 = pLLD (Pressure), 5 = Capacitive | enum |
| `-534183928` | float | **LLD Sensitivity** | 1-5 scale |
| `-534183918` | float | **Pressure LLD Sensing** | -- |
| `-534183933` | int | **cLLD Sensitivity** | -- |
| `-534183622` | float | **Retract Distance from Surface** | mm |
| `-534183629` | float | **Side Touch** (0 = off) | -- |
| `-534183926` | float | **Retract Speed** | -- |
| `-534183920` | int | **Swap Speed** | -- |
| `-534183700` | float | **pLLD Sensitivity** | -- |
| `-534183876` | int | **Channel Enable** (1 = enabled) | bool |
| `-534183813` | int | **Touch Off Distance** | -- |
| `-534183909` | int | **Dispense Position Above Z-Start** | -- |

---

## How to Interpret a Pipetting Step

When you see a line like:
```hsl
arrRetValues = ML_STAR._827392A0_B7E8_4472_9ED3_B45B71B5D27A("89a59053_b35c_4f52_8b2411eb1cf98914"); // Head96Aspirate
```

1. **Identify the step type** from the CLSID: `827392A0...` = `Head96Aspirate`
2. **Look up the instance GUID** `89a59053...` in the `.stp` file
3. **Read the parameters**: sequence, liquid class, volume, mix settings, LLD mode, etc.

### Example Decoded Step

For the step above, the `.stp` file contains:
- **Sequence:** ML_STAR.Cells (counting: Manually)
- **Liquid Class:** HighVolumeFilter_96COREHead1000ul_Water_DispenseSurface_Empty
- **Aspirate Volume:** 150 µL
- **Mix:** 150 µL × 4 cycles
- **Submerge Depth:** 2 mm
- **LLD:** Capacitive, Sensitivity: 5
- **Liquid Following:** On

---

## Initialize Step Requirement (Critical)

The **Initialize** step (`ML_STAR._1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2("guid")`) **must** be called inside `method main()` before **any** other instrument commands that use the device object (typically `ML_STAR`). This includes -- but is not limited to -- all pipetting steps (Aspirate, Dispense, TipPickUp, TipEject), carrier movements (LoadCarrier, UnloadCarrier, MoveAutoLoad), and CO-RE 96 head operations (Head96Aspirate, Head96Dispense, Head96TipPickUp, Head96TipEject).

Without the Initialize step the instrument hardware is **not** initialised. Every subsequent device command will fail at runtime.

### Rules

1. **One Initialize per `method main()`**: Place the Initialize call early in `method main()`, before any `ML_STAR._*` call.
2. **Not needed in library functions**: Functions and sub-methods receive an already-initialised `device &` reference; they must not call Initialize again.
3. **Omitting Initialize is a critical syntax error**: The VS Code extension flags the first `ML_STAR` device call that appears before (or without) an Initialize step as an error.
4. **The Hamilton Method Editor adds this automatically** when you graphically insert an "Initialize" step, but hand-written HSL must include it explicitly.

### Example

```hsl
method main()
{
    // Initialize MUST come first
    ML_STAR._1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2("62b7b0ef_8e71_4cd4_8763df32a80db666"); // Initialize

    // Now device commands are safe
    ML_STAR._541143FA_7FA2_11D3_AD85_0004ACB1DCB2("..."); // TipPickUp
    ML_STAR._541143F5_7FA2_11D3_AD85_0004ACB1DCB2("..."); // Aspirate
    ML_STAR._541143F8_7FA2_11D3_AD85_0004ACB1DCB2("..."); // Dispense
    ML_STAR._541143FC_7FA2_11D3_AD85_0004ACB1DCB2("..."); // TipEject
}
```

---

## Common Validation Checks

When reviewing pipetting steps, check for these potential issues:

1. **Non-ASCII characters in source files**: Any character outside printable ASCII (em dashes, en dashes, smart quotes, arrows, non-breaking spaces, etc.) will cause the VENUS compiler to misinterpret the file. The extension flags these with diagnostic code `non-ascii-character`. Replace em dashes with `--`, en dashes with `-`, smart quotes with straight quotes, and remove or replace any other non-ASCII characters.
2. **Missing Initialize step**: If `method main()` uses any `ML_STAR._<CLSID>(...)` call without a preceding Initialize step (`ML_STAR._1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2`), the program will fail at runtime. This is a critical error.
2. **Volume out of range**: Aspirate/dispense volumes should be within the tip type's capacity (e.g., 0-1000 µL for 1000 µL tips, 0-5000 µL for 5 mL tips).
2. **Mix volume vs aspirate volume**: Mix volume should generally be ≤ the tip capacity and appropriate for the vessel.
3. **Mix cycles = 0 with non-zero mix volume**: Likely an error -- mix won't execute without cycles.
4. **LLD off with submerge depth**: If LLD is off, the submerge depth is relative to container bottom, not liquid surface. Verify this is intentional.
5. **Empty liquid class on aspirate**: Aspirate steps should always have a liquid class specified.
6. **Dispense volume ≠ aspirate volume**: Unless performing partial dispenses, these should usually match within a pipetting cycle.
7. **Sequence counting mismatch**: If a sequence is set to "Manually" but inside a loop without manual position management, positions won't advance.
8. **Liquid following without LLD**: Liquid following requires LLD to detect the surface; having it on without LLD is unusual though not always wrong.

---

## HSL Language Rules (Critical for Code Generation)

The following rules **must** be followed when generating or modifying HSL code. Violating any of these causes compile errors in the VENUS syntax checker.

### Type System -- `variable` vs `string`

HSL has distinct types: `variable`, `string`, `sequence`, `device`, `object`, `timer`, `event`, `file`, `resource`, `dialog`.

**`string` member functions** (`.GetLength()`, `.Find()`, `.Left()`, `.Mid()`, `.Right()`, `.Compare()`, `.MakeUpper()`, `.MakeLower()`, `.SpanExcluding()`) are available **only** on the `string` type. Calling them on a `variable` produces **VENUS error 1317**.

**`variable`** is a generic type that can hold numbers or text, but it does **not** have string member functions.

#### Rule: When you need string member functions, use `string` type

```hsl
// WRONG -- causes error 1317 on every member function call
variable strInput;
variable intLen;
intLen = strInput.GetLength();       // ERROR: GetLength is not a member of variable

// CORRECT -- use string type
string strInput;
variable intLen;
intLen = strInput.GetLength();       // OK: GetLength is a member of string
```

#### Rule: Converting `variable` to `string` for member function use

When a function receives a `variable` parameter but needs to use string member functions internally, declare a local `string` variable and assign:

```hsl
function MyFunction(variable i_strInput) void
{
   string strLocal;
   variable intLen;

   strLocal = i_strInput;                // assign variable to string
   intLen = strLocal.GetLength();        // now member functions work
}
```

This avoids changing the function's public signature while enabling string operations internally.

#### String member functions reference

| Method | Signature | Returns |
|---|---|---|
| `GetLength` | `str.GetLength()` | integer -- length of string |
| `Find` | `str.Find(searchStr)` | integer -- index of first occurrence, or -1 |
| `Left` | `str.Left(count)` | string -- leftmost `count` characters |
| `Mid` | `str.Mid(start, count)` | string -- substring from `start` for `count` chars |
| `Right` | `str.Right(count)` | string -- rightmost `count` characters |
| `Compare` | `str.Compare(other)` | integer -- <0, 0, or >0 (lexicographic) |
| `MakeUpper` | `str.MakeUpper()` | void -- converts to uppercase in place |
| `MakeLower` | `str.MakeLower()` | void -- converts to lowercase in place |
| `SpanExcluding` | `str.SpanExcluding(charSet)` | string -- prefix before any character in charSet |

### Sequence Member Functions

**`sequence.GetPositionId()`** takes **zero** arguments (VENUS error 1315 if called with arguments). You must first call `sequence.SetCurrentPosition(index)` to set the position, then call `GetPositionId()`:

```hsl
// WRONG -- GetPositionId takes 0 arguments
strId = mySeq.GetPositionId(intIndex);     // ERROR 1315

// CORRECT -- SetCurrentPosition first, then GetPositionId
mySeq.SetCurrentPosition(intIndex);
strId = mySeq.GetPositionId();
```

**`sequence.Add(labwareId, positionId)`** -- the first argument is the **labware ID**, the second is the **position ID**:

```hsl
// WRONG -- arguments are swapped
mySeq.Add("A1", "");           // puts "A1" as labwareId, "" as positionId

// CORRECT
mySeq.Add("", "A1");           // "" as labwareId, "A1" as positionId
```

### Function Visibility -- `private` Scope

**`private` functions can only be called from within the same file** (VENUS error 1343). If a helper file needs to call a function defined in another file, that function must **not** be `private`.

```hsl
// In LibraryA.hsl
namespace LibA
{
   private function _InternalOnly() void;    // only callable within LibraryA.hsl
   function SharedHelper() void;             // callable from any file that includes LibraryA.hsl
}

// In LibraryB.hsl -- after #include "LibraryA.hsl"
LibA::_InternalOnly();     // ERROR 1343 -- private function
LibA::SharedHelper();      // OK
```

Use the underscore prefix (`_FunctionName`) as a naming convention for internal functions, but only mark them `private` if they are truly file-local.

### No Anonymous Blocks Inside Functions

HSL does **not** support C-style anonymous blocks (`{ ... }`) with local variable declarations inside functions. All variable declarations must be at the **top** of the function/method body, before any executable code.

```hsl
// WRONG -- anonymous block with local declarations
method main()
{
   variable x;
   x = 5;
   {
      variable y;       // ERROR -- HSL does not support block-scoped declarations
      y = x + 1;
   }
}

// CORRECT -- all declarations at the top
method main()
{
   variable x;
   variable y;

   x = 5;
   y = x + 1;
}
```

### Variable Declarations Must Be at Top of Scope

All `variable`, `string`, `sequence`, `object`, and other type declarations must appear at the **beginning** of their enclosing scope (function, method, or namespace), before any executable statements. Interleaving declarations with code is a syntax error.

```hsl
// WRONG -- declaration after executable code
function Example() void
{
   variable x;
   x = 5;
   variable y;          // ERROR -- declaration after executable statement
   y = 10;
}

// CORRECT
function Example() void
{
   variable x;
   variable y;

   x = 5;
   y = 10;
}
```

### Array Element Assignment

Array element assignment using bracket notation (`arr[index] = value`) is valid HSL syntax. However, place **one assignment per line** for parser compatibility:

```hsl
// AVOID -- multiple assignments on one line (may cause parser issues)
arrRows[0] = "A"; arrRows[1] = "B"; arrRows[2] = "C";

// PREFERRED -- one per line
arrRows[0] = "A";
arrRows[1] = "B";
arrRows[2] = "C";
```

### No Array Element Access in `+` Expressions

The VENUS parser **cannot** handle array element access (`arr[index]`) used directly as an operand in a `+` expression (concatenation or addition). The bracket notation confuses the parser and produces cascading "syntax error before ';'" errors (error 1002) followed by "unexpected end of file" (error 1311).

**Always** assign the array element to a temporary variable first, then use that variable in the expression.

The VS Code extension flags this with diagnostic code `array-element-in-expression`.

```hsl
// WRONG -- causes cascading syntax errors
strResult = strResult + arrPositions[intIdx];       // ERROR 1002
strResult = strResult + "," + arrData[i];            // ERROR 1002

// CORRECT -- extract to a temporary variable first
strPos = arrPositions[intIdx];
strResult = strResult + strPos;

strItem = arrData[i];
strResult = strResult + "," + strItem;
```

This restriction applies to **all** uses of `arr[index]` as an operand of `+`, including both left and right sides. The assignment `arr[index] = value` itself is fine -- only the use inside `+` expressions is prohibited.

### No `continue` Keyword

HSL does **not** support the `continue` keyword in loops. Use conditional logic instead:

```hsl
// WRONG
while(i < 10)
{
   i = i + 1;
   if(i == 5) continue;    // ERROR -- 'continue' not supported
   Trace(IStr(i));
}

// CORRECT
while(i < 10)
{
   i = i + 1;
   if(i != 5)
   {
      Trace(IStr(i));
   }
}
```

### No Compound Assignment Operators

HSL does **not** support `+=`, `-=`, `*=`, `/=`. Use explicit assignment:

```hsl
// WRONG
x += 5;          // ERROR

// CORRECT
x = x + 5;
```

### Function Declaration and Definition Pairing

Every function must have both a forward **declaration** (prototype ending with `;`) and a **definition** (implementation with `{ ... }`). The signatures must match exactly (modifiers, name, parameter types, return type).

```hsl
// Forward declaration
function MyFunc(variable i_param) variable;

// Definition -- must match exactly
function MyFunc(variable i_param) variable
{
   return(i_param + 1);
}
```

---

## HSL Debugger -- Simulation Runtime

This workspace includes a **Python-based HSL simulation runtime** at `HSL Debugger/hsl_runtime/`. It preprocesses, tokenizes, parses, and interprets HSL source code entirely in Python -- no Hamilton hardware or VENUS installation is required at runtime (only the Hamilton library `.hsl`/`.sub` files are needed for `#include` resolution).

**Use this debugger to run, test, and validate HSL method files.** When you write or modify HSL code and need to verify it works, run it through this debugger rather than guessing.

### Purpose and Scope

The HSL Debugger is **exclusively for executing and testing HSL method files** -- files that contain a `method main()` entry point. It is not a general HSL compiler or library validator.

**Critical limitation:** The debugger **will fail** if you try to run a library file (`.hsl` or `.sub`) that does not contain a `method main()`. Library files define functions and namespaces but have no entry point. The interpreter will emit `"No main() method found"` and only process top-level declarations without executing any logic. To test a library, you must create or use a method file that `#include`s the library and calls its functions from `method main()`.

### How to Run

```powershell
cd "HSL Debugger"
python -m hsl_runtime.main "<path-to-method.hsl>" --hamilton-dir "C:\Program Files (x86)\Hamilton"
```

### Command-Line Options

| Flag | Description |
|------|-------------|
| `--verbose` | Show detailed trace output (default) |
| `--quiet` | Suppress trace output |
| `--dump-tokens` | Print token stream and exit |
| `--dump-ast` | Print abstract syntax tree and exit |
| `--dump-preprocessed` | Print preprocessed source and exit |
| `--max-iterations N` | Safety limit for loops (default: 100,000) |
| `--hamilton-dir PATH` | Hamilton installation directory (default: `C:\Program Files (x86)\Hamilton`) |
| `--log-dir PATH` | Directory for `.trc` trace log output (default: `<hamilton-dir>/Logfiles/vscode`) |

### What the Debugger Does

1. **Preprocesses** the HSL file -- resolves `#include` directives, `#define` macros, and conditional compilation (`#ifdef`/`#ifndef`).
2. **Tokenizes** the preprocessed source into an HSL token stream.
3. **Parses** tokens into an abstract syntax tree (AST).
4. **Executes** the AST in simulation mode:
   - All HSL control flow (if/else, while, for, return, abort) executes for real.
   - All variable assignments, string operations, array operations, and sequence operations execute for real.
   - Device steps (`ML_STAR._<CLSID>(...)`) are recognized but return simulated success -- no firmware commands are generated. This is the same approach Hamilton's own `HxRun.exe` uses in simulation mode: a virtual device that always returns OK.
   - COM objects (e.g., `BarcodedTipTracking.Engine`) are simulated with pure-Python implementations.
   - `Trace()` and `FormatTrace()` output is captured and written to a `.trc` file in Hamilton's trace log format.

### What the Debugger Does NOT Do

- **No deck layout loading** -- `.lay` files are not parsed; labware positions are not validated.
- **No `.stp` file reading** -- pipetting parameters (volumes, LLD, liquid classes) are not decoded.
- **No firmware emulation** -- device steps are stubs that return success, not a physics simulation.
- **No library-only execution** -- the file **must** have `method main()` or execution will not occur.

### Interpreting Output

- **Exit code 0** = success. The method's `main()` ran to completion.
- **Exit code 1** = failure. Check the terminal output for the phase that failed (Preprocessor, Lexer, Parser, or Runtime).
- **Trace log** = written to `<hamilton-dir>/Logfiles/vscode/<MethodName>_<RunId>_Trace.trc` in standard Hamilton `.trc` format.
- **`[HSL TRACE]` lines** in terminal output show every `Trace()` call from the method.

### Example: Testing a Library

If you have a library `MyLib.hsl` with helper functions, you cannot run it directly. Create a test method:

```hsl
#include "MyLib.hsl"

method main()
{
   variable result;
   // Call library functions and verify results
   result = MyLib::SomeFunction("test input");
   Trace("Result: ");
   Trace(result);
}
```

Then run:
```powershell
python -m hsl_runtime.main "TestMyLib.hsl"
```
