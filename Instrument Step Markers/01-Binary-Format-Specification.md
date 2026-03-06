# 01 — Binary Format Specification

This document describes the byte-level binary format of Hamilton `.stp` files — `HxCfgFile v3` containers that store device step parameters for liquid-handling methods.

---

## File Identity

| Property | Value |
|----------|-------|
| **Format name** | HxCfgFile v3 |
| **Used for** | `.stp`, `.med`, `.lay` files |
| **Byte order** | Little-endian |
| **String encoding** | Latin-1 (ISO 8859-1) |
| **Default form** | Binary (text form exists for debugging) |

The same HxCfgFile v3 container format is shared across `.stp`, `.med`, and `.lay` files. The difference is the semantic content inside. This document focuses on the `.stp` usage.

---

## Top-Level Structure

```
┌─────────────────────────────────────────┐
│ u16   Version (always 3)                │
│ u16   Section type                      │
│ u32   Named section count (N)           │
├─────────────────────────────────────────┤
│ Named Section 0                         │
│ Named Section 1                         │
│ ...                                     │
│ Named Section N-1                       │
├─────────────────────────────────────────┤
│ u8    HxPars section count (H)          │
│ u8[3] Padding (zero bytes)              │
├─────────────────────────────────────────┤
│ HxPars Section 0                        │
│ HxPars Section 1                        │
│ ...                                     │
│ HxPars Section H-1                      │
├─────────────────────────────────────────┤
│ Footer (checksum)                       │
└─────────────────────────────────────────┘
```

---

## String Primitives

Two string encoding formats are used throughout the binary file:

### Short String

Used for section names and field keys. The length is constrained to fit in a single byte.

```
┌──────────┬──────────────────┐
│ u8 len   │ bytes[len]       │
│ (0–255)  │ (Latin-1 text)   │
└──────────┴──────────────────┘
```

### Variable-Length String (VarString)

Used for field values and HxPars tokens. Supports both short (≤254 byte) and long (≥255 byte) payloads.

```
Short form (marker ≠ 0xFF):
┌──────────┬──────────────────┐
│ u8 len   │ bytes[len]       │
│ (0–254)  │ (Latin-1 text)   │
└──────────┴──────────────────┘

Long form (marker = 0xFF):
┌──────────┬────────────┬──────────────────┐
│ u8 0xFF  │ u16 len    │ bytes[len]       │
│          │ (LE)       │ (Latin-1 text)   │
└──────────┴────────────┴──────────────────┘
```

When the first byte is `0xFF`, the next two bytes are a little-endian u16 giving the actual string length. This allows strings up to 65,535 bytes.

---

## Named Sections

Named sections appear first in the file and hold simple key-value metadata. In `.stp` files, there is typically one named section with key `"Method"` containing a single property `"ReadOnly"` = `"0"`.

### Named Section Layout

```
┌──────────────────────┬──────────────────┬──────────────────┐
│ ShortString name     │ u16 field_type   │ u32 field_count  │
├──────────────────────┴──────────────────┴──────────────────┤
│ Field 0: ShortString key, VarString value                  │
│ Field 1: ShortString key, VarString value                  │
│ ...                                                        │
│ Field F-1: ShortString key, VarString value                │
└────────────────────────────────────────────────────────────┘
```

In a typical `.stp` file:
```
Name: "Method"
FieldType: 1
FieldCount: 1
  Key: "Properties"  →  Value: "ReadOnly"
  Key: "ReadOnly"    →  Value: "0"
```

---

## HxPars Sections

This is where the actual step parameters live. Each HxPars section corresponds to either a device step instance (keyed by GUID), an audit trail record, or other metadata.

### HxPars Section Layout

```
┌──────────────────────────────────────────┐
│ ShortString rawName                      │
│   (format: "HxPars,<sectionKey>")        │
│   e.g., "HxPars,89a59053_b35c_..."       │
├──────────────────────────────────────────┤
│ u16  version                             │
│ u32  tokenCount (T)                      │
├──────────────────────────────────────────┤
│ VarString token[0]                       │
│ VarString token[1]                       │
│ ...                                      │
│ VarString token[T-1]                     │
└──────────────────────────────────────────┘
```

The `rawName` field typically starts with `"HxPars,"` followed by the section key. The parser strips the `"HxPars,"` prefix to get the section key (e.g., the step instance GUID).

### Token Stream Interpretation

Tokens are an ordered list of strings. They encode a recursive key-value structure with nested groups:

1. **Key-Value Pairs**: Tokens alternate as key, value, key, value:
   ```
   "1StepName"  "Aspirate"  "1SequenceObject"  "ML_STAR.Samples"
   ```

2. **Key Prefix Convention**: The first character of a key indicates the value type:
   - `1` → string value
   - `3` → integer value (stored as string)
   - `5` → float value (stored as string)

3. **Group Open**: A token starting with `(` opens a nested group:
   ```
   "(-534183935"   ← opens the 96-head parameter group
   ```

4. **Group Close**: The token `")"` closes the most recent group.

5. **Nested Structure Example**:
   ```
   "(-534183935"              ← open 96-head group
     "5-534183924"  "150"     ← Aspirate Volume = 150 µL
     "3-534183919"  "5"       ← LLD Mode = 5 (Capacitive)
     "5-534183913"  "2"       ← Submerge Depth = 2 mm
   ")"                        ← close group
   ```

### Special Sections

| Section Key | Purpose |
|-------------|---------|
| `<instance_guid>` | Device step parameters (one per step) |
| `AuditTrailData` | Audit trail metadata |

---

## Token Organization Within a Step Section

A typical device step section contains tokens in this order:

```
1. Metadata fields:
   - 1CommandStepFileGuid
   - 1StepName
   - 1Timestamp

2. Sequence configuration:
   - 1SequenceObject
   - 1SequenceName
   - 3SequenceCounting

3. Channel configuration:
   - 1ChannelPattern
   - 3TipType

4. Liquid handling settings:
   - 1LiquidName
   - 3LiquidFollowing
   - 3DispenseMode
   - 3SameLiquid

5. Parameter groups (one of):
   a. (-534183935 ...)  — flat group for CO-RE 96 head steps
   b. (-534183936 ...)  — per-channel groups for single-channel steps

6. Error/Recovery policy:
   - (Errors ...)

7. Variables block:
   - (Variables ...)
```

---

## 96-Head vs. Single-Channel Parameter Groups

### CO-RE 96 Head Steps

96-head steps use the group marker `(-534183935 ...)`. All parameters are flat key-value pairs inside a single group because the 96-head operates uniformly:

```
"(-534183935"
  "5-534183924"  "150"      ← Volume
  "3-534183914"  "4"        ← Mix Cycles
  "5-534183915"  "150"      ← Mix Volume
  "3-534183919"  "5"        ← LLD Mode
  "5-534183928"  "5"        ← LLD Sensitivity
  "5-534183913"  "2"        ← Submerge Depth
  "5-534183622"  "10"       ← Retract Distance
  "3LiquidFollowing" "1"    ← Liquid Following On
")"
```

### Single-Channel Steps

Single-channel steps use the group marker `(-534183936 ...)`. Inside, there are **sub-groups**, one per pipetting channel, because each channel can have independent settings:

```
"(-534183936"
  "(3"                       ← channel sub-group for channel 1
    "5-534183924"  "100"     ← Volume for ch1
    "3-534183919"  "1"       ← LLD Mode for ch1
    "3-534183876"  "1"       ← Channel Enable for ch1
  ")"
  "(1"                       ← channel sub-group for channel 2
    "5-534183924"  "100"
    "3-534183919"  "1"
    "3-534183876"  "1"
  ")"
  ...                        ← repeats for all channels
")"
```

---

## Text Representation

The binary format has a text equivalent produced by the `hxcfgfile_codec.py` tool (in `solutionToBlockMarkers/`). The text form uses this syntax:

```
HxCfgFile,3;
ConfigIsValid,Y;
DataDef,Method,1,Properties, { ReadOnly, "0" }
DataDef,HxPars,3,<guid>, [ "1StepName" "Aspirate" "1SequenceObject" "ML_STAR.Samples" ... ]
DataDef,HxPars,3,AuditTrailData, [ ")" ]
DataDef,SYSTEM,1,default, [ "<checksum>" ]
```

Key points:
- Named sections use `{ ... }` delimiters
- HxPars sections use `[ ... ]` delimiters
- All tokens are quoted strings inside `[ ... ]`
- The text form is roundtrip-safe: binary → text → binary produces identical output

---

## Footer and Checksum

The file ends with a checksum section. In text form, this appears as:

```
DataDef,SYSTEM,1,default, [ "<crc32_hex>" ]
```

The checksum covers the entire preceding file content and is validated by Hamilton's runtime. The extension's `AddCheckSum` tool (in `dotnet/`) can regenerate these checksums.
