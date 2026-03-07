# Hamilton .med and .stp File Format

## .med File Purpose

The `.med` file is a binary HxCfgFile v3 container that stores method step
metadata for the Hamilton Method Editor. It is a companion file to the `.hsl`
source file and contains:

- A base-64-encoded **ActivityData** flowchart blob (the graphical step layout)
- Per-step metadata sections with display text, icons, HSL source code, and
  step-type-specific parameters
- Method editor configuration (version, component flags, device declarations)
- Submethod definitions and parameters

The `.med` file is **not** the source of truth for step logic -- the `.hsl`
file is. Instead, the `.med` provides the visual metadata that the Method
Editor GUI needs to render the step list. The sync pipeline regenerates the
`.med` from the `.hsl` whenever the method is saved.

---

## .med Text Format Structure

When converted to text (via the HxCfgFile v3 codec), a `.med` file has this
structure:

```
HxCfgFile,3;

ConfigIsValid,Y;

DataDef,ActivityData,1,ActivityData,
{
ActivityDocument, "<base64 blob>"
};

DataDef,HxPars,3,<step1_guid>,
[
...step tokens...
];

DataDef,HxPars,3,<step2_guid>,
[
...step tokens...
];

DataDef,HxPars,3,HxMetEdData,
[
...editor configuration tokens...
];

DataDef,HxPars,3,HxMetEd_MainDefinition,
[
...main function definition...
];

DataDef,HxPars,3,HxMetEd_Outlining,
[
")"
];

DataDef,HxPars,3,HxMetEd_Submethods,
[
...submethod definitions...
];

* $$author=admin$$valid=0$$time=2024-01-15 09:30$$checksum=a1b2c3d4$$length=087$$
```

### Section Order

1. **Header** -- `HxCfgFile,3;` and `ConfigIsValid,Y;`
2. **ActivityData** -- Base-64 flowchart blob (named section)
3. **Step sections** -- One `DataDef,HxPars,3,<guid>` per step (sorted by GUID)
4. **HxMetEdData** -- Method Editor metadata
5. **HxMetEd_MainDefinition** -- Main function structure
6. **HxMetEd_Outlining** -- Outlining/folding state
7. **HxMetEd_Submethods** -- Submethod declarations
8. **Checksum footer** -- CRC-32 checksum line

---

## Step Section Format (`[ActivityData:StepNN]`)

Each step gets a `DataDef,HxPars,3,<instance_guid>` section. The section key
is the Hamilton underscore-format instance GUID.

### Key Fields in Step Sections

Step sections use a token-pair format where a key token (prefixed with a type
indicator) is followed by a value token:

| Field ID             | Constant               | Token Key              | Description                        |
|----------------------|------------------------|------------------------|------------------------------------|
| HSL Code             | `FIELD_HSL_CODE`       | `1-533921779`          | HSL source code of the block       |
| Display Text         | `FIELD_DISPLAY_TEXT`   | `1-533921780`          | Human-readable step summary        |
| Step Type Name       | `FIELD_STEP_TYPE_NAME` | `1-533921781`          | Step type label (e.g. "Comment")   |
| Icon                 | `FIELD_ICON`           | `1-533921782`          | Icon filename (e.g. `Comment.bmp`) |

### Step-Type-Specific Fields

Different step types include additional fields before the `BlockData` section:

| Step Type            | Extra Fields                                                     |
|----------------------|------------------------------------------------------------------|
| Comment              | `3TraceSwitch`, `1Comment`                                       |
| Assignment           | `3Expression`, `1Result`                                         |
| Loop                 | `3ComparisonOperator`, `1LeftComparisonValue`, `1LoopCounter`, `3NbrOfIterations` |
| SingleLibFunction    | `1ReturnValue`, `1FunctionName`, `3FieldCount`, `(FunctionPars …)` |
| SubmethodCall        | `1ReturnValue`, `1FunctionName`, `3FieldCount`, `(FunctionPars …)` |
| ArrayDeclare         | `1NewSize`, `1ArrayName`, `3ArrayTypeCommandKey`                 |
| ArraySetAt           | `3AddAsLastFlag`, `ValueToSet`, `1ArrayName`, `1Index`           |
| ArrayGetAt           | `1ArrayName`, `1Result`                                          |
| ArrayGetSize         | `1ArrayName`, `1Result`                                          |

### BlockData Structure

Every step section contains a `(BlockData …)` group with one sub-group per
block (most steps have 1 block; Loop has 2; If/Then/Else has 3):

```
"(BlockData"
  "(1"                   ← block index
    "1-533921780"        ← display text key
    "<Hello World>"      ← display text value
    "1-533921781"        ← step type name key
    "Comment"            ← step type name value
    "1-533921782"        ← icon key
    "Comment.bmp"        ← icon value
    "1-533921779"        ← HSL code key
    "MECC::TraceComment(Translate(\"Hello World\"));" ← code value
  ")"
")"
```

### Multi-Block Steps

| Step Type    | Blocks | Block 1         | Block 2     | Block 3    |
|--------------|--------|-----------------|-------------|------------|
| Comment      | 1      | Comment         | --           | --          |
| Assignment   | 1      | Assignment      | --           | --          |
| Loop         | 2      | Loop            | End Loop    | --          |
| IfThenElse   | 3      | If              | Else        | End If     |

### Device Step Stubs

Device steps (Initialize, Aspirate, Dispense, etc.) store their full
parameters in the `.stp` file, not in `.med`. The `.med` only contains a
minimal placeholder stub:

```
DataDef,HxPars,3,<guid>,
[
"33",
"3",           ← field count (3 for most, 6 for LoadCarrier)
"(1",
"10", "",      ← field 10 (empty)
"11", "",      ← field 11 (empty)
"12", "",      ← field 12 (empty)
")",
")"
];
```

LoadCarrier stubs additionally include fields `13`, `14`, `15` (barcode-related).

---

## Relationship: .hsl Block Markers → .med Step Sections

Each step block marker in the `.hsl` file maps to one `DataDef,HxPars,3,<guid>`
section in the `.med` file, keyed by the same instance GUID:

```
.hsl file:
  // {{ 1 1 0 "a1b2c3d4_e5f6_7890_abcdef1234567890" "{F07B0071-8EFC-11d4-A3BA-002035848439}"
  MECC::TraceComment(Translate("Hello"));
  // }} ""
                    ↓
.med file:
  DataDef,HxPars,3,a1b2c3d4_e5f6_7890_abcdef1234567890,
  [
  "3TraceSwitch", "1",
  "1Comment", "Hello",
  "3ParsCommandVersion", "1",
  "(BlockData", "(1", "1-533921780", "<Hello>", ... ")", ")",
  "1Timestamp", "2024-01-15 09:30"
  ];
```

Multi-block steps (Loop, If/Then/Else) share one GUID across all blocks in the
`.hsl` and map to a single `.med` section with multiple `BlockData` sub-groups.

---

## Sync Pipeline

The full sync pipeline converts `.hsl` source to the companion `.med` and `.stp`
binary files:

```
┌─────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  .hsl file  │────→│ parse_block_markers  │────→│  Step records    │
│  .sub file  │────→│  (both files)        │     │  (by GUID)       │
└─────────────┘     └─────────────────────┘     └────────┬─────────┘
                                                          │
                    ┌─────────────────────┐               │
                    │  build_med_text()   │←──────────────┤
                    │  build_stp_text()   │←──────────────┘
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │  text_to_binary()   │
                    │  (HxCfgFile codec)  │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │  Transactional      │
                    │  binary write       │
                    │  (tmp → bak → final)│
                    └─────────────────────┘
```

### Pipeline Steps

1. **Parse** -- Read `.hsl` and `.sub` files, extract all block markers using
   `parse_block_markers()`
2. **Group** -- Aggregate step block markers by instance GUID into
   `HslStepRecord` objects (each with ordered `HslStepBlock` entries)
3. **Cross-file numbering** -- `.hsl` rows start at 1; `.sub` rows continue
   from `lastHslRow + 1`
4. **Build text** -- Generate the `.med` text representation with all sections
5. **Convert** -- Convert text to binary using the HxCfgFile v3 codec
6. **Write** -- Transactional binary write (see below)
7. **Checksum** -- Update checksums on `.hsl`, `.sub`, `.med`, and `.stp` files

### On-Save Pipeline (`correct_block_markers_on_save`)

When a `.hsl` or `.sub` file is saved, the full on-save pipeline runs:

1. **Guard checks** -- Skip if not `.hsl`/`.sub`, no step markers (library), or
   no companion `.med`/`.smt` exists
2. **Reconcile** -- Run `reconcile_block_marker_headers()` to fix mismatches
3. **Renumber** -- Apply cross-file row numbering
4. **Sync .med** -- Regenerate the `.med` from corrected sources
5. **Sync .stp** -- Regenerate the `.stp` for device steps
6. **Checksums** -- Update CRC-32 checksums on all text companion files

---

## .stp File Purpose

The `.stp` file is a binary HxCfgFile v3 container that stores
**device-specific step parameters** -- the detailed configuration for hardware
commands like tip pickup sequences, aspirate volumes, channel patterns, etc.
Each device step in a method gets its own section in the `.stp` keyed by its
instance GUID.

While the `.med` file stores only a minimal stub for device steps, the `.stp`
file stores the full parameter set needed by the instrument driver.

---

## .stp Format

### Text Structure

```
HxCfgFile,3;

ConfigIsValid,Y;

DataDef,Method,1,Properties,
{
ReadOnly, "0"
};

DataDef,HxPars,3,<step1_guid>,
[
...device step tokens...
];

DataDef,HxPars,3,AuditTrailData,
[
")"
];

* $$author=admin$$valid=0$$time=2024-01-15 09:30$$checksum=a1b2c3d4$$length=087$$
```

### Sections Keyed by Step GUID

Each device step section (`DataDef,HxPars,3,<guid>`) contains:

| Field                  | Description                                         |
|------------------------|-----------------------------------------------------|
| `1CommandStepFileGuid` | Instance GUID (same as section key)                 |
| `3AlwaysInitialize`    | Initialize flag (Initialize step only)              |
| `1SequenceObject`      | Sequence object reference                           |
| `1SequenceName`        | Sequence name for tip/liquid operations             |
| `1ChannelPattern`      | 8-character channel enable pattern (e.g. `11111111`)|
| `3TipType`             | Tip type ID (Aspirate/Dispense only)                |
| `3UseDefaultWaste`     | Use default waste flag (TipEject only)              |
| `3NbrOfErrors`         | Number of error entries (always 4)                  |
| `(Errors …)`          | Error recovery tree                                  |
| `3SequenceCounting`    | Sequence counting mode                              |
| `3Optimizing channel use` | Channel optimization flag                        |
| `1StepName`            | Friendly step name (e.g. "Aspirate")                |
| `(-534183936 …)`      | Per-channel defaults (8 channels)                    |
| `3ParsCommandVersion`  | Parameter command version                           |
| `1Timestamp`           | Last-modified timestamp                             |

### Step-Type-Specific Fields

| Step Type       | Additional Fields                                         |
|-----------------|-----------------------------------------------------------|
| Initialize      | `AlwaysInitialize`                                        |
| TipPickUp       | `SequenceObject`, `SequenceName`, `ChannelPattern`        |
| Aspirate        | `SequenceObject`, `SequenceName`, `ChannelPattern`, `TipType` |
| Dispense        | `SequenceObject`, `SequenceName`, `ChannelPattern`, `TipType` |
| TipEject        | `SequenceObject`, `SequenceName`, `ChannelPattern`, `UseDefaultWaste` |
| LoadCarrier     | `SequenceName` (optional)                                 |
| UnloadCarrier   | `SequenceName` (optional)                                 |
| MoveAutoLoad    | (common fields only)                                      |
| GetLastLiquidLevel | (common fields only)                                   |

---

## Default Error Recovery Structure

All device steps share a standard set of **four error entries**, each with
recovery options:

### Error 3 -- Hardware Error
- **Infinite retry**: Yes
- **Recoveries**: Retry (default), Abort, Cancel

### Error 999 -- Unknown Error
- **Infinite retry**: No
- **Recoveries**: Retry, Bottom, Abort (default), Cancel

### Error 10 -- Position Not Found
- **Infinite retry**: Yes
- **Recoveries**: Retry (default), Abort, Cancel

### Error 2 -- Not Initialized
- **Infinite retry**: Yes
- **Recoveries**: Retry (default), Abort, Cancel

### Error Entry Token Structure

```
"(<error_tag>"
  "3RepeatCount",     "0"
  "3UseDefault",      "1"
  "3Timeout",         "0"
  "1ErrorSound",      ""
  "3AddRecovery",     "0"
  "3Infinite",        "<0|1>"
  "3ErrorDescription","<resource_id>"
  "3ErrorNumber",     "<error_number>"
  "(Recoveries"
    "(<recovery_id>"
      "3RecoveryVisible",    "1"
      "3RecoveryDescription","<resource_id>"
      "3RecoveryFlag",       "1"
      "3RecoveryTitle",      "<resource_id>"
      "3RecoveryDefault",    "<0|1>"
    ")"
    ...
  ")"
  "3NbrOfRecovery",   "<count>"
  "3ErrorTitle",      "<resource_id>"
")"
```

---

## Device Step Types and Default Parameters

The `DEVICE_CLSIDS` set defines the 9 ML_STAR device step types that require
`.stp` entries:

| Step Name          | Bare CLSID                                     | Channel Pattern | TipType | Special Fields |
|--------------------|-------------------------------------------------|-----------------|---------|----------------|
| Initialize         | `{1C0C0CB0-7C87-11D3-AD83-0004ACB1DCB2}`       | --               | --       | AlwaysInitialize=0 |
| LoadCarrier        | `{54114402-7FA2-11D3-AD85-0004ACB1DCB2}`       | --               | --       | SequenceName (optional) |
| UnloadCarrier      | `{54114400-7FA2-11D3-AD85-0004ACB1DCB2}`       | --               | --       | SequenceName (optional) |
| TipPickUp          | `{541143FA-7FA2-11D3-AD85-0004ACB1DCB2}`       | `11111111`      | --       | SequenceObject, SequenceName |
| Aspirate           | `{541143F5-7FA2-11D3-AD85-0004ACB1DCB2}`       | `11111111`      | 5       | SequenceObject, SequenceName |
| Dispense           | `{541143F8-7FA2-11D3-AD85-0004ACB1DCB2}`       | `11111111`      | 5       | SequenceObject, SequenceName |
| TipEject           | `{541143FC-7FA2-11D3-AD85-0004ACB1DCB2}`       | `11111111`      | --       | UseDefaultWaste=1 |
| MoveAutoLoad       | `{EA251BFB-66DE-48D1-83E5-6884B4DD8D11}`       | --               | --       | -- |
| GetLastLiquidLevel | `{9FB6DFE0-4132-4d09-B502-98C722734D4C}`       | --               | --       | -- |

Default TipType `5` = 1000µl High Volume with Filter.

Default ChannelPattern `11111111` = all 8 channels enabled.

---

## Transactional Write Strategy

Both `.med` and `.stp` files use a transactional write strategy for data safety:

```
1. Write text content → temporary file (~hxsync_<timestamp>.med)
2. Convert temp file text → binary (in-place via HxCfgFile codec)
3. Verify temp file exists after conversion
4. Backup existing target → <target>.bak
5. Copy temp → target (uses copy+delete for Windows compatibility)
6. Clean up temp and backup files
```

**Rollback on failure**: If the conversion or copy fails, the backup file is
restored to the original target path, ensuring the existing file is never lost.

---

## Existing Section Preservation

When regenerating `.stp` files, existing sections are preserved by GUID to
retain user-configured parameters:

1. Read existing `.stp` binary → convert to text → parse sections by GUID
2. For each device step GUID found in current code:
   - If a section already exists → **preserve it** (user may have configured
     custom tip types, changed channel patterns, etc.)
   - If new → **generate a default section** with minimal valid parameters
3. GUIDs not found in code are **removed** (orphan cleanup)

A belt-and-suspenders check is also performed: if the actual code inside a
block references a different instance GUID than the block marker comment, both
GUIDs receive `.stp` entries.

---

## CLI Usage

### .med Sync

```bash
# Sync .med from .hsl
python -m standalone_med_tools.med_generator sync MyMethod.hsl

# Sync with explicit output path
python -m standalone_med_tools.med_generator sync MyMethod.hsl --med MyMethod.med

# Run the full on-save pipeline
python -m standalone_med_tools.med_generator on-save MyMethod.hsl

# Build .med text to stdout (no binary conversion)
python -m standalone_med_tools.med_generator build-text MyMethod.hsl

# Sync .stp only
python -m standalone_med_tools.med_generator stp-sync MyMethod.hsl
```

### .stp Sync (standalone module)

```bash
# Sync .stp from .hsl
python -m standalone_med_tools.stp_generator sync MyMethod.hsl

# Sync with explicit output path
python -m standalone_med_tools.stp_generator sync MyMethod.hsl --stp MyMethod.stp
```

---

## Module Dependencies

```
med_generator.py ──→ block_markers.py ──→ checksum.py
                 ──→ hxcfgfile_codec.py
                 ──→ checksum.py

stp_generator.py ──→ block_markers.py ──→ checksum.py
                 ──→ hxcfgfile_codec.py
                 ──→ checksum.py
```

All modules require **Python 3.8+** with **no external dependencies**.
