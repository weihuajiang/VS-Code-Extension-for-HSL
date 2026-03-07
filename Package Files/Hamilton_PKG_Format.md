# Hamilton VENUS .pkg File Format Specification

## Overview

The `.pkg` file format is a proprietary binary package format used by **Hamilton VENUS** instrument control software to distribute and install software components — including method files, libraries, labware definitions, configuration files, images, and help documentation.

A `.pkg` file is a single-file archive containing:
- A **header** identifying the format and version
- An **entry table** (index) listing all packaged items
- **Compressed data blocks** for each entry (zlib/deflate)
- A **manifest** mapping entries to their installation file paths
- A **trailer** with package-level metadata (author, timestamp, checksum)

The format is sometimes referred to as **HamPkg** after its magic bytes.

> **Note:** This format is distinct from the `.hxlibpkg` format used by the Library Manager for Venus 6 application, which uses XOR-scrambled ZIP with HMAC-SHA256 integrity verification.

---

## File Layout

```
┌──────────────────────────────────────────┐
│  Header (46 bytes)                       │
├──────────────────────────────────────────┤
│  Entry Table (N × 36 bytes)              │
│    Entry 0                               │
│    Entry 1                               │
│    ...                                   │
│    Entry N-1                             │
├──────────────────────────────────────────┤
│  Data Section                            │
│    Data Block 0 (8-byte header + zlib)   │
│    Data Block 1                          │
│    ...                                   │
│    Data Block N-1                        │
├──────────────────────────────────────────┤
│  Trailer (87 bytes)                      │
└──────────────────────────────────────────┘
```

---

## 1. Header (46 bytes)

| Offset | Size | Type         | Description                                        |
|--------|------|--------------|----------------------------------------------------|
| 0      | 6    | ASCII        | Magic bytes: `HamPkg` (`48 61 6D 50 6B 67`)        |
| 6      | 2    | uint16 LE    | Reserved (always `0`)                               |
| 8      | 2    | uint16 LE    | Format version (observed: `2`)                      |
| 10     | 2    | uint16 LE    | Sub-version (observed: `1`)                         |
| 12     | 2    | uint16 LE    | Reserved (always `0`)                               |
| 14     | 2    | uint16 LE    | **Entry count** — total number of entries (N)       |
| 16     | 2    | uint16 LE    | Reserved (always `0`)                               |
| 18     | 8    | FILETIME     | **Package creation timestamp** (Windows FILETIME)   |
| 26     | 20   | ASCII (null) | **VENUS version string**, null-padded (e.g. `4.6.0.8061`) |

### FILETIME Conversion

Windows FILETIME is a 64-bit value representing 100-nanosecond intervals since January 1, 1601 UTC. To convert to Unix timestamp:

```
unix_ms = (FILETIME - 116444736000000000) / 10000
```

### Example Header

```
Offset  Hex                                              ASCII
0000:   48 61 6D 50 6B 67 00 00 02 00 01 00 00 00 AD 00  HamPkg..........
0010:   00 00 A0 7D 4C AF 38 41 D9 01 34 2E 36 2E 30 2E  ...}L.8A..4.6.0.
0020:   38 30 36 31 00 00 00 00 00 00 00 00 00 00         8061..........
```

Decoded:
- Magic: `HamPkg`
- Format version: `2.1`
- Entry count: `173` (0x00AD)
- Created: `2023-02-15T12:26:09.914Z`
- VENUS version: `4.6.0.8061`

---

## 2. Entry Table

The entry table immediately follows the header at offset **46**. Each entry is **36 bytes**. The table contains `N` entries (from the header's entry count field).

### Entry Structure (36 bytes)

| Offset | Size | Type         | Description                                                |
|--------|------|--------------|------------------------------------------------------------|
| 0      | 8    | ASCII (null) | **Entry ID** — 7-character lowercase hex string, null-terminated (e.g. `0000000\0`, `00000ac\0`) |
| 8      | 4    | uint32 LE    | **Flags** — `1` = file data entry, `0` = manifest/catalog entry |
| 12     | 8    | FILETIME     | **Created timestamp** of the original file                  |
| 20     | 8    | FILETIME     | **Modified timestamp** of the original file                 |
| 28     | 4    | uint32 LE    | **Data offset** — absolute byte offset to the data block    |
| 32     | 4    | uint32 LE    | **Data size** — total size of the data block (compressed size + 8) |

### Key Details

- **Entry IDs** are sequential hex values starting from `0000000` and incrementing: `0000001`, `0000002`, ..., `00000ac`.
- Entry IDs do **not** encode filenames. The filename-to-entry mapping exists only in the **manifest** (the last entry with `flags=0`).
- The **data offset** is an absolute position in the file. The first entry's data offset equals `46 + (N × 36)` — immediately after the entry table.
- **Data size** = compressed payload size + 8 bytes (for the uncompressed/compressed size header).

### Example Entry

```
Entry 0:
  Hex: 30 30 30 30 30 30 30 00  01 00 00 00  00 46 C3 49
       76 45 D6 01  80 1B 0C DA 61 41 D9 01  82 18 00 00
       51 0D 00 00

  ID:       "0000000"
  Flags:    1 (file data)
  Created:  2020-06-18T13:42:20.000Z
  Modified: 2023-02-15T17:20:51.000Z
  Offset:   6274
  Size:     3409
```

---

## 3. Data Section

Data blocks are stored contiguously after the entry table. Each block consists of an 8-byte header followed by zlib-compressed data.

### Data Block Layout

| Offset | Size | Type      | Description                              |
|--------|------|-----------|------------------------------------------|
| 0      | 4    | uint32 LE | **Uncompressed size** (bytes)             |
| 4      | 4    | uint32 LE | **Compressed size** (bytes)               |
| 8      | N    | bytes     | **zlib/deflate compressed data** (starts with `78 9C`) |

### Relationship to Entry Table

```
entry.dataOffset  →  points to this data block
entry.dataSize    =  compressedSize + 8
```

### Decompression

Each data block's payload (starting at offset + 8, for `compressedSize` bytes) is standard **zlib/deflate** compressed data. It can be decompressed with any zlib-compatible library:

- **Node.js**: `zlib.inflateSync(buffer)`
- **Python**: `zlib.decompress(buffer)`
- **C/C++**: `inflate()` from zlib

The decompressed output is the raw file content — whether that's HSL source code, a PNG image, a BMP, an HxPars binary structure, or plain text.

---

## 4. Content Types

Entries 0 through N-2 (flags=1) contain the actual packaged file data. Entry N-1 (flags=0) is always the manifest. After decompression, file content can be identified by magic bytes or text signatures:

| Content Type        | Count | Magic Bytes / Signature           | File Extensions                    |
|---------------------|-------|-----------------------------------|------------------------------------|
| HxPars structured   | 42    | `03 00 01 00`                     | .stp, .smt, .hsi, .adp, .rck, .ctr, .tml, .cfg, .lay, .res, .dck, .tpl |
| Per-file metadata   | 35    | `02 00 01 00`                     | (internal metadata, not user files) |
| HSL source code     | 25    | `// `, `/*`, `#pragma`, `function`, `namespace`, etc. | .hsl, .hs_                         |
| Plain text / config | 38    | Various text patterns             | .cfg, .hsl, miscellaneous          |
| PNG images          | 15    | `89 50 4E 47` (`‰PNG`)           | .png, .bmp (misnamed)              |
| BMP images          | 6     | `42 4D` (`BM`)                   | .bmp                               |
| CHM help files      | 9     | `49 54 53 46` (`ITSF`)           | .chm                               |
| OLE compound doc    | 1     | `D0 CF 11 E0`                    | .xls                               |
| ZIP / Office XML    | 1     | `50 4B 03 04` (`PK`)             | .xlsx                              |
| UTF-16 LE text      | 1     | `FF FE`                          | (text with BOM)                    |

### HxPars Binary Format (`03 00 01 00`)

Many VENUS data files use the **HxPars** serialization format — a proprietary key-value binary encoding. Structure:

```
Offset  Size  Description
0       4     Magic: 03 00 01 00
4       4     Flags/reserved
8       4     Flags/reserved (often 0x00000001)
12      1     Length of subtype name string
13      N     Subtype name (ASCII)
13+N    ...   Key-value data pairs
```

Observed HxPars subtypes:
| Subtype                          | Description                 | Count |
|----------------------------------|-----------------------------|-------|
| `HxPars,AuditTrailData`         | Audit trail records         | 3     |
| `HxPars,ActivityTypes`          | Activity type definitions   | 2     |
| `HxPars,SystemDefFileDeps`      | System file dependencies    | 1     |
| `HxPars,Bookmarks`             | Method editor bookmarks     | 1     |
| `HxPars,UserDefFileDeps`       | User file dependencies      | 1     |
| `HxPars,MLStarConfig`          | ML STAR configuration       | 1     |
| `HxPars,McListData`            | Manifest/catalog (entry N-1)| 1     |
| `HxPars,<GUID>`                | GUID-keyed internal data    | 4     |
| `RACK,default...`              | Labware rack definition     | 4     |
| `CONTAINER,default...`         | Labware container definition| 1     |
| `LATE,default...`              | Labware template            | 1     |
| `LAY,...`                       | Deck layout                 | 1     |

### Per-File Metadata (`02 00 01 00`)

35 entries use the `02 00 01 00` magic and contain audit metadata about individual files:

```
02 00 01 00 [binary header...] $$author=<username>$$valid=<0|1|2>$$time=<YYYY-MM-DD HH:MM>$$checksum=<hex>$$length=<NNN>$$
```

Fields:
- **author**: Windows username that last modified the file
- **valid**: Validation state (`0` = not validated, `1` = partially, `2` = fully validated)
- **time**: Timestamp of last modification
- **checksum**: CRC32 or similar hash of the file content (8-character hex)
- **length**: Length of this metadata string (3-digit zero-padded decimal)

---

## 5. Manifest (Entry N-1)

The **last entry** in the table (highest entry ID, `flags=0`) is a special manifest/catalog that maps entry IDs to their installation file paths. Without this manifest, there is no way to determine which entry corresponds to which file, as entry IDs are opaque hex numbers.

### Manifest Structure

The manifest decompresses to an HxPars structure with subtype `HxPars,McListData`. It contains a list of records, each with:

| HxPars Key  | Type   | Description                        |
|-------------|--------|------------------------------------|
| 347734013   | String | Entry hex ID (e.g. `0000000`)      |
| 347734014   | String | Relative filename (e.g. `Vantage IDL Tools.hs_`) |
| 347734015   | String | Absolute installation path         |
| 347734012   | Int    | File type/category code            |
| 347733952   | Int    | List metadata / count              |

### HxPars Key-Value Encoding

Within the manifest, key-value pairs are encoded as:

```
<type_byte><key_digits><length_byte><value_bytes>
```

- **Type byte**: `1` = string value (followed by key, length byte, string data), `3` = integer value
- **Key digits**: The numeric key as ASCII digits (e.g. `347734013`)
- **Length byte**: Single byte indicating the string value length (0–255)
- **Value bytes**: The raw string or integer data

### Path Convention

All absolute paths point to the VENUS installation directory:
```
C:\Program Files (x86)\HAMILTON\<subdirectory>\<filename>
```

Common subdirectories:
- `Library\` — HSL source libraries, step files, images, help
- `Labware\` — Labware definitions (carriers, racks, containers)
- `Config\` — System and instrument configuration files
- `System\` — System-level files (ADP, bookmarks)
- `Methods\` — User methods (HSL)

### Manifest to File Mapping

A typical manifest maps sequential entry IDs to their installation paths. For example:

| Entry | Hex ID    | File Path                                                     |
|-------|-----------|---------------------------------------------------------------|
| 0     | `0000000` | `...\Library\Vantage Tools\Vantage IDL Tools Demo.hsl`        |
| 1     | `0000001` | `...\Library\Vantage Tools\Vantage IDL Tools Demo.med`        |
| 6     | `0000006` | `...\Library\Vantage Tools\Vantage IDL Tools.hs_`             |
| 40    | `0000028` | `...\Library\HSLExtensions\File.chm`                          |
| 101   | `0000065` | `...\Labware\ML_STAR\CORE\VStarWasteBlock_Config.tml`         |
| 117   | `0000075` | `...\Config\ActivityTypes.cfg`                                |
| 172   | `00000ac` | *(manifest itself — not mapped to a file)*                    |

---

## 6. Trailer (87 bytes)

The trailer appears at the very end of the file, immediately after the last data block. It contains package-level metadata in a `$$key=value$$` text format.

### Trailer Structure

```
<SP><CR><LF><SP>$$author=<username>$$valid=<N>$$time=<datetime>$$checksum=<hex>$$length=<NNN>$$
```

| Field      | Description                                          | Example              |
|------------|------------------------------------------------------|----------------------|
| `author`   | Windows username that created the package             | `Windows10`          |
| `valid`    | Validation state of the package                       | `2`                  |
| `time`     | Package creation timestamp                            | `2023-02-15 12:26`   |
| `checksum` | Package integrity checksum (8-char hex)               | `594ac20b`           |
| `length`   | Length of the metadata string in bytes (zero-padded)   | `086`                |

### Example Trailer Hex

```
Offset  Hex                                              ASCII
0000:   20 0D 0A 20 24 24 61 75 74 68 6F 72 3D 57 69 6E   .. $$author=Win
0010:   64 6F 77 73 31 30 24 24 76 61 6C 69 64 3D 32 24  dows10$$valid=2$
0020:   24 74 69 6D 65 3D 32 30 32 33 2D 30 32 2D 31 35  $time=2023-02-15
0030:   20 31 32 3A 32 36 24 24 63 68 65 63 6B 73 75 6D   12:26$$checksum
0040:   3D 35 39 34 61 63 32 30 62 24 24 6C 65 6E 67 74  =594ac20b$$lengt
0050:   68 3D 30 38 36 24 24                             h=086$$
```

---

## 7. Complete Format Summary

For a package with **N** entries:

| Region       | Offset                | Size               |
|--------------|-----------------------|--------------------|
| Header       | `0`                   | `46` bytes         |
| Entry Table  | `46`                  | `N × 36` bytes     |
| Data Section | `46 + (N × 36)`      | Variable           |
| Trailer      | End of data section   | `87` bytes         |

**Total file size** = 46 + (N × 36) + Σ(compressed sizes + 8) + 87

---

## 8. How to Extract a .pkg File

### Step-by-Step Manual Extraction

#### Prerequisites
- Node.js (v12+) or Python 3 with zlib support

#### Step 1: Read the Header

Read the first 46 bytes. Verify the magic bytes are `HamPkg`. Read the entry count at offset 14 (uint16 LE).

#### Step 2: Parse the Entry Table

Starting at offset 46, read `entryCount × 36` bytes. For each 36-byte entry, extract:
- Entry ID (bytes 0–7, ASCII string)
- Flags (bytes 8–11, uint32 LE)
- Data offset (bytes 28–31, uint32 LE)
- Data size (bytes 32–35, uint32 LE)

#### Step 3: Parse the Manifest

Find the entry with `flags=0` (typically the last entry). Decompress its data block. Parse the HxPars binary structure to extract `key 347734013` (entry ID) → `key 347734015` (absolute path) mappings.

#### Step 4: Extract All Files

For each entry with `flags=1`:
1. Seek to `entry.dataOffset`
2. Read `uncompressedSize` (uint32 LE) and `compressedSize` (uint32 LE)
3. Read `compressedSize` bytes of zlib data
4. Decompress with zlib inflate
5. Look up the entry ID in the manifest to determine the output filename and path
6. Write the decompressed data to disk

### Node.js Extraction Script

```javascript
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

function extractPkg(pkgPath, outputDir) {
    const buf = fs.readFileSync(pkgPath);

    // Validate magic
    const magic = buf.toString('ascii', 0, 6);
    if (magic !== 'HamPkg') {
        throw new Error('Not a valid Hamilton .pkg file (expected HamPkg magic)');
    }

    // Read header
    const entryCount = buf.readUInt16LE(14);
    const version = buf.toString('ascii', 26, 46).replace(/\0+$/, '');
    console.log(`VENUS version: ${version}, Entries: ${entryCount}`);

    // Parse entry table
    const entries = [];
    for (let i = 0; i < entryCount; i++) {
        const off = 46 + i * 36;
        entries.push({
            index: i,
            id: buf.toString('ascii', off, off + 7),
            flags: buf.readUInt32LE(off + 8),
            dataOffset: buf.readUInt32LE(off + 28),
            dataSize: buf.readUInt32LE(off + 32)
        });
    }

    // Decompress an entry's data block
    function decompress(entry) {
        const off = entry.dataOffset;
        const compressedSize = buf.readUInt32LE(off + 4);
        return zlib.inflateSync(buf.slice(off + 8, off + 8 + compressedSize));
    }

    // Parse manifest (flags=0 entry)
    const manifestEntry = entries.find(e => e.flags === 0);
    if (!manifestEntry) {
        throw new Error('No manifest entry found (flags=0)');
    }

    const manifest = decompress(manifestEntry);
    const fileMap = parseManifest(manifest);
    console.log(`Manifest contains ${Object.keys(fileMap).length} file mappings`);

    // Extract all file entries
    fs.mkdirSync(outputDir, { recursive: true });
    for (const entry of entries) {
        if (entry.flags !== 1) continue;

        const data = decompress(entry);
        const absPath = fileMap[entry.id];

        let relPath;
        if (absPath) {
            // Convert absolute Hamilton path to relative
            const hamiltonIdx = absPath.toLowerCase().indexOf('\\hamilton\\');
            relPath = hamiltonIdx >= 0
                ? absPath.substring(hamiltonIdx + '\\hamilton\\'.length)
                : path.basename(absPath);
        } else {
            relPath = `unmapped/${entry.id}.bin`;
        }

        const outPath = path.join(outputDir, relPath);
        fs.mkdirSync(path.dirname(outPath), { recursive: true });
        fs.writeFileSync(outPath, data);
        console.log(`  Extracted: ${relPath} (${data.length} bytes)`);
    }

    console.log('Extraction complete.');
}

function parseManifest(manifest) {
    const KEY_ENTRY_ID = Buffer.from('347734013');
    const KEY_ABS_PATH = Buffer.from('347734015');
    const map = {};

    let pos = 0;
    while (pos < manifest.length) {
        const idIdx = manifest.indexOf(KEY_ENTRY_ID, pos);
        if (idIdx === -1) break;

        const afterId = idIdx + 9;
        if (afterId >= manifest.length) break;

        const idLen = manifest[afterId];
        if (idLen > 0 && idLen < 20 && afterId + 1 + idLen <= manifest.length) {
            const entryId = manifest.toString('ascii', afterId + 1, afterId + 1 + idLen);
            if (/^[0-9a-f]+$/.test(entryId)) {
                // Search for abs path key within 200 bytes forward
                const searchEnd = Math.min(afterId + 200, manifest.length);
                const searchBuf = manifest.slice(afterId, searchEnd);
                const pathIdx = searchBuf.indexOf(KEY_ABS_PATH);
                if (pathIdx !== -1) {
                    const pathStart = afterId + pathIdx + 9;
                    const pathLen = manifest[pathStart];
                    if (pathLen > 0 && pathStart + 1 + pathLen <= manifest.length) {
                        const absPath = manifest.toString('utf8', pathStart + 1, pathStart + 1 + pathLen);
                        map[entryId] = absPath;
                    }
                }
            }
        }
        pos = afterId + 1;
    }

    return map;
}

// Usage:
// extractPkg('path/to/package.pkg', './extracted');
const args = process.argv.slice(2);
if (args.length < 1) {
    console.log('Usage: node extract_pkg.js <file.pkg> [output_dir]');
    process.exit(1);
}
extractPkg(args[0], args[1] || './extracted');
```

**Usage:**
```bash
node extract_pkg.js "Vantage IDL Tools Demo 230215.pkg" ./extracted
```

### Python Extraction Script

```python
import struct
import zlib
import os
import sys
import re

def extract_pkg(pkg_path, output_dir):
    with open(pkg_path, 'rb') as f:
        buf = f.read()

    # Validate magic
    magic = buf[0:6].decode('ascii')
    if magic != 'HamPkg':
        raise ValueError('Not a valid Hamilton .pkg file')

    # Read header
    entry_count = struct.unpack_from('<H', buf, 14)[0]
    version = buf[26:46].split(b'\x00')[0].decode('ascii')
    print(f'VENUS version: {version}, Entries: {entry_count}')

    # Parse entry table
    entries = []
    for i in range(entry_count):
        off = 46 + i * 36
        entry_id = buf[off:off+7].decode('ascii').rstrip('\x00')
        flags = struct.unpack_from('<I', buf, off + 8)[0]
        data_offset = struct.unpack_from('<I', buf, off + 28)[0]
        data_size = struct.unpack_from('<I', buf, off + 32)[0]
        entries.append({
            'index': i, 'id': entry_id, 'flags': flags,
            'data_offset': data_offset, 'data_size': data_size
        })

    # Decompress helper
    def decompress(entry):
        off = entry['data_offset']
        compressed_size = struct.unpack_from('<I', buf, off + 4)[0]
        return zlib.decompress(buf[off + 8:off + 8 + compressed_size])

    # Parse manifest
    manifest_entry = next((e for e in entries if e['flags'] == 0), None)
    if not manifest_entry:
        raise ValueError('No manifest entry found')

    manifest = decompress(manifest_entry)
    file_map = parse_manifest(manifest)
    print(f'Manifest contains {len(file_map)} file mappings')

    # Extract files
    os.makedirs(output_dir, exist_ok=True)
    for entry in entries:
        if entry['flags'] != 1:
            continue

        data = decompress(entry)
        abs_path = file_map.get(entry['id'])

        if abs_path:
            hamilton_idx = abs_path.lower().find('\\hamilton\\')
            if hamilton_idx >= 0:
                rel_path = abs_path[hamilton_idx + len('\\hamilton\\'):]
            else:
                rel_path = os.path.basename(abs_path)
        else:
            rel_path = f'unmapped/{entry["id"]}.bin'

        out_path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(data)
        print(f'  Extracted: {rel_path} ({len(data)} bytes)')

    print('Extraction complete.')


def parse_manifest(manifest):
    key_entry_id = b'347734013'
    key_abs_path = b'347734015'
    file_map = {}

    pos = 0
    while pos < len(manifest):
        id_idx = manifest.find(key_entry_id, pos)
        if id_idx == -1:
            break

        after_id = id_idx + 9
        if after_id >= len(manifest):
            break

        id_len = manifest[after_id]
        if 0 < id_len < 20 and after_id + 1 + id_len <= len(manifest):
            entry_id = manifest[after_id + 1:after_id + 1 + id_len].decode('ascii')
            if re.match(r'^[0-9a-f]+$', entry_id):
                # Search for abs path key nearby
                search_end = min(after_id + 200, len(manifest))
                search_buf = manifest[after_id:search_end]
                path_idx = search_buf.find(key_abs_path)
                if path_idx != -1:
                    path_start = after_id + path_idx + 9
                    path_len = manifest[path_start]
                    if 0 < path_len and path_start + 1 + path_len <= len(manifest):
                        abs_path = manifest[path_start + 1:path_start + 1 + path_len].decode('utf-8')
                        file_map[entry_id] = abs_path
        pos = after_id + 1

    return file_map


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python extract_pkg.py <file.pkg> [output_dir]')
        sys.exit(1)
    extract_pkg(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else './extracted')
```

**Usage:**
```bash
python extract_pkg.py "Vantage IDL Tools Demo 230215.pkg" ./extracted
```

---

## 9. File Extensions Reference

Common file types found inside VENUS .pkg packages:

| Extension | Category     | Description                                |
|-----------|--------------|--------------------------------------------|
| `.hsl`    | Library      | HSL (Hamilton Standard Language) source     |
| `.hs_`    | Library      | HSL compiled/preprocessed library           |
| `.smt`    | Library      | Step method template (HxPars binary)        |
| `.hsi`    | Library      | HSL interface definition (HxPars binary)    |
| `.stp`    | Library      | Step definition file (HxPars or text)       |
| `.med`    | Method       | Method file (HxPars binary)                 |
| `.sub`    | Method       | Sub-method file                             |
| `.res`    | Method       | Resource file                               |
| `.lay`    | Deck         | Deck layout definition                      |
| `.dck`    | Deck         | Deck configuration                          |
| `.adp`    | System       | Application data profile                    |
| `.cfg`    | Config       | Configuration file (text or HxPars)         |
| `.tpl`    | Config       | Template file                               |
| `.rck`    | Labware      | Rack definition (HxPars binary)             |
| `.ctr`    | Labware      | Container definition (HxPars binary)        |
| `.tml`    | Labware      | Template labware definition                 |
| `.hxx`    | Labware      | 3D model reference                          |
| `.chm`    | Help         | Compiled HTML help file                     |
| `.bmp`    | Image        | Bitmap image (step icons, labware images)   |
| `.png`    | Image        | PNG image                                   |
| `.xls`    | Data         | Excel spreadsheet (OLE format)              |
| `.xlsx`   | Data         | Excel spreadsheet (Office Open XML)         |
| `.medbkm` | Bookmarks    | Method editor bookmarks                     |

---

## 10. Comparison: `.pkg` vs `.hxlibpkg`

| Feature              | `.pkg` (Hamilton VENUS)           | `.hxlibpkg` (Library Manager)     |
|----------------------|-----------------------------------|-----------------------------------|
| Magic bytes          | `HamPkg` (6 bytes)                | `HXLPKG\x01\x00` (8 bytes)       |
| Creator              | VENUS Method Editor / Package Editor | Library Manager for Venus 6     |
| Compression          | zlib/deflate per entry             | ZIP archive (entire payload)      |
| Encryption           | None                               | XOR scramble (32-byte key)        |
| Integrity            | CRC32 checksum in trailer          | HMAC-SHA256 (32 bytes in header)  |
| Entry indexing       | Hex ID table + manifest            | ZIP directory structure            |
| Metadata             | Per-file `$$key=value$$` strings   | JSON manifest inside ZIP           |
| Code signing         | Not built-in                       | Ed25519 signatures                 |
| Header size          | 46 bytes                           | 48 bytes                           |
| Content types        | Methods, labware, config, libraries | Libraries only                     |
| Path preservation    | Absolute paths in manifest         | Relative paths in ZIP              |

---

## Appendix A: Sample File Listing

The analyzed package (`Vantage IDL Tools Demo 230215.pkg`, 2,992,569 bytes) contains 172 files + 1 manifest:

<details>
<summary>Click to expand full file listing (172 entries)</summary>

| # | Entry ID | Installation Path |
|---|----------|-------------------|
| 0 | 0000000 | Library\Vantage Tools\Vantage IDL Tools Demo.hsl |
| 1 | 0000001 | Library\Vantage Tools\Vantage IDL Tools Demo.med |
| 2 | 0000002 | Library\Vantage Tools\Vantage IDL Tools Demo.sub |
| 3 | 0000003 | Library\Vantage Tools\Vantage IDL Tools Demo.stp |
| 4 | 0000004 | System\c--program files (x86)-hamilton-library-vantage tools-vantage idl tools demo.adp |
| 5 | 0000005 | System\C--Program Files (x86)-HAMILTON-Library-Vantage Tools-Vantage IDL Tools DemoWindows10.medbkm |
| 6 | 0000006 | Library\Vantage Tools\Vantage IDL Tools.hs_ |
| 7 | 0000007 | Library\Vantage Tools\Vantage IDL Tools.smt |
| 8 | 0000008 | Library\Vantage Tools\Vantage IDL Tools.hsi |
| 9 | 0000009 | Library\Vantage Tools\Vantage IDL Tools.stp |
| 10 | 000000a | System\c--program files (x86)-hamilton-library-vantage tools-vantage idl tools.adp |
| 11 | 000000b | Library\Vantage Tools\Vantage IDL Tools.bmp |
| 12 | 000000c | Library\Vantage Tools\Vantage IDL Tools.IPG_PresentAndScan.bmp |
| 13 | 000000d | Library\Vantage Tools\Vantage IDL Tools.IPG_PresentAndScan2.bmp |
| 14 | 000000e | Library\Vantage Tools\Vantage IDL Tools.QCG_PresentAndScan.bmp |
| 15 | 000000f | Library\Vantage Tools\Vantage IDL Tools.QCG_PresentAndScan2.bmp |
| 16 | 0000010 | Library\Vantage Tools\Vantage IDL Tools.SCAN_GetScanResult.bmp |
| 17 | 0000011 | Library\Vantage Tools\Vantage IDL Tools.SCAN_GetScanResultsTubes.bmp |
| 18 | 0000012 | Library\Vantage Tools\Vantage IDL Tools.SCAN_PlateCarrier.bmp |
| 19 | 0000013 | Library\Vantage Tools\Vantage IDL Tools.SCAN_PlateCarrier2.bmp |
| 20 | 0000014 | Library\Vantage Tools\Vantage IDL Tools.SCAN_TubeCarrier.bmp |
| 21 | 0000015 | Library\Vantage Tools\Vantage IDL Tools.SCAN_TubeCarrier2.bmp |
| 22 | 0000016 | Library\Vantage Tools\Vantage IDL Tools.SCAN_TubeCarrierFast.bmp |
| 23 | 0000017 | Library\Vantage Tools\Vantage IDL Tools.SCAN_TubeCarrierFastBlindRead.bmp |
| 24 | 0000018 | Library\Vantage Tools\Vantage IDL Tools.SCAN_TubeCarriers.bmp |
| 25 | 0000019 | Library\Vantage Tools\Vantage IDL Tools.TRAY_LightUpTracks.bmp |
| 26 | 000001a | Library\Vantage Tools\Vantage IDL Tools.TRAY_LowerLoadTray.bmp |
| 27 | 000001b | Library\Vantage Tools\Vantage IDL Tools.TRAY_RaiseLoadTray.bmp |
| 28 | 000001c | Library\HSL_MethodHelper.hsl |
| 29 | 000001d | Library\HSL_MethodHelper.stp |
| 30 | 000001e | Library\Vantage Tools\Resources\SubMethods\HelperLibraryVoV.hs_ |
| 31 | 000001f | Library\Vantage Tools\Resources\SubMethods\HelperLibraryVoV.smt |
| 32 | 0000020 | Library\Vantage Tools\Resources\SubMethods\HelperLibraryVoV.hsi |
| 33 | 0000021 | Library\Vantage Tools\Resources\SubMethods\HelperLibraryVoV.stp |
| 34 | 0000022 | Library\Alpha Numeric Conversion\Alpha Numeric Conversion.hs_ |
| 35 | 0000023 | Library\Alpha Numeric Conversion\Alpha Numeric Conversion.smt |
| 36 | 0000024 | Library\Alpha Numeric Conversion\Alpha Numeric Conversion.hsi |
| 37 | 0000025 | Library\Alpha Numeric Conversion\Alpha Numeric Conversion.stp |
| 38 | 0000026 | Library\HSLExtensions\File.hsl |
| 39 | 0000027 | Library\HSLExtensions\File.stp |
| 40 | 0000028 | Library\HSLExtensions\File.chm |
| 41 | 0000029 | Library\HSLExtensions\Framework\HSLExtensionsFramework.hsl |
| 42 | 000002a | Library\HSLExtensions\Framework\HSLExtensionsFramework.stp |
| 43 | 000002b | Library\ASWStandard\TraceLevel\TraceLevel.hsl |
| 44 | 000002c | Library\ASWStandard\TraceLevel\TraceLevel.stp |
| 45 | 000002d | Library\ASWStandard\TraceLevel\TraceLevel.chm |
| 46 | 000002e | Library\HSLExtensions\Framework\Enumerators.hsl |
| 47 | 000002f | Library\HSLExtensions\Framework\Enumerators.stp |
| 48 | 0000030 | Library\HSLTipCountingLib.stp |
| 49 | 0000031 | Library\HSLTipCountingLib.bmp |
| 50 | 0000032 | Library\HSLStatistics.hsl |
| 51 | 0000033 | Library\HSLStatistics.stp |
| 52 | 0000034 | Library\HSLStatistics.hs_ |
| 53 | 0000035 | Library\HSLStatistics.chm |
| 54 | 0000036 | Library\HSLStatistics.bmp |
| 55 | 0000037 | Library\Vantage Tools\Resources\SubMethods\IDL_FW_Commands.hs_ |
| 56 | 0000038 | Library\Vantage Tools\Resources\SubMethods\IDL_FW_Commands.smt |
| 57 | 0000039 | Library\Vantage Tools\Resources\SubMethods\IDL_FW_Commands.hsi |
| 58 | 000003a | Library\Vantage Tools\Resources\SubMethods\IDL_FW_Commands.stp |
| 59 | 000003b | Library\HSLExtensions\Dictionary.hsl |
| 60 | 000003c | Library\HSLExtensions\Dictionary.stp |
| 61 | 000003d | Library\HSLExtensions\Dictionary.chm |
| 62 | 000003e | Library\HSLExtensions\String.hsl |
| 63 | 000003f | Library\HSLExtensions\String.stp |
| 64 | 0000040 | Library\HSLExtensions\String.chm |
| 65 | 0000041 | Library\Firmware Libraries\FirmwareTools.hs_ |
| 66 | 0000042 | Library\Firmware Libraries\FirmwareTools.smt |
| 67 | 0000043 | Library\Firmware Libraries\FirmwareTools.hsi |
| 68 | 0000044 | Library\Firmware Libraries\FirmwareTools.stp |
| 69 | 0000045 | System\c--program files (x86)-hamilton-library-firmware libraries-firmwaretools.adp |
| 70 | 0000046 | Library\HSL_Regex.hsl |
| 71 | 0000047 | Library\HSL_Regex.stp |
| 72 | 0000048 | Library\HexToBinaryStringPattern.hsl |
| 73 | 0000049 | Library\HexToBinaryStringPattern.stp |
| 74 | 000004a | Library\HSLExtensions\Array.hsl |
| 75 | 000004b | Library\HSLExtensions\Array.stp |
| 76 | 000004c | Library\HSLExtensions\Array.chm |
| 77 | 000004d | Library\HSLExtensions\Directory.hsl |
| 78 | 000004e | Library\HSLExtensions\Directory.stp |
| 79 | 000004f | Library\HSLExtensions\Directory.chm |
| 80 | 0000050 | Library\Labware Properties\Labware_Property_Query.hs_ |
| 81 | 0000051 | Library\Labware Properties\Labware_Property_Query.smt |
| 82 | 0000052 | Library\Labware Properties\Labware_Property_Query.hsi |
| 83 | 0000053 | Library\Labware Properties\Labware_Property_Query.stp |
| 84 | 0000054 | System\c--program files (x86)-hamilton-library-labware properties-labware_property_query.adp |
| 85 | 0000055 | Library\Labware Properties\Resources\LPQ_GLOBAL.hsl |
| 86 | 0000056 | Library\Labware Properties\Resources\LPQ_GLOBAL.stp |
| 87 | 0000057 | Library\HSLExtensions\Sequence.hsl |
| 88 | 0000058 | Library\HSLExtensions\Sequence.stp |
| 89 | 0000059 | Library\HSLExtensions\Sequence.chm |
| 90 | 000005a | Library\HSLExtensions\Core.hsl |
| 91 | 000005b | Library\HSLExtensions\Core.stp |
| 92 | 000005c | Library\HSLExtensions\Core.chm |
| 93 | 000005d | Library\Vantage Tools\Resources\SubMethods\HSLConfigurationEditor.hs_ |
| 94 | 000005e | Library\Vantage Tools\Resources\SubMethods\HSLConfigurationEditor.smt |
| 95 | 000005f | Library\Vantage Tools\Resources\SubMethods\HSLConfigurationEditor.hsi |
| 96 | 0000060 | Library\Vantage Tools\Resources\SubMethods\HSLConfigurationEditor.stp |
| 97 | 0000061 | Library\ASWStandard\ASWGlobal\ASWGlobal.hsl |
| 98 | 0000062 | Library\ASWStandard\ASWGlobal\ASWGlobal.stp |
| 99 | 0000063 | Library\Vantage Tools\Vantage IDL Tools Demo.res |
| 100 | 0000064 | Library\Vantage Tools\Vantage IDL Tools Demo.lay |
| 101 | 0000065 | Labware\ML_STAR\CORE\VStarWasteBlock_Config.tml |
| 102 | 0000066 | Labware\ML_STAR\CORE\TeachingNeedleBlock_VStar_4.rck |
| 103 | 0000067 | Labware\ML_STAR\CORE\VStarWaste_16Pos.rck |
| 104 | 0000068 | Labware\ML_STAR\CORE\StarPlusWaste.bmp |
| 105 | 0000069 | Labware\ML_STAR\CORE\Waste2.hxx |
| 106 | 000006a | Labware\ML_STAR\CORE\VOVVerificationSquare.rck |
| 107 | 000006b | Labware\ML_STAR\CORE\VOVVerificationSquare.ctr |
| 108 | 000006c | Labware\UPMC\SMP_CAR_32_Blue_Adapters_Flip_Top_Tube\SMP_CAR_32_EPIL_A01_2.0mLTubes.rck |
| 109 | 000006d | Labware\UPMC\SMP_CAR_32_Blue_Adapters_Flip_Top_Tube\SMP_CAR_32.bmp |
| 110 | 000006e | Labware\UPMC\SMP_CAR_32_Blue_Adapters_Flip_Top_Tube\SMP_CAR_32_Blue_Adapters_Flip_Top_Tube.x |
| 111 | 000006f | Labware\UPMC\SMP_CAR_32_Blue_Adapters_Flip_Top_Tube\2.0ml-epil.ctr |
| 112 | 0000070 | Library\Vantage Tools\Resources\SubMethods\ScannerType.cfg |
| 113 | 0000071 | Library\Vantage Tools\Resources\IDL Macro File\Base64 Export To Image.xls |
| 114 | 0000072 | Library\Labware Properties\Labware Definition Keys.xlsx |
| 115 | 0000073 | *(C:\Temp\{GUID}\ML_STAR_22089728)* |
| 116 | 0000074 | *(C:\Temp\{GUID}\SystemConf)* |
| 117 | 0000075 | Config\ActivityTypes.cfg |
| 118 | 0000076 | Config\ActivityTypesEnu.cfg |
| 119 | 0000077 | Config\Diagnostic.dck |
| 120 | 0000078 | Config\Diagnostic.lay |
| 121 | 0000079 | Config\DummyResponse.cfg |
| 122 | 000007a | Config\FDxProtocol.cfg |
| 123 | 000007b | Config\HamHeaterShakerUsb.cfg |
| 124 | 000007c | Config\HSLKeywords.cfg |
| 125 | 000007d | Config\HxAtFilter.cfg |
| 126 | 000007e | Config\HxConfigEditor.cfg |
| 127 | 000007f | Config\HxCustomDialogCompCmd.cfg |
| 128 | 0000080 | Config\HxGRUCompCmd.cfg |
| 129 | 0000081 | Config\HxMetEd.cfg |
| 130 | 0000082 | Config\HxMetEdCompCmd.cfg |
| 131 | 0000083 | Config\HxMethodCopy.cfg |
| 132 | 0000084 | Config\HxMultiPipetteCmd.cfg |
| 133 | 0000085 | Config\HxRs232Com.cfg |
| 134 | 0000086 | Config\HxSchedCompCmd.cfg |
| 135 | 0000087 | Config\HxScheduleView.cfg |
| 136 | 0000088 | Config\HxServices.cfg |
| 137 | 0000089 | Config\HxStandardLanguage.cfg |
| 138 | 000008a | Config\HxStarMaintAndVer.cfg |
| 139 | 000008b | Config\HxStarMaintAndVerEnu.cfg |
| 140 | 000008c | Config\HxSTCompCmd.cfg |
| 141 | 000008d | Config\HxTcpIpBdzComm.cfg |
| 142 | 000008e | Config\HxTcpVStarComm.cfg |
| 143 | 000008f | Config\HxTrace.cfg |
| 144 | 0000090 | Config\HxVectorDb.cfg |
| 145 | 0000091 | Config\HxWatchView.cfg |
| 146 | 0000092 | Config\ML_FlexStar.cfg |
| 147 | 0000093 | Config\ML_FlexStar.dck |
| 148 | 0000094 | Config\ML_FlexStar.tpl |
| 149 | 0000095 | Config\ML_FlexStar_Simulator.cfg |
| 150 | 0000096 | Config\ML_STAR.cfg |
| 151 | 0000097 | Config\ML_STAR.dck |
| 152 | 0000098 | Config\ML_STAR2.dck |
| 153 | 0000099 | Config\ML_STAR2.tpl |
| 154 | 000009a | Config\ML_Starlet.cfg |
| 155 | 000009b | Config\ML_Starlet.dck |
| 156 | 000009c | Config\ML_Starlet.tpl |
| 157 | 000009d | Config\ML_Starlet_Simulator.cfg |
| 158 | 000009e | Config\ML_STARType.cfg |
| 159 | 000009f | Config\ML_STARTypeEnu.cfg |
| 160 | 00000a0 | Config\ML_STAR_Simulator.cfg |
| 161 | 00000a1 | Config\StarToVantageTranslation.cfg |
| 162 | 00000a2 | Config\users.cfg |
| 163 | 00000a3 | Config\VantageToStarTranslation.cfg |
| 164 | 00000a4 | Config\VantageToStarTranslation_BACKUP.cfg |
| 165 | 00000a5 | Config\VOVEntryExit.cfg |
| 166 | 00000a6 | Config\VOVExtConfig.cfg |
| 167 | 00000a7 | Config\VOVTrackGripper.cfg |
| 168 | 00000a8 | Config\VStar.cfg |
| 169 | 00000a9 | Config\VStar.tpl |
| 170 | 00000aa | Config\VStarCabinet.cfg |
| 171 | 00000ab | Config\VStar_Simulator.cfg |

</details>

---

*Document generated from reverse-engineering analysis of `Vantage IDL Tools Demo 230215.pkg` (2,992,569 bytes). Format version 2.1, VENUS 4.6.0.8061.*
