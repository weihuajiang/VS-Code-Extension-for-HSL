# Hamilton HSL — Pipetting Step Reference

This VS Code extension supports Hamilton Standard Language (HSL) files for Hamilton liquid-handling robots. This document explains how pipetting steps are encoded in HSL code and companion `.stp` files so that an LLM can interpret, validate, and explain them.

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
| `-534183918` | float | **Pressure LLD Sensing** | — |
| `-534183933` | int | **cLLD Sensitivity** | — |
| `-534183622` | float | **Retract Distance from Surface** | mm |
| `-534183629` | float | **Side Touch** (0 = off) | — |
| `-534183926` | float | **Retract Speed** | — |
| `-534183920` | int | **Swap Speed** | — |
| `-534183700` | float | **pLLD Sensitivity** | — |
| `-534183876` | int | **Channel Enable** (1 = enabled) | bool |
| `-534183813` | int | **Touch Off Distance** | — |
| `-534183909` | int | **Dispense Position Above Z-Start** | — |

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

The **Initialize** step (`ML_STAR._1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2("guid")`) **must** be called inside `method main()` before **any** other instrument commands that use the device object (typically `ML_STAR`). This includes — but is not limited to — all pipetting steps (Aspirate, Dispense, TipPickUp, TipEject), carrier movements (LoadCarrier, UnloadCarrier, MoveAutoLoad), and CO-RE 96 head operations (Head96Aspirate, Head96Dispense, Head96TipPickUp, Head96TipEject).

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

1. **Missing Initialize step**: If `method main()` uses any `ML_STAR._<CLSID>(...)` call without a preceding Initialize step (`ML_STAR._1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2`), the program will fail at runtime. This is a critical error.
2. **Volume out of range**: Aspirate/dispense volumes should be within the tip type's capacity (e.g., 0-1000 µL for 1000 µL tips, 0-5000 µL for 5 mL tips).
2. **Mix volume vs aspirate volume**: Mix volume should generally be ≤ the tip capacity and appropriate for the vessel.
3. **Mix cycles = 0 with non-zero mix volume**: Likely an error — mix won't execute without cycles.
4. **LLD off with submerge depth**: If LLD is off, the submerge depth is relative to container bottom, not liquid surface. Verify this is intentional.
5. **Empty liquid class on aspirate**: Aspirate steps should always have a liquid class specified.
6. **Dispense volume ≠ aspirate volume**: Unless performing partial dispenses, these should usually match within a pipetting cycle.
7. **Sequence counting mismatch**: If a sequence is set to "Manually" but inside a loop without manual position management, positions won't advance.
8. **Liquid following without LLD**: Liquid following requires LLD to detect the surface; having it on without LLD is unusual though not always wrong.

---

## HSL Language Rules (Critical for Code Generation)

The following rules **must** be followed when generating or modifying HSL code. Violating any of these causes compile errors in the VENUS syntax checker.

### Type System — `variable` vs `string`

HSL has distinct types: `variable`, `string`, `sequence`, `device`, `object`, `timer`, `event`, `file`, `resource`, `dialog`.

**`string` member functions** (`.GetLength()`, `.Find()`, `.Left()`, `.Mid()`, `.Right()`, `.Compare()`, `.MakeUpper()`, `.MakeLower()`, `.SpanExcluding()`) are available **only** on the `string` type. Calling them on a `variable` produces **VENUS error 1317**.

**`variable`** is a generic type that can hold numbers or text, but it does **not** have string member functions.

#### Rule: When you need string member functions, use `string` type

```hsl
// WRONG — causes error 1317 on every member function call
variable strInput;
variable intLen;
intLen = strInput.GetLength();       // ERROR: GetLength is not a member of variable

// CORRECT — use string type
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
| `GetLength` | `str.GetLength()` | integer — length of string |
| `Find` | `str.Find(searchStr)` | integer — index of first occurrence, or -1 |
| `Left` | `str.Left(count)` | string — leftmost `count` characters |
| `Mid` | `str.Mid(start, count)` | string — substring from `start` for `count` chars |
| `Right` | `str.Right(count)` | string — rightmost `count` characters |
| `Compare` | `str.Compare(other)` | integer — <0, 0, or >0 (lexicographic) |
| `MakeUpper` | `str.MakeUpper()` | void — converts to uppercase in place |
| `MakeLower` | `str.MakeLower()` | void — converts to lowercase in place |
| `SpanExcluding` | `str.SpanExcluding(charSet)` | string — prefix before any character in charSet |

### Sequence Member Functions

**`sequence.GetPositionId()`** takes **zero** arguments (VENUS error 1315 if called with arguments). You must first call `sequence.SetCurrentPosition(index)` to set the position, then call `GetPositionId()`:

```hsl
// WRONG — GetPositionId takes 0 arguments
strId = mySeq.GetPositionId(intIndex);     // ERROR 1315

// CORRECT — SetCurrentPosition first, then GetPositionId
mySeq.SetCurrentPosition(intIndex);
strId = mySeq.GetPositionId();
```

**`sequence.Add(labwareId, positionId)`** — the first argument is the **labware ID**, the second is the **position ID**:

```hsl
// WRONG — arguments are swapped
mySeq.Add("A1", "");           // puts "A1" as labwareId, "" as positionId

// CORRECT
mySeq.Add("", "A1");           // "" as labwareId, "A1" as positionId
```

### Function Visibility — `private` Scope

**`private` functions can only be called from within the same file** (VENUS error 1343). If a helper file needs to call a function defined in another file, that function must **not** be `private`.

```hsl
// In LibraryA.hsl
namespace LibA
{
   private function _InternalOnly() void;    // only callable within LibraryA.hsl
   function SharedHelper() void;             // callable from any file that includes LibraryA.hsl
}

// In LibraryB.hsl — after #include "LibraryA.hsl"
LibA::_InternalOnly();     // ERROR 1343 — private function
LibA::SharedHelper();      // OK
```

Use the underscore prefix (`_FunctionName`) as a naming convention for internal functions, but only mark them `private` if they are truly file-local.

### No Anonymous Blocks Inside Functions

HSL does **not** support C-style anonymous blocks (`{ ... }`) with local variable declarations inside functions. All variable declarations must be at the **top** of the function/method body, before any executable code.

```hsl
// WRONG — anonymous block with local declarations
method main()
{
   variable x;
   x = 5;
   {
      variable y;       // ERROR — HSL does not support block-scoped declarations
      y = x + 1;
   }
}

// CORRECT — all declarations at the top
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
// WRONG — declaration after executable code
function Example() void
{
   variable x;
   x = 5;
   variable y;          // ERROR — declaration after executable statement
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
// AVOID — multiple assignments on one line (may cause parser issues)
arrRows[0] = "A"; arrRows[1] = "B"; arrRows[2] = "C";

// PREFERRED — one per line
arrRows[0] = "A";
arrRows[1] = "B";
arrRows[2] = "C";
```

### No `continue` Keyword

HSL does **not** support the `continue` keyword in loops. Use conditional logic instead:

```hsl
// WRONG
while(i < 10)
{
   i = i + 1;
   if(i == 5) continue;    // ERROR — 'continue' not supported
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

// Definition — must match exactly
function MyFunc(variable i_param) variable
{
   return(i_param + 1);
}
```
