#!/usr/bin/env python3
"""
Hamilton VENUS .pkg Unpackager
==============================
Extracts files from Hamilton VENUS .pkg package files.

The .pkg format uses "HamPkg" magic bytes, a 46-byte header, an entry table
(36 bytes per entry), zlib-compressed data blocks, and an HxPars manifest
that maps entry IDs to installation file paths.

See Hamilton_PKG_Format.md for the full format specification.

Usage:
    python extract_pkg.py <file.pkg> [output_dir]
    python extract_pkg.py --info <file.pkg>

Examples:
    python extract_pkg.py "Vantage IDL Tools Demo 230215.pkg"
    python extract_pkg.py "Vantage IDL Tools Demo 230215.pkg" ./my_output
    python extract_pkg.py --info "Vantage IDL Tools Demo 230215.pkg"
"""

import argparse
import os
import re
import struct
import sys
import zlib
from datetime import datetime, timezone, timedelta


# ── Constants ──────────────────────────────────────────────────────────────────

MAGIC = b'HamPkg'
HEADER_SIZE = 46
ENTRY_SIZE = 36
KEY_ENTRY_ID = b'347734013'
KEY_REL_PATH = b'347734014'
KEY_ABS_PATH = b'347734015'

# Windows FILETIME epoch: Jan 1, 1601 UTC
FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


# ── Format Parsing ─────────────────────────────────────────────────────────────

def filetime_to_datetime(low, high):
    """Convert a Windows FILETIME (two uint32 LE halves) to a Python datetime."""
    ticks = (high << 32) | low
    if ticks == 0:
        return None
    microseconds = ticks // 10  # 100-ns intervals -> microseconds
    return FILETIME_EPOCH + timedelta(microseconds=microseconds)


def parse_header(buf):
    """Parse the 46-byte .pkg header. Returns a dict of header fields."""
    if len(buf) < HEADER_SIZE:
        raise ValueError(f'File too small ({len(buf)} bytes) to contain a valid header')
    if buf[0:6] != MAGIC:
        raise ValueError(f'Not a Hamilton .pkg file (expected magic "HamPkg", got {buf[0:6]!r})')

    entry_count = struct.unpack_from('<H', buf, 14)[0]
    ft_lo, ft_hi = struct.unpack_from('<II', buf, 18)
    created = filetime_to_datetime(ft_lo, ft_hi)
    version = buf[26:46].split(b'\x00')[0].decode('ascii', errors='replace')
    fmt_ver = struct.unpack_from('<H', buf, 8)[0]
    fmt_sub = struct.unpack_from('<H', buf, 10)[0]

    return {
        'format_version': f'{fmt_ver}.{fmt_sub}',
        'entry_count': entry_count,
        'created': created,
        'venus_version': version,
    }


def parse_entry_table(buf, entry_count):
    """Parse the entry table into a list of entry dicts."""
    entries = []
    for i in range(entry_count):
        off = HEADER_SIZE + i * ENTRY_SIZE
        entry_id = buf[off:off + 7].decode('ascii', errors='replace').rstrip('\x00')
        flags = struct.unpack_from('<I', buf, off + 8)[0]
        cr_lo, cr_hi = struct.unpack_from('<II', buf, off + 12)
        mod_lo, mod_hi = struct.unpack_from('<II', buf, off + 20)
        data_offset = struct.unpack_from('<I', buf, off + 28)[0]
        data_size = struct.unpack_from('<I', buf, off + 32)[0]

        entries.append({
            'index': i,
            'id': entry_id,
            'flags': flags,
            'created': filetime_to_datetime(cr_lo, cr_hi),
            'modified': filetime_to_datetime(mod_lo, mod_hi),
            'data_offset': data_offset,
            'data_size': data_size,
        })
    return entries


def decompress_entry(buf, entry):
    """Decompress a single entry's zlib data block. Returns the raw bytes."""
    off = entry['data_offset']
    uncompressed_size = struct.unpack_from('<I', buf, off)[0]
    compressed_size = struct.unpack_from('<I', buf, off + 4)[0]
    data = zlib.decompress(buf[off + 8:off + 8 + compressed_size])
    if len(data) != uncompressed_size:
        print(f'  Warning: entry {entry["id"]} size mismatch '
              f'(expected {uncompressed_size}, got {len(data)})', file=sys.stderr)
    return data


def parse_manifest(manifest_data):
    """
    Parse the HxPars,McListData manifest to build a mapping of
    entry hex ID -> absolute installation path.
    """
    file_map = {}
    pos = 0
    while pos < len(manifest_data):
        id_idx = manifest_data.find(KEY_ENTRY_ID, pos)
        if id_idx == -1:
            break

        after_id = id_idx + len(KEY_ENTRY_ID)
        if after_id >= len(manifest_data):
            break

        id_len = manifest_data[after_id]
        if 0 < id_len < 20 and after_id + 1 + id_len <= len(manifest_data):
            entry_id = manifest_data[after_id + 1:after_id + 1 + id_len].decode('ascii', errors='replace')
            if re.match(r'^[0-9a-f]+$', entry_id):
                # Look for the absolute path key within 200 bytes forward
                search_end = min(after_id + 300, len(manifest_data))
                search_buf = manifest_data[after_id:search_end]
                path_idx = search_buf.find(KEY_ABS_PATH)
                if path_idx != -1:
                    path_start = after_id + path_idx + len(KEY_ABS_PATH)
                    path_len = manifest_data[path_start]
                    if 0 < path_len and path_start + 1 + path_len <= len(manifest_data):
                        abs_path = manifest_data[path_start + 1:path_start + 1 + path_len].decode(
                            'utf-8', errors='replace')
                        file_map[entry_id] = abs_path

        pos = after_id + 1

    return file_map


def parse_trailer(buf):
    """Parse the $$key=value$$ trailer at the end of the file."""
    # The trailer is at most ~100 bytes at the end
    tail = buf[-120:].decode('ascii', errors='replace')
    match = re.search(r'\$\$author=(.+?)\$\$valid=(.+?)\$\$time=(.+?)\$\$checksum=(.+?)\$\$length=(.+?)\$\$', tail)
    if match:
        return {
            'author': match.group(1),
            'valid': match.group(2),
            'time': match.group(3),
            'checksum': match.group(4),
            'length': match.group(5),
        }
    return None


def abs_path_to_relative(abs_path):
    """Convert an absolute Hamilton install path to a relative path for extraction."""
    lower = abs_path.lower()
    hamilton_idx = lower.find('\\hamilton\\')
    if hamilton_idx >= 0:
        return abs_path[hamilton_idx + len('\\hamilton\\'):]
    # Fall back: strip drive letter and leading path separators
    if len(abs_path) > 2 and abs_path[1] == ':':
        return abs_path[2:].lstrip('\\/')
    return os.path.basename(abs_path)


def detect_content_type(data):
    """Identify a decompressed entry's content type by magic bytes."""
    if len(data) < 4:
        return 'unknown'
    b = data[:4]
    if b == b'\x03\x00\x01\x00':
        return 'HxPars'
    if b == b'\x02\x00\x01\x00':
        return 'Metadata'
    if b[:2] == b'\x89\x50':
        return 'PNG'
    if b[:2] == b'BM':
        return 'BMP'
    if b == b'ITSF':
        return 'CHM'
    if b == b'\xd0\xcf\x11\xe0':
        return 'OLE/XLS'
    if b == b'PK\x03\x04':
        return 'ZIP/XLSX'
    if b[:2] == b'\xff\xfe':
        return 'UTF-16LE'
    text_start = data[:20].decode('ascii', errors='replace')
    if text_start.startswith(('//', '/*', '#pragma', '#include', 'function', 'namespace',
                               'variable', 'method', 'global', 'static')):
        return 'HSL Source'
    return 'Text/Other'


# ── Commands ───────────────────────────────────────────────────────────────────

def show_info(pkg_path):
    """Print package information without extracting."""
    with open(pkg_path, 'rb') as f:
        buf = f.read()

    header = parse_header(buf)
    entries = parse_entry_table(buf, header['entry_count'])
    trailer = parse_trailer(buf)

    # Find and parse manifest
    manifest_entry = next((e for e in entries if e['flags'] == 0), None)
    file_map = {}
    if manifest_entry:
        manifest_data = decompress_entry(buf, manifest_entry)
        file_map = parse_manifest(manifest_data)

    # Header info
    print(f'File:            {os.path.basename(pkg_path)}')
    print(f'File size:       {len(buf):,} bytes')
    print(f'Format version:  {header["format_version"]}')
    print(f'VENUS version:   {header["venus_version"]}')
    print(f'Created:         {header["created"].strftime("%Y-%m-%d %H:%M:%S UTC") if header["created"] else "unknown"}')
    print(f'Total entries:   {header["entry_count"]} ({header["entry_count"] - 1} files + 1 manifest)')

    if trailer:
        print(f'Package author:  {trailer["author"]}')
        print(f'Package time:    {trailer["time"]}')
        print(f'Checksum:        {trailer["checksum"]}')
        print(f'Valid:           {trailer["valid"]}')

    # Content type summary
    print(f'\n{"─" * 60}')
    print('Content Types:')
    type_counts = {}
    for entry in entries:
        if entry['flags'] != 1:
            continue
        data = decompress_entry(buf, entry)
        ct = detect_content_type(data)
        type_counts[ct] = type_counts.get(ct, 0) + 1
    for ct, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f'  {ct:<16} {count:>4}')

    # File listing
    print(f'\n{"─" * 60}')
    print('File Listing:')
    print(f'  {"#":>3}  {"Entry ID":<10} {"Size":>10}  Path')
    print(f'  {"─"*3}  {"─"*10} {"─"*10}  {"─"*40}')
    for entry in entries:
        if entry['flags'] != 1:
            continue
        data = decompress_entry(buf, entry)
        abs_path = file_map.get(entry['id'], f'(unmapped: {entry["id"]})')
        rel = abs_path_to_relative(abs_path) if entry['id'] in file_map else abs_path
        print(f'  {entry["index"]:>3}  {entry["id"]:<10} {len(data):>10,}  {rel}')

    if manifest_entry:
        manifest_data = decompress_entry(buf, manifest_entry)
        print(f'\n  {"─"*3}  {"─"*10} {"─"*10}  {"─"*40}')
        print(f'  {manifest_entry["index"]:>3}  {manifest_entry["id"]:<10} {len(manifest_data):>10,}  (manifest/catalog)')

    print(f'\nMapped files: {len(file_map)} / {header["entry_count"] - 1}')


def extract_pkg(pkg_path, output_dir):
    """Extract all files from a .pkg package."""
    with open(pkg_path, 'rb') as f:
        buf = f.read()

    header = parse_header(buf)
    entries = parse_entry_table(buf, header['entry_count'])

    print(f'Hamilton VENUS Package Extractor')
    print(f'{"─" * 40}')
    print(f'File:          {os.path.basename(pkg_path)}')
    print(f'VENUS version: {header["venus_version"]}')
    print(f'Entries:       {header["entry_count"]}')
    print(f'Output:        {os.path.abspath(output_dir)}')
    print()

    # Find and parse manifest
    manifest_entry = next((e for e in entries if e['flags'] == 0), None)
    if not manifest_entry:
        raise ValueError('No manifest entry found (no entry with flags=0)')

    manifest_data = decompress_entry(buf, manifest_entry)
    file_map = parse_manifest(manifest_data)
    print(f'Manifest parsed: {len(file_map)} file mappings found')
    print()

    # Extract all file entries
    os.makedirs(output_dir, exist_ok=True)
    extracted = 0
    unmapped = 0

    for entry in entries:
        if entry['flags'] != 1:
            continue

        data = decompress_entry(buf, entry)
        abs_path = file_map.get(entry['id'])

        if abs_path:
            rel_path = abs_path_to_relative(abs_path)
        else:
            rel_path = os.path.join('unmapped', f'{entry["id"]}.bin')
            unmapped += 1

        out_path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(data)

        extracted += 1
        print(f'  [{extracted:>3}] {rel_path} ({len(data):,} bytes)')

    print()
    print(f'{"─" * 40}')
    print(f'Extraction complete: {extracted} files extracted')
    if unmapped:
        print(f'  ({unmapped} unmapped entries saved to unmapped/)')


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Hamilton VENUS .pkg Package Extractor',
        epilog='See Hamilton_PKG_Format.md for the full format specification.',
    )
    parser.add_argument('pkg_file', help='Path to the .pkg file')
    parser.add_argument('output_dir', nargs='?', default='./extracted',
                        help='Output directory for extracted files (default: ./extracted)')
    parser.add_argument('--info', action='store_true',
                        help='Show package info and file listing without extracting')

    args = parser.parse_args()

    if not os.path.isfile(args.pkg_file):
        print(f'Error: File not found: {args.pkg_file}', file=sys.stderr)
        sys.exit(1)

    if args.info:
        show_info(args.pkg_file)
    else:
        extract_pkg(args.pkg_file, args.output_dir)


if __name__ == '__main__':
    main()
