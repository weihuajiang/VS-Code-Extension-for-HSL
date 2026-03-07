#!/usr/bin/env python3
"""
Repair Tool for Hamilton .med / .stp Files Corrupted by CRLF Normalization
==========================================================================

Root Cause
----------
The VS Code extension's ``updateChecksumInFile()`` function (in
``medGenerator.ts``) formerly read binary .med / .stp files as text,
split lines on ``\\r?\\n``, and rejoined them with ``\\r\\n``.  This
inserted a ``0x0D`` byte before every lone ``0x0A`` in the binary stream.

Because the HxCfgFile v3 container stores string lengths as inline byte
values (short-string: 1-byte prefix; var-string: 1-byte or 0xFF + u16-LE
prefix), prepending ``0x0D`` before ``0x0A`` shifts all downstream data
by one byte per occurrence.  The result is that length prefixes no longer
match their payloads, and the Hamilton Method Editor fails with
"Reached end-of-file while parsing…".

Repair Strategy
---------------
1. **Strip** -- replace every ``0x0D 0x0A`` pair with a lone ``0x0A``.
   This undoes the CRLF normalization and restores the original binary
   structure.
2. **Parse** -- decode the resulting binary through the HxCfgFile v3 codec.
   If parsing succeeds the structure is sound.
3. **Rebuild** -- emit a clean binary from the parsed model.  The codec
   writes legitimate ``\\r\\n`` sequences in the footer/metadata, so the
   output is byte-for-byte correct.

The only data loss is that token strings which originally contained
``\\r\\n`` (e.g., Comment text) will lose their ``\\r``.  In practice this
is harmless -- the Hamilton Method Editor re-normalizes these on the next
save.

CLI Usage
---------
::

    # Check a single file
    python -m standalone_med_tools.repair_corrupt check  input.med

    # Repair a single file (overwrites in-place, saves .corrupt_bak)
    python -m standalone_med_tools.repair_corrupt repair input.med

    # Repair to a different output path
    python -m standalone_med_tools.repair_corrupt repair input.med -o repaired.med

    # Dry-run -- show what would happen without writing anything
    python -m standalone_med_tools.repair_corrupt repair input.med --dry-run

    # Batch mode -- process every .med / .stp in a directory tree
    python -m standalone_med_tools.repair_corrupt repair --batch C:/Methods/

    # Validate binary structure (no corruption check, just parse and dump)
    python -m standalone_med_tools.repair_corrupt validate input.med

Requirements: Python 3.8+  (no external dependencies)
"""

from __future__ import annotations

import argparse
import os
import shutil
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .hxcfgfile_codec import HxCfgTextModel, parse_binary_med, build_binary_med


# ---------------------------------------------------------------------------
# Byte-level analysis helpers
# ---------------------------------------------------------------------------

def _count_byte_patterns(data: bytes) -> Dict[str, int]:
    """Count diagnostic byte patterns in *data*.

    Returns a dict with the following keys:

    * ``lone_lf``   -- count of ``0x0A`` bytes **not** preceded by ``0x0D``
    * ``crlf_pairs`` -- count of ``0x0D 0x0A`` pairs
    * ``total_lf``  -- ``lone_lf + crlf_pairs``
    * ``lone_cr``   -- count of ``0x0D`` bytes **not** followed by ``0x0A``
    * ``size``      -- total byte count of *data*

    This is the foundational metric used by :func:`detect_corruption`.
    """
    lone_lf: int = 0
    crlf_pairs: int = 0
    lone_cr: int = 0

    i = 0
    length = len(data)
    while i < length:
        b = data[i]
        if b == 0x0D:
            if i + 1 < length and data[i + 1] == 0x0A:
                crlf_pairs += 1
                i += 2
                continue
            else:
                lone_cr += 1
        elif b == 0x0A:
            lone_lf += 1
        i += 1

    return {
        "lone_lf": lone_lf,
        "crlf_pairs": crlf_pairs,
        "total_lf": lone_lf + crlf_pairs,
        "lone_cr": lone_cr,
        "size": length,
    }


def detect_corruption(data: bytes) -> Dict[str, object]:
    """Analyze a binary .med / .stp file for CRLF-normalization corruption.

    A healthy HxCfgFile v3 binary contains a mix of lone ``0x0A`` bytes
    (inside length prefixes and token data) **and** ``0x0D 0x0A`` pairs
    (in the metadata footer and occasionally inside token strings).

    A CRLF-corrupted file has *zero* lone ``0x0A`` bytes -- every single
    one was paired with a preceding ``0x0D``.  The heuristic fires when
    the file contains more than five ``0x0A`` bytes total and none of
    them are standalone.

    Parameters
    ----------
    data : bytes
        Raw file contents.

    Returns
    -------
    dict
        Keys:

        * ``is_corrupt`` (*bool*) -- ``True`` when corruption is detected.
        * ``lone_lf`` (*int*) -- number of lone ``0x0A`` bytes.
        * ``crlf_pairs`` (*int*) -- number of ``0x0D 0x0A`` pairs.
        * ``total_lf`` (*int*) -- ``lone_lf + crlf_pairs``.
        * ``lone_cr`` (*int*) -- stray ``0x0D`` bytes (unusual).
        * ``size`` (*int*) -- total file size.
        * ``estimated_extra_bytes`` (*int*) -- bytes added by corruption
          (equal to ``crlf_pairs`` when corrupt, else 0).
    """
    counts = _count_byte_patterns(data)

    is_corrupt: bool = counts["total_lf"] > 5 and counts["lone_lf"] == 0

    return {
        "is_corrupt": is_corrupt,
        "lone_lf": counts["lone_lf"],
        "crlf_pairs": counts["crlf_pairs"],
        "total_lf": counts["total_lf"],
        "lone_cr": counts["lone_cr"],
        "size": counts["size"],
        "estimated_extra_bytes": counts["crlf_pairs"] if is_corrupt else 0,
    }


# ---------------------------------------------------------------------------
# Byte-level corruption detail report
# ---------------------------------------------------------------------------

def byte_level_corruption_report(
    data: bytes,
    *,
    context: int = 8,
    max_sites: int = 50,
) -> List[Dict[str, object]]:
    """Return a list of corruption sites with surrounding byte context.

    Each entry is a dict with:

    * ``offset`` -- file offset of the ``0x0D`` byte in the pair.
    * ``context_hex`` -- hex dump of the surrounding bytes.
    * ``context_ascii`` -- printable-ASCII representation (non-printable → ``.``).

    Parameters
    ----------
    data : bytes
        Raw (possibly corrupt) file contents.
    context : int
        Number of bytes to include before and after the site.
    max_sites : int
        Maximum number of sites to report (to keep output manageable).

    Returns
    -------
    list[dict]
        One dict per ``0x0D 0x0A`` site found, up to *max_sites*.
    """
    sites: List[Dict[str, object]] = []
    i = 0
    length = len(data)
    while i < length - 1 and len(sites) < max_sites:
        if data[i] == 0x0D and data[i + 1] == 0x0A:
            start = max(0, i - context)
            end = min(length, i + 2 + context)
            window = data[start:end]
            hex_str = " ".join(f"{b:02X}" for b in window)
            ascii_str = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in window)
            sites.append({
                "offset": i,
                "context_hex": hex_str,
                "context_ascii": ascii_str,
            })
            i += 2
        else:
            i += 1
    return sites


# ---------------------------------------------------------------------------
# Repair logic
# ---------------------------------------------------------------------------

def strip_crlf(data: bytes) -> bytes:
    """Replace every ``0x0D 0x0A`` pair with a lone ``0x0A``.

    This is the first step of the repair pipeline: it undoes the blanket
    CRLF normalization that was applied to a binary file.

    Parameters
    ----------
    data : bytes
        Raw (corrupted) file contents.

    Returns
    -------
    bytes
        Data with all ``0x0D 0x0A`` collapsed to ``0x0A``.
    """
    result = bytearray()
    i = 0
    length = len(data)
    while i < length:
        if i + 1 < length and data[i] == 0x0D and data[i + 1] == 0x0A:
            result.append(0x0A)
            i += 2
        else:
            result.append(data[i])
            i += 1
    return bytes(result)


def repair_crlf_corruption(data: bytes) -> bytes:
    """Fully repair a CRLF-corrupted HxCfgFile v3 binary.

    Performs the three-step pipeline:

    1. :func:`strip_crlf` -- remove all ``0x0D`` preceding ``0x0A``.
    2. :func:`parse_binary_med` -- decode the binary into an in-memory model.
    3. :func:`build_binary_med` -- re-encode to a clean binary.

    Step 3 is essential because the codec knows which ``\\r\\n`` sequences
    are *legitimate* (e.g., in the footer) and writes them back correctly.

    Parameters
    ----------
    data : bytes
        Raw corrupted file contents.

    Returns
    -------
    bytes
        Repaired binary that should be byte-for-byte valid.

    Raises
    ------
    Exception
        If the stripped binary still cannot be parsed, the file may be
        too damaged for automatic repair.
    """
    stripped = strip_crlf(data)
    model: HxCfgTextModel = parse_binary_med(stripped)
    return build_binary_med(model)


# ---------------------------------------------------------------------------
# Validation / structure dump
# ---------------------------------------------------------------------------

def validate_binary(data: bytes) -> Tuple[bool, str]:
    """Parse a binary .med / .stp file and return a structural summary.

    This function does **not** attempt corruption repair -- it parses the
    raw bytes as-is.  Use it on healthy files (or post-repair) to verify
    structural integrity.

    Parameters
    ----------
    data : bytes
        Raw file contents.

    Returns
    -------
    tuple[bool, str]
        ``(success, report)`` where *success* is ``True`` when parsing
        succeeds and *report* is a multi-line human-readable summary.
    """
    lines: List[str] = []
    lines.append(f"File size: {len(data)} bytes")

    # Header quick-peek
    if len(data) >= 4:
        version = struct.unpack_from("<H", data, 0)[0]
        type_marker = struct.unpack_from("<H", data, 2)[0]
        lines.append(f"Header: version={version}, type_marker={type_marker}")
    else:
        lines.append("Header: file too short to read header")
        return False, "\n".join(lines)

    try:
        model: HxCfgTextModel = parse_binary_med(data)
    except Exception as exc:
        lines.append(f"Parse FAILED: {exc}")
        return False, "\n".join(lines)

    lines.append("Parse: OK")

    # Named section
    if model.named_section is not None:
        ns = model.named_section
        val_preview = ns.value[:60] + ("…" if len(ns.value) > 60 else "")
        lines.append(f"Named section: name={ns.name!r}, key={ns.key!r}, "
                      f"value_len={len(ns.value)}, preview={val_preview!r}")
    else:
        lines.append("Named section: (none)")

    # HxPars sections
    lines.append(f"HxPars sections: {len(model.hxpars_sections)}")
    for idx, sec in enumerate(model.hxpars_sections):
        lines.append(f"  [{idx}] key={sec.key!r}, tokens={len(sec.tokens)}")

    # Footer
    if model.footer:
        footer_preview = model.footer[:80] + ("…" if len(model.footer) > 80 else "")
        lines.append(f"Footer: {footer_preview!r}")
    else:
        lines.append("Footer: (none)")

    return True, "\n".join(lines)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_diag(diag: Dict[str, object], *, indent: str = "  ") -> str:
    """Format a corruption-diagnostic dict as a multi-line string.

    Parameters
    ----------
    diag : dict
        Result from :func:`detect_corruption`.
    indent : str
        Prefix for each line.

    Returns
    -------
    str
        Human-readable diagnostic block.
    """
    lines = [
        f"{indent}Size:                 {diag['size']} bytes",
        f"{indent}CRLF pairs (0D 0A):   {diag['crlf_pairs']}",
        f"{indent}Lone LF (0A only):    {diag['lone_lf']}",
        f"{indent}Lone CR (0D only):    {diag['lone_cr']}",
        f"{indent}Total LF:             {diag['total_lf']}",
        f"{indent}Corrupt:              {'YES' if diag['is_corrupt'] else 'no'}",
    ]
    if diag["is_corrupt"]:
        lines.append(
            f"{indent}Est. extra bytes:     {diag['estimated_extra_bytes']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File discovery for batch mode
# ---------------------------------------------------------------------------

def discover_files(root: Path, extensions: Sequence[str] = (".med", ".stp")) -> List[Path]:
    """Recursively discover Hamilton binary files under *root*.

    Parameters
    ----------
    root : Path
        Starting directory (or single file).
    extensions : sequence of str
        File extensions to include (case-insensitive).

    Returns
    -------
    list[Path]
        Sorted list of matching file paths.
    """
    ext_set = {e.lower() for e in extensions}

    if root.is_file():
        if root.suffix.lower() in ext_set:
            return [root]
        return []

    found: List[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in ext_set:
                found.append(p)
    found.sort()
    return found


# ---------------------------------------------------------------------------
# Single-file processing
# ---------------------------------------------------------------------------

def _process_one_file(
    path: Path,
    *,
    output: Optional[Path] = None,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> Tuple[bool, str]:
    """Check and optionally repair a single file.

    Parameters
    ----------
    path : Path
        Input file.
    output : Path or None
        Explicit output path.  ``None`` means overwrite in-place
        (a ``.corrupt_bak`` backup is created first).
    force : bool
        Repair even if corruption is not detected.
    dry_run : bool
        If ``True``, report what would happen but do not write anything.
    verbose : bool
        If ``True``, include byte-level corruption site listing.

    Returns
    -------
    tuple[bool, str]
        ``(repaired, message)`` -- *repaired* is ``True`` when the file
        was (or would be) written; *message* is a human-readable report.
    """
    lines: List[str] = []
    data = path.read_bytes()
    diag = detect_corruption(data)

    lines.append(f"File: {path}")
    lines.append(_format_diag(diag))

    if verbose and diag["is_corrupt"]:
        sites = byte_level_corruption_report(data, max_sites=20)
        if sites:
            lines.append("  Corruption sites (first 20):")
            for s in sites:
                lines.append(
                    f"    offset 0x{s['offset']:06X}: "
                    f"{s['context_hex']}  |{s['context_ascii']}|"
                )

    if not diag["is_corrupt"] and not force:
        lines.append("  Status: OK -- file does not appear corrupted.")
        return False, "\n".join(lines)

    # Attempt repair
    try:
        repaired = repair_crlf_corruption(data)
    except Exception as exc:
        lines.append(f"  Repair FAILED: {exc}")
        lines.append("  The file may be too damaged for automatic repair.")
        return False, "\n".join(lines)

    repaired_diag = detect_corruption(repaired)
    lines.append("  After repair:")
    lines.append(f"    Size:       {len(repaired)} bytes (was {len(data)})")
    lines.append(f"    CRLF pairs: {repaired_diag['crlf_pairs']}")
    lines.append(f"    Lone LF:    {repaired_diag['lone_lf']}")
    lines.append(f"    Delta:      {len(data) - len(repaired)} bytes removed")

    # Validate repaired binary
    try:
        parse_binary_med(repaired)
        lines.append("    Validation: OK (binary parses correctly)")
    except Exception as exc:
        lines.append(f"    Validation: FAILED ({exc})")
        lines.append("  Aborting -- repaired file is not valid.")
        return False, "\n".join(lines)

    if dry_run:
        dest = output or path
        lines.append(f"  Dry-run: would write repaired file to {dest}")
        return True, "\n".join(lines)

    dest = output or path
    if dest == path:
        bak = path.with_suffix(path.suffix + ".corrupt_bak")
        shutil.copy2(path, bak)
        lines.append(f"  Backup:  {bak}")

    dest.write_bytes(repaired)
    lines.append(f"  Written: {dest}")
    return True, "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI -- subcommands
# ---------------------------------------------------------------------------

def _cmd_check(args: argparse.Namespace) -> int:
    """``check`` subcommand -- report corruption without modifying files.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments with ``input`` (Path) and ``verbose`` (bool).

    Returns
    -------
    int
        Exit code: 1 if corrupt, 0 if healthy.
    """
    path: Path = args.input
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 2

    data = path.read_bytes()
    diag = detect_corruption(data)

    print(f"File: {path}")
    print(_format_diag(diag))

    if args.verbose and diag["is_corrupt"]:
        sites = byte_level_corruption_report(data, max_sites=30)
        if sites:
            print("  Corruption sites (up to 30):")
            for s in sites:
                print(
                    f"    offset 0x{s['offset']:06X}: "
                    f"{s['context_hex']}  |{s['context_ascii']}|"
                )

    return 1 if diag["is_corrupt"] else 0


def _cmd_repair(args: argparse.Namespace) -> int:
    """``repair`` subcommand -- repair one or more corrupt files.

    Supports single-file and ``--batch`` modes, ``--dry-run``, ``--force``,
    and ``--verbose`` flags.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.

    Returns
    -------
    int
        Exit code: 0 on success, 1 on failure.
    """
    # Determine file list
    if args.batch:
        root = args.input
        if not root.is_dir():
            print(f"Error: --batch requires a directory, got: {root}", file=sys.stderr)
            return 2
        files = discover_files(root)
        if not files:
            print(f"No .med/.stp files found under {root}")
            return 0
        print(f"Batch mode: found {len(files)} file(s) under {root}\n")
    else:
        if not args.input.exists():
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            return 2
        files = [args.input]

    output: Optional[Path] = getattr(args, "output", None)
    if output and args.batch:
        print("Error: --output cannot be used with --batch", file=sys.stderr)
        return 2

    repaired_count = 0
    failed_count = 0
    skipped_count = 0

    for fpath in files:
        try:
            did_repair, msg = _process_one_file(
                fpath,
                output=output,
                force=args.force,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )
        except Exception as exc:
            msg = f"File: {fpath}\n  Unexpected error: {exc}"
            did_repair = False
            failed_count += 1

        print(msg)
        print()

        if did_repair:
            repaired_count += 1
        elif "FAILED" in msg:
            failed_count += 1
        else:
            skipped_count += 1

    if args.batch:
        print(f"Summary: {repaired_count} repaired, "
              f"{skipped_count} skipped (healthy), "
              f"{failed_count} failed")

    return 1 if failed_count > 0 else 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """``validate`` subcommand -- parse a binary file and report its structure.

    This does **not** perform corruption repair; it reads the file as-is
    and reports whether it can be parsed and what its internal structure
    looks like.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments with ``input`` (Path).

    Returns
    -------
    int
        Exit code: 0 if valid, 1 if parse fails.
    """
    path: Path = args.input
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 2

    data = path.read_bytes()
    success, report = validate_binary(data)
    print(report)
    return 0 if success else 1


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser with all subcommands.

    Returns
    -------
    argparse.ArgumentParser
        Fully configured parser ready for ``parse_args()``.
    """
    parser = argparse.ArgumentParser(
        prog="repair_corrupt",
        description=(
            "Detect and repair Hamilton .med / .stp files corrupted by "
            "CRLF normalization.  Can also validate the binary structure "
            "of healthy files."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- check ---------------------------------------------------------------
    p_check = subparsers.add_parser(
        "check",
        help="Check a file for CRLF corruption (read-only)",
    )
    p_check.add_argument("input", type=Path, help="Path to a .med or .stp file")
    p_check.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show byte-level corruption site listing",
    )

    # -- repair --------------------------------------------------------------
    p_repair = subparsers.add_parser(
        "repair",
        help="Repair corrupt file(s)",
    )
    p_repair.add_argument(
        "input",
        type=Path,
        help="Path to a .med / .stp file (or directory with --batch)",
    )
    p_repair.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output path (default: overwrite in-place with .corrupt_bak backup)",
    )
    p_repair.add_argument(
        "--batch",
        action="store_true",
        help="Treat INPUT as a directory and repair all .med / .stp files recursively",
    )
    p_repair.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing any files",
    )
    p_repair.add_argument(
        "--force",
        action="store_true",
        help="Repair even if corruption is not detected",
    )
    p_repair.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show byte-level corruption detail",
    )

    # -- validate ------------------------------------------------------------
    p_validate = subparsers.add_parser(
        "validate",
        help="Parse a binary file and report its internal structure",
    )
    p_validate.add_argument("input", type=Path, help="Path to a .med or .stp file")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point.

    Parameters
    ----------
    argv : list[str] or None
        Command-line arguments.  ``None`` uses ``sys.argv[1:]``.

    Returns
    -------
    int
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "check": _cmd_check,
        "repair": _cmd_repair,
        "validate": _cmd_validate,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
