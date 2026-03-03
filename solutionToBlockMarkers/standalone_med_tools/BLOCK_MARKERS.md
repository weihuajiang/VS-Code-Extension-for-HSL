# Hamilton HSL Block Markers

## Purpose

Hamilton HSL method files (`.hsl`) use structured comments called **block
markers** to associate regions of code with compound step instances in the
Method Editor GUI. Every step visible in the Hamilton Method Editor is wrapped
with an opening marker comment and a closing marker comment. Block markers
enable the Method Editor to map visual step rows to specific code regions and
to track step identity across edits.

The `block_markers.py` module provides parsing, generation, reconciliation,
and renumbering of block markers as a standalone Python library with no
external dependencies.

---

## Block Marker Types

There are **two** kinds of block markers:

### 1. Step Block Markers

Wrap code belonging to a single compound step (e.g. Comment, Assignment, Loop,
If/Then/Else, device commands).

**Opening format (double-brace):**
```
// {{ ROW COL SUBLEVEL "instance_guid" "step_clsid"
```

**Opening format (triple-brace, scope-creating):**
```
// {{{ ROW COL SUBLEVEL "instance_guid" "step_clsid"
```

**Closing format:**
```
// }} ""
```

**Fields:**

| Field           | Description                                                         |
|-----------------|---------------------------------------------------------------------|
| `ROW`           | 1-based visual position of the step in the Method Editor step list  |
| `COL`           | Column number (always `1` for single-process methods)               |
| `SUBLEVEL`      | Sub-level (`0` for most steps)                                      |
| `instance_guid` | Hamilton underscore-format GUID uniquely identifying this step instance |
| `step_clsid`    | COM CLSID identifying the step type; device steps carry a prefix like `ML_STAR:{…}` |

Multi-block steps (e.g. If/Then/Else has 3 blocks, Loop has 2 blocks) share
the same `instance_guid` across all their blocks.

### 2. Structural Block Markers

Delimit file-level sections required by the Method Editor framework that are
not individual steps.

**Opening format:**
```
// {{ LEVEL "SectionName" "Qualifier"
```

**Inline format (empty section):**
```
/* {{ LEVEL "SectionName" "Qualifier" */ // }} ""
```

**Closing format:**
```
// }} ""
```

**Common structural sections:**

| Level | Section Name                  | Qualifier   | Purpose                            |
|-------|-------------------------------|-------------|------------------------------------|
| 2     | `LibraryInsertLine`           | `""`        | Library include insertion point     |
| 2     | `VariableInsertLine`          | `""`        | Variable declaration insertion point|
| 2     | `TemplateIncludeBlock`        | `""`        | Template header includes            |
| 2     | `LocalSubmethodInclude`       | `""`        | `.sub` file include                 |
| 2     | `ProcessInsertLine`           | `""`        | Process insertion point             |
| 2     | `AutoInitBlock`               | `""`        | Auto-initialization code            |
| 2     | `AutoExitBlock`               | `""`        | Auto-exit/cleanup code              |
| 2     | `SubmethodForwardDeclaration` | `""`        | Submethod forward declarations      |
| 2     | `SubmethodInsertLine`         | `""`        | Submethod insertion point           |
| 5     | `main`                        | `"Begin"`   | `main()` function start             |
| 5     | `main`                        | `"InitLocals"` | Local variable initialization    |
| 5     | `main`                        | `"End"`     | `main()` function end               |
| 5     | `OnAbort`                     | `"Begin"`   | Abort handler start                 |
| 5     | `OnAbort`                     | `"InitLocals"` | Abort handler locals             |
| 5     | `OnAbort`                     | `"End"`     | Abort handler end                   |

---

## Triple-Brace Markers

Triple-brace `{{{` markers are used for **scope-creating / external-reference
steps** — steps that reference code from other files (submethods, library
functions) and open a new scope in the HSL interpreter.

### Triple-Brace CLSIDs

| Step Type            | CLSID                                          |
|----------------------|------------------------------------------------|
| `SingleLibFunction`  | `{C1F3C015-47B3-4514-9407-AC2E65043419}`       |
| `SubmethodCall`      | `{7C4EF7A7-39BE-406a-897F-71F3A35B4093}`       |
| `Return`             | `{9EC997CD-FD3B-4280-811B-49E99DCF062C}`       |

Example:
```
// {{{ 5 1 0 "a1b2c3d4_e5f6_7890_abcdef1234567890" "{C1F3C015-47B3-4514-9407-AC2E65043419}"
HSLUtilLib2::Util2_GetRunParameter("param1", result);
// }} ""
```

---

## Hamilton GUID Format

Hamilton uses an underscore-separated GUID format that differs from the
standard hyphenated UUID format:

| Format   | Pattern                                     | Example                                      |
|----------|---------------------------------------------|----------------------------------------------|
| Standard | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`      | `550e8400-e29b-41d4-a716-446655440000`       |
| Hamilton | `xxxxxxxx_xxxx_xxxx_xxxxxxxxxxxxxxxx`       | `550e8400_e29b_41d4_a716446655440000`        |

The Hamilton format merges the last two UUID segments (4-char + 12-char) into
a single 16-character segment: `8_4_4_16`.

Conversion functions:
- `generate_instance_guid()` — create a new random GUID in Hamilton format
- `hamilton_guid_to_standard(h_guid)` — Hamilton → standard conversion
- `standard_guid_to_hamilton(std_guid)` — standard → Hamilton conversion

---

## Complete CLSID Registry

### General Step CLSIDs (`STEP_CLSID`)

| Step Type             | CLSID                                          | Braces |
|-----------------------|------------------------------------------------|--------|
| `Comment`             | `{F07B0071-8EFC-11d4-A3BA-002035848439}`       | `{{`   |
| `Assignment`          | `{B31F3543-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `MathExpression`      | `{B31F3544-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `IfThenElse`          | `{B31F3531-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `Loop`                | `{B31F3532-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `Break`               | `{B31F3533-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `Return`              | `{9EC997CD-FD3B-4280-811B-49E99DCF062C}`       | `{{{`  |
| `Abort`               | `{930D6C31-8EFB-11d4-A3BA-002035848439}`       | `{{`   |
| `Shell`               | `{B31F3545-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `FileOpen`            | `{B31F3534-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `FileFind`            | `{B31F3535-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `FileRead`            | `{B31F3536-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `FileWrite`           | `{B31F3537-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `FileClose`           | `{B31F3538-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `UserInput`           | `{B31F3539-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `UserOutput`          | `{21E07B31-8D2E-11d4-A3B8-002035848439}`       | `{{`   |
| `SetCurrentSeqPos`    | `{B31F353A-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `GetCurrentSeqPos`    | `{B31F353B-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `SetTotalSeqCount`    | `{B31F353C-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `GetTotalSeqCount`    | `{B31F353D-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `AlignSequences`      | `{EBC6FD39-B416-4461-BD0E-312FBC5AEF1F}`       | `{{`   |
| `StartTimer`          | `{B31F353E-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `WaitTimer`           | `{B31F353F-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `ReadElapsedTime`     | `{B31F3540-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `ResetTimer`          | `{B31F3541-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `StopTimer`           | `{83FFBD43-B4F2-4ECB-BE0A-1A183AC5063D}`       | `{{`   |
| `WaitForEvent`        | `{D97BA841-8303-11d4-A3AC-002035848439}`       | `{{`   |
| `SetEvent`            | `{90ADC087-865A-4b6c-A658-A0F3AE1E29C4}`       | `{{`   |
| `LibraryFunction`     | `{B31F3542-5D80-11d4-A5EB-0050DA737D89}`       | `{{`   |
| `SingleLibFunction`   | `{C1F3C015-47B3-4514-9407-AC2E65043419}`       | `{{{`  |
| `SubmethodCall`       | `{7C4EF7A7-39BE-406a-897F-71F3A35B4093}`       | `{{{`  |
| `ComPortOpen`         | `{7AC8762F-512C-4f2c-8D1F-A86A73A6FA99}`       | `{{`   |
| `ComPortRead`         | `{6B1F17F6-3E69-4bbd-A8F2-3214BFB930AA}`       | `{{`   |
| `ComPortWrite`        | `{6193FE29-76EE-483b-AB12-EDDF6CB95FDD}`       | `{{`   |
| `ComPortClose`        | `{EB07D635-0C14-4880-8F99-4301CB1D4E3B}`       | `{{`   |
| `ArrayDeclare`        | `{4900C1F7-0FB7-4033-8253-760BDB9354DC}`       | `{{`   |
| `ArraySetAt`          | `{F17B7626-27CB-47f1-8477-8C4158339A6D}`       | `{{`   |
| `ArrayGetAt`          | `{67A8F1C9-6546-41e9-AD2F-3C54F7818853}`       | `{{`   |
| `ArrayGetSize`        | `{72EACF88-8D49-43e3-92C8-2F90E81E3260}`       | `{{`   |
| `ArrayCopy`           | `{DB5A2B39-67F2-4a78-A78F-DAF3FB056366}`       | `{{`   |
| `UserErrorHandling`   | `{3293659E-F71E-472f-AFB4-6A674E32B114}`       | `{{`   |
| `ThreadBegin`         | `{1A4D922E-531A-405b-BF19-FFD9AF850726}`       | `{{`   |
| `ThreadWaitFor`       | `{7DA7AD24-F79A-43aa-A47C-A7F0B82CCA71}`       | `{{`   |
| `SchedulerActivity`   | `{4FB3C56D-3EF5-4317-8A5B-7CDFAC1CAC8F}`       | `{{`   |
| `CustomDialog`        | `{998A7CCC-4374-484D-A6ED-E8A4F0EB71BA}`       | `{{`   |
| `GroupSeparator`      | `{586C3429-F931-405f-9938-928E22C90BFA}`       | `{{`   |

### ML_STAR Device CLSIDs (`ML_STAR_CLSID`)

Device steps carry a `ML_STAR:` prefix before the CLSID in block marker
headers:

| Step Type           | Full CLSID                                                  |
|---------------------|-------------------------------------------------------------|
| `Initialize`        | `ML_STAR:{1C0C0CB0-7C87-11D3-AD83-0004ACB1DCB2}`           |
| `LoadCarrier`       | `ML_STAR:{54114402-7FA2-11D3-AD85-0004ACB1DCB2}`           |
| `UnloadCarrier`     | `ML_STAR:{54114400-7FA2-11D3-AD85-0004ACB1DCB2}`           |
| `TipPickUp`         | `ML_STAR:{541143FA-7FA2-11D3-AD85-0004ACB1DCB2}`           |
| `Aspirate`          | `ML_STAR:{541143F5-7FA2-11D3-AD85-0004ACB1DCB2}`           |
| `Dispense`          | `ML_STAR:{541143F8-7FA2-11D3-AD85-0004ACB1DCB2}`           |
| `TipEject`          | `ML_STAR:{541143FC-7FA2-11D3-AD85-0004ACB1DCB2}`           |
| `MoveAutoLoad`      | `ML_STAR:{EA251BFB-66DE-48D1-83E5-6884B4DD8D11}`           |
| `GetLastLiquidLevel`| `ML_STAR:{9FB6DFE0-4132-4d09-B502-98C722734D4C}`           |

---

## Step Builder Functions

The module provides convenience functions for creating `MethodStep` objects:

| Function                 | Step Type            | Description                        |
|--------------------------|----------------------|------------------------------------|
| `comment_step(text)`     | Comment              | Wraps text in `MECC::TraceComment` |
| `assignment_step(var, val)` | Assignment        | `var = val;`                       |
| `for_loop_step(ctr, n, body)` | Loop (for)      | `for(ctr = 0; ctr < n;)`          |
| `while_loop_step(cond, ctr, body)` | Loop (while) | `while (condition)`             |
| `if_else_step(cond, then, else)` | IfThenElse    | `if (cond) { … } else { … }`      |
| `submethod_call_step(fn, args)` | SubmethodCall  | `fn(arg1, arg2);`                  |
| `library_function_step(ns, fn, args)` | SingleLibFunction | `ns::fn(arg1, arg2);`      |
| `abort_step()`           | Abort                | `abort;`                           |
| `break_step()`           | Break                | `break;`                           |
| `return_step()`          | Return               | `return;`                          |
| `shell_step(cmd, wait)`  | Shell                | `Shell(cmd, hslTrue/hslFalse);`    |

---

## Reconciliation Algorithm

The `reconcile_block_marker_headers()` function performs comprehensive block
marker repair. It handles all of the following cases in a single pass:

### First Pass — Per-Block Repairs

1. **Header mismatch**: Block marker comment references a different CLSID/GUID
   than the code inside → updates the comment header to match the actual code.

2. **Multiple device calls in one block**: A single block marker wraps two or
   more device step calls → splits into separate blocks, each with its own
   correctly-matched header.

3. **Empty device blocks**: A device step block with no code inside (user
   deleted the code) → removes the block marker pair entirely.

4. **Duplicate instance GUIDs**: Two blocks reference the same instance GUID →
   removes the duplicate (keeps the first occurrence).

5. **Missing close markers**: A step block's close marker (`// }} ""`) was
   deleted → adds a synthetic close marker, or removes the block if empty.

6. **Multi-statement single-statement blocks**: A single-statement step type
   (e.g. Assignment, SingleLibFunction) contains multiple executable lines →
   splits into separate blocks with appropriate CLSIDs and new GUIDs.

### Single-Statement CLSIDs

Step types that should contain exactly one executable statement per block:

`SingleLibFunction`, `Assignment`, `MathExpression`, `Abort`,
`SetCurrentSeqPos`, `GetCurrentSeqPos`, `SetTotalSeqCount`,
`GetTotalSeqCount`, `UserInput`, `UserOutput`, `ArrayDeclare`, `ArraySetAt`,
`ArrayGetAt`, `ArrayGetSize`, `ArrayCopy`, `Shell`, `Return`,
`SubmethodCall`, `Break`

### Second Pass — Orphan Code Wrapping

After the first pass, the function detects **orphaned code** — executable
lines sitting between two step blocks with no wrapping marker. These lines are
wrapped with an appropriate new block marker:

- Lines matching `Namespace::Function(…)` → `SingleLibFunction` with `{{{`
- Lines matching `abort;` → `Abort` with `{{`
- All other lines → `Assignment` with `{{`

### Important Notes

- Non-device steps and structural markers are left untouched when they don't
  need repair.
- Row numbers are **not** adjusted by reconciliation; call
  `renumber_block_markers()` afterward.
- The function returns the original string object (same reference) if no
  changes were needed, allowing efficient identity checks.

---

## Renumbering Algorithm

The `renumber_block_markers()` function renumbers all step block marker row
numbers sequentially starting from 1. It:

1. Uses a regex to find all step opening markers in order of appearance
2. Replaces each row number with a sequential counter (1, 2, 3, …)
3. Preserves all other content (code, structural markers, GUIDs, CLSIDs)

The function is safe to call on any `.hsl` content — if there are no step
markers, the content is returned unchanged.

For cross-file numbering (`.hsl` + `.sub`), the `.hsl` file is numbered
starting at row 1, and the `.sub` file continues from `lastHslRow + 1`.

---

## Validation Rules

### Block Marker Detection

- `has_step_block_markers(content)` — quick-check guard that returns `True` if
  the file contains at least one step block marker. Used to distinguish method
  files from library files (library files never have step markers).

### Regex Patterns

| Pattern                 | Purpose                                      |
|-------------------------|----------------------------------------------|
| `RE_STEP_MARKER`        | Quick detection of any step marker            |
| `RE_STEP_OPEN`          | Parse opening step marker fields              |
| `RE_STRUCTURAL_OPEN`    | Parse opening structural marker fields        |
| `RE_INLINE_STRUCTURAL`  | Parse single-line inline structural markers   |
| `RE_CLOSE`              | Match closing marker `// }} ""`               |
| `RE_CHECKSUM`           | Parse checksum footer fields                  |
| `RE_DEVICE_STEP_CALL`   | Extract device function calls from HSL code   |
| `RE_NAMESPACE_CALL`     | Detect `Namespace::Function(` patterns        |
| `RE_ABORT`              | Detect `abort;` statements                    |

### Device Call Extraction

Device step function calls in HSL code follow this pattern:

```
ML_STAR._541143FC_7FA2_11D3_AD85_0004ACB1DCB2("122ed496_fe1b_4df4_aee6e5fe2130e41b")
```

The `extract_device_call_from_code()` function captures:
- Device name (`ML_STAR`)
- Function CLSID in underscore form → converted to standard `{CLSID}` format
- Instance GUID argument

---

## Checksum Footer

Every Hamilton file ends with a checksum footer line:

```
// $$author=<name>$$valid=<0|1>$$time=<YYYY-MM-DD HH:MM>$$checksum=<8hex>$$length=<NNN>$$
```

The CRC-32 is computed over all preceding content plus the prefix through
`checksum=`. See the [CODEC_REFERENCE.md](CODEC_REFERENCE.md) for full
checksum algorithm details.

---

## CLI Usage

```bash
# Display the full CLSID registry
python -m standalone_med_tools.block_markers --show-clsids

# Generate a complex demo method
python -m standalone_med_tools.block_markers --demo-complex

# Generate a method with N comment steps
python -m standalone_med_tools.block_markers --steps 5

# Run block marker reconciliation on a file
python -m standalone_med_tools.block_markers --reconcile MyMethod.hsl
```
