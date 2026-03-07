"""
Comprehensive unit tests for standalone_med_tools.hxcfgfile_codec.

Covers escape/unescape helpers, binary I/O primitives, short-string and
var-string encoding, text and binary parsing/building, and full roundtrips
for both .med and .stp structures.
"""

from __future__ import annotations

import struct
import unittest

from standalone_med_tools.hxcfgfile_codec import (
    ACTIVITY_KEY,
    ACTIVITY_SECTION_NAME,
    HXCFG_TYPE_MARKER,
    HXCFG_VERSION,
    PROPERTIES_KEY,
    PROPERTIES_SECTION_NAME,
    HxCfgTextModel,
    HxParsSection,
    NamedSection,
    _escape_token_for_text,
    _read_short_string,
    _read_u16_le,
    _read_u32_le,
    _read_var_string,
    _unescape_token_from_text,
    _write_short_string,
    _write_u16_le,
    _write_u32_le,
    _write_var_string,
    build_binary_med,
    build_text_med,
    parse_binary_med,
    parse_text_med,
)

# ── Shared helpers ─────────────────────────────────────────────────────────

FOOTER = "* $$author=UnitTest $$"


def _minimal_model(
    named_section: NamedSection | None = None,
    tokens: list[str] | None = None,
    footer: str = FOOTER,
) -> HxCfgTextModel:
    """Build a tiny but valid HxCfgTextModel for testing."""
    hxpars = []
    if tokens is not None:
        hxpars.append(HxParsSection(key="Method", tokens=tokens))
    return HxCfgTextModel(
        named_section=named_section,
        hxpars_sections=hxpars,
        footer_line=footer,
    )


# ── 1. Escape / unescape roundtrip ────────────────────────────────────────

class TestEscapeTokenRoundtrip(unittest.TestCase):
    """Various token strings survive escape → unescape roundtrip."""

    def _roundtrip(self, raw: str) -> None:
        escaped = _escape_token_for_text(raw)
        recovered = _unescape_token_from_text(escaped)
        self.assertEqual(recovered, raw)

    def test_plain_ascii(self):
        self._roundtrip("Hello, world!")

    def test_empty_string(self):
        self._roundtrip("")

    def test_backslash(self):
        self._roundtrip("a\\b")

    def test_double_quote(self):
        self._roundtrip('say "hi"')

    def test_newline_and_cr(self):
        self._roundtrip("line1\nline2\r\n")

    def test_control_chars(self):
        self._roundtrip("\x00\x01\x1f")

    def test_high_latin1_bytes(self):
        self._roundtrip("\x80\xff\xa9")

    def test_mixed_special(self):
        self._roundtrip('path\\to\\"file\\"\n\r\x00\xfe')


# ── 2. Unescape special sequences ─────────────────────────────────────────

class TestUnescapeSpecialSequences(unittest.TestCase):
    """Verify individual escape sequences in isolation."""

    def test_escaped_backslash(self):
        self.assertEqual(_unescape_token_from_text(r'"\\"'), "\\")

    def test_escaped_double_quote(self):
        self.assertEqual(_unescape_token_from_text('"\\""'), '"')

    def test_escaped_n(self):
        self.assertEqual(_unescape_token_from_text('"\\n"'), "\n")

    def test_escaped_r(self):
        self.assertEqual(_unescape_token_from_text('"\\r"'), "\r")

    def test_hex_escape(self):
        self.assertEqual(_unescape_token_from_text('"\\0x41"'), "A")

    def test_hex_escape_non_printable(self):
        self.assertEqual(_unescape_token_from_text('"\\0x00"'), "\x00")

    def test_multiple_escapes(self):
        result = _unescape_token_from_text('"\\\\\\n\\r\\0xff"')
        self.assertEqual(result, "\\\n\r\xff")


# ── 3. read / write u16‑LE ─────────────────────────────────────────────────

class TestReadWriteU16LE(unittest.TestCase):
    """16-bit little-endian encoding / decoding."""

    def test_zero(self):
        data = _write_u16_le(0)
        val, pos = _read_u16_le(data, 0)
        self.assertEqual(val, 0)
        self.assertEqual(pos, 2)

    def test_max(self):
        data = _write_u16_le(0xFFFF)
        val, _ = _read_u16_le(data, 0)
        self.assertEqual(val, 0xFFFF)

    def test_known_value(self):
        data = _write_u16_le(0x0301)
        self.assertEqual(data, b"\x01\x03")
        val, _ = _read_u16_le(data, 0)
        self.assertEqual(val, 0x0301)

    def test_offset_read(self):
        buf = b"\xAA" + _write_u16_le(42)
        val, pos = _read_u16_le(buf, 1)
        self.assertEqual(val, 42)
        self.assertEqual(pos, 3)


# ── 4. read / write u32‑LE ─────────────────────────────────────────────────

class TestReadWriteU32LE(unittest.TestCase):
    """32-bit little-endian encoding / decoding."""

    def test_zero(self):
        data = _write_u32_le(0)
        val, pos = _read_u32_le(data, 0)
        self.assertEqual(val, 0)
        self.assertEqual(pos, 4)

    def test_max(self):
        data = _write_u32_le(0xFFFFFFFF)
        val, _ = _read_u32_le(data, 0)
        self.assertEqual(val, 0xFFFFFFFF)

    def test_known_value(self):
        data = _write_u32_le(0x01020304)
        self.assertEqual(data, b"\x04\x03\x02\x01")
        val, _ = _read_u32_le(data, 0)
        self.assertEqual(val, 0x01020304)


# ── 5. Short-string roundtrip ─────────────────────────────────────────────

class TestShortStringRoundtrip(unittest.TestCase):
    """Short strings (0-255 bytes) survive write → read."""

    def _roundtrip(self, s: str) -> None:
        encoded = _write_short_string(s)
        decoded, end_pos = _read_short_string(encoded, 0)
        self.assertEqual(decoded, s)
        self.assertEqual(end_pos, len(encoded))

    def test_empty(self):
        self._roundtrip("")

    def test_ascii(self):
        self._roundtrip("HxPars,Method")

    def test_max_length(self):
        self._roundtrip("A" * 255)

    def test_latin1_high(self):
        self._roundtrip("\xe4\xf6\xfc")  # äöü in Latin-1


# ── 6. Short-string overflow ──────────────────────────────────────────────

class TestShortStringOverflow(unittest.TestCase):
    """Strings >255 bytes raise ValueError."""

    def test_256_bytes_raises(self):
        with self.assertRaises(ValueError):
            _write_short_string("X" * 256)

    def test_1000_bytes_raises(self):
        with self.assertRaises(ValueError):
            _write_short_string("Z" * 1000)


# ── 7. Var-string short ───────────────────────────────────────────────────

class TestVarStringShort(unittest.TestCase):
    """Var-strings under 255 bytes use single-byte length."""

    def test_empty(self):
        encoded = _write_var_string("")
        self.assertEqual(encoded[0], 0)  # length byte = 0
        decoded, _ = _read_var_string(encoded, 0)
        self.assertEqual(decoded, "")

    def test_short_value(self):
        s = "hello"
        encoded = _write_var_string(s)
        self.assertEqual(encoded[0], len(s))
        decoded, pos = _read_var_string(encoded, 0)
        self.assertEqual(decoded, s)
        self.assertEqual(pos, len(encoded))

    def test_254_bytes(self):
        s = "B" * 254
        encoded = _write_var_string(s)
        self.assertEqual(encoded[0], 254)
        decoded, _ = _read_var_string(encoded, 0)
        self.assertEqual(decoded, s)


# ── 8. Var-string long ────────────────────────────────────────────────────

class TestVarStringLong(unittest.TestCase):
    """Var-strings 255-65535 bytes use 0xFF + u16 length."""

    def test_255_bytes(self):
        s = "C" * 255
        encoded = _write_var_string(s)
        self.assertEqual(encoded[0], 0xFF)
        # next two bytes are u16-LE length = 255
        length = struct.unpack_from("<H", encoded, 1)[0]
        self.assertEqual(length, 255)
        decoded, _ = _read_var_string(encoded, 0)
        self.assertEqual(decoded, s)

    def test_1000_bytes(self):
        s = "D" * 1000
        encoded = _write_var_string(s)
        self.assertEqual(encoded[0], 0xFF)
        decoded, _ = _read_var_string(encoded, 0)
        self.assertEqual(decoded, s)

    def test_65535_bytes(self):
        s = "E" * 65535
        encoded = _write_var_string(s)
        decoded, _ = _read_var_string(encoded, 0)
        self.assertEqual(decoded, s)


# ── 9. Var-string overflow ────────────────────────────────────────────────

class TestVarStringOverflow(unittest.TestCase):
    """Strings >65535 bytes raise ValueError."""

    def test_65536_bytes_raises(self):
        with self.assertRaises(ValueError):
            _write_var_string("F" * 65536)


# ── 10. Parse text -- simple ───────────────────────────────────────────────

class TestParseTextSimple(unittest.TestCase):
    """Parse a minimal valid text format."""

    def test_minimal_text(self):
        text = (
            "HxCfgFile,3;\r\n\r\n"
            "ConfigIsValid,Y;\r\n\r\n"
            "DataDef,HxPars,3,Method,\r\n"
            "[\r\n"
            '"hello"\r\n'
            "];\r\n\r\n"
            "* $$author=Test $$\r\n"
        )
        model = parse_text_med(text)
        self.assertIsNone(model.named_section)
        self.assertEqual(len(model.hxpars_sections), 1)
        self.assertEqual(model.hxpars_sections[0].key, "Method")
        self.assertEqual(model.hxpars_sections[0].tokens, ["hello"])
        self.assertIn("author=Test", model.footer_line)


# ── 11. Parse text with ActivityData ──────────────────────────────────────

class TestParseTextWithActivityData(unittest.TestCase):
    """Parse text with an ActivityData section."""

    def test_activity_data(self):
        text = (
            "HxCfgFile,3;\r\n\r\n"
            "ConfigIsValid,Y;\r\n\r\n"
            "DataDef,ActivityData,1,ActivityData,\r\n"
            "{\r\n"
            'ActivityDocument, "AQAAAA=="\r\n'
            "};\r\n\r\n"
            "DataDef,HxPars,3,Method,\r\n"
            "[\r\n"
            '"tok1"\r\n'
            "];\r\n\r\n"
            "* $$author=Test $$\r\n"
        )
        model = parse_text_med(text)
        self.assertIsNotNone(model.named_section)
        self.assertEqual(model.named_section.name, ACTIVITY_SECTION_NAME)
        self.assertEqual(model.named_section.key, ACTIVITY_KEY)
        self.assertEqual(model.named_section.value, "AQAAAA==")
        self.assertEqual(model.activity_document_b64, "AQAAAA==")


# ── 12. Parse text with Properties ────────────────────────────────────────

class TestParseTextWithProperties(unittest.TestCase):
    """Parse text with a Method,Properties section (.stp style)."""

    def test_properties(self):
        text = (
            "HxCfgFile,3;\r\n\r\n"
            "ConfigIsValid,Y;\r\n\r\n"
            "DataDef,Method,1,Properties,\r\n"
            "{\r\n"
            'ReadOnly, "0"\r\n'
            "};\r\n\r\n"
            "DataDef,HxPars,3,Step,\r\n"
            "[\r\n"
            '"val"\r\n'
            "];\r\n\r\n"
            "* $$author=Test $$\r\n"
        )
        model = parse_text_med(text)
        self.assertIsNotNone(model.named_section)
        self.assertEqual(model.named_section.name, PROPERTIES_SECTION_NAME)
        self.assertEqual(model.named_section.key, PROPERTIES_KEY)
        self.assertEqual(model.named_section.value, "0")


# ── 13. Build text roundtrip ──────────────────────────────────────────────

class TestBuildTextRoundtrip(unittest.TestCase):
    """Parse text → build text produces same output (ignoring whitespace)."""

    def test_roundtrip_no_named_section(self):
        text = (
            "HxCfgFile,3;\r\n\r\n"
            "ConfigIsValid,Y;\r\n\r\n"
            "DataDef,HxPars,3,Method,\r\n"
            "[\r\n"
            '"alpha",\r\n'
            '"beta"\r\n'
            "];\r\n\r\n"
            "* $$author=Roundtrip $$\r\n"
        )
        model = parse_text_med(text)
        rebuilt = build_text_med(model)
        self.assertEqual(rebuilt.strip(), text.strip())

    def test_roundtrip_with_activity(self):
        text = (
            "HxCfgFile,3;\r\n\r\n"
            "ConfigIsValid,Y;\r\n\r\n"
            "DataDef,ActivityData,1,ActivityData,\r\n"
            "{\r\n"
            'ActivityDocument, "blob=="\r\n'
            "};\r\n\r\n"
            "DataDef,HxPars,3,Method,\r\n"
            "[\r\n"
            '"x"\r\n'
            "];\r\n\r\n"
            "* $$author=Roundtrip $$\r\n"
        )
        model = parse_text_med(text)
        rebuilt = build_text_med(model)
        self.assertEqual(rebuilt.strip(), text.strip())


# ── 14. Build binary header ───────────────────────────────────────────────

class TestBuildBinaryHeader(unittest.TestCase):
    """Binary output starts with version=3, type=1."""

    def test_header_bytes(self):
        model = _minimal_model(tokens=["t1"])
        binary = build_binary_med(model)
        version, _ = _read_u16_le(binary, 0)
        type_marker, _ = _read_u16_le(binary, 2)
        self.assertEqual(version, HXCFG_VERSION)
        self.assertEqual(type_marker, HXCFG_TYPE_MARKER)


# ── 15. Parse binary version check ────────────────────────────────────────

class TestParseBinaryVersionCheck(unittest.TestCase):
    """Non-v3 binary raises ValueError."""

    def test_version_2_raises(self):
        bad = _write_u16_le(2) + _write_u16_le(1) + b"\x00" * 20
        with self.assertRaises(ValueError) as cm:
            parse_binary_med(bad)
        self.assertIn("version", str(cm.exception).lower())

    def test_version_0_raises(self):
        bad = _write_u16_le(0) + _write_u16_le(1) + b"\x00" * 20
        with self.assertRaises(ValueError):
            parse_binary_med(bad)


# ── 16. Named section present ─────────────────────────────────────────────

class TestNamedSectionPresent(unittest.TestCase):
    """Parse binary with a named section."""

    def test_activity_data_present(self):
        ns = NamedSection(
            name=ACTIVITY_SECTION_NAME,
            key=ACTIVITY_KEY,
            value="AQAAAA==",
        )
        model = _minimal_model(named_section=ns, tokens=["tok"])
        binary = build_binary_med(model)
        parsed = parse_binary_med(binary)
        self.assertIsNotNone(parsed.named_section)
        self.assertEqual(parsed.named_section.name, ACTIVITY_SECTION_NAME)
        self.assertEqual(parsed.named_section.key, ACTIVITY_KEY)
        self.assertEqual(parsed.named_section.value, "AQAAAA==")


# ── 17. Named section absent ──────────────────────────────────────────────

class TestNamedSectionAbsent(unittest.TestCase):
    """Parse binary with no named section (count=0)."""

    def test_no_named_section(self):
        model = _minimal_model(tokens=["tok"])
        binary = build_binary_med(model)
        parsed = parse_binary_med(binary)
        self.assertIsNone(parsed.named_section)
        # named-section count should be 0 in the raw bytes
        count, _ = _read_u32_le(binary, 4)
        self.assertEqual(count, 0)


# ── 18. Full roundtrip in memory ──────────────────────────────────────────

class TestFullRoundtripInMemory(unittest.TestCase):
    """text → binary → text produces an equivalent model."""

    def test_roundtrip(self):
        text = (
            "HxCfgFile,3;\r\n\r\n"
            "ConfigIsValid,Y;\r\n\r\n"
            "DataDef,ActivityData,1,ActivityData,\r\n"
            "{\r\n"
            'ActivityDocument, "SGVsbG8="\r\n'
            "};\r\n\r\n"
            "DataDef,HxPars,3,Method,\r\n"
            "[\r\n"
            '"token_one",\r\n'
            '"token_two"\r\n'
            "];\r\n\r\n"
            "* $$author=RoundtripTest $$\r\n"
        )
        model1 = parse_text_med(text)
        binary = build_binary_med(model1)
        model2 = parse_binary_med(binary)

        # Named section
        self.assertEqual(model1.named_section.name, model2.named_section.name)
        self.assertEqual(model1.named_section.key, model2.named_section.key)
        self.assertEqual(model1.named_section.value, model2.named_section.value)

        # HxPars
        self.assertEqual(len(model1.hxpars_sections), len(model2.hxpars_sections))
        for s1, s2 in zip(model1.hxpars_sections, model2.hxpars_sections):
            self.assertEqual(s1.key, s2.key)
            self.assertEqual(s1.tokens, s2.tokens)

        # Footer
        self.assertEqual(model1.footer_line, model2.footer_line)

    def test_roundtrip_multiple_sections(self):
        model = HxCfgTextModel(
            named_section=None,
            hxpars_sections=[
                HxParsSection(key="Method", tokens=["a", "b"]),
                HxParsSection(key="Instrument", tokens=["x"]),
            ],
            footer_line=FOOTER,
        )
        binary = build_binary_med(model)
        parsed = parse_binary_med(binary)

        self.assertIsNone(parsed.named_section)
        self.assertEqual(len(parsed.hxpars_sections), 2)
        self.assertEqual(parsed.hxpars_sections[0].key, "Method")
        self.assertEqual(parsed.hxpars_sections[0].tokens, ["a", "b"])
        self.assertEqual(parsed.hxpars_sections[1].key, "Instrument")
        self.assertEqual(parsed.hxpars_sections[1].tokens, ["x"])


# ── 19. Minimal .med file ─────────────────────────────────────────────────

class TestMinimalMedFile(unittest.TestCase):
    """Create, convert, and parse back a minimal .med structure."""

    def test_create_and_parse(self):
        ns = NamedSection(
            name=ACTIVITY_SECTION_NAME,
            key=ACTIVITY_KEY,
            value="AQAAAA==",
        )
        model = HxCfgTextModel(
            named_section=ns,
            hxpars_sections=[
                HxParsSection(key="Method", tokens=["Version", "1"]),
            ],
            footer_line="* $$author=test $$",
        )

        # model → text → model2
        text = build_text_med(model)
        model2 = parse_text_med(text)
        self.assertEqual(model2.named_section.name, ACTIVITY_SECTION_NAME)
        self.assertEqual(model2.hxpars_sections[0].tokens, ["Version", "1"])

        # model → binary → model3
        binary = build_binary_med(model)
        model3 = parse_binary_med(binary)
        self.assertEqual(model3.named_section.value, "AQAAAA==")
        self.assertEqual(model3.hxpars_sections[0].key, "Method")

        # binary → text → binary2  (byte-for-byte)
        text_from_bin = build_text_med(model3)
        model4 = parse_text_med(text_from_bin)
        binary2 = build_binary_med(model4)
        self.assertEqual(binary, binary2)


# ── 20. Minimal .stp file ─────────────────────────────────────────────────

class TestMinimalStpFile(unittest.TestCase):
    """Create, convert, and parse back a minimal .stp structure."""

    def test_create_and_parse(self):
        ns = NamedSection(
            name=PROPERTIES_SECTION_NAME,
            key=PROPERTIES_KEY,
            value="0",
        )
        model = HxCfgTextModel(
            named_section=ns,
            hxpars_sections=[
                HxParsSection(key="Step", tokens=["StepName", "MyStep"]),
            ],
            footer_line="* $$author=stp_test $$",
        )

        # model → text → model2
        text = build_text_med(model)
        model2 = parse_text_med(text)
        self.assertEqual(model2.named_section.name, PROPERTIES_SECTION_NAME)
        self.assertEqual(model2.named_section.key, PROPERTIES_KEY)
        self.assertEqual(model2.named_section.value, "0")
        self.assertEqual(model2.hxpars_sections[0].tokens, ["StepName", "MyStep"])

        # model → binary → model3
        binary = build_binary_med(model)
        model3 = parse_binary_med(binary)
        self.assertEqual(model3.named_section.name, PROPERTIES_SECTION_NAME)
        self.assertEqual(model3.hxpars_sections[0].key, "Step")

        # binary roundtrip byte-for-byte
        binary2 = build_binary_med(model3)
        self.assertEqual(binary, binary2)

    def test_stp_without_named_section(self):
        """Some minimal .stp files have no named section at all."""
        model = HxCfgTextModel(
            named_section=None,
            hxpars_sections=[
                HxParsSection(key="Step", tokens=["v"]),
            ],
            footer_line="* $$author=bare $$",
        )
        binary = build_binary_med(model)
        parsed = parse_binary_med(binary)
        self.assertIsNone(parsed.named_section)
        self.assertEqual(parsed.hxpars_sections[0].tokens, ["v"])


if __name__ == "__main__":
    unittest.main()
