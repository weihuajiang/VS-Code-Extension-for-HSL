"""Unit tests for standalone_med_tools.checksum module."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime

from standalone_med_tools.checksum import (
    crc32_hamilton,
    compute_hsl_checksum,
    finalize_hsl_file,
    generate_checksum_line,
    parse_checksum_line,
    update_checksum_in_file,
    verify_file_checksum,
)


class TestCRC32Hamilton(unittest.TestCase):
    """Tests for the low-level crc32_hamilton function."""

    def test_crc32_empty(self):
        """CRC-32 of empty bytes should be 00000000."""
        self.assertEqual(crc32_hamilton(b""), "00000000")

    def test_crc32_known_values(self):
        """CRC-32 of b'123456789' must equal the canonical cbf43926."""
        self.assertEqual(crc32_hamilton(b"123456789"), "cbf43926")

    def test_crc32_hello(self):
        """CRC-32 of b'Hello, world!' must match the docstring example."""
        self.assertEqual(crc32_hamilton(b"Hello, world!"), "ebe6c6e6")

    def test_crc32_output_format(self):
        """Output must always be an 8-character lowercase hex string."""
        for data in (b"", b"\x00", b"abc", b"123456789"):
            result = crc32_hamilton(data)
            self.assertEqual(len(result), 8, f"Length wrong for {data!r}")
            self.assertTrue(
                all(c in "0123456789abcdef" for c in result),
                f"Non-lowercase-hex character in {result!r}",
            )


class TestComputeHslChecksum(unittest.TestCase):
    """Tests for compute_hsl_checksum."""

    def test_compute_hsl_checksum_basic(self):
        """Basic content + prefix produces an 8-hex checksum."""
        content = "variable x;\r\n"
        prefix = "// $$author=admin$$valid=0$$time=2024-01-01 12:00$$checksum="
        result = compute_hsl_checksum(content, prefix)
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_compute_hsl_checksum_latin1(self):
        """Non-ASCII latin1 characters are handled (no UnicodeEncodeError)."""
        # \xe4 = ä, \xfc = ü - valid in latin1
        content = "// comment with \xe4\xfc\r\n"
        prefix = "// $$author=admin$$valid=0$$time=2024-01-01 12:00$$checksum="
        result = compute_hsl_checksum(content, prefix)
        self.assertEqual(len(result), 8)


class TestGenerateChecksumLine(unittest.TestCase):
    """Tests for generate_checksum_line."""

    _FIXED_TS = datetime(2024, 6, 15, 9, 30)

    def test_generate_checksum_line_format(self):
        """Output contains all expected $$ fields in the right order."""
        content = "variable x;\r\n"
        line = generate_checksum_line(
            content, author="tester", valid=1, prefix_char="//",
            timestamp=self._FIXED_TS,
        )
        self.assertIn("$$author=tester$$", line)
        self.assertIn("$$valid=1$$", line)
        self.assertIn("$$time=2024-06-15 09:30$$", line)
        self.assertRegex(line, r"\$\$checksum=[0-9a-f]{8}\$\$")
        self.assertRegex(line, r"\$\$length=\d{3}\$\$$")
        self.assertTrue(line.startswith("// "))

    def test_generate_checksum_line_hsl_prefix(self):
        """HSL files use '//' prefix."""
        content = "x;\r\n"
        line = generate_checksum_line(
            content, prefix_char="//", timestamp=self._FIXED_TS,
        )
        self.assertTrue(line.startswith("// "))

    def test_generate_checksum_line_med_prefix(self):
        """MED files use '*' prefix."""
        content = "x;\r\n"
        line = generate_checksum_line(
            content, prefix_char="*", timestamp=self._FIXED_TS,
        )
        self.assertTrue(line.startswith("* "))

    def test_generate_checksum_line_length(self):
        """The length field equals the full line length including \\r\\n."""
        content = "variable x;\r\n"
        line = generate_checksum_line(
            content, author="admin", valid=0, prefix_char="//",
            timestamp=self._FIXED_TS,
        )
        parsed = parse_checksum_line(line)
        self.assertIsNotNone(parsed)
        expected_len = len(line) + 2  # + \r\n
        self.assertEqual(int(parsed["length"]), expected_len)


class TestFinalizeHslFile(unittest.TestCase):
    """Tests for finalize_hsl_file."""

    def test_finalize_hsl_file(self):
        """finalize_hsl_file appends a checksum line ending with \\r\\n."""
        content = "variable x;\r\n"
        result = finalize_hsl_file(content, author="admin")
        self.assertTrue(result.endswith("\r\n"))
        # The last real line (before final \r\n) should be a valid checksum line
        lines = result.rstrip("\r\n").split("\r\n")
        last_line = lines[-1]
        parsed = parse_checksum_line(last_line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["author"], "admin")

    def test_finalize_hsl_file_adds_crlf(self):
        """If content lacks trailing \\r\\n, one is added before the footer."""
        content = "variable x;"  # no trailing \r\n
        result = finalize_hsl_file(content, author="admin")
        # content portion should now have \r\n
        self.assertIn("variable x;\r\n", result)
        self.assertTrue(result.endswith("\r\n"))


class TestParseChecksumLine(unittest.TestCase):
    """Tests for parse_checksum_line."""

    def test_parse_checksum_line_valid(self):
        """All fields are correctly parsed from a '//' prefixed line."""
        line = (
            "// $$author=admin$$valid=0$$time=2024-06-15 09:30"
            "$$checksum=abc12345$$length=089$$"
        )
        parsed = parse_checksum_line(line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["prefix"], "//")
        self.assertEqual(parsed["author"], "admin")
        self.assertEqual(parsed["valid"], "0")
        self.assertEqual(parsed["time"], "2024-06-15 09:30")
        self.assertEqual(parsed["checksum"], "abc12345")
        self.assertEqual(parsed["length"], "089")

    def test_parse_checksum_line_star_prefix(self):
        """Parses '*' prefix correctly (MED/STP style)."""
        line = (
            "* $$author=user$$valid=1$$time=2025-01-01 00:00"
            "$$checksum=deadbeef$$length=085$$"
        )
        parsed = parse_checksum_line(line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["prefix"], "*")
        self.assertEqual(parsed["author"], "user")
        self.assertEqual(parsed["checksum"], "deadbeef")

    def test_parse_checksum_line_invalid(self):
        """Non-checksum lines return None."""
        self.assertIsNone(parse_checksum_line(""))
        self.assertIsNone(parse_checksum_line("// just a comment"))
        self.assertIsNone(parse_checksum_line("random text"))


class TestVerifyFileChecksum(unittest.TestCase):
    """Tests for verify_file_checksum."""

    def _write_tmp(self, content: str, suffix: str = ".hsl") -> str:
        """Write *content* to a temp file and return its path."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "w", encoding="latin1", newline="") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_verify_file_checksum_valid(self):
        """A file produced by finalize_hsl_file should verify as valid."""
        body = "variable x;\r\n"
        full = finalize_hsl_file(body, author="admin")
        path = self._write_tmp(full)
        result = verify_file_checksum(path)
        self.assertIsNone(result["error"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["stored_checksum"], result["computed_checksum"])

    def test_verify_file_checksum_invalid(self):
        """Tampering with content should cause a mismatch."""
        body = "variable x;\r\n"
        full = finalize_hsl_file(body, author="admin")
        # Corrupt: change 'x' to 'y' in the body while keeping old checksum
        corrupted = full.replace("variable x;", "variable y;", 1)
        path = self._write_tmp(corrupted)
        result = verify_file_checksum(path)
        self.assertIsNone(result["error"])
        self.assertFalse(result["valid"])
        self.assertNotEqual(result["stored_checksum"], result["computed_checksum"])


class TestUpdateChecksumInFile(unittest.TestCase):
    """Tests for update_checksum_in_file."""

    def _write_tmp(self, content: str, suffix: str = ".hsl") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "w", encoding="latin1", newline="") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_update_checksum_in_file(self):
        """After update, the file should verify as valid."""
        body = "variable x;\r\n"
        full = finalize_hsl_file(body, author="admin")
        # Corrupt it so stored checksum is wrong
        corrupted = full.replace("variable x;", "variable y;", 1)
        path = self._write_tmp(corrupted)

        # Pre-condition: invalid
        pre = verify_file_checksum(path)
        self.assertFalse(pre["valid"])

        # Update
        update_checksum_in_file(path)

        # Post-condition: valid
        post = verify_file_checksum(path)
        self.assertTrue(post["valid"])

    def test_update_checksum_binary_guard(self):
        """update_checksum_in_file raises ValueError for binary extensions."""
        for ext in (".med", ".stp", ".smt"):
            body = "dummy\r\n"
            full = finalize_hsl_file(body, author="admin")
            # Write with binary extension
            path = self._write_tmp(full, suffix=ext)
            with self.assertRaises(ValueError, msg=f"Expected ValueError for {ext}"):
                update_checksum_in_file(path)


if __name__ == "__main__":
    unittest.main()
