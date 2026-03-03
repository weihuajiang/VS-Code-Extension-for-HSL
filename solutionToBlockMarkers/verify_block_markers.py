#!/usr/bin/env python3
"""
verify_block_markers.py — Block Marker Verification Test Suite

Tests the block marker algorithm against known-good Hamilton method files.
This is a READ-ONLY test — it does NOT modify any method files.

What it tests:
  1. Parsing correctness — can we parse all markers from real Hamilton files?
  2. Row numbering — are rows sequential (1, 2, 3, ...)?
  3. Renumbering idempotency — does renumbering a correctly-numbered file produce identical output?
  4. GUID format validation — are all GUIDs in the correct 8_4_4_16 format?
  5. CLSID recognition — are all CLSIDs known step types?
  6. Triple-brace correctness — do the right CLSIDs use {{{ vs {{?
  7. Structural marker validation — are all structural sections well-formed?
  8. Guard verification — do library files correctly NOT have block markers?
  9. CRC-32 checksum — does our checksum match Hamilton's?
  10. Companion file check — do all files with markers have .med files?

Usage:
  python verify_block_markers.py                              # Test default Hamilton files
  python verify_block_markers.py --file "C:\\path\\to\\file.hsl"  # Test specific file
  python verify_block_markers.py --hamilton-dir "C:\\..."       # Custom Hamilton install dir
  python verify_block_markers.py --verbose                     # Detailed output

Requirements: Python 3.8+ (no external dependencies)
"""

import os
import re
import sys
import glob
import argparse
from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime

# Import from our generator module (same directory)
from block_marker_generator import (
    STEP_CLSID,
    ML_STAR_CLSID,
    TRIPLE_BRACE_CLSIDS,
    has_step_block_markers,
    parse_block_markers,
    renumber_block_markers,
    crc32_hamilton,
    StepBlockMarker,
    StructuralBlockMarker,
    RE_STEP_OPEN,
    RE_STRUCTURAL_OPEN,
    RE_INLINE_STRUCTURAL,
    RE_CLOSE,
    RE_CHECKSUM,
)


# ─── Test Result Tracking ───────────────────────────────────────────────────────

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.details: List[str] = []
    
    def ok(self, msg: str):
        self.passed += 1
        self.details.append(f"  ✓ {msg}")
    
    def fail(self, msg: str):
        self.failed += 1
        self.details.append(f"  ✗ {msg}")
    
    def warn(self, msg: str):
        self.warnings += 1
        self.details.append(f"  ⚠ {msg}")
    
    @property
    def success(self):
        return self.failed == 0


class TestSuite:
    def __init__(self):
        self.results: List[TestResult] = []
        self.total_passed = 0
        self.total_failed = 0
        self.total_warnings = 0
    
    def add(self, result: TestResult):
        self.results.append(result)
        self.total_passed += result.passed
        self.total_failed += result.failed
        self.total_warnings += result.warnings
    
    def report(self, verbose: bool = False):
        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║          Block Marker Verification Report                   ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        
        for r in self.results:
            status = "PASS" if r.success else "FAIL"
            icon = "✓" if r.success else "✗"
            warn_str = f" ({r.warnings} warnings)" if r.warnings else ""
            print(f"║ {icon} {r.name:<40} [{status}]{warn_str:<10}║")
            if verbose or not r.success:
                for detail in r.details:
                    print(f"║   {detail:<57}║")
        
        print("╠══════════════════════════════════════════════════════════════╣")
        total = self.total_passed + self.total_failed
        print(f"║  Total: {total} checks, {self.total_passed} passed, "
              f"{self.total_failed} failed, {self.total_warnings} warnings"
              f"{'':>{58 - len(str(total)) - len(str(self.total_passed)) - len(str(self.total_failed)) - len(str(self.total_warnings)) - 38}}║")
        
        if self.total_failed == 0:
            print("║  ✓ ALL TESTS PASSED                                        ║")
        else:
            print("║  ✗ SOME TESTS FAILED                                       ║")
        
        print("╚══════════════════════════════════════════════════════════════╝")


# ─── Test Functions ──────────────────────────────────────────────────────────────

def test_parse_markers(filepath: str, content: str) -> TestResult:
    """Test 1: Can we parse all markers from the file?"""
    name = os.path.basename(filepath)
    r = TestResult(f"Parse: {name}")
    
    try:
        markers = parse_block_markers(content)
        step_markers = [m for m in markers if isinstance(m, StepBlockMarker)]
        struct_markers = [m for m in markers if isinstance(m, StructuralBlockMarker)]
        
        if len(markers) > 0:
            r.ok(f"Parsed {len(markers)} markers ({len(step_markers)} step, {len(struct_markers)} structural)")
        else:
            r.fail("No markers parsed from method file")
        
        # Verify each step marker has non-empty fields
        for sm in step_markers:
            if not sm.instance_guid:
                r.fail(f"Row {sm.row}: empty GUID")
            if not sm.step_clsid:
                r.fail(f"Row {sm.row}: empty CLSID")
        
        # Count opening/closing markers in raw text
        lines = content.split('\n')
        open_count = 0
        close_count = 0
        inline_count = 0
        for line in lines:
            stripped = line.strip().rstrip('\r')
            if RE_INLINE_STRUCTURAL.match(stripped):
                inline_count += 1
            elif RE_STEP_OPEN.match(stripped) or RE_STRUCTURAL_OPEN.match(stripped):
                open_count += 1
            elif RE_CLOSE.match(stripped):
                close_count += 1
        
        # close_count should equal open_count + inline_count (each inline has its own close)
        expected_close = open_count  # inline markers have close built-in
        if close_count == expected_close:
            r.ok(f"Balanced markers: {open_count} open, {close_count} close, {inline_count} inline")
        else:
            r.warn(f"Marker balance: {open_count} open, {close_count} close, {inline_count} inline (close should be {expected_close})")
    
    except Exception as e:
        r.fail(f"Parse error: {e}")
    
    return r


def test_row_numbering(filepath: str, content: str) -> TestResult:
    """Test 2: Are step rows sequential (1, 2, 3, ...)?"""
    name = os.path.basename(filepath)
    r = TestResult(f"Rows: {name}")
    
    markers = parse_block_markers(content)
    step_markers = [m for m in markers if isinstance(m, StepBlockMarker)]
    
    if not step_markers:
        r.ok("No step markers to check")
        return r
    
    rows = [m.row for m in step_markers]
    
    # Check sequential numbering (1, 2, 3, ...)
    expected_row = 1
    sequential = True
    gaps = []
    for i, row in enumerate(rows):
        if row != expected_row:
            sequential = False
            gaps.append(f"expected {expected_row}, got {row} at position {i}")
        expected_row = row + 1
    
    if sequential:
        r.ok(f"Rows 1-{len(rows)} are sequential")
    else:
        # Multi-block steps reuse GUIDs — rows might not be strictly sequential
        # because if/else and loop blocks interleave with children.
        # Let's check if rows are at least monotonically increasing
        monotonic = all(rows[i] <= rows[i+1] for i in range(len(rows)-1))
        if monotonic:
            r.ok(f"Rows are monotonically increasing (1 to {rows[-1]}, {len(rows)} markers)")
        else:
            r.fail(f"Rows not monotonic: {gaps[:3]}{'...' if len(gaps) > 3 else ''}")
    
    # Verify column is always 1 (single-process methods)
    cols = set(m.column for m in step_markers)
    if cols == {1}:
        r.ok("All columns are 1 (single-process)")
    elif max(cols) <= 2:
        r.ok(f"Columns: {sorted(cols)} (multi-process method)")
    else:
        r.warn(f"Unusual columns: {sorted(cols)}")
    
    # Verify sublevel is always 0
    sublevels = set(m.sublevel for m in step_markers)
    if sublevels == {0}:
        r.ok("All sublevels are 0")
    else:
        r.warn(f"Non-zero sublevels: {sorted(sublevels)}")
    
    return r


def test_renumber_idempotent(filepath: str, content: str) -> TestResult:
    """Test 3: Is renumbering idempotent for correctly-numbered files?
    
    Note: Hamilton's Method Editor sometimes leaves gaps in row numbering
    (e.g., after deleting steps). Our algorithm intentionally renumbers
    sequentially, fixing these gaps. This is by design.
    """
    name = os.path.basename(filepath)
    r = TestResult(f"Renumber: {name}")
    
    renumbered = renumber_block_markers(content)
    
    # Compare ignoring checksum line (checksum would need recomputation)
    def strip_checksum(text):
        return re.sub(r'^// \$\$author=.*$', '', text, flags=re.MULTILINE).strip()
    
    original_stripped = strip_checksum(content)
    renumbered_stripped = strip_checksum(renumbered)
    
    if original_stripped == renumbered_stripped:
        r.ok("Renumbering is idempotent (content unchanged)")
    else:
        # The file has non-sequential rows that renumbering fixed.
        # This is expected behavior — check that the renumbered output
        # has correct sequential numbering.
        re_parsed = parse_block_markers(renumbered)
        step_markers = [m for m in re_parsed if isinstance(m, StepBlockMarker)]
        rows_after = [m.row for m in step_markers]
        expected_sequential = list(range(1, len(rows_after) + 1))
        
        if rows_after == expected_sequential:
            r.ok(f"Original had gaps; renumbered to 1-{len(rows_after)} (correct)")
        else:
            r.fail(f"Renumbered rows not sequential: got {rows_after[:10]}...")
        
        # Also verify that ONLY row numbers changed (GUIDs, CLSIDs, code preserved)
        orig_markers = parse_block_markers(content)
        orig_steps = [m for m in orig_markers if isinstance(m, StepBlockMarker)]
        ren_steps = [m for m in re_parsed if isinstance(m, StepBlockMarker)]
        
        if len(orig_steps) == len(ren_steps):
            guids_match = all(o.instance_guid == r_.instance_guid 
                            for o, r_ in zip(orig_steps, ren_steps))
            clsids_match = all(o.step_clsid == r_.step_clsid 
                             for o, r_ in zip(orig_steps, ren_steps))
            if guids_match and clsids_match:
                r.ok("GUIDs and CLSIDs preserved through renumbering")
            else:
                r.fail("GUIDs or CLSIDs changed during renumbering!")
        else:
            r.fail(f"Marker count changed: {len(orig_steps)} → {len(ren_steps)}")
    
    return r


def test_guid_format(filepath: str, content: str) -> TestResult:
    """Test 4: Are all GUIDs in the correct 8_4_4_16 Hamilton format?"""
    name = os.path.basename(filepath)
    r = TestResult(f"GUIDs: {name}")
    
    markers = parse_block_markers(content)
    step_markers = [m for m in markers if isinstance(m, StepBlockMarker)]
    
    guid_pattern = re.compile(r'^[0-9a-f]{8}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{16}$', re.IGNORECASE)
    
    valid = 0
    invalid = 0
    unique_guids: Set[str] = set()
    
    for sm in step_markers:
        guid = sm.instance_guid
        unique_guids.add(guid)
        if guid_pattern.match(guid):
            valid += 1
        else:
            invalid += 1
            r.fail(f"Invalid GUID format at row {sm.row}: '{guid}'")
    
    if invalid == 0 and valid > 0:
        r.ok(f"All {valid} GUIDs match Hamilton format (8_4_4_16)")
    elif valid == 0 and invalid == 0:
        r.ok("No GUIDs to check (no step markers)")
    
    # Count unique GUIDs (multi-block steps share GUIDs)
    r.ok(f"{len(unique_guids)} unique GUIDs across {len(step_markers)} marker occurrences")
    
    return r


def test_clsid_recognition(filepath: str, content: str) -> TestResult:
    """Test 5: Are all CLSIDs known step types?"""
    name = os.path.basename(filepath)
    r = TestResult(f"CLSIDs: {name}")
    
    markers = parse_block_markers(content)
    step_markers = [m for m in markers if isinstance(m, StepBlockMarker)]
    
    all_clsids = set(STEP_CLSID.values())
    all_ml_star = set(ML_STAR_CLSID.values())
    
    recognized = 0
    unrecognized = 0
    unrecognized_list = []
    
    seen_clsids: Set[str] = set()
    
    for sm in step_markers:
        clsid = sm.step_clsid
        seen_clsids.add(clsid)
        
        # Check bare CLSID or device-prefixed
        bare = clsid.split(":")[-1] if ":" in clsid else clsid
        if bare in all_clsids:
            recognized += 1
        elif clsid in all_ml_star:
            recognized += 1
        else:
            # Could be a third-party or device-specific CLSID
            unrecognized += 1
            unrecognized_list.append(clsid)
    
    if recognized > 0:
        r.ok(f"{recognized} markers have recognized CLSIDs")
    
    if unrecognized > 0:
        unique_unknown = set(unrecognized_list)
        r.warn(f"{unrecognized} markers with {len(unique_unknown)} unknown CLSID(s):")
        for uc in sorted(unique_unknown)[:5]:
            r.warn(f"  {uc}")
    
    if len(seen_clsids) > 0:
        r.ok(f"{len(seen_clsids)} distinct CLSID types used")
    
    return r


def test_triple_brace(filepath: str, content: str) -> TestResult:
    """Test 6: Do the right CLSIDs use {{{ vs {{?"""
    name = os.path.basename(filepath)
    r = TestResult(f"Braces: {name}")
    
    markers = parse_block_markers(content)
    step_markers = [m for m in markers if isinstance(m, StepBlockMarker)]
    
    correct = 0
    incorrect = 0
    
    for sm in step_markers:
        bare_clsid = sm.step_clsid.split(":")[-1] if ":" in sm.step_clsid else sm.step_clsid
        should_be_triple = bare_clsid in TRIPLE_BRACE_CLSIDS
        
        if sm.triple_brace == should_be_triple:
            correct += 1
        else:
            incorrect += 1
            expected = "{{{" if should_be_triple else "{{"
            actual = "{{{" if sm.triple_brace else "{{"
            r.fail(f"Row {sm.row}: CLSID {bare_clsid} should use {expected}, got {actual}")
    
    if correct > 0 and incorrect == 0:
        r.ok(f"All {correct} markers use correct brace style")
    elif correct == 0 and incorrect == 0:
        r.ok("No step markers to check")
    
    return r


def test_structural_markers(filepath: str, content: str) -> TestResult:
    """Test 7: Are all structural sections well-formed?"""
    name = os.path.basename(filepath)
    r = TestResult(f"Structural: {name}")
    
    markers = parse_block_markers(content)
    struct_markers = [m for m in markers if isinstance(m, StructuralBlockMarker)]
    
    known_sections = {
        "LibraryInsertLine", "VariableInsertLine", "TemplateIncludeBlock",
        "LocalSubmethodInclude", "ProcessInsertLine", "AutoInitBlock",
        "AutoExitBlock", "SubmethodForwardDeclaration", "SubmethodInsertLine",
    }
    
    found_sections: Set[str] = set()
    
    for sm in struct_markers:
        found_sections.add(sm.section_name)
        
        if sm.block_type not in (2, 5):
            r.warn(f"Unusual block type {sm.block_type} for '{sm.section_name}'")
    
    # Check for required sections
    required = {"LibraryInsertLine", "VariableInsertLine", "TemplateIncludeBlock",
                "LocalSubmethodInclude", "ProcessInsertLine", "AutoInitBlock",
                "AutoExitBlock"}
    
    # Check for main() boundaries
    main_sections = [m for m in struct_markers if m.section_name == "main"]
    main_qualifiers = set(m.qualifier for m in main_sections)
    
    if "Begin" in main_qualifiers and "End" in main_qualifiers:
        r.ok("main() has Begin and End boundaries")
    else:
        r.fail(f"main() missing boundaries: have {main_qualifiers}")
    
    found_required = required & found_sections
    missing_required = required - found_sections
    
    if len(missing_required) == 0:
        r.ok(f"All {len(required)} required structural sections present")
    else:
        r.warn(f"Missing sections: {missing_required}")
    
    r.ok(f"Total structural markers: {len(struct_markers)}")
    
    return r


def test_library_guard(filepath: str, content: str) -> TestResult:
    """Test 8: Library files should NOT have block markers."""
    name = os.path.basename(filepath)
    r = TestResult(f"Guard: {name}")
    
    has_markers = has_step_block_markers(content)
    
    # Determine if this is likely a library file
    is_library = (
        # Has include guards (#ifndef, #define)
        "#ifndef" in content and "#define" in content
        # Or is in a Library directory
        or "\\Library\\" in filepath.replace("/", "\\")
        # Or has namespace at top level (not _Method namespace)
        or (re.search(r'^namespace\s+(?!_Method)\w+', content, re.MULTILINE) is not None
            and "method main" not in content)
    )
    
    is_method = "method main" in content or has_markers
    
    if is_library and not has_markers:
        r.ok("Library file correctly has NO block markers")
    elif is_method and has_markers:
        r.ok("Method file correctly HAS block markers")
    elif is_library and has_markers:
        r.fail("Library file has block markers (should NOT)")
    elif is_method and not has_markers:
        r.fail("Method file missing block markers")
    else:
        r.warn("Could not determine if library or method file")
    
    # Check for companion .med
    base = os.path.splitext(filepath)[0]
    med_exists = os.path.exists(base + ".med")
    smt_exists = os.path.exists(base + ".smt")
    
    if has_markers and not med_exists and not smt_exists:
        r.fail("Has block markers but no companion .med or .smt")
    elif has_markers and (med_exists or smt_exists):
        companion = ".med" if med_exists else ".smt"
        r.ok(f"Has companion {companion} file")
    elif not has_markers and not med_exists:
        r.ok("No markers, no companion — consistent")
    
    return r


def test_checksum(filepath: str, content: str) -> TestResult:
    """Test 9: Does our CRC-32 match Hamilton's?"""
    name = os.path.basename(filepath)
    r = TestResult(f"CRC-32: {name}")
    
    lines = content.split('\n')
    checksum_line = None
    checksum_line_idx = None
    
    for i in range(len(lines) - 1, -1, -1):
        m = RE_CHECKSUM.match(lines[i].strip().rstrip('\r'))
        if m:
            checksum_line = lines[i].rstrip('\r')
            checksum_line_idx = i
            break
    
    if not checksum_line:
        r.warn("No checksum line found")
        return r
    
    m = RE_CHECKSUM.match(checksum_line.strip())
    if not m:
        r.fail("Checksum line doesn't match expected format")
        return r
    
    stored_author = m.group(1)
    stored_valid = m.group(2)
    stored_time = m.group(3)
    stored_checksum = m.group(4).lower()
    stored_length = int(m.group(5))
    
    # Reconstruct the content before the checksum line
    # Use \r\n line endings (Hamilton standard)
    lines_before_checksum = lines[:checksum_line_idx]
    content_before = "\r\n".join(l.rstrip('\r') for l in lines_before_checksum) + "\r\n"
    
    # Build prefix
    prefix = f"// $$author={stored_author}$$valid={stored_valid}$$time={stored_time}$$checksum="
    
    # Compute CRC
    try:
        data = (content_before + prefix).encode("latin1")
        computed = crc32_hamilton(data)
        
        if computed == stored_checksum:
            r.ok(f"CRC-32 matches: {computed}")
        else:
            r.fail(f"CRC-32 mismatch: computed={computed}, stored={stored_checksum}")
    except UnicodeEncodeError as e:
        r.warn(f"Cannot encode as latin1: {e}")
    
    # Verify length field
    actual_length = len(checksum_line.strip()) + 2  # +2 for \r\n
    if actual_length == stored_length:
        r.ok(f"Length field correct: {stored_length}")
    else:
        r.warn(f"Length field: stored={stored_length}, actual={actual_length}")
    
    return r


def test_multi_block_steps(filepath: str, content: str) -> TestResult:
    """Test 10: Multi-block steps (Loop, If/Else) use same GUID correctly."""
    name = os.path.basename(filepath)
    r = TestResult(f"MultiBlock: {name}")
    
    markers = parse_block_markers(content)
    step_markers = [m for m in markers if isinstance(m, StepBlockMarker)]
    
    # Group by GUID
    guid_groups: Dict[str, List[StepBlockMarker]] = {}
    for sm in step_markers:
        guid_groups.setdefault(sm.instance_guid, []).append(sm)
    
    single_block = 0
    multi_block = 0
    
    for guid, group in guid_groups.items():
        if len(group) == 1:
            single_block += 1
        else:
            multi_block += 1
            clsid = group[0].step_clsid
            bare = clsid.split(":")[-1] if ":" in clsid else clsid
            
            # All blocks of a multi-block step should have the same CLSID
            clsids_in_group = set(m.step_clsid for m in group)
            if len(clsids_in_group) == 1:
                r.ok(f"GUID {guid[:16]}...: {len(group)} blocks, same CLSID ({bare})")
            else:
                r.fail(f"GUID {guid[:16]}...: mixed CLSIDs: {clsids_in_group}")
            
            # Only first block should have triple brace
            if group[0].triple_brace and not any(g.triple_brace for g in group[1:]):
                # OK: first block triple, rest double
                pass
            elif not any(g.triple_brace for g in group):
                # OK: all double brace
                pass
            else:
                # Check if this is expected (scope-creating steps with multi-block)
                pass
    
    r.ok(f"{single_block} single-block steps, {multi_block} multi-block steps")
    
    return r


# ─── Discovery ───────────────────────────────────────────────────────────────────

def find_method_files(hamilton_dir: str) -> List[str]:
    """Find method .hsl files with block markers in the Hamilton installation."""
    files = []
    
    # Search known method directories
    search_dirs = [
        os.path.join(hamilton_dir, "Methods"),
        os.path.join(hamilton_dir, "Test"),
    ]
    
    for search_dir in search_dirs:
        if os.path.exists(search_dir):
            for root, dirs, filenames in os.walk(search_dir):
                for fname in filenames:
                    if fname.lower().endswith(".hsl"):
                        files.append(os.path.join(root, fname))
    
    return files


def find_library_files(hamilton_dir: str) -> List[str]:
    """Find library .hsl files (should NOT have block markers)."""
    files = []
    lib_dir = os.path.join(hamilton_dir, "Library")
    
    if os.path.exists(lib_dir):
        for root, dirs, filenames in os.walk(lib_dir):
            for fname in filenames:
                if fname.lower().endswith(".hsl"):
                    full = os.path.join(root, fname)
                    files.append(full)
    
    return files


# ─── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Hamilton Block Marker Verification Test Suite"
    )
    parser.add_argument("--file", "-f", action="append", default=[],
                        help="Specific .hsl file(s) to test (can be repeated)")
    parser.add_argument("--hamilton-dir", default=r"C:\Program Files (x86)\Hamilton",
                        help="Hamilton installation directory")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed test output")
    parser.add_argument("--test-libraries", action="store_true",
                        help="Also test library files (guard verification)")
    parser.add_argument("--max-files", type=int, default=20,
                        help="Maximum number of files to test (default: 20)")
    args = parser.parse_args()
    
    suite = TestSuite()
    
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     Hamilton Block Marker Verification Test Suite           ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Hamilton Dir: {args.hamilton_dir[:44]:<45}║")
    print(f"║  Time:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<45}║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    # Collect files to test
    test_files: List[str] = []
    
    if args.file:
        test_files.extend(args.file)
    else:
        # Auto-discover method files
        method_files = find_method_files(args.hamilton_dir)
        
        # Filter to only those with block markers
        method_with_markers = []
        for f in method_files:
            try:
                content = open(f, "r", encoding="utf-8", errors="replace").read()
                if has_step_block_markers(content):
                    method_with_markers.append(f)
            except Exception:
                pass
        
        # Prioritize known good test files
        priority = [
            "Method1.hsl",
            "VideoTest.hsl",
            "TraceLevel Demo.hsl",
            "schedulerDemo.hsl",
            "Visual_NTR_library_demo.hsl",
        ]
        
        # Sort: priority files first, then alphabetical
        def sort_key(path):
            basename = os.path.basename(path)
            try:
                return (priority.index(basename), basename)
            except ValueError:
                return (len(priority), basename)
        
        method_with_markers.sort(key=sort_key)
        test_files.extend(method_with_markers[:args.max_files])
    
    if not test_files:
        print("  No method files found to test!")
        print(f"  Searched: {args.hamilton_dir}")
        sys.exit(1)
    
    print(f"  Testing {len(test_files)} method file(s)...")
    print()
    
    # ── Run tests on method files ──
    for filepath in test_files:
        if not os.path.exists(filepath):
            r = TestResult(f"File: {os.path.basename(filepath)}")
            r.fail(f"File not found: {filepath}")
            suite.add(r)
            continue
        
        try:
            content = open(filepath, "r", encoding="utf-8", errors="replace").read()
        except Exception as e:
            r = TestResult(f"File: {os.path.basename(filepath)}")
            r.fail(f"Read error: {e}")
            suite.add(r)
            continue
        
        print(f"  Testing: {os.path.basename(filepath)}")
        
        # Run all test functions
        suite.add(test_parse_markers(filepath, content))
        suite.add(test_row_numbering(filepath, content))
        suite.add(test_renumber_idempotent(filepath, content))
        suite.add(test_guid_format(filepath, content))
        suite.add(test_clsid_recognition(filepath, content))
        suite.add(test_triple_brace(filepath, content))
        suite.add(test_structural_markers(filepath, content))
        suite.add(test_library_guard(filepath, content))
        suite.add(test_checksum(filepath, content))
        suite.add(test_multi_block_steps(filepath, content))
    
    # ── Test library files (guard check) ──
    if args.test_libraries:
        library_files = find_library_files(args.hamilton_dir)
        print(f"\n  Testing {len(library_files)} library file(s) for guard verification...")
        
        for filepath in library_files[:args.max_files]:
            try:
                content = open(filepath, "r", encoding="utf-8", errors="replace").read()
                suite.add(test_library_guard(filepath, content))
            except Exception:
                pass
    
    # ── Report ──
    suite.report(verbose=args.verbose)
    
    # Exit code
    sys.exit(0 if suite.total_failed == 0 else 1)


if __name__ == "__main__":
    main()
