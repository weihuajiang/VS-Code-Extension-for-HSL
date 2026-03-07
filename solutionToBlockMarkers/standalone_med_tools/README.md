# standalone_med_tools

Standalone Python tooling for Hamilton HSL (Hamilton Standard Language) method files, `.med` (Method Editor Data) binary files, `.stp` (Step Parameters) binary files, and block marker management.

## Overview

- **Python 3.8+** -- no external dependencies required
- Provides tools for **Hamilton liquid handling robot** method development
- All file I/O uses **Latin1 encoding** (Hamilton convention)
- Originally extracted from a VS Code extension to provide independent, portable functionality
- Includes CLI entry points, importable Python APIs, and three Tkinter GUI applications

## Installation

No `pip install` is needed -- just clone the repository and use the package directly:

```bash
git clone <repo-url>
cd PRIVATE-VS-Code-Extension-for-HSL
```

**Requirements:**

- Python 3.8 or newer
- Tkinter (required for GUI applications only; included with standard Python on Windows)

## Package Structure

| File | Description |
|------|-------------|
| `__init__.py` | Package initialization and version metadata |
| `checksum.py` | CRC-32 checksum computation (polynomial `0xEDB88320`) for `.hsl`, `.sub`, `.med`, `.stp` file footers |
| `hxcfgfile_codec.py` | Binary ↔ text codec for HxCfgFile v3 containers (`.med` and `.stp` files) |
| `block_markers.py` | Block marker parsing, generation, renumbering, reconciliation, CLSID registry, and validation |
| `med_generator.py` | `.med` text builder and full sync pipeline from `.hsl` block markers |
| `stp_generator.py` | `.stp` file generation for Hamilton device step parameters |
| `repair_corrupt.py` | Detect and repair CRLF-corrupted `.med`/`.stp` binary files |
| `gui_codec_tester.py` | Tkinter app for binary conversion testing and roundtrip verification |
| `gui_block_marker_tester.py` | Tkinter app for block marker parsing, validation, and demo generation |
| `gui_med_viewer.py` | Tkinter app for viewing and inspecting decoded `.med`/`.stp` files |
| `tests/` | Comprehensive unit test suite |

## Quick Start

### Converting a `.med` binary to text

```python
from pathlib import Path
from standalone_med_tools.hxcfgfile_codec import parse_binary_med

binary_data = Path("MyMethod.med").read_bytes()
model = parse_binary_med(binary_data)
print(model.to_text())
```

### File-based conversion

```python
from pathlib import Path
from standalone_med_tools.hxcfgfile_codec import binary_to_text_file, text_to_binary_file

binary_to_text_file(Path("MyMethod.med"), Path("MyMethod.med.txt"))
text_to_binary_file(Path("MyMethod.med.txt"), Path("MyMethod_rebuilt.med"))
```

### Parsing block markers from `.hsl`

```python
from standalone_med_tools.block_markers import parse_block_markers

with open("MyMethod.hsl", encoding="latin1") as f:
    content = f.read()

markers = parse_block_markers(content)
for m in markers:
    print(m)
```

### Computing and verifying checksums

```python
from standalone_med_tools.checksum import verify_file_checksum, update_checksum_in_file

# Verify an existing checksum
result = verify_file_checksum("MyMethod.hsl")
print(f"Valid: {result['valid']}, Stored: {result['stored_checksum']}")

# Recompute and update the checksum in-place
update_checksum_in_file("MyMethod.hsl")
```

### Syncing `.med` from `.hsl`

```python
from standalone_med_tools.med_generator import sync_med_from_hsl

sync_med_from_hsl("MyMethod.hsl")
```

### Syncing `.stp` from `.hsl`

```python
from standalone_med_tools.stp_generator import sync_stp_from_hsl

sync_stp_from_hsl("MyMethod.hsl")
```

### Repairing corrupt files

```python
from standalone_med_tools.repair_corrupt import detect_corruption, repair_crlf_corruption

data = open("corrupt.med", "rb").read()
info = detect_corruption(data)

if info["is_corrupt"]:
    repaired = repair_crlf_corruption(data)
    with open("repaired.med", "wb") as f:
        f.write(repaired)
```

## CLI Usage

Each module provides CLI entry points via `python -m`:

### Binary ↔ Text Codec (`hxcfgfile_codec`)

```bash
# Convert binary .med/.stp to human-readable text
python -m standalone_med_tools.hxcfgfile_codec to-text input.med output.med.txt

# Convert text back to binary
python -m standalone_med_tools.hxcfgfile_codec to-binary input.med.txt output.med

# Roundtrip verification (binary → text → binary, byte comparison)
python -m standalone_med_tools.hxcfgfile_codec roundtrip input.med

# Dump binary structure summary
python -m standalone_med_tools.hxcfgfile_codec dump input.med
```

### Checksum (`checksum`)

```bash
# Verify checksum of an .hsl/.sub file
python -m standalone_med_tools.checksum verify MyMethod.hsl

# Recompute and update checksum in-place
python -m standalone_med_tools.checksum update MyMethod.hsl

# Compute raw CRC-32 from stdin
echo -n "data" | python -m standalone_med_tools.checksum compute
```

### Repair Corrupt Files (`repair_corrupt`)

```bash
# Check a file for CRLF corruption (read-only)
python -m standalone_med_tools.repair_corrupt check input.med

# Repair a corrupt file (overwrites in-place, saves .corrupt_bak)
python -m standalone_med_tools.repair_corrupt repair input.med

# Repair to a different output path
python -m standalone_med_tools.repair_corrupt repair input.med -o repaired.med

# Dry-run -- show what would happen without writing
python -m standalone_med_tools.repair_corrupt repair input.med --dry-run

# Batch repair all .med/.stp files in a directory tree
python -m standalone_med_tools.repair_corrupt repair --batch C:/Methods/

# Validate binary structure (parse and dump, no corruption check)
python -m standalone_med_tools.repair_corrupt validate input.med
```

### MED Generator (`med_generator`)

```bash
# Sync a .med file from an .hsl file
python -m standalone_med_tools.med_generator sync MyMethod.hsl

# Sync with explicit output path
python -m standalone_med_tools.med_generator sync MyMethod.hsl --med MyMethod.med

# Run the full on-save pipeline (reconcile, renumber, sync, checksum)
python -m standalone_med_tools.med_generator on-save MyMethod.hsl

# Build .med text without binary conversion (prints to stdout)
python -m standalone_med_tools.med_generator build-text MyMethod.hsl

# Sync a .stp file from an .hsl file
python -m standalone_med_tools.med_generator stp-sync MyMethod.hsl
```

### STP Generator (`stp_generator`)

```bash
# Sync a .stp file from an .hsl file
python -m standalone_med_tools.stp_generator sync MyMethod.hsl

# Sync with explicit output path
python -m standalone_med_tools.stp_generator sync MyMethod.hsl --stp MyMethod.stp
```

### Block Markers (`block_markers`)

```bash
# Generate a demo .hsl method with 5 comment steps
python -m standalone_med_tools.block_markers --steps 5 --name MyDemo

# Generate a complex demo with loops, if/else, etc.
python -m standalone_med_tools.block_markers --demo-complex

# Print the full CLSID registry
python -m standalone_med_tools.block_markers --show-clsids

# Reconcile block markers in an existing .hsl file
python -m standalone_med_tools.block_markers --reconcile MyMethod.hsl
```

## GUI Applications

All three GUI applications require Tkinter (included with standard Python on Windows).

### Codec Tester

```bash
python -m standalone_med_tools.gui_codec_tester
```

Interactive binary file conversion and testing tool:

- Browse and load binary `.med` / `.stp` files
- Convert binary → text and display the decoded result
- Edit text and convert back to binary
- Roundtrip verification (binary → text → binary) with byte comparison
- Batch roundtrip testing across an entire folder
- Structural dump of the binary container format
- File info panel with size, hex preview, and format detection

### Block Marker Tester

```bash
python -m standalone_med_tools.gui_block_marker_tester
```

Block marker parsing and validation tool:

- Browse and load `.hsl` / `.sub` files
- Parse block markers and display them in a structured tree view
- Validate block markers (row numbering, GUID format, CLSID recognition, brace balance)
- Renumber block marker rows and show the diff
- Reconcile block marker headers and show changes
- Generate demo `.hsl` methods with configurable step count
- Display the full CLSID lookup table
- Verify the CRC-32 checksum of the loaded file
- Statistics panel (step count, unique GUIDs, structural sections, etc.)

### MED Viewer

```bash
python -m standalone_med_tools.gui_med_viewer
python -m standalone_med_tools.gui_med_viewer path/to/file.med
```

Decoded `.med`/`.stp` file viewer:

- Open and auto-detect binary vs. text format files
- Decoded text view with line numbers in a monospace font
- `Ctrl+F` search with next/previous navigation and highlight-all
- Section navigation sidebar -- click a section to jump to it
- Export decoded text to `.txt`
- Repair integration -- detect and repair CRLF-corrupted files in-place
- Step summary for `.med` files (instance GUID, step type from CLSID)
- Recently opened file history (persisted across sessions)

## Running Tests

```bash
python -m pytest standalone_med_tools/tests/ -v
```

The test suite covers:

| Test Module | Covers |
|-------------|--------|
| `test_checksum.py` | CRC-32 computation, footer parsing, file verification |
| `test_codec.py` | Binary ↔ text roundtrip, container parsing, encoding |
| `test_block_markers.py` | Marker parsing, renumbering, reconciliation, CLSID registry |
| `test_med_generator.py` | `.med` text building and sync pipeline |
| `test_stp_generator.py` | `.stp` generation and device step parameter handling |

## Related Documentation

- **CODEC_REFERENCE.md** -- HxCfgFile v3 binary format specification
- **BLOCK_MARKERS.md** -- Block marker format and CLSID registry reference
- **MED_FORMAT.md** -- `.med`/`.stp` text format documentation

## License

This code is extracted from a private repository and should be treated accordingly. See the repository root [LICENSE](../LICENSE) for details.
