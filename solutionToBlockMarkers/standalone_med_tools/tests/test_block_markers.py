#!/usr/bin/env python3
"""Comprehensive unit tests for standalone_med_tools.block_markers."""

from __future__ import annotations

import re
import unittest
from typing import List

from standalone_med_tools.block_markers import (
    # CLSID registries
    STEP_CLSID,
    ML_STAR_CLSID,
    TRIPLE_BRACE_CLSIDS,
    # GUID utilities
    generate_instance_guid,
    hamilton_guid_to_standard,
    standard_guid_to_hamilton,
    # Detection
    has_step_block_markers,
    is_triple_brace_clsid,
    # Parsing
    parse_block_markers,
    StepBlockMarker,
    StructuralBlockMarker,
    DeviceCallInfo,
    # Generation
    make_step_open_marker,
    make_structural_open_marker,
    make_inline_structural_marker,
    make_close_marker,
    # Renumbering
    renumber_block_markers,
    # Step builders
    MethodStep,
    comment_step,
    assignment_step,
    for_loop_step,
    while_loop_step,
    if_else_step,
    submethod_call_step,
    library_function_step,
    abort_step,
    break_step,
    return_step,
    shell_step,
    # Full generation
    generate_hsl_method,
    # Device call extraction
    extract_device_call_from_code,
    # Reconciler
    reconcile_block_marker_headers,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

# Regex for Hamilton GUID format: 8_4_4_16 hex characters
_HAMILTON_GUID_RE = re.compile(
    r'^[0-9a-f]{8}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{16}$'
)

# Regex for standard GUID format: 8-4-4-4-12 hex characters
_STANDARD_GUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)

# Regex for a CLSID: {8-4-4-4-12} hex (case-insensitive)
_CLSID_RE = re.compile(
    r'^\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}'
    r'-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$'
)


def _make_method_content(step_lines: List[str]) -> str:
    """Build a minimal HSL method file string containing the given step lines.

    The result has structural scaffolding around the steps so that
    parse_block_markers / reconcile_block_marker_headers / etc. can
    operate on realistic content.
    """
    parts: List[str] = []
    parts.append('/* {{ 2 "LibraryInsertLine" "" */ // }} ""')
    parts.append('/* {{ 2 "VariableInsertLine" "" */ // }} ""')
    parts.append('// {{ 2 "TemplateIncludeBlock" ""')
    parts.append(' namespace _Method { #include "HSLMETEDLib.hs_" } ')
    parts.append('// }} ""')
    parts.append('// {{{ 2 "LocalSubmethodInclude" ""')
    parts.append(' namespace _Method {  #include __filename__ ".sub"  } ')
    parts.append('// }} ""')
    parts.append('/* {{ 2 "ProcessInsertLine" "" */ // }} ""')
    parts.append('// {{{ 5 "main" "Begin"')
    parts.append('namespace _Method { method main(  ) void {')
    parts.append('// }} ""')
    parts.append('// {{ 5 "main" "InitLocals"')
    parts.append('// }} ""')
    parts.append('// {{ 2 "AutoInitBlock" ""')
    parts.append('::RegisterAbortHandler( "OnAbort");')
    parts.append('// }} ""')
    # Insert caller-supplied step lines
    parts.extend(step_lines)
    parts.append('// {{ 2 "AutoExitBlock" ""')
    parts.append('// }} ""')
    parts.append('// {{{ 5 "main" "End"')
    parts.append('} }')
    parts.append('// }} ""')
    return '\n'.join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestGenerateInstanceGuidFormat(unittest.TestCase):
    """1. GUID matches Hamilton pattern 8_4_4_16 hex."""

    def test_generate_instance_guid_format(self):
        guid = generate_instance_guid()
        self.assertRegex(guid, _HAMILTON_GUID_RE,
                         f"GUID {guid!r} does not match 8_4_4_16 pattern")


class TestGenerateInstanceGuidUniqueness(unittest.TestCase):
    """2. Multiple calls produce different GUIDs."""

    def test_generate_instance_guid_uniqueness(self):
        guids = {generate_instance_guid() for _ in range(100)}
        self.assertEqual(len(guids), 100, "Expected 100 unique GUIDs")


class TestHamiltonToStandardGuid(unittest.TestCase):
    """3. Hamilton underscore → standard dash conversion."""

    def test_hamilton_to_standard_guid(self):
        h_guid = "550e8400_e29b_41d4_a716446655440000"
        result = hamilton_guid_to_standard(h_guid)
        self.assertEqual(result, "550e8400-e29b-41d4-a716-446655440000")
        self.assertRegex(result, _STANDARD_GUID_RE)


class TestStandardToHamiltonGuid(unittest.TestCase):
    """4. Standard dash → Hamilton underscore conversion."""

    def test_standard_to_hamilton_guid(self):
        std = "{550E8400-E29B-41D4-A716-446655440000}"
        result = standard_guid_to_hamilton(std)
        self.assertEqual(result, "550e8400_e29b_41d4_a716446655440000")
        self.assertRegex(result, _HAMILTON_GUID_RE)

    def test_standard_to_hamilton_guid_no_braces(self):
        std = "550E8400-E29B-41D4-A716-446655440000"
        result = standard_guid_to_hamilton(std)
        self.assertEqual(result, "550e8400_e29b_41d4_a716446655440000")


class TestGuidRoundtrip(unittest.TestCase):
    """5. hamilton_to_standard(standard_to_hamilton(guid)) == guid."""

    def test_guid_roundtrip(self):
        std = "550e8400-e29b-41d4-a716-446655440000"
        roundtripped = hamilton_guid_to_standard(standard_guid_to_hamilton(std))
        self.assertEqual(roundtripped, std)

    def test_guid_roundtrip_generated(self):
        h_guid = generate_instance_guid()
        std = hamilton_guid_to_standard(h_guid)
        back = standard_guid_to_hamilton(std)
        self.assertEqual(back, h_guid)


class TestHasStepBlockMarkersTrue(unittest.TestCase):
    """6. Method file content returns True."""

    def test_has_step_block_markers_true(self):
        content = _make_method_content([
            '// {{ 1 1 0 "aaaaaaaa_bbbb_cccc_dddddddddddddddd" '
            '"{F07B0071-8EFC-11d4-A3BA-002035848439}"',
            'MECC::TraceComment(Translate("hello"));',
            '// }} ""',
        ])
        self.assertTrue(has_step_block_markers(content))


class TestHasStepBlockMarkersFalse(unittest.TestCase):
    """7. Library file content returns False."""

    def test_has_step_block_markers_false(self):
        # Library files have structural markers but no step markers
        content = (
            '// {{ 2 "LibraryInsertLine" ""\n'
            '// }} ""\n'
            'function myFunc() void {\n'
            '  return;\n'
            '}\n'
        )
        self.assertFalse(has_step_block_markers(content))


class TestParseStepMarkers(unittest.TestCase):
    """8. Parse a sample with step markers, verify row/col/guid/clsid."""

    def test_parse_step_markers(self):
        guid = "aaaaaaaa_bbbb_cccc_dddddddddddddddd"
        clsid = "{F07B0071-8EFC-11d4-A3BA-002035848439}"
        content = (
            f'// {{{{ 3 1 0 "{guid}" "{clsid}"\n'
            'MECC::TraceComment(Translate("hello"));\n'
            '// }} ""\n'
        )
        markers = parse_block_markers(content)
        steps = [m for m in markers if isinstance(m, StepBlockMarker)]
        self.assertEqual(len(steps), 1)
        s = steps[0]
        self.assertEqual(s.row, 3)
        self.assertEqual(s.column, 1)
        self.assertEqual(s.sublevel, 0)
        self.assertEqual(s.instance_guid, guid)
        self.assertEqual(s.step_clsid, clsid)
        self.assertFalse(s.triple_brace)
        self.assertTrue(any("TraceComment" in l for l in s.code_lines))


class TestParseStructuralMarkers(unittest.TestCase):
    """9. Parse structural markers (block type, section name, qualifier)."""

    def test_parse_structural_markers(self):
        content = (
            '// {{{ 5 "main" "Begin"\n'
            'namespace _Method { method main(  ) void {\n'
            '// }} ""\n'
        )
        markers = parse_block_markers(content)
        structs = [m for m in markers if isinstance(m, StructuralBlockMarker)]
        self.assertEqual(len(structs), 1)
        s = structs[0]
        self.assertEqual(s.block_type, 5)
        self.assertEqual(s.section_name, "main")
        self.assertEqual(s.qualifier, "Begin")
        self.assertTrue(s.triple_brace)
        self.assertFalse(s.inline)


class TestParseInlineStructural(unittest.TestCase):
    """10. Parse inline structural markers."""

    def test_parse_inline_structural(self):
        content = '/* {{ 2 "LibraryInsertLine" "" */ // }} ""\n'
        markers = parse_block_markers(content)
        self.assertEqual(len(markers), 1)
        m = markers[0]
        self.assertIsInstance(m, StructuralBlockMarker)
        self.assertEqual(m.block_type, 2)
        self.assertEqual(m.section_name, "LibraryInsertLine")
        self.assertEqual(m.qualifier, "")
        self.assertTrue(m.inline)
        self.assertEqual(m.code_lines, [])


class TestParseEmptyFile(unittest.TestCase):
    """11. Returns empty list for empty input."""

    def test_parse_empty_file(self):
        markers = parse_block_markers("")
        self.assertEqual(markers, [])

    def test_parse_no_markers(self):
        markers = parse_block_markers("// just a comment\nint x = 1;\n")
        self.assertEqual(markers, [])


class TestParseMixedMarkers(unittest.TestCase):
    """12. File with both step and structural markers."""

    def test_parse_mixed_markers(self):
        guid = "11111111_2222_3333_4444444444444444"
        clsid = STEP_CLSID["Comment"]
        content = (
            '// {{{ 5 "main" "Begin"\n'
            'namespace _Method { method main(  ) void {\n'
            '// }} ""\n'
            f'// {{{{ 1 1 0 "{guid}" "{clsid}"\n'
            'MECC::TraceComment(Translate("hi"));\n'
            '// }} ""\n'
            '/* {{ 2 "AutoExitBlock" "" */ // }} ""\n'
        )
        markers = parse_block_markers(content)
        step_markers = [m for m in markers if isinstance(m, StepBlockMarker)]
        struct_markers = [m for m in markers if isinstance(m, StructuralBlockMarker)]
        self.assertEqual(len(step_markers), 1)
        self.assertGreaterEqual(len(struct_markers), 2)


class TestRenumberSequential(unittest.TestCase):
    """13. Already sequential content unchanged."""

    def test_renumber_sequential(self):
        guid1 = "aaaaaaaa_bbbb_cccc_dddddddddddddddd"
        guid2 = "eeeeeeee_ffff_0000_1111111111111111"
        clsid = STEP_CLSID["Comment"]
        content = (
            f'// {{{{ 1 1 0 "{guid1}" "{clsid}"\n'
            'code1;\n'
            '// }} ""\n'
            f'// {{{{ 2 1 0 "{guid2}" "{clsid}"\n'
            'code2;\n'
            '// }} ""\n'
        )
        result = renumber_block_markers(content)
        self.assertEqual(result, content)


class TestRenumberWithGaps(unittest.TestCase):
    """14. Gaps corrected to 1,2,3,..."""

    def test_renumber_with_gaps(self):
        guid1 = "aaaaaaaa_bbbb_cccc_dddddddddddddddd"
        guid2 = "eeeeeeee_ffff_0000_1111111111111111"
        clsid = STEP_CLSID["Comment"]
        content = (
            f'// {{{{ 5 1 0 "{guid1}" "{clsid}"\n'
            'code1;\n'
            '// }} ""\n'
            f'// {{{{ 10 1 0 "{guid2}" "{clsid}"\n'
            'code2;\n'
            '// }} ""\n'
        )
        result = renumber_block_markers(content)
        # Rows should now be 1 and 2
        self.assertIn(f'// {{{{ 1 1 0 "{guid1}" "{clsid}"', result)
        self.assertIn(f'// {{{{ 2 1 0 "{guid2}" "{clsid}"', result)


class TestRenumberPreservesGuids(unittest.TestCase):
    """15. GUIDs and CLSIDs unchanged after renumber."""

    def test_renumber_preserves_guids(self):
        guid = "abcdef01_2345_6789_abcdef0123456789"
        clsid = STEP_CLSID["Assignment"]
        content = (
            f'// {{{{ 99 1 0 "{guid}" "{clsid}"\n'
            'x = 1;\n'
            '// }} ""\n'
        )
        result = renumber_block_markers(content)
        self.assertIn(guid, result)
        self.assertIn(clsid, result)


class TestMakeStepOpenMarkerDouble(unittest.TestCase):
    """16. Generates correct // {{ format."""

    def test_make_step_open_marker_double(self):
        guid = "aaaaaaaa_bbbb_cccc_dddddddddddddddd"
        clsid = STEP_CLSID["Comment"]
        marker = make_step_open_marker(1, 1, 0, guid, clsid, triple_brace=False)
        self.assertTrue(marker.startswith("// {{ "))
        self.assertIn(f'"{guid}"', marker)
        self.assertIn(f'"{clsid}"', marker)
        self.assertNotIn("{{{", marker)


class TestMakeStepOpenMarkerTriple(unittest.TestCase):
    """17. Generates correct // {{{ format."""

    def test_make_step_open_marker_triple(self):
        guid = "aaaaaaaa_bbbb_cccc_dddddddddddddddd"
        clsid = STEP_CLSID["SingleLibFunction"]
        marker = make_step_open_marker(2, 1, 0, guid, clsid, triple_brace=True)
        self.assertTrue(marker.startswith("// {{{ "))
        self.assertIn(f'"{guid}"', marker)
        self.assertIn(f'"{clsid}"', marker)


class TestMakeStructuralMarkers(unittest.TestCase):
    """18. Both regular and inline structural markers."""

    def test_make_structural_open_marker(self):
        marker = make_structural_open_marker(2, "LibraryInsertLine", "")
        self.assertEqual(marker, '// {{ 2 "LibraryInsertLine" ""')

    def test_make_structural_open_marker_triple(self):
        marker = make_structural_open_marker(5, "main", "Begin", triple_brace=True)
        self.assertEqual(marker, '// {{{ 5 "main" "Begin"')

    def test_make_inline_structural_marker(self):
        marker = make_inline_structural_marker(2, "VariableInsertLine", "")
        self.assertEqual(marker, '/* {{ 2 "VariableInsertLine" "" */ // }} ""')

    def test_make_close_marker(self):
        self.assertEqual(make_close_marker(), '// }} ""')


class TestClsidRegistryCompleteness(unittest.TestCase):
    """19. All STEP_CLSID values are valid CLSID format."""

    def test_clsid_registry_completeness(self):
        for name, clsid in STEP_CLSID.items():
            with self.subTest(step=name):
                self.assertRegex(
                    clsid, _CLSID_RE,
                    f"STEP_CLSID[{name!r}] = {clsid!r} is not a valid CLSID"
                )

    def test_ml_star_clsid_format(self):
        for name, clsid in ML_STAR_CLSID.items():
            with self.subTest(device_step=name):
                self.assertTrue(clsid.startswith("ML_STAR:"),
                                f"ML_STAR_CLSID[{name!r}] missing 'ML_STAR:' prefix")
                bare = clsid.split(":", 1)[1]
                self.assertRegex(bare, _CLSID_RE,
                                 f"ML_STAR_CLSID[{name!r}] bare CLSID invalid")


class TestTripleBraceClsids(unittest.TestCase):
    """20. SingleLibFunction, SubmethodCall, Return use triple brace."""

    def test_triple_brace_clsids(self):
        self.assertTrue(is_triple_brace_clsid(STEP_CLSID["SingleLibFunction"]))
        self.assertTrue(is_triple_brace_clsid(STEP_CLSID["SubmethodCall"]))
        self.assertTrue(is_triple_brace_clsid(STEP_CLSID["Return"]))

    def test_non_triple_brace(self):
        self.assertFalse(is_triple_brace_clsid(STEP_CLSID["Comment"]))
        self.assertFalse(is_triple_brace_clsid(STEP_CLSID["Assignment"]))
        self.assertFalse(is_triple_brace_clsid(STEP_CLSID["Loop"]))

    def test_triple_brace_set_size(self):
        self.assertEqual(len(TRIPLE_BRACE_CLSIDS), 3)


class TestStepBuilders(unittest.TestCase):
    """21. comment_step, assignment_step, etc. produce correct MethodStep."""

    def test_comment_step(self):
        step = comment_step("Hello world")
        self.assertEqual(step.step_type, "Comment")
        self.assertTrue(any("TraceComment" in l for l in step.code))
        self.assertIn("Hello world", step.code[0])

    def test_comment_step_no_trace(self):
        step = comment_step("silent", trace=False)
        self.assertEqual(step.step_type, "Comment")
        self.assertFalse(any("TraceComment" in l for l in step.code))

    def test_assignment_step(self):
        step = assignment_step("myVar", "42")
        self.assertEqual(step.step_type, "Assignment")
        self.assertIn("myVar = 42;", step.code[0])

    def test_for_loop_step(self):
        body = [comment_step("inside loop")]
        step = for_loop_step("i", 10, body)
        self.assertEqual(step.step_type, "Loop")
        self.assertEqual(len(step.children), 1)
        self.assertIsNotNone(step.close_code)

    def test_while_loop_step(self):
        body = [comment_step("loop body")]
        step = while_loop_step("x > 0", "i", body)
        self.assertEqual(step.step_type, "Loop")
        self.assertTrue(any("while" in l for l in step.code))

    def test_if_else_step(self):
        then = [comment_step("then")]
        els = [comment_step("else")]
        step = if_else_step("x == 1", then, els)
        self.assertEqual(step.step_type, "IfThenElse")
        self.assertEqual(len(step.children), 1)
        self.assertEqual(len(step.else_children), 1)

    def test_submethod_call_step(self):
        step = submethod_call_step("MyFunc", ["arg1", "arg2"])
        self.assertEqual(step.step_type, "SubmethodCall")
        self.assertIn("MyFunc(arg1, arg2);", step.code[0])

    def test_library_function_step(self):
        step = library_function_step("HSLUtilLib2", "GetUniqueRunId", [])
        self.assertEqual(step.step_type, "SingleLibFunction")
        self.assertIn("HSLUtilLib2::GetUniqueRunId();", step.code[0])

    def test_abort_step(self):
        step = abort_step()
        self.assertEqual(step.step_type, "Abort")
        self.assertIn("abort;", step.code)

    def test_break_step(self):
        step = break_step()
        self.assertEqual(step.step_type, "Break")
        self.assertIn("break;", step.code)

    def test_return_step(self):
        step = return_step()
        self.assertEqual(step.step_type, "Return")
        self.assertIn("return;", step.code)

    def test_shell_step(self):
        step = shell_step('"notepad.exe"', wait=True)
        self.assertEqual(step.step_type, "Shell")
        self.assertIn("hslTrue", step.code[0])

    def test_shell_step_no_wait(self):
        step = shell_step('"calc.exe"', wait=False)
        self.assertIn("hslFalse", step.code[0])


class TestGenerateHslMethodOutput(unittest.TestCase):
    """22. Generated .hsl has correct structure."""

    def test_generate_hsl_method_output(self):
        steps = [comment_step("Test"), assignment_step("x", "1")]
        hsl, sub, info = generate_hsl_method(steps=steps, author="tester")

        # Must contain structural markers
        self.assertIn("LibraryInsertLine", hsl)
        self.assertIn("VariableInsertLine", hsl)
        self.assertIn("TemplateIncludeBlock", hsl)
        self.assertIn("AutoInitBlock", hsl)
        self.assertIn("AutoExitBlock", hsl)

        # Must contain main function boundary markers
        self.assertIn('"main" "Begin"', hsl)
        self.assertIn('"main" "End"', hsl)

        # Must contain the steps we added
        self.assertIn("TraceComment", hsl)
        self.assertIn("x = 1;", hsl)

        # Must end with a checksum line
        self.assertIn("$$checksum=", hsl)
        self.assertIn("$$author=tester$$", hsl)

        # generated_steps should have at least 2 entries
        self.assertGreaterEqual(len(info), 2)

    def test_generate_hsl_method_empty(self):
        hsl, sub, info = generate_hsl_method(steps=[], author="admin")
        self.assertIn('"main" "Begin"', hsl)
        self.assertIn("$$checksum=", hsl)
        self.assertEqual(len(info), 0)


class TestGenerateHslMethodSub(unittest.TestCase):
    """23. Generated .sub has OnAbort."""

    def test_generate_hsl_method_sub(self):
        _, sub, _ = generate_hsl_method(steps=[comment_step("x")])

        # .sub must contain OnAbort sections
        self.assertIn("OnAbort", sub)
        self.assertIn('"OnAbort" "Begin"', sub)
        self.assertIn('"OnAbort" "End"', sub)
        self.assertIn("SubmethodForwardDeclaration", sub)
        self.assertIn("SubmethodInsertLine", sub)
        self.assertIn("$$checksum=", sub)


class TestReconcileHeaderMismatch(unittest.TestCase):
    """24. Mismatched header gets corrected."""

    def test_reconcile_header_mismatch(self):
        # Build a block where the header GUID/CLSID disagrees with the code
        wrong_guid = "00000000_0000_0000_0000000000000000"
        real_guid = "122ed496_fe1b_4df4_aee6e5fe2130e41b"
        wrong_clsid = STEP_CLSID["Comment"]
        real_clsid_bare = "{541143F5-7FA2-11D3-AD85-0004ACB1DCB2}"
        real_clsid = f"ML_STAR:{real_clsid_bare}"

        step_lines = [
            f'// {{{{ 1 1 0 "{wrong_guid}" "{wrong_clsid}"',
            f'ML_STAR._541143F5_7FA2_11D3_AD85_0004ACB1DCB2("{real_guid}");',
            '// }} ""',
        ]
        content = _make_method_content(step_lines)
        result = reconcile_block_marker_headers(content)

        # The corrected header should reference the real GUID and CLSID
        self.assertIn(f'"{real_guid}"', result)
        self.assertIn(f'"{real_clsid}"', result)


class TestReconcileEmptyDeviceBlock(unittest.TestCase):
    """25. Empty device blocks removed."""

    def test_reconcile_empty_device_block(self):
        device_clsid = "ML_STAR:{541143F5-7FA2-11D3-AD85-0004ACB1DCB2}"
        guid = "aaaaaaaa_bbbb_cccc_dddddddddddddddd"
        step_lines = [
            f'// {{{{ 1 1 0 "{guid}" "{device_clsid}"',
            '',  # no code
            '// }} ""',
        ]
        content = _make_method_content(step_lines)
        result = reconcile_block_marker_headers(content)

        # The empty device block marker should be removed
        self.assertNotIn(f'"{device_clsid}"', result)


class TestExtractDeviceCall(unittest.TestCase):
    """26. Extract ML_STAR device call from code."""

    def test_extract_device_call(self):
        code_lines = [
            '{',
            'ML_STAR._541143F5_7FA2_11D3_AD85_0004ACB1DCB2'
            '("122ed496_fe1b_4df4_aee6e5fe2130e41b");',
            '}',
        ]
        info = extract_device_call_from_code(code_lines)
        self.assertIsNotNone(info)
        self.assertEqual(info.device, "ML_STAR")
        self.assertEqual(
            info.clsid,
            "ML_STAR:{541143F5-7FA2-11D3-AD85-0004ACB1DCB2}"
        )
        self.assertEqual(info.instance_guid,
                         "122ed496_fe1b_4df4_aee6e5fe2130e41b")

    def test_extract_device_call_none(self):
        code_lines = ["x = 1;", "y = 2;"]
        info = extract_device_call_from_code(code_lines)
        self.assertIsNone(info)


if __name__ == "__main__":
    unittest.main()
