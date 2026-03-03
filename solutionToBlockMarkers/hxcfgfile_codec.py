#!/usr/bin/env python3
"""
Pure-Python HxCfgFile v3 codec for Hamilton .med and .stp files.

This implementation converts between:
  - binary HxCfgFile v3 container (.med and .stp)
  - textual HxCfgFile representation used by HxCfgFilConverter /t

.med files contain an ActivityData section (flowchart blob) + HxPars sections.
.stp files contain only HxPars sections (no ActivityData).
Both share the same v3 binary container format.

No COM objects and no third-party executables are required.
Only Python standard library is used.
"""

from __future__ import annotations

import argparse
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


HEADER_TEXT = "HxCfgFile,3;\r\n\r\nConfigIsValid,Y;\r\n\r\n"
ACTIVITY_SECTION_NAME = "ActivityData,ActivityData"
ACTIVITY_KEY = "ActivityDocument"
PROPERTIES_SECTION_NAME = "Method,Properties"
PROPERTIES_KEY = "ReadOnly"


@dataclass
class NamedSection:
    """First section in binary container.
    
    For .med: name="ActivityData,ActivityData", key="ActivityDocument", value=<base64>
    For .stp: name="Method,Properties", key="ReadOnly", value="0"
    """
    name: str
    key: str
    value: str


@dataclass
class HxParsSection:
    key: str
    tokens: List[str]


@dataclass
class HxCfgTextModel:
    named_section: NamedSection | None  # None when absent (some .stp files)
    hxpars_sections: List[HxParsSection]
    footer_line: str

    @property
    def activity_document_b64(self) -> str:
        """Backward-compat: return ActivityDocument value or empty string."""
        if self.named_section and self.named_section.name == ACTIVITY_SECTION_NAME:
            return self.named_section.value
        return ""


def _escape_token_for_text(token: str) -> str:
    out: List[str] = ['"']
    for byte in token.encode("latin1"):
        if byte == 0x5C:
            out.append("\\\\")
        elif byte == 0x22:
            out.append('\\"')
        elif byte == 0x0A:
            out.append("\\n")
        elif byte == 0x0D:
            out.append("\\r")
        elif byte < 0x20 or byte > 0x7E:
            out.append(f"\\0x{byte:02x}")
        else:
            out.append(chr(byte))
    out.append('"')
    return "".join(out)


def _unescape_token_from_text(line: str) -> str:
    s = line.strip()
    if len(s) < 2 or s[0] != '"' or s[-1] != '"':
        raise ValueError(f"Invalid quoted token line: {line}")

    inner = s[1:-1]
    out = bytearray()
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch != "\\":
            out.extend(ch.encode("latin1"))
            i += 1
            continue

        if i + 1 >= len(inner):
            out.append(0x5C)
            i += 1
            continue

        nxt = inner[i + 1]
        if nxt == "\\":
            out.append(0x5C)
            i += 2
        elif nxt == '"':
            out.append(0x22)
            i += 2
        elif nxt == "n":
            out.append(0x0A)
            i += 2
        elif nxt == "r":
            out.append(0x0D)
            i += 2
        elif nxt == "0" and i + 4 < len(inner) and inner[i + 2] in {"x", "X"}:
            hh = inner[i + 3 : i + 5]
            try:
                out.append(int(hh, 16))
                i += 5
            except ValueError:
                out.append(0x5C)
                i += 1
        else:
            out.append(0x5C)
            i += 1

    return out.decode("latin1")


def _read_u16_le(data: bytes, pos: int) -> Tuple[int, int]:
    return struct.unpack_from("<H", data, pos)[0], pos + 2


def _read_u32_le(data: bytes, pos: int) -> Tuple[int, int]:
    return struct.unpack_from("<I", data, pos)[0], pos + 4



def _write_u16_le(value: int) -> bytes:
    return struct.pack("<H", value)


def _write_u32_le(value: int) -> bytes:
    return struct.pack("<I", value)



def _read_short_string(data: bytes, pos: int) -> Tuple[str, int]:
    length = data[pos]
    pos += 1
    value = data[pos : pos + length].decode("latin1")
    return value, pos + length


def _write_short_string(value: str) -> bytes:
    raw = value.encode("latin1")
    if len(raw) > 255:
        raise ValueError("short string exceeds 255 bytes")
    return bytes([len(raw)]) + raw


def _read_var_string(data: bytes, pos: int) -> Tuple[str, int]:
    marker = data[pos]
    pos += 1
    if marker == 0xFF:
        length, pos = _read_u16_le(data, pos)
    else:
        length = marker
    value = data[pos : pos + length].decode("latin1")
    return value, pos + length


def _write_var_string(value: str) -> bytes:
    raw = value.encode("latin1")
    n = len(raw)
    if n <= 0xFE:
        return bytes([n]) + raw
    if n <= 0xFFFF:
        return b"\xFF" + _write_u16_le(n) + raw
    raise ValueError("string too long for current var-string encoding (>65535)")


def parse_binary_med(binary_data: bytes) -> HxCfgTextModel:
    """Parse a binary HxCfgFile v3 container (.med or .stp)."""
    pos = 0

    version, pos = _read_u16_le(binary_data, pos)
    if version != 3:
        raise ValueError(f"Unsupported HxCfgFile version: {version}")

    section_type, pos = _read_u16_le(binary_data, pos)
    if section_type != 1:
        raise ValueError(f"Unexpected section type: {section_type}")

    named_section_count, pos = _read_u32_le(binary_data, pos)

    named_section: NamedSection | None = None

    if named_section_count == 1:
        # Has a named section (ActivityData for .med, Method,Properties for .stp)
        section_name, pos = _read_short_string(binary_data, pos)

        field_type, pos = _read_u16_le(binary_data, pos)
        if field_type != 1:
            raise ValueError(f"Unexpected field type in {section_name}: {field_type}")

        field_count, pos = _read_u32_le(binary_data, pos)
        if field_count != 1:
            raise ValueError(f"Unexpected field count in {section_name}: {field_count}")

        field_key, pos = _read_short_string(binary_data, pos)
        field_value, pos = _read_var_string(binary_data, pos)

        named_section = NamedSection(name=section_name, key=field_key, value=field_value)
    elif named_section_count != 0:
        raise ValueError(f"Unexpected named section count: {named_section_count}")
    # else: count == 0 → no named section (some .stp files)

    hxpars_count = binary_data[pos]
    pos += 1

    # Observed on all tested files: 3-byte zero pad before first HxPars section
    pos += 3

    hxpars_sections: List[HxParsSection] = []

    for _ in range(hxpars_count):
        raw_name, pos = _read_short_string(binary_data, pos)

        if not raw_name.startswith("HxPars,"):
            raise ValueError(f"Unexpected section header: {raw_name}")

        section_key = raw_name.split(",", 1)[1]

        pars_version, pos = _read_u16_le(binary_data, pos)
        if pars_version != 3:
            raise ValueError(f"Unexpected HxPars version in section {section_key}: {pars_version}")

        token_count, pos = _read_u32_le(binary_data, pos)
        tokens: List[str] = []

        for _ in range(token_count):
            token, pos = _read_var_string(binary_data, pos)
            tokens.append(token)

        hxpars_sections.append(HxParsSection(key=section_key, tokens=tokens))

    remainder = binary_data[pos:].decode("latin1")
    footer_match = re.search(r"\* \$\$author=.*\$\$", remainder)
    if not footer_match:
        raise ValueError("Could not locate footer line in binary remainder")
    footer_line = footer_match.group(0)

    return HxCfgTextModel(
        named_section=named_section,
        hxpars_sections=hxpars_sections,
        footer_line=footer_line,
    )


def build_text_med(model: HxCfgTextModel) -> str:
    """Build text representation from model (.med or .stp)."""
    parts: List[str] = [HEADER_TEXT]

    if model.named_section:
        # Emit the named section: DataDef,<part1>,1,<part2>,{<key>, "<value>"}
        # The section name contains a comma, e.g. "ActivityData,ActivityData"
        # which becomes "DataDef,ActivityData,1,ActivityData,"
        ns = model.named_section
        parts.append(f"DataDef,{ns.name.split(',', 1)[0]},1,{ns.name.split(',', 1)[1]},\r\n")
        parts.append("{\r\n")
        parts.append(f'{ns.key}, "{ns.value}"\r\n')
        parts.append("};\r\n\r\n")

    for section in model.hxpars_sections:
        parts.append(f"DataDef,HxPars,3,{section.key},\r\n")
        parts.append("[\r\n")
        for index, token in enumerate(section.tokens):
            parts.append(_escape_token_for_text(token))
            if index < len(section.tokens) - 1:
                parts.append(",\r\n")
            else:
                parts.append("\r\n")
        parts.append("];\r\n\r\n")

    parts.append(model.footer_line)
    parts.append("\r\n")

    return "".join(parts)


def parse_text_med(text: str) -> HxCfgTextModel:
    """Parse text HxCfgFile (.med or .stp). Named sections are auto-detected."""
    if not text.startswith("HxCfgFile,3;"):
        raise ValueError("Input is not HxCfgFile,3 text")

    # Try to find a named section: DataDef,<type>,1,<name>,\s*{\s*<key>,\s*"<value>"\s*};
    named_section: NamedSection | None = None
    named_pattern = re.compile(
        r'DataDef,(\w+),1,(\w+),\s*\{\s*(\w+),\s*"([^"]*?)"\s*\};',
        flags=re.S,
    )
    named_match = named_pattern.search(text)
    if named_match:
        section_name = f"{named_match.group(1)},{named_match.group(2)}"
        named_section = NamedSection(
            name=section_name,
            key=named_match.group(3),
            value=named_match.group(4),
        )

    hxpars_sections: List[HxParsSection] = []
    header_pattern = re.compile(r"DataDef,HxPars,3,([^,]+),\s*\[", flags=re.S)
    search_pos = 0

    while True:
        section_match = header_pattern.search(text, search_pos)
        if not section_match:
            break

        key = section_match.group(1)
        cursor = section_match.end()
        tokens: List[str] = []

        while cursor < len(text):
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1

            if text.startswith("];", cursor):
                cursor += 2
                break

            if cursor >= len(text) or text[cursor] != '"':
                snippet = text[cursor : cursor + 80]
                raise ValueError(f"Unexpected token start in section {key}: {snippet!r}")

            token_start = cursor
            cursor += 1
            escaped = False
            while cursor < len(text):
                ch = text[cursor]
                if escaped:
                    escaped = False
                    cursor += 1
                    continue
                if ch == "\\":
                    escaped = True
                    cursor += 1
                    continue
                if ch == '"':
                    cursor += 1
                    break
                cursor += 1

            token_literal = text[token_start:cursor]
            tokens.append(_unescape_token_from_text(token_literal))

            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor < len(text) and text[cursor] == ",":
                cursor += 1

        hxpars_sections.append(HxParsSection(key=key, tokens=tokens))
        search_pos = cursor

    footer_match = re.search(r"\* \$\$author=.*\$\$", text)
    if not footer_match:
        raise ValueError("Could not parse footer line")
    footer_line = footer_match.group(0)

    return HxCfgTextModel(
        named_section=named_section,
        hxpars_sections=hxpars_sections,
        footer_line=footer_line,
    )


def build_binary_med(model: HxCfgTextModel) -> bytes:
    """Build binary HxCfgFile v3 container (.med or .stp)."""
    out = bytearray()

    out += _write_u16_le(3)   # version
    out += _write_u16_le(1)   # type marker (always 1)

    if model.named_section:
        # Has a named section (ActivityData for .med, Method,Properties for .stp)
        ns = model.named_section
        out += _write_u32_le(1)
        out += _write_short_string(ns.name)
        out += _write_u16_le(1)
        out += _write_u32_le(1)
        out += _write_short_string(ns.key)
        out += _write_var_string(ns.value)
    else:
        # No named section (some .stp files)
        out += _write_u32_le(0)

    if len(model.hxpars_sections) > 255:
        raise ValueError("HxPars section count exceeds single-byte capacity")
    out.append(len(model.hxpars_sections))

    out += b"\x00\x00\x00"

    for section in model.hxpars_sections:
        name = f"HxPars,{section.key}"
        out += _write_short_string(name)

        out += _write_u16_le(3)
        out += _write_u32_le(len(section.tokens))
        for token in section.tokens:
            out += _write_var_string(token)

    out += b"\r\n"
    out += model.footer_line.encode("latin1")

    return bytes(out)


def binary_to_text_file(input_path: Path, output_path: Path) -> None:
    model = parse_binary_med(input_path.read_bytes())
    output_path.write_text(build_text_med(model), encoding="latin1", newline="")


def text_to_binary_file(input_path: Path, output_path: Path) -> None:
    model = parse_text_med(input_path.read_text(encoding="latin1"))
    output_path.write_bytes(build_binary_med(model))


def main() -> int:
    parser = argparse.ArgumentParser(description="Pure-Python HxCfgFile v3 codec (.med and .stp)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_to_text = sub.add_parser("to-text", help="Convert binary .med/.stp to text")
    p_to_text.add_argument("input", type=Path)
    p_to_text.add_argument("output", type=Path)

    p_to_bin = sub.add_parser("to-binary", help="Convert text .med/.stp to binary")
    p_to_bin.add_argument("input", type=Path)
    p_to_bin.add_argument("output", type=Path)

    args = parser.parse_args()

    if args.cmd == "to-text":
        binary_to_text_file(args.input, args.output)
        return 0

    if args.cmd == "to-binary":
        text_to_binary_file(args.input, args.output)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
