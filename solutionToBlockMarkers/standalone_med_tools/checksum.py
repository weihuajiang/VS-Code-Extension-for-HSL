#!/usr/bin/env python3
"""
checksum.py — CRC-32 Checksum Computation for Hamilton HSL Files

This module provides CRC-32 checksum computation that matches Hamilton's
algorithm, used in .hsl, .sub, .med, and .stp file footer lines.

Hamilton File Footer Format:
    // $$author=<name>$$valid=<0|1>$$time=<YYYY-MM-DD HH:MM>$$checksum=<8hex>$$length=<3digits>$$

    For .med/.stp files, the prefix is "*" instead of "//":
    * $$author=<name>$$valid=0$$time=<YYYY-MM-DD HH:MM>$$checksum=<8hex>$$length=<3digits>$$

CRC-32 Algorithm:
    - Polynomial: 0xEDB88320 (standard CRC-32, reflected/LSB-first)
    - Initial value: 0xFFFFFFFF
    - Final XOR: 0xFFFFFFFF
    - Data input: all file content before checksum line + the prefix up to "checksum="
    - Encoding: latin1 (ISO 8859-1) to preserve raw byte values

Usage:
    from checksum import compute_hsl_checksum, generate_checksum_line, update_checksum_in_file

    # Compute a raw checksum
    checksum = compute_hsl_checksum(content_before, prefix)

    # Generate a complete footer line
    footer = generate_checksum_line(content_before, author="admin", valid=0, prefix_char="//")

    # Update the checksum in an existing .hsl file
    update_checksum_in_file("MyMethod.hsl")

Requirements: Python 3.8+ (no external dependencies)
"""

from __future__ import annotations

import re
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict


# ─── CRC-32 Lookup Table ────────────────────────────────────────────────────────

def _build_crc32_table() -> list:
    """
    Pre-compute the CRC-32 lookup table.
    
    Uses the standard CRC-32 polynomial 0xEDB88320 (bit-reversed form of 0x04C11DB7).
    This is the same polynomial used by zlib, gzip, and most CRC-32 implementations.
    
    Returns:
        list: 256-entry lookup table for byte-at-a-time CRC-32 computation
    """
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
        table.append(crc)
    return table


# Pre-computed lookup table (module-level constant)
_CRC32_TABLE = _build_crc32_table()


# ─── Core CRC-32 Functions ──────────────────────────────────────────────────────

def crc32_hamilton(data: bytes) -> str:
    """
    Compute CRC-32 matching Hamilton's algorithm.
    
    This uses the standard CRC-32 algorithm with:
      - Polynomial: 0xEDB88320 (reflected/LSB-first)
      - Initial value: 0xFFFFFFFF
      - Final XOR: 0xFFFFFFFF
    
    This is equivalent to Python's zlib.crc32(), but implemented directly
    for portability and clarity.
    
    Args:
        data: Raw bytes to compute the checksum over
        
    Returns:
        8-character lowercase hexadecimal string (e.g. "a1b2c3d4")
        
    Example:
        >>> crc32_hamilton(b"Hello, world!")
        'ebe6c6e6'
    """
    crc = 0xFFFFFFFF
    for byte in data:
        crc = _CRC32_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return format(crc ^ 0xFFFFFFFF, '08x')


def compute_hsl_checksum(content_before: str, prefix: str) -> str:
    """
    Compute the CRC-32 checksum for a Hamilton file.
    
    The checksum is computed over all file content BEFORE the checksum line,
    concatenated with the checksum line prefix (everything up to and including
    "checksum=").
    
    IMPORTANT: Uses latin1 encoding, NOT utf-8, to preserve raw byte values.
    Hamilton files use latin1 (ISO 8859-1) encoding, and non-ASCII characters
    must be preserved as single bytes.
    
    Args:
        content_before: All file content before the checksum line (including
                       trailing \\r\\n)
        prefix: The checksum line from its start up to and including "checksum="
                (e.g., '// $$author=admin$$valid=0$$time=2024-01-01 12:00$$checksum=')
        
    Returns:
        8-character lowercase hex checksum string
        
    Example:
        >>> content = "variable x;\\r\\n"
        >>> prefix = "// $$author=admin$$valid=0$$time=2024-01-01 12:00$$checksum="
        >>> checksum = compute_hsl_checksum(content, prefix)
    """
    data = (content_before + prefix).encode("latin1")
    return crc32_hamilton(data)


# ─── Checksum Line Generation ───────────────────────────────────────────────────

def generate_checksum_line(
    content_before: str,
    author: str = "admin",
    valid: int = 0,
    prefix_char: str = "//",
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Generate a complete checksum footer line for a Hamilton file.
    
    The footer line format is:
        <prefix_char> $$author=<author>$$valid=<valid>$$time=<time>$$checksum=<hex>$$length=<len>$$
    
    Where:
        - prefix_char: "//" for .hsl/.sub files, "*" for .med/.stp files
        - author: Name of the file author (usually Windows username)
        - valid: Validation state (0=user, 1=library, 2=config)
        - time: Timestamp in "YYYY-MM-DD HH:MM" format
        - checksum: 8-character hex CRC-32
        - length: 3-digit zero-padded total line length (including \\r\\n)
    
    Args:
        content_before: All file content before the footer line (must end with \\r\\n)
        author: Author name for the footer
        valid: Validation state integer
        prefix_char: Comment prefix — "//" for .hsl/.sub, "*" for .med/.stp
        timestamp: Optional datetime; defaults to now
        
    Returns:
        Complete footer line string (without trailing newline)
        
    Example:
        >>> content = "variable x;\\r\\n"
        >>> footer = generate_checksum_line(content, author="admin")
        >>> # Returns: "// $$author=admin$$valid=0$$time=2024-01-01 12:00$$checksum=abc12345$$length=089$$"
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    time_str = timestamp.strftime("%Y-%m-%d %H:%M")
    
    # Build the prefix: everything up to and including "checksum="
    prefix = f"{prefix_char} $$author={author}$$valid={valid}$$time={time_str}$$checksum="
    
    # Compute CRC-32 over content + prefix
    checksum = compute_hsl_checksum(content_before, prefix)
    
    # Build suffix and compute line length
    suffix = "$$length="
    line_without_length = f"{prefix}{checksum}{suffix}"
    
    # Total length = line characters + 3 (NNN) + 2 ($$) + 2 (\r\n)
    total_length = len(line_without_length) + 3 + 2 + 2
    length_str = str(total_length).zfill(3)
    
    return f"{prefix}{checksum}{suffix}{length_str}$$"


def finalize_hsl_file(content: str, author: str = "admin") -> str:
    """
    Finalize an HSL file by appending a checksum line.
    
    The content should already end with \\r\\n. If it doesn't, \\r\\n is appended.
    
    Args:
        content: HSL file content without checksum line
        author: Author name for the checksum footer
        
    Returns:
        Complete file content with checksum footer line
    """
    if not content.endswith("\r\n"):
        content += "\r\n"
    footer = generate_checksum_line(content, author=author, prefix_char="//")
    return content + footer + "\r\n"


# ─── Checksum Line Parsing ──────────────────────────────────────────────────────

# Regex pattern for parsing Hamilton checksum footer lines.
# Matches both "//" prefix (for .hsl/.sub) and "*" prefix (for .med/.stp).
RE_CHECKSUM_LINE = re.compile(
    r'^(//|\*)\s*\$\$author=([^$]*)\$\$valid=(\d+)\$\$time=([^$]*)'
    r'\$\$checksum=([0-9a-fA-F]{8})\$\$length=(\d{3})\$\$\s*$'
)


def parse_checksum_line(line: str) -> Optional[Dict[str, str]]:
    """
    Parse a Hamilton checksum footer line.
    
    Args:
        line: A single line from a Hamilton file (with or without trailing whitespace)
        
    Returns:
        Dictionary with keys: prefix, author, valid, time, checksum, length
        Returns None if the line is not a valid checksum line
        
    Example:
        >>> info = parse_checksum_line('// $$author=admin$$valid=0$$time=2024-01-01 12:00$$checksum=abc12345$$length=089$$')
        >>> info['author']
        'admin'
        >>> info['checksum']
        'abc12345'
    """
    m = RE_CHECKSUM_LINE.match(line.strip())
    if not m:
        return None
    
    return {
        "prefix": m.group(1),
        "author": m.group(2),
        "valid": m.group(3),
        "time": m.group(4),
        "checksum": m.group(5).lower(),
        "length": m.group(6),
    }


# ─── File-Level Checksum Operations ─────────────────────────────────────────────

def verify_file_checksum(filepath: str) -> Dict[str, object]:
    """
    Verify the CRC-32 checksum of a Hamilton text file (.hsl or .sub).
    
    WARNING: Do NOT use this on binary files (.med, .stp). Binary files use
    a different structure that cannot be safely split on newlines.
    
    Args:
        filepath: Path to the .hsl or .sub file
        
    Returns:
        Dictionary with keys:
            - valid: bool — True if checksum matches
            - stored_checksum: str — checksum from the file
            - computed_checksum: str — freshly computed checksum
            - author: str — author name from footer
            - time: str — timestamp from footer
            - error: str or None — error message if verification failed
    """
    result = {
        "valid": False,
        "stored_checksum": "",
        "computed_checksum": "",
        "author": "",
        "time": "",
        "error": None,
    }
    
    try:
        raw = Path(filepath).read_text(encoding="latin1")
    except Exception as e:
        result["error"] = f"Failed to read file: {e}"
        return result
    
    lines = raw.split("\n")
    lines = [line.rstrip("\r") for line in lines]
    
    # Find the last checksum line
    checksum_idx = -1
    parsed = None
    for i in range(len(lines) - 1, -1, -1):
        parsed = parse_checksum_line(lines[i])
        if parsed:
            checksum_idx = i
            break
    
    if checksum_idx == -1 or parsed is None:
        result["error"] = "No checksum line found"
        return result
    
    result["stored_checksum"] = parsed["checksum"]
    result["author"] = parsed["author"]
    result["time"] = parsed["time"]
    
    # Reconstruct content before checksum line
    content_before = "\r\n".join(lines[:checksum_idx]) + "\r\n"
    
    # Build prefix
    prefix = (
        f"{parsed['prefix']} $$author={parsed['author']}$$valid={parsed['valid']}"
        f"$$time={parsed['time']}$$checksum="
    )
    
    # Compute CRC
    computed = compute_hsl_checksum(content_before, prefix)
    result["computed_checksum"] = computed
    result["valid"] = (computed == parsed["checksum"])
    
    return result


def update_checksum_in_file(filepath: str) -> None:
    """
    Recompute and replace the checksum footer line in a Hamilton text file.
    
    Works for TEXT files only: .hsl, .sub (// prefix).
    
    WARNING: Do NOT call this on binary files (.med, .stp, .smt). Binary files
    contain raw bytes that would be corrupted by text-mode line splitting.
    The split(\\n)/join(\\r\\n) approach inserts 0x0D before every 0x0A byte
    found in the binary stream, corrupting var-string length prefixes and
    token data.
    
    Args:
        filepath: Path to the .hsl or .sub file to update
        
    Raises:
        ValueError: If the file has no checksum line
        ValueError: If the file is a binary container (.med/.stp/.smt)
    """
    # Guard: refuse to process binary container files
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".med", ".stp", ".smt"):
        raise ValueError(
            f"Cannot update checksum on binary file {os.path.basename(filepath)}. "
            "Binary files use a different structure."
        )
    
    # Read with latin1 to preserve raw bytes
    raw = Path(filepath).read_text(encoding="latin1")
    lines = raw.split("\n")
    lines = [line.rstrip("\r") for line in lines]
    
    # Find the last checksum line
    checksum_idx = -1
    parsed = None
    for i in range(len(lines) - 1, -1, -1):
        parsed = parse_checksum_line(lines[i])
        if parsed:
            checksum_idx = i
            break
    
    if checksum_idx == -1 or parsed is None:
        raise ValueError("No checksum line found in file")
    
    # Preserve original author and valid values
    author = parsed["author"]
    valid = int(parsed["valid"])
    prefix_char = parsed["prefix"]
    
    # Everything before the checksum line
    content_before = "\r\n".join(lines[:checksum_idx]) + "\r\n"
    
    # Generate new checksum line
    new_line = generate_checksum_line(
        content_before, author=author, valid=valid, prefix_char=prefix_char
    )
    
    # Replace and write
    lines[checksum_idx] = new_line
    output = "\r\n".join(lines)
    Path(filepath).write_text(output, encoding="latin1", newline="")


# ─── CLI Entry Point ────────────────────────────────────────────────────────────

def main() -> int:
    """CLI entry point for checksum operations."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Hamilton HSL CRC-32 checksum utility"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    
    # verify command
    p_verify = sub.add_parser("verify", help="Verify checksum of an .hsl/.sub file")
    p_verify.add_argument("file", type=str, help="Path to the .hsl or .sub file")
    
    # update command
    p_update = sub.add_parser("update", help="Update checksum in an .hsl/.sub file")
    p_update.add_argument("file", type=str, help="Path to the .hsl or .sub file")
    
    # compute command (raw CRC-32)
    p_compute = sub.add_parser("compute", help="Compute raw CRC-32 of bytes from stdin")
    
    args = parser.parse_args()
    
    if args.cmd == "verify":
        result = verify_file_checksum(args.file)
        print(f"File: {args.file}")
        print(f"  Author:   {result['author']}")
        print(f"  Time:     {result['time']}")
        print(f"  Stored:   {result['stored_checksum']}")
        print(f"  Computed: {result['computed_checksum']}")
        if result["error"]:
            print(f"  Error:    {result['error']}")
            return 1
        if result["valid"]:
            print(f"  Status:   VALID ✓")
            return 0
        else:
            print(f"  Status:   MISMATCH ✗")
            return 1
    
    elif args.cmd == "update":
        try:
            update_checksum_in_file(args.file)
            print(f"Checksum updated: {args.file}")
            return 0
        except Exception as e:
            print(f"Error: {e}")
            return 1
    
    elif args.cmd == "compute":
        import sys
        data = sys.stdin.buffer.read()
        print(crc32_hamilton(data))
        return 0
    
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
