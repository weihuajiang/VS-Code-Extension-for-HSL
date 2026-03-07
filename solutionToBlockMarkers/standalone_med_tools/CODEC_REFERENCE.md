# HxCfgFile v3 Binary Codec Reference

## Overview

The HxCfgFile v3 binary container format is a proprietary binary format used by
Hamilton STAR / STARlet / Vantage liquid-handling robots to store instrument
method (`.med`) and step parameter (`.stp`) files. The
`hxcfgfile_codec.py` module provides a fully self-contained, zero-dependency
Python codec for reading and writing this format, including round-trip
conversion between binary and a human-readable text representation.

The text representation mirrors what Hamilton's own `HxCfgFilConverter.exe /t`
utility produces, allowing files to be inspected, diffed, and modified with
standard text tools.

---

## Binary Structure

The on-disk binary layout is strictly sequential with no alignment padding
(except for a single 3-byte zero pad after the HxPars count).

```
┌──────────────────────────────────────────────────────────────┐
│  File Header (4 bytes)                                       │
│    [u16-LE]  version          -- always 3                     │
│    [u16-LE]  type_marker      -- always 1                     │
├──────────────────────────────────────────────────────────────┤
│  Named-Section Count (4 bytes)                               │
│    [u32-LE]  count            -- 0 or 1                       │
├──────────────────────────────────────────────────────────────┤
│  Named Section (optional -- present when count == 1)          │
│    [short-string]  section_name                              │
│    [u16-LE]        field_type       -- always 1               │
│    [u32-LE]        field_count      -- always 1               │
│    [short-string]  field_key                                 │
│    [var-string]    field_value                                │
├──────────────────────────────────────────────────────────────┤
│  HxPars Count (1 byte) + 3-byte zero pad                    │
│    [u8]     hxpars_count                                     │
│    [3×0x00] padding                                          │
├──────────────────────────────────────────────────────────────┤
│  HxPars Sections (repeated hxpars_count times)               │
│    [short-string]  section_header  -- "HxPars,<key>"          │
│    [u16-LE]  pars_version     -- always 3                     │
│    [u32-LE]  token_count                                     │
│    [var-string × token_count]  tokens                        │
├──────────────────────────────────────────────────────────────┤
│  Footer                                                      │
│    \r\n                                                      │
│    ASCII metadata line ($$author=… $$)                       │
└──────────────────────────────────────────────────────────────┘
```

### Version Header

| Offset | Type    | Value | Description                     |
|--------|---------|-------|---------------------------------|
| 0x0000 | u16-LE  | 3     | HxCfgFile container version     |
| 0x0002 | u16-LE  | 1     | Type marker (always 1)          |

### Named-Section Count

| Offset | Type    | Value | Description                     |
|--------|---------|-------|---------------------------------|
| 0x0004 | u32-LE  | 0-1   | Number of named sections        |

---

## Encoding Details

All integers are **little-endian**. All string payloads use **Latin-1
(ISO 8859-1)** encoding.

### Short String

A 1-byte length prefix followed by the raw payload. Maximum payload: **255 bytes**.

```
[u8 length] [length bytes of Latin-1 payload]
```

Used for: section names, field keys, HxPars section headers.

### Var String

A variable-length encoding with two forms:

| Marker Byte | Form   | Layout                                        | Max Length  |
|-------------|--------|-----------------------------------------------|-------------|
| 0x00-0xFE   | Short  | `[marker=length] [payload]`                   | 254 bytes   |
| 0xFF        | Long   | `[0xFF] [u16-LE length] [payload]`            | 65 535 bytes |

Used for: field values (e.g. base-64 blobs), HxPars tokens.

### Integer Types

| Type   | Size    | Encoding     | Usage                                  |
|--------|---------|--------------|----------------------------------------|
| u8     | 1 byte  | unsigned     | HxPars count, short-string length      |
| u16-LE | 2 bytes | little-endian | Version, type marker, field type       |
| u32-LE | 4 bytes | little-endian | Named-section count, field count, token count |

---

## Named Section Format

The named section is an optional block that appears when the named-section
count is 1. Its structure depends on the file type:

| File Type | Section Name              | Field Key          | Field Value                       |
|-----------|---------------------------|--------------------|-----------------------------------|
| `.med`    | `ActivityData,ActivityData` | `ActivityDocument` | Base-64-encoded flowchart blob    |
| `.stp`    | `Method,Properties`       | `ReadOnly`         | `"0"`                             |

Some minimal `.stp` files have a named-section count of 0 (no named section).

The named section always has:
- `field_type` = 1 (u16-LE)
- `field_count` = 1 (u32-LE)

---

## HxPars Token Arrays

Each HxPars section stores an ordered list of free-form Latin-1 strings
called **tokens**. The section header is a short-string of the form
`"HxPars,<key>"`, followed by a version word (always 3), a token count
(u32-LE), and the tokens themselves (each as a var-string).

Tokens encode structured data using a naming convention where the first
character indicates the value type:

| Prefix | Token Type | Meaning                                    | Example Token     |
|--------|------------|--------------------------------------------|--------------------|
| `1`    | String     | String value (key prefixed with `1`)       | `1Comment`         |
| `3`    | Integer    | Integer value (key prefixed with `3`)      | `3TraceSwitch`     |
| `5`    | Float      | Float value (key prefixed with `5`)        | `5Volume`          |
| `6`    | Boolean    | Boolean value (key prefixed with `6`)      | `6-533725154`      |
| `(`    | Open group | Start of a named sub-group                 | `(BlockData`       |
| `)`    | Close      | End of the current group                   | `)`                |

Tokens are stored as key-value pairs: the key token (e.g. `"1Comment"`)
is immediately followed by the value token (e.g. `"Hello world"`).

---

## Text Representation Format

The text format (`.med.txt` or `.stp.txt`) is a human-readable serialization
of the binary container. Every text file begins with a fixed header:

```
HxCfgFile,3;

ConfigIsValid,Y;

```

### Named Section in Text

The optional named section is emitted as a `DataDef` block:

```
DataDef,ActivityData,1,ActivityData,
{
ActivityDocument, "<base64-blob>"
};
```

For `.stp` files:

```
DataDef,Method,1,Properties,
{
ReadOnly, "0"
};
```

### HxPars Section in Text  (`[Section:key]`)

Each HxPars section becomes a `DataDef,HxPars,3,<key>,` block with tokens
listed in square brackets:

```
DataDef,HxPars,3,<key>,
[
"token1",
"token2",
"token3"
];
```

The last token has no trailing comma; all others do.

### Escape Sequences

Inside quoted token strings, the following escape sequences are used:

| Escape     | Meaning                          | Byte Value |
|------------|----------------------------------|------------|
| `\\`       | Literal backslash                | `0x5C`     |
| `\"`       | Literal double-quote             | `0x22`     |
| `\n`       | Line feed                        | `0x0A`     |
| `\r`       | Carriage return                  | `0x0D`     |
| `\0xHH`    | Arbitrary byte (hex)             | `0xHH`     |

Characters in the range `0x20`-`0x7E` (excluding `\` and `"`) are emitted
literally. All other byte values are escaped as `\0xHH`.

---

## Checksum Footer

Every file ends with a metadata footer line. The format differs by file type:

**HSL/SUB files** (prefix `//`):
```
// $$author=admin$$valid=0$$time=2024-01-15 09:30$$checksum=a1b2c3d4$$length=089$$
```

**MED/STP files** (prefix `*`):
```
* $$author=admin$$valid=0$$time=2024-01-15 09:30$$checksum=a1b2c3d4$$length=087$$
```

### Footer Fields

| Field      | Description                                                    |
|------------|----------------------------------------------------------------|
| `author`   | Windows username of the file author                            |
| `valid`    | Validation state: `0` = user, `1` = library, `2` = config     |
| `time`     | Timestamp in `YYYY-MM-DD HH:MM` format                        |
| `checksum` | 8-character lowercase hex CRC-32                               |
| `length`   | 3-digit zero-padded total line length (including `\r\n`)       |

### CRC-32 Algorithm

- **Polynomial**: `0xEDB88320` (standard CRC-32, reflected/LSB-first)
- **Initial value**: `0xFFFFFFFF`
- **Final XOR**: `0xFFFFFFFF`
- **Input data**: All file content before the checksum line, concatenated with the line prefix up to and including `checksum=`
- **Encoding**: Latin-1 (ISO 8859-1)

This is equivalent to Python's `zlib.crc32()`.

---

## Example: Minimal .med Text File

```
HxCfgFile,3;

ConfigIsValid,Y;

DataDef,ActivityData,1,ActivityData,
{
ActivityDocument, "PEFjdGl2a..."
};

DataDef,HxPars,3,a1b2c3d4_e5f6_7890_abcdef1234567890,
[
"3TraceSwitch",
"1",
"1Comment",
"Hello World",
"3ParsCommandVersion",
"1",
"(BlockData",
"(1",
"1-533921780",
"<Hello World>",
"1-533921781",
"Comment",
"1-533921782",
"Comment.bmp",
"1-533921779",
"MECC::TraceComment(Translate(\"Hello World\"));",
")",
")",
"1Timestamp",
"2024-01-15 09:30"
];

DataDef,HxPars,3,HxMetEdData,
[
"1Version",
"6.2.2.4006",
")"
];

* $$author=admin$$valid=0$$time=2024-01-15 09:30$$checksum=a1b2c3d4$$length=087$$
```

---

## Error Handling and Corruption Detection

The codec performs strict validation at every structural boundary:

| Check                          | Error Raised When                          |
|--------------------------------|--------------------------------------------|
| Version validation             | Version word ≠ 3                           |
| Type marker validation         | Type marker ≠ 1                            |
| Named-section count            | Count > 1                                  |
| Field type in named section    | Field type ≠ 1                             |
| Field count in named section   | Field count ≠ 1                            |
| HxPars section header prefix   | Header does not start with `"HxPars,"`     |
| HxPars version                 | Version ≠ 3                                |
| Footer detection               | `* $$author=…$$` pattern not found         |
| Text header validation         | Text does not start with `"HxCfgFile,3;"`  |
| Token quoting                  | Token string not properly double-quoted     |
| String length limits           | Short-string > 255 bytes, var-string > 65 535 bytes |

### Roundtrip Verification

The codec includes a built-in roundtrip verification command:

```
python hxcfgfile_codec.py roundtrip input.med
```

This performs binary → text → binary conversion and compares the result
byte-for-byte against the original. If any byte differs, the offset and
values of the first mismatch are reported.

---

## CLI Commands

```
python hxcfgfile_codec.py to-text   input.med  output.med.txt
python hxcfgfile_codec.py to-binary input.med.txt  output.med
python hxcfgfile_codec.py roundtrip input.med  [output.med]
python hxcfgfile_codec.py dump      input.med
```

| Command     | Description                                                |
|-------------|------------------------------------------------------------|
| `to-text`   | Convert binary `.med`/`.stp` to text representation        |
| `to-binary` | Convert text representation back to binary                 |
| `roundtrip` | Binary → text → binary, verify byte-for-byte equality      |
| `dump`      | Print a human-readable structural summary with byte offsets |

---

## Data Model Classes

| Class            | Description                                           |
|------------------|-------------------------------------------------------|
| `NamedSection`   | The optional leading section (name, key, value)       |
| `HxParsSection`  | One HxPars section with key and token list            |
| `HxCfgTextModel` | Complete in-memory model: named section + HxPars list + footer |

The `HxCfgTextModel` is the intermediate form used by both the binary
parser/builder and the text parser/emitter, enabling lossless conversion
in either direction.
