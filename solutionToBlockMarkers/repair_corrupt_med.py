#!/usr/bin/env python3
"""
Repair tool for Hamilton .med/.stp files corrupted by CRLF normalization.

Root cause (fixed in medGenerator.ts):
  updateChecksumInFile() was called on binary .med/.stp files. It read them
  as text, split on \\r?\\n, and rejoined with \\r\\n — inserting a 0x0D byte
  before every lone 0x0A in the binary stream. This corrupts var-string
  length prefixes and token data, making the file unparseable by the
  Hamilton Method Editor ("Reached end-of-file while parsing...").

Repair strategy:
  1. Replace every 0x0D 0x0A pair with lone 0x0A (undoes the CRLF normalization)
  2. Parse the resulting binary with the HxCfgFile v3 codec (structure is now valid)
  3. Rebuild the binary from the parsed model (restores legitimate CRLF in tokens)

  The only data loss is that token strings which originally contained \\r\\n
  (e.g., Comment text) will lose their \\r. In practice this is harmless —
  Hamilton re-normalizes these on the next Method Editor save.

Usage:
  python repair_corrupt_med.py <corrupt_file> [<output_file>]

  If <output_file> is omitted, the repaired file overwrites the original
  (a .corrupt_bak backup is created first).
"""

from __future__ import annotations

import argparse
import shutil
import struct
import sys
from pathlib import Path

# Import the codec from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from hxcfgfile_codec import parse_binary_med, build_binary_med


def detect_corruption(data: bytes) -> dict:
    """Analyze a binary file for CRLF-normalization corruption.
    
    Returns a dict with diagnostic info:
      - is_corrupt: True if the file appears corrupted
      - lone_lf: count of lone 0x0A bytes (not preceded by 0x0D)
      - crlf_pairs: count of 0x0D 0x0A pairs
      - total_lf: total count of 0x0A bytes
    """
    lone_lf = 0
    crlf_pairs = 0
    for i in range(len(data)):
        if data[i] == 0x0A:
            if i > 0 and data[i - 1] == 0x0D:
                crlf_pairs += 1
            else:
                lone_lf += 1

    total_lf = lone_lf + crlf_pairs

    # A healthy binary file has a mix of lone 0x0A (length prefixes, token data)
    # and 0x0D 0x0A pairs (footer, some token strings).
    # A corrupted file has 0 lone 0x0A — every single one was paired with 0x0D.
    # Heuristic: if there are many 0x0A bytes but zero lone ones, it's corrupt.
    is_corrupt = total_lf > 5 and lone_lf == 0

    return {
        "is_corrupt": is_corrupt,
        "lone_lf": lone_lf,
        "crlf_pairs": crlf_pairs,
        "total_lf": total_lf,
    }


def repair_crlf_corruption(data: bytes) -> bytes:
    """Remove CRLF normalization from a binary HxCfgFile.

    Replaces every 0x0D 0x0A pair with lone 0x0A, then re-parses and
    rebuilds the binary to restore correct structure including legitimate
    CRLF in token strings.
    """
    # Step 1: Strip all 0x0D before 0x0A → restores original structure
    stripped = bytearray()
    i = 0
    while i < len(data):
        if i + 1 < len(data) and data[i] == 0x0D and data[i + 1] == 0x0A:
            stripped.append(0x0A)  # keep just the 0x0A
            i += 2
        else:
            stripped.append(data[i])
            i += 1

    # Step 2: Parse the now-valid binary structure
    model = parse_binary_med(bytes(stripped))

    # Step 3: Rebuild binary (codec writes correct CRLF in footer etc.)
    return build_binary_med(model)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair Hamilton .med/.stp files corrupted by CRLF normalization"
    )
    parser.add_argument("input", type=Path, help="Path to the corrupt .med or .stp file")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="Output path (default: overwrite input, saving .corrupt_bak)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check for corruption, don't repair",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Repair even if corruption is not detected",
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        return 1

    data = args.input.read_bytes()
    diag = detect_corruption(data)

    print(f"File: {args.input}")
    print(f"  Size:       {len(data)} bytes")
    print(f"  CRLF pairs: {diag['crlf_pairs']}")
    print(f"  Lone LF:    {diag['lone_lf']}")
    print(f"  Total LF:   {diag['total_lf']}")
    print(f"  Corrupt:    {'YES' if diag['is_corrupt'] else 'no'}")

    if args.check:
        return 1 if diag["is_corrupt"] else 0

    if not diag["is_corrupt"] and not args.force:
        print("\nFile does not appear corrupted. Use --force to repair anyway.")
        return 0

    try:
        repaired = repair_crlf_corruption(data)
    except Exception as e:
        print(f"\nRepair failed: {e}", file=sys.stderr)
        print("The file may be too damaged to repair automatically.", file=sys.stderr)
        return 1

    # Verify the repaired file
    repaired_diag = detect_corruption(repaired)
    print(f"\nRepaired file:")
    print(f"  Size:       {len(repaired)} bytes (was {len(data)})")
    print(f"  CRLF pairs: {repaired_diag['crlf_pairs']}")
    print(f"  Lone LF:    {repaired_diag['lone_lf']}")
    print(f"  Size delta: {len(data) - len(repaired)} bytes removed")

    # Verify round-trip: parse the repaired binary and check it's valid
    try:
        parse_binary_med(repaired)
        print("  Validation: OK (binary parses correctly)")
    except Exception as e:
        print(f"  Validation: FAILED ({e})", file=sys.stderr)
        print("Aborting — repaired file is not valid.", file=sys.stderr)
        return 1

    output = args.output or args.input
    if output == args.input:
        bak = args.input.with_suffix(args.input.suffix + ".corrupt_bak")
        shutil.copy2(args.input, bak)
        print(f"\n  Backup: {bak}")

    output.write_bytes(repaired)
    print(f"  Written: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
