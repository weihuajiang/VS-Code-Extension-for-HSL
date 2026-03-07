#!/usr/bin/env python3
"""
block_markers.py -- Hamilton HSL Block Marker Generator, Parser & Reconciler

A comprehensive standalone Python module for working with Hamilton HSL block markers.
Combines and enhances functionality from:
  - solutionToBlockMarkers/block_marker_generator.py (Python reference implementation)
  - src/blockMarkers.ts (TypeScript VS Code extension, with additional repair features)

Block Marker Format
===================
Hamilton HSL method files (.hsl) use structured comments called "block markers" to
associate regions of code with compound step instances in the Method Editor GUI.
Every step visible in the Hamilton Method Editor is wrapped with an opening marker
comment and a closing marker comment.

There are TWO kinds of block markers:

1. **Step Block Markers** -- wrap code belonging to a single compound step (e.g. Comment,
   Assignment, Loop, If/Then/Else, device commands, etc.)

   Opening formats:
     ``// {{ ROW COL SUBLEVEL "instance_guid" "step_clsid"``       (double-brace)
     ``// {{{ ROW COL SUBLEVEL "instance_guid" "step_clsid"``      (triple-brace, scope-creating)

   Closing format:
     ``// }} ""``

   Fields:
     - ROW: 1-based visual position of the step in the Method Editor step list
     - COL: Column number (always 1 for single-process methods)
     - SUBLEVEL: Sub-level (0 for most steps)
     - instance_guid: Hamilton underscore-format GUID (``xxxxxxxx_xxxx_xxxx_xxxxxxxxxxxxxxxx``)
       that uniquely identifies this step instance; shared across all blocks of the same step
       (e.g. an If/Then/Else step has 3 blocks sharing one GUID)
     - step_clsid: COM CLSID identifying the step type, e.g.
       ``{F07B0071-8EFC-11d4-A3BA-002035848439}`` for Comment;
       device steps carry a prefix like ``ML_STAR:{541143F5-7FA2-11D3-AD85-0004ACB1DCB2}``

   Triple-brace ``{{{`` is used for scope-creating / external-reference steps:
     - SingleLibFunction (Smart Steps / library calls)
     - SubmethodCall
     - Return

2. **Structural Block Markers** -- delimit file-level sections that are not individual
   steps but are required by the Method Editor framework.

   Opening formats:
     ``// {{ LEVEL "SectionName" "Qualifier"``        (block with content)
     ``// {{{ LEVEL "SectionName" "Qualifier"``       (scope-creating structural)
     ``/* {{ LEVEL "SectionName" "Qualifier" */ // }} ""``   (inline / empty section)

   Closing format (same as step):
     ``// }} ""``

   Common sections:
     - Level 2: LibraryInsertLine, VariableInsertLine, TemplateIncludeBlock,
       LocalSubmethodInclude, ProcessInsertLine, AutoInitBlock, AutoExitBlock,
       SubmethodForwardDeclaration, SubmethodInsertLine
     - Level 5: function boundaries -- ``"main" "Begin"``, ``"main" "InitLocals"``,
       ``"main" "End"``, ``"OnAbort" "Begin"``, etc.

Checksum Footer
===============
Every Hamilton file ends with a checksum line:
  ``// $$author=<name>$$valid=<0|1>$$time=<YYYY-MM-DD HH:MM>$$checksum=<8hex>$$length=<NNN>$$``

The CRC-32 is computed over all preceding content plus the prefix through ``checksum=``.

This module provides
====================
- CLSID dictionaries (STEP_CLSID, ML_STAR_CLSID, TRIPLE_BRACE_CLSIDS)
- GUID utilities (generate, convert between Hamilton and standard formats)
- Block marker regex patterns and detection
- Parsing of step and structural block markers
- Block marker generation functions
- Row renumbering
- MethodStep class and step builder helpers
- Generation state and HSL method file generation
- Device call extraction from code (single and batch)
- Comprehensive block marker reconciliation / repair (reconcile_block_marker_headers)
- Orphan code wrapping (second-pass repair)
- CLI entry point for demos and CLSID display

Usage::

    # As a library
    from standalone_med_tools.block_markers import (
        STEP_CLSID, parse_block_markers, generate_hsl_method, comment_step,
        reconcile_block_marker_headers, renumber_block_markers,
    )

    # As a CLI tool
    python -m standalone_med_tools.block_markers --show-clsids
    python -m standalone_med_tools.block_markers --demo-complex
    python -m standalone_med_tools.block_markers --steps 5

Requirements: Python 3.8+ (no external dependencies)
"""

from __future__ import annotations

import uuid
import re
import os
import sys
import argparse
from datetime import datetime
from typing import (
    List,
    Dict,
    Tuple,
    Optional,
    NamedTuple,
    Set,
    Union,
)

from .checksum import (
    crc32_hamilton,
    compute_hsl_checksum,
    generate_checksum_line,
    finalize_hsl_file,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CLSID Registry
# ═══════════════════════════════════════════════════════════════════════════════

STEP_CLSID: Dict[str, str] = {
    # General steps
    "Comment":          "{F07B0071-8EFC-11d4-A3BA-002035848439}",
    "Assignment":       "{B31F3543-5D80-11d4-A5EB-0050DA737D89}",
    "MathExpression":   "{B31F3544-5D80-11d4-A5EB-0050DA737D89}",
    "IfThenElse":       "{B31F3531-5D80-11d4-A5EB-0050DA737D89}",
    "Loop":             "{B31F3532-5D80-11d4-A5EB-0050DA737D89}",
    "Break":            "{B31F3533-5D80-11d4-A5EB-0050DA737D89}",
    "Return":           "{9EC997CD-FD3B-4280-811B-49E99DCF062C}",
    "Abort":            "{930D6C31-8EFB-11d4-A3BA-002035848439}",
    "Shell":            "{B31F3545-5D80-11d4-A5EB-0050DA737D89}",

    # File operations
    "FileOpen":         "{B31F3534-5D80-11d4-A5EB-0050DA737D89}",
    "FileFind":         "{B31F3535-5D80-11d4-A5EB-0050DA737D89}",
    "FileRead":         "{B31F3536-5D80-11d4-A5EB-0050DA737D89}",
    "FileWrite":        "{B31F3537-5D80-11d4-A5EB-0050DA737D89}",
    "FileClose":        "{B31F3538-5D80-11d4-A5EB-0050DA737D89}",

    # Dialogs
    "UserInput":        "{B31F3539-5D80-11d4-A5EB-0050DA737D89}",
    "UserOutput":       "{21E07B31-8D2E-11d4-A3B8-002035848439}",

    # Sequences
    "SetCurrentSeqPos": "{B31F353A-5D80-11d4-A5EB-0050DA737D89}",
    "GetCurrentSeqPos": "{B31F353B-5D80-11d4-A5EB-0050DA737D89}",
    "SetTotalSeqCount": "{B31F353C-5D80-11d4-A5EB-0050DA737D89}",
    "GetTotalSeqCount": "{B31F353D-5D80-11d4-A5EB-0050DA737D89}",
    "AlignSequences":   "{EBC6FD39-B416-4461-BD0E-312FBC5AEF1F}",

    # Timers
    "StartTimer":       "{B31F353E-5D80-11d4-A5EB-0050DA737D89}",
    "WaitTimer":        "{B31F353F-5D80-11d4-A5EB-0050DA737D89}",
    "ReadElapsedTime":  "{B31F3540-5D80-11d4-A5EB-0050DA737D89}",
    "ResetTimer":       "{B31F3541-5D80-11d4-A5EB-0050DA737D89}",
    "StopTimer":        "{83FFBD43-B4F2-4ECB-BE0A-1A183AC5063D}",

    # Events
    "WaitForEvent":     "{D97BA841-8303-11d4-A3AC-002035848439}",
    "SetEvent":         "{90ADC087-865A-4b6c-A658-A0F3AE1E29C4}",

    # Function calls
    "LibraryFunction":      "{B31F3542-5D80-11d4-A5EB-0050DA737D89}",
    "SingleLibFunction":    "{C1F3C015-47B3-4514-9407-AC2E65043419}",
    "SubmethodCall":        "{7C4EF7A7-39BE-406a-897F-71F3A35B4093}",

    # COM Port
    "ComPortOpen":      "{7AC8762F-512C-4f2c-8D1F-A86A73A6FA99}",
    "ComPortRead":      "{6B1F17F6-3E69-4bbd-A8F2-3214BFB930AA}",
    "ComPortWrite":     "{6193FE29-76EE-483b-AB12-EDDF6CB95FDD}",
    "ComPortClose":     "{EB07D635-0C14-4880-8F99-4301CB1D4E3B}",

    # Array operations
    "ArrayDeclare":     "{4900C1F7-0FB7-4033-8253-760BDB9354DC}",
    "ArraySetAt":       "{F17B7626-27CB-47f1-8477-8C4158339A6D}",
    "ArrayGetAt":       "{67A8F1C9-6546-41e9-AD2F-3C54F7818853}",
    "ArrayGetSize":     "{72EACF88-8D49-43e3-92C8-2F90E81E3260}",
    "ArrayCopy":        "{DB5A2B39-67F2-4a78-A78F-DAF3FB056366}",

    # Error handling
    "UserErrorHandling": "{3293659E-F71E-472f-AFB4-6A674E32B114}",

    # Threading
    "ThreadBegin":      "{1A4D922E-531A-405b-BF19-FFD9AF850726}",
    "ThreadWaitFor":    "{7DA7AD24-F79A-43aa-A47C-A7F0B82CCA71}",

    # Scheduler
    "SchedulerActivity": "{4FB3C56D-3EF5-4317-8A5B-7CDFAC1CAC8F}",

    # Custom Dialog
    "CustomDialog":     "{998A7CCC-4374-484D-A6ED-E8A4F0EB71BA}",

    # Group Separator (invisible in code, visible in GUI)
    "GroupSeparator":   "{586C3429-F931-405f-9938-928E22C90BFA}",
}
"""Registry of known Hamilton Method Editor compound step CLSIDs.

Keys are human-readable step type names; values are COM CLSIDs in
``{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}`` format.
"""

ML_STAR_CLSID: Dict[str, str] = {
    "Initialize":           "ML_STAR:{1C0C0CB0-7C87-11D3-AD83-0004ACB1DCB2}",
    "LoadCarrier":          "ML_STAR:{54114402-7FA2-11D3-AD85-0004ACB1DCB2}",
    "UnloadCarrier":        "ML_STAR:{54114400-7FA2-11D3-AD85-0004ACB1DCB2}",
    "TipPickUp":            "ML_STAR:{541143FA-7FA2-11D3-AD85-0004ACB1DCB2}",
    "Aspirate":             "ML_STAR:{541143F5-7FA2-11D3-AD85-0004ACB1DCB2}",
    "Dispense":             "ML_STAR:{541143F8-7FA2-11D3-AD85-0004ACB1DCB2}",
    "TipEject":             "ML_STAR:{541143FC-7FA2-11D3-AD85-0004ACB1DCB2}",
    "MoveAutoLoad":         "ML_STAR:{EA251BFB-66DE-48D1-83E5-6884B4DD8D11}",
    "GetLastLiquidLevel":   "ML_STAR:{9FB6DFE0-4132-4d09-B502-98C722734D4C}",
}
"""ML_STAR device-specific CLSIDs.

These carry a ``ML_STAR:`` prefix before the CLSID and are used for
Hamilton STAR instrument-specific commands.
"""

TRIPLE_BRACE_CLSIDS: Set[str] = {
    STEP_CLSID["SingleLibFunction"],   # {C1F3C015-47B3-4514-9407-AC2E65043419}
    STEP_CLSID["SubmethodCall"],       # {7C4EF7A7-39BE-406a-897F-71F3A35B4093}
    STEP_CLSID["Return"],             # {9EC997CD-FD3B-4280-811B-49E99DCF062C}
}
"""CLSIDs that use triple-brace ``{{{`` markers (scope-creating / external reference steps).

These steps reference code from other files (submethods, library functions) and
open a new scope in the HSL interpreter.
"""

# CLSIDs that are "single statement per block" types -- used by the reconciler
# to detect when multiple statements were incorrectly merged into one block.
SINGLE_STATEMENT_CLSIDS: Set[str] = {
    STEP_CLSID["SingleLibFunction"],
    STEP_CLSID["Assignment"],
    STEP_CLSID["MathExpression"],
    STEP_CLSID["Abort"],
    STEP_CLSID["SetCurrentSeqPos"],
    STEP_CLSID["GetCurrentSeqPos"],
    STEP_CLSID["SetTotalSeqCount"],
    STEP_CLSID["GetTotalSeqCount"],
    STEP_CLSID["UserInput"],
    STEP_CLSID["UserOutput"],
    STEP_CLSID["ArrayDeclare"],
    STEP_CLSID["ArraySetAt"],
    STEP_CLSID["ArrayGetAt"],
    STEP_CLSID["ArrayGetSize"],
    STEP_CLSID["ArrayCopy"],
    STEP_CLSID["Shell"],
    STEP_CLSID["Return"],
    STEP_CLSID["SubmethodCall"],
    STEP_CLSID["Break"],
}
"""CLSIDs for step types that should contain exactly one executable statement per block.

Used by :func:`reconcile_block_marker_headers` to detect and split blocks that
erroneously contain multiple statements.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# GUID Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def generate_instance_guid() -> str:
    """Generate a new random GUID in Hamilton underscore format.

    Standard UUID:  ``550e8400-e29b-41d4-a716-446655440000``
    Hamilton GUID:  ``550e8400_e29b_41d4_a716446655440000``

    The Hamilton format merges the last two UUID segments (4-char + 12-char)
    into a single 16-char segment, separated by underscores:
    ``xxxxxxxx_xxxx_xxxx_xxxxxxxxxxxxxxxx`` (8_4_4_16).

    Returns:
        Hamilton-format GUID string (lowercase hex with underscores).
    """
    u = uuid.uuid4()
    s = str(u)  # e.g. "550e8400-e29b-41d4-a716-446655440000"
    parts = s.split("-")  # ["550e8400", "e29b", "41d4", "a716", "446655440000"]
    return f"{parts[0]}_{parts[1]}_{parts[2]}_{parts[3]}{parts[4]}"


def hamilton_guid_to_standard(h_guid: str) -> str:
    """Convert Hamilton underscore GUID to standard hyphenated GUID format.

    Args:
        h_guid: GUID in Hamilton format ``xxxxxxxx_xxxx_xxxx_xxxxxxxxxxxxxxxx``

    Returns:
        Standard GUID format ``xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx``

    Example:
        >>> hamilton_guid_to_standard("550e8400_e29b_41d4_a716446655440000")
        '550e8400-e29b-41d4-a716-446655440000'
    """
    parts = h_guid.split("_")  # ["550e8400", "e29b", "41d4", "a716446655440000"]
    last = parts[3]
    return f"{parts[0]}-{parts[1]}-{parts[2]}-{last[:4]}-{last[4:]}"


def standard_guid_to_hamilton(std_guid: str) -> str:
    """Convert standard GUID to Hamilton underscore format.

    Args:
        std_guid: GUID in standard format, with or without braces.

    Returns:
        Hamilton-format GUID string (lowercase hex with underscores).

    Example:
        >>> standard_guid_to_hamilton("{550E8400-E29B-41D4-A716-446655440000}")
        '550e8400_e29b_41d4_a716446655440000'
    """
    clean = std_guid.replace("{", "").replace("}", "").lower()
    parts = clean.split("-")
    return f"{parts[0]}_{parts[1]}_{parts[2]}_{parts[3]}{parts[4]}"


def _underscore_clsid_to_standard(uc_clsid: str) -> str:
    """Convert an underscore CLSID from HSL code to standard brace format.

    Used internally to convert device step function identifiers found in code
    back to the standard ``{CLSID}`` format used in block marker headers.

    Args:
        uc_clsid: CLSID with underscores, e.g. ``541143FC_7FA2_11D3_AD85_0004ACB1DCB2``

    Returns:
        Standard CLSID, e.g. ``{541143FC-7FA2-11D3-AD85-0004ACB1DCB2}``
    """
    parts = uc_clsid.split("_")
    return f"{{{parts[0]}-{parts[1]}-{parts[2]}-{parts[3]}-{parts[4]}}}"


# ═══════════════════════════════════════════════════════════════════════════════
# Block Marker Regex Patterns
# ═══════════════════════════════════════════════════════════════════════════════

# Quick detection of step markers (for has_step_block_markers guard)
RE_STEP_MARKER = re.compile(
    r'^//\s*\{\{\{?\s+\d+\s+\d+\s+\d+\s+"[^"]+"\s+"[^"]+"', re.MULTILINE
)

# Opening step marker:  // {{ ROW COL SUBLEVEL "guid" "clsid"
#                    or: // {{{ ROW COL SUBLEVEL "guid" "clsid"
RE_STEP_OPEN = re.compile(
    r'^//\s*(\{\{\{?)\s+(\d+)\s+(\d+)\s+(\d+)\s+"([^"]+)"\s+"([^"]+)"\s*$'
)

# Opening structural marker:  // {{ LEVEL "name" "qualifier"
#                          or: // {{{ LEVEL "name" "qualifier"
RE_STRUCTURAL_OPEN = re.compile(
    r'^//\s*(\{\{\{?)\s+(\d+)\s+"([^"]+)"\s+"([^"]*)"\s*$'
)

# Inline structural marker:  /* {{ LEVEL "name" "qualifier" */ // }} ""
RE_INLINE_STRUCTURAL = re.compile(
    r'^/\*\s*(\{\{\{?)\s+(\d+)\s+"([^"]+)"\s+"([^"]*)"\s*\*/\s*//\s*\}\}\s*""\s*$'
)

# Closing marker:  // }} ""
RE_CLOSE = re.compile(r'^//\s*\}\}\s*""\s*$')

# Checksum / footer line
RE_CHECKSUM = re.compile(
    r'^//\s*\$\$author=([^$]*)\$\$valid=(\d+)\$\$time=([^$]*)'
    r'\$\$checksum=([0-9a-fA-F]{8})\$\$length=(\d{3})\$\$\s*$'
)

# Device step function call in code -- matches patterns like:
#   ML_STAR._541143FC_7FA2_11D3_AD85_0004ACB1DCB2("122ed496_fe1b_4df4_aee6e5fe2130e41b")
# Captures:
#   [1] Device name (e.g. "ML_STAR")
#   [2] Function CLSID in underscore form (e.g. "541143FC_7FA2_11D3_AD85_0004ACB1DCB2")
#   [3] Instance GUID argument (e.g. "122ed496_fe1b_4df4_aee6e5fe2130e41b")
RE_DEVICE_STEP_CALL = re.compile(
    r'(\w+)\._([0-9A-Fa-f]{8}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{12})'
    r'\s*\(\s*"([0-9a-f]{8}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{16})"\s*\)',
    re.IGNORECASE,
)

# Namespace-qualified library call:  NAMESPACE::Function(
RE_NAMESPACE_CALL = re.compile(r'^\s*\w+::\w+\s*\(')

# Abort statement
RE_ABORT = re.compile(r'^\s*abort\s*;\s*$')


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Checks
# ═══════════════════════════════════════════════════════════════════════════════

def has_step_block_markers(content: str) -> bool:
    """Quick check: does *content* contain any step block markers?

    Used as a guard to prevent processing library files.
    Library files (``ArrayTable.hsl``) never have step block markers;
    method files (``Method1.hsl``) always have them.

    Args:
        content: Raw text content of an HSL file.

    Returns:
        ``True`` if at least one step block marker is found.
    """
    return bool(RE_STEP_MARKER.search(content))


def is_triple_brace_clsid(clsid: str) -> bool:
    """Whether *clsid* should use triple-brace ``{{{`` markers.

    Args:
        clsid: A CLSID string (with or without device prefix).

    Returns:
        ``True`` if the CLSID is in :data:`TRIPLE_BRACE_CLSIDS`.
    """
    return clsid in TRIPLE_BRACE_CLSIDS


# ═══════════════════════════════════════════════════════════════════════════════
# Block Marker Types
# ═══════════════════════════════════════════════════════════════════════════════

class StepBlockMarker(NamedTuple):
    """A parsed compound step block marker.

    Attributes:
        row: 1-based visual row position in the Method Editor.
        column: Column number (1 for single-process methods).
        sublevel: Sub-level (0 for most steps).
        instance_guid: Hamilton underscore-format GUID.
        step_clsid: COM CLSID (or ``DEVICE:CLSID`` for device steps).
        triple_brace: ``True`` if the marker uses ``{{{``.
        code_lines: HSL code lines between open and close markers.
    """
    row: int
    column: int
    sublevel: int
    instance_guid: str
    step_clsid: str
    triple_brace: bool
    code_lines: List[str]


class StructuralBlockMarker(NamedTuple):
    """A parsed structural block marker.

    Attributes:
        block_type: Block type number (2 = framework, 5 = function boundary).
        section_name: Section name (e.g. ``"LibraryInsertLine"``, ``"main"``).
        qualifier: Qualifier string (e.g. ``"Begin"``, ``"End"``, ``""``).
        triple_brace: ``True`` if the marker uses ``{{{``.
        inline: ``True`` if this is a single-line inline marker.
        code_lines: HSL code lines between open and close markers.
    """
    block_type: int
    section_name: str
    qualifier: str
    triple_brace: bool
    inline: bool
    code_lines: List[str]


# Union type for any block marker
BlockMarker = Union[StepBlockMarker, StructuralBlockMarker]


# ═══════════════════════════════════════════════════════════════════════════════
# Device Call Info
# ═══════════════════════════════════════════════════════════════════════════════

class DeviceCallInfo(NamedTuple):
    """Information about a device step function call extracted from code.

    Attributes:
        device: Device name (e.g. ``"ML_STAR"``).
        clsid: Full CLSID with device prefix (e.g. ``"ML_STAR:{...}"``).
        instance_guid: Hamilton-format instance GUID from the call argument.
    """
    device: str
    clsid: str
    instance_guid: str


# ═══════════════════════════════════════════════════════════════════════════════
# Block Marker Parsing
# ═══════════════════════════════════════════════════════════════════════════════

def parse_block_markers(content: str) -> List[BlockMarker]:
    """Parse all block markers from an HSL file's text content.

    Iterates through the file line-by-line, identifying opening markers,
    collecting code lines, and matching closing markers. Returns a flat
    list of :class:`StepBlockMarker` and :class:`StructuralBlockMarker`
    objects in order of appearance.

    Args:
        content: Raw text content of an HSL file.

    Returns:
        List of parsed block markers (step and structural).
    """
    lines = content.split('\n')
    # Normalize \r\n
    lines = [line.rstrip('\r') for line in lines]
    markers: List[BlockMarker] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Check for inline structural marker first (single-line)
        m = RE_INLINE_STRUCTURAL.match(line)
        if m:
            markers.append(StructuralBlockMarker(
                block_type=int(m.group(2)),
                section_name=m.group(3),
                qualifier=m.group(4),
                triple_brace=(m.group(1) == "{{{"),
                inline=True,
                code_lines=[],
            ))
            i += 1
            continue

        # Check for step opening marker
        m = RE_STEP_OPEN.match(line)
        if m:
            code_lines: List[str] = []
            i += 1
            while i < len(lines) and not RE_CLOSE.match(lines[i].strip()):
                code_lines.append(lines[i])
                i += 1
            markers.append(StepBlockMarker(
                row=int(m.group(2)),
                column=int(m.group(3)),
                sublevel=int(m.group(4)),
                instance_guid=m.group(5),
                step_clsid=m.group(6),
                triple_brace=(m.group(1) == "{{{"),
                code_lines=code_lines,
            ))
            i += 1  # skip closing // }} ""
            continue

        # Check for structural opening marker
        m = RE_STRUCTURAL_OPEN.match(line)
        if m:
            code_lines = []
            i += 1
            while i < len(lines) and not RE_CLOSE.match(lines[i].strip()):
                code_lines.append(lines[i])
                i += 1
            markers.append(StructuralBlockMarker(
                block_type=int(m.group(2)),
                section_name=m.group(3),
                qualifier=m.group(4),
                triple_brace=(m.group(1) == "{{{"),
                inline=False,
                code_lines=code_lines,
            ))
            i += 1  # skip closing // }} ""
            continue

        i += 1

    return markers


def parse_checksum_footer(content: str) -> Optional[Dict[str, str]]:
    """Parse the checksum footer line from an HSL file.

    Searches backwards from the end of the file for a valid checksum line.

    Args:
        content: Raw text content of an HSL file.

    Returns:
        Dictionary with keys ``author``, ``valid``, ``time``, ``checksum``,
        ``length``; or ``None`` if no valid checksum line was found.
    """
    lines = content.split('\n')
    for i in range(len(lines) - 1, -1, -1):
        m = RE_CHECKSUM.match(lines[i].strip())
        if m:
            return {
                "author": m.group(1),
                "valid": m.group(2),
                "time": m.group(3),
                "checksum": m.group(4).lower(),
                "length": m.group(5),
            }
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Block Marker Generation
# ═══════════════════════════════════════════════════════════════════════════════

def make_step_open_marker(
    row: int,
    column: int,
    sublevel: int,
    instance_guid: str,
    step_clsid: str,
    triple_brace: bool = False,
) -> str:
    """Generate an opening block marker line for a compound step.

    Args:
        row: 1-based step row number.
        column: Column number (usually 1).
        sublevel: Sub-level (usually 0).
        instance_guid: Hamilton-format instance GUID.
        step_clsid: Step type CLSID (or ``DEVICE:CLSID``).
        triple_brace: Use ``{{{`` instead of ``{{``.

    Returns:
        A complete opening marker comment line.
    """
    braces = "{{{" if triple_brace else "{{"
    return f'// {braces} {row} {column} {sublevel} "{instance_guid}" "{step_clsid}"'


def make_structural_open_marker(
    block_type: int,
    section_name: str,
    qualifier: str,
    triple_brace: bool = False,
) -> str:
    """Generate an opening structural block marker line.

    Args:
        block_type: Block type number (2 = framework, 5 = function boundary).
        section_name: Section name.
        qualifier: Qualifier string (e.g. ``"Begin"``, ``"End"``).
        triple_brace: Use ``{{{`` instead of ``{{``.

    Returns:
        A complete opening structural marker comment line.
    """
    braces = "{{{" if triple_brace else "{{"
    return f'// {braces} {block_type} "{section_name}" "{qualifier}"'


def make_inline_structural_marker(
    block_type: int,
    section_name: str,
    qualifier: str,
) -> str:
    """Generate an inline structural block marker (single-line with close).

    Inline markers are used for empty sections like ``LibraryInsertLine``
    and ``VariableInsertLine``.

    Args:
        block_type: Block type number.
        section_name: Section name.
        qualifier: Qualifier string.

    Returns:
        A complete inline marker line (``/* {{ ... */ // }} ""``)
    """
    return f'/* {{{{ {block_type} "{section_name}" "{qualifier}" */ // }}}} ""'


def make_close_marker() -> str:
    """Generate a closing block marker line.

    Returns:
        The string ``// }} ""``.
    """
    return '// }} ""'


# ═══════════════════════════════════════════════════════════════════════════════
# Row Renumbering
# ═══════════════════════════════════════════════════════════════════════════════

def renumber_block_markers(content: str) -> str:
    """Renumber all step block marker rows sequentially starting from 1.

    Only modifies the row number in each step opening marker; all other content
    (code, structural markers, GUIDs, CLSIDs) is preserved exactly.

    Safe to call on any ``.hsl`` content -- if there are no step markers,
    the content is returned unchanged.

    Args:
        content: Raw text content of an HSL file.

    Returns:
        Content with step marker rows renumbered 1, 2, 3, …
    """
    counter = [0]  # Use list for closure mutability in Python 3

    def replace_row(match: re.Match) -> str:
        counter[0] += 1
        return f"{match.group(1)}{counter[0]}{match.group(2)}"

    pattern = re.compile(
        r'^(//\s*\{\{\{?\s+)\d+(\s+\d+\s+\d+\s+"[^"]+"\s+"[^"]+")',
        re.MULTILINE,
    )
    return pattern.sub(replace_row, content)


# ═══════════════════════════════════════════════════════════════════════════════
# Device Call Extraction
# ═══════════════════════════════════════════════════════════════════════════════

def extract_device_call_from_code(code_lines: List[str]) -> Optional[DeviceCallInfo]:
    """Extract the FIRST device step function call from *code_lines*.

    Looks for patterns like::

        ML_STAR._541143FC_7FA2_11D3_AD85_0004ACB1DCB2("instance_guid")

    and returns a :class:`DeviceCallInfo` with the device name, full CLSID,
    and instance GUID.

    Args:
        code_lines: Lines of HSL code from inside a block marker.

    Returns:
        :class:`DeviceCallInfo` for the first device call found, or ``None``.
    """
    for line in code_lines:
        m = RE_DEVICE_STEP_CALL.search(line)
        if m:
            return DeviceCallInfo(
                device=m.group(1),
                clsid=f"{m.group(1)}:{_underscore_clsid_to_standard(m.group(2))}",
                instance_guid=m.group(3),
            )
    return None


def extract_all_device_calls_from_code(code_lines: List[str]) -> List[DeviceCallInfo]:
    """Extract ALL device step function calls from *code_lines*.

    Returns one :class:`DeviceCallInfo` per distinct call found. Scans the
    joined text of all code lines with a global regex match.

    Args:
        code_lines: Lines of HSL code from inside a block marker.

    Returns:
        List of :class:`DeviceCallInfo` objects (may be empty).
    """
    calls: List[DeviceCallInfo] = []
    joined = "\n".join(code_lines)
    for m in RE_DEVICE_STEP_CALL.finditer(joined):
        calls.append(DeviceCallInfo(
            device=m.group(1),
            clsid=f"{m.group(1)}:{_underscore_clsid_to_standard(m.group(2))}",
            instance_guid=m.group(3),
        ))
    return calls


def _extract_code_block_for_call(
    code_lines: List[str],
    call_instance_guid: str,
) -> List[str]:
    """Extract the code block surrounding a specific device call.

    Given code lines that may contain multiple device step calls, finds
    the line with *call_instance_guid* and walks backwards/forwards to
    locate the enclosing ``{`` … ``}`` pair.

    Args:
        code_lines: All lines within a block marker.
        call_instance_guid: The instance GUID of the specific call to extract.

    Returns:
        The subset of lines belonging to this call's code block,
        or an empty list if the GUID was not found.
    """
    # Find the line containing this specific call
    call_line_idx = -1
    for idx, line in enumerate(code_lines):
        if call_instance_guid in line:
            call_line_idx = idx
            break
    if call_line_idx == -1:
        return []

    # Walk backwards to find the opening { for this code block
    start_idx = call_line_idx
    brace_depth = 0
    for idx in range(call_line_idx, -1, -1):
        trimmed = code_lines[idx].strip()
        for ch in trimmed:
            if ch == "}":
                brace_depth += 1
            elif ch == "{":
                brace_depth -= 1
        if brace_depth <= 0:
            start_idx = idx
            break

    # Walk forwards to find the closing } for this code block
    end_idx = call_line_idx
    brace_depth = 0
    for idx in range(start_idx, len(code_lines)):
        trimmed = code_lines[idx].strip()
        for ch in trimmed:
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
        if brace_depth <= 0 and idx >= call_line_idx:
            end_idx = idx
            break

    return code_lines[start_idx:end_idx + 1]


# ═══════════════════════════════════════════════════════════════════════════════
# Block Marker Reconciliation / Repair
# ═══════════════════════════════════════════════════════════════════════════════

def reconcile_block_marker_headers(content: str) -> str:
    """Comprehensive block marker repair for Hamilton HSL method files.

    This function handles ALL of the following repair cases:

    1. **Header mismatch**: Block marker comment references a different
       CLSID/GUID than the code inside → updates the comment to match the code.

    2. **Multiple device calls in one block**: A single block marker wraps
       two or more device step calls → splits into separate blocks, each
       with its own correctly-matched header.

    3. **Empty device blocks**: A device step block with no code inside
       (user deleted the code) → removes the block marker pair entirely.

    4. **Duplicate instance GUIDs**: Two blocks reference the same instance
       GUID → removes the duplicate (keeps the first occurrence).

    5. **Missing close markers**: A step block's close marker was deleted
       → adds a synthetic close (or removes the block if empty).

    6. **Multi-statement single-statement blocks**: A single-statement step
       type (like Assignment) contains multiple executable lines → splits
       into separate blocks.

    7. **Orphaned code** (second pass): Executable code sitting between
       two step blocks with no wrapping marker → wraps it with an
       appropriate new block marker.

    Non-device steps (Comment, Assignment, Loop, If/Else, etc.) and structural
    markers are left untouched when they don't need repair.

    **Row numbers are NOT adjusted here**; call :func:`renumber_block_markers`
    afterward.

    Args:
        content: Raw text content of an HSL method file.

    Returns:
        Repaired content. If no repairs were needed, the original *content*
        is returned unchanged (same string object).
    """
    lines = content.split('\n')
    # Detect existing line ending style
    eol = "\r\n" if "\r\n" in content else "\n"
    # Strip \r from line endings for uniform processing
    lines = [line.rstrip('\r') for line in lines]

    result: List[str] = []
    modified = False
    seen_guids: Set[str] = set()

    i = 0
    while i < len(lines):
        trimmed = lines[i].strip()

        # ── Inline structural markers -- pass through ──
        if RE_INLINE_STRUCTURAL.match(trimmed):
            result.append(lines[i])
            i += 1
            continue

        # ── Step opening marker ──
        step_match = RE_STEP_OPEN.match(trimmed)
        if step_match:
            braces = step_match.group(1)
            row = step_match.group(2)
            col = step_match.group(3)
            sublevel = step_match.group(4)
            comment_guid = step_match.group(5)
            comment_clsid = step_match.group(6)
            open_line_original = lines[i]

            # Collect code lines until closing marker.
            # If we encounter another open marker before a close, the current
            # block's close was deleted -- handle accordingly.
            code_lines: List[str] = []
            missing_close = False
            i += 1
            while i < len(lines) and not RE_CLOSE.match(lines[i].strip()):
                peek_trimmed = lines[i].strip()
                # Check if we hit another step/structural open marker
                if (RE_STEP_OPEN.match(peek_trimmed) or
                        RE_STRUCTURAL_OPEN.match(peek_trimmed) or
                        RE_INLINE_STRUCTURAL.match(peek_trimmed)):
                    # Current block's close is missing -- stop here
                    missing_close = True
                    break
                code_lines.append(lines[i])
                i += 1

            close_line_idx = -1 if missing_close else i

            # ── Handle missing close marker ──
            if missing_close:
                modified = True
                has_real_code = any(
                    t.strip() not in ("", "{", "}")
                    for t in code_lines
                )
                if not has_real_code:
                    # Empty block with missing close -- remove entirely
                    continue
                else:
                    # Block has code but lost its close -- re-emit with synthetic close
                    result.append(open_line_original)
                    result.extend(code_lines)
                    result.append('// }} ""')
                    continue

            # Find ALL device step calls in this block's code
            device_calls = extract_all_device_calls_from_code(code_lines)

            # ── Case: Non-device step block ──
            if len(device_calls) == 0:
                is_device_clsid = ":" in comment_clsid

                # Empty device block -- remove entirely
                if is_device_clsid and all(
                    l.strip() in ("", "{", "}") for l in code_lines
                ):
                    modified = True
                    if close_line_idx >= 0 and close_line_idx < len(lines):
                        i = close_line_idx + 1
                    continue

                # Count executable statements in the block
                executable_lines: List[Tuple[int, str]] = []
                for ci, cl in enumerate(code_lines):
                    ct = cl.strip()
                    if (ct and ct != "{" and ct != "}" and
                            not ct.startswith("//") and
                            not ct.startswith("/*")):
                        executable_lines.append((ci, cl))

                is_single_statement_type = comment_clsid in SINGLE_STATEMENT_CLSIDS

                # Empty single-statement block -- remove
                if is_single_statement_type and len(executable_lines) == 0:
                    modified = True
                    if close_line_idx >= 0 and close_line_idx < len(lines):
                        i = close_line_idx + 1
                    continue

                # Multiple statements in a single-statement type -- split
                if is_single_statement_type and len(executable_lines) > 1:
                    modified = True
                    for si, (_, stmt_line) in enumerate(executable_lines):
                        stmt_trimmed = stmt_line.strip()

                        # Determine the correct CLSID for this statement
                        stmt_clsid = comment_clsid
                        stmt_braces = braces

                        if RE_NAMESPACE_CALL.match(stmt_trimmed):
                            stmt_clsid = STEP_CLSID["SingleLibFunction"]
                            stmt_braces = "{{{"
                        elif RE_ABORT.match(stmt_trimmed):
                            stmt_clsid = STEP_CLSID["Abort"]
                            stmt_braces = "{{"

                        # Override brace style from CLSID
                        if stmt_clsid in TRIPLE_BRACE_CLSIDS:
                            stmt_braces = "{{{"

                        # First statement keeps original GUID; extras get new GUIDs
                        stmt_guid = comment_guid if si == 0 else generate_instance_guid()

                        result.append(
                            f'// {stmt_braces} {row} {col} {sublevel} '
                            f'"{stmt_guid}" "{stmt_clsid}"'
                        )
                        result.append(stmt_line)
                        result.append('// }} ""')

                    if close_line_idx >= 0 and close_line_idx < len(lines):
                        i = close_line_idx + 1
                    continue

                # Normal non-device step -- keep as-is
                result.append(open_line_original)
                result.extend(code_lines)
                if close_line_idx >= 0 and close_line_idx < len(lines):
                    result.append(lines[close_line_idx])
                    i = close_line_idx + 1
                else:
                    result.append('// }} ""')
                    modified = True
                continue

            # ── Case: Exactly one device call ──
            if len(device_calls) == 1:
                call = device_calls[0]

                # Duplicate GUID check
                if call.instance_guid in seen_guids:
                    modified = True
                    if close_line_idx >= 0 and close_line_idx < len(lines):
                        i = close_line_idx + 1
                    continue
                seen_guids.add(call.instance_guid)

                # Update header if mismatched
                if (call.instance_guid != comment_guid or
                        call.clsid != comment_clsid):
                    new_line = (
                        f'// {braces} {row} {col} {sublevel} '
                        f'"{call.instance_guid}" "{call.clsid}"'
                    )
                    result.append(new_line)
                    modified = True
                else:
                    result.append(open_line_original)

                result.extend(code_lines)
                if close_line_idx >= 0 and close_line_idx < len(lines):
                    result.append(lines[close_line_idx])
                    i = close_line_idx + 1
                else:
                    result.append('// }} ""')
                    modified = True
                continue

            # ── Case: Multiple device calls in one block -- SPLIT ──
            modified = True
            for call in device_calls:
                # Duplicate GUID check
                if call.instance_guid in seen_guids:
                    continue
                seen_guids.add(call.instance_guid)

                # Extract just this call's code block
                call_code_lines = _extract_code_block_for_call(
                    code_lines, call.instance_guid
                )

                # Emit the block marker pair for this call
                result.append(
                    f'// {braces} {row} {col} {sublevel} '
                    f'"{call.instance_guid}" "{call.clsid}"'
                )
                result.extend(call_code_lines)
                result.append('// }} ""')

            # Skip past the original closing marker
            if close_line_idx >= 0 and close_line_idx < len(lines):
                i = close_line_idx + 1
            continue

        # ── Structural opening marker -- pass through with content ──
        struct_match = RE_STRUCTURAL_OPEN.match(trimmed)
        if struct_match:
            result.append(lines[i])
            i += 1
            while i < len(lines) and not RE_CLOSE.match(lines[i].strip()):
                s_peek = lines[i].strip()
                if (RE_STEP_OPEN.match(s_peek) or
                        RE_STRUCTURAL_OPEN.match(s_peek) or
                        RE_INLINE_STRUCTURAL.match(s_peek)):
                    # Structural block's close is missing -- add synthetic close
                    result.append('// }} ""')
                    modified = True
                    break
                result.append(lines[i])
                i += 1
            if i < len(lines) and RE_CLOSE.match(lines[i].strip()):
                result.append(lines[i])  # closing // }} ""
                i += 1
            continue

        # ── Everything else -- pass through unchanged ──
        result.append(lines[i])
        i += 1

    # ═══════════════════════════════════════════════════════════════════════════
    # Second pass: Wrap orphaned code between step blocks
    # ═══════════════════════════════════════════════════════════════════════════
    # When a user deletes a block marker, the code line sits naked between
    # two step blocks. Detect this pattern: close-marker → executable code →
    # open-marker. Only wrap code that sits between TWO STEP markers.
    final_result: List[str] = []
    second_pass_modified = False

    for ri in range(len(result)):
        rt = result[ri].strip()

        # Check if this is a non-empty, non-marker, non-comment line
        if (rt and
                not RE_STEP_OPEN.match(rt) and
                not RE_CLOSE.match(rt) and
                not RE_STRUCTURAL_OPEN.match(rt) and
                not RE_INLINE_STRUCTURAL.match(rt) and
                not rt.startswith("//") and
                not rt.startswith("/*")):

            # Look backwards for the nearest marker
            prev_is_step_close = False
            for j in range(ri - 1, -1, -1):
                pt = result[j].strip()
                if RE_CLOSE.match(pt):
                    # Found a close -- was the corresponding open a step marker?
                    depth = 1
                    for k in range(j - 1, -1, -1):
                        kt = result[k].strip()
                        if RE_CLOSE.match(kt):
                            depth += 1
                        elif RE_STEP_OPEN.match(kt):
                            depth -= 1
                            if depth == 0:
                                # Check if this is a "free-code-allowed" step type
                                step_open_match = RE_STEP_OPEN.match(kt)
                                open_clsid = step_open_match.group(6) if step_open_match else ""
                                if open_clsid in (
                                    STEP_CLSID["GroupSeparator"],
                                    STEP_CLSID["Comment"],
                                ):
                                    prev_is_step_close = False
                                else:
                                    prev_is_step_close = True
                                break
                        elif (RE_STRUCTURAL_OPEN.match(kt) or
                              RE_INLINE_STRUCTURAL.match(kt)):
                            depth -= 1
                            if depth == 0:
                                prev_is_step_close = False
                                break
                    break
                if (RE_STEP_OPEN.match(pt) or
                        RE_STRUCTURAL_OPEN.match(pt) or
                        RE_INLINE_STRUCTURAL.match(pt)):
                    break  # We're inside a block, not between blocks
                if (pt and
                        not pt.startswith("//") and
                        not pt.startswith("/*")):
                    break  # Hit another code line -- not our concern

            # Look forward for the nearest open marker
            next_is_step_open = False
            for j in range(ri + 1, len(result)):
                nt = result[j].strip()
                if RE_STEP_OPEN.match(nt):
                    next_is_step_open = True
                    break
                if (RE_STRUCTURAL_OPEN.match(nt) or
                        RE_INLINE_STRUCTURAL.match(nt) or
                        RE_CLOSE.match(nt)):
                    break
                if (nt and
                        not nt.startswith("//") and
                        not nt.startswith("/*")):
                    # Another code line -- might be part of the same orphan group
                    continue

            if prev_is_step_close and next_is_step_open:
                # This is orphaned code -- wrap it with an appropriate marker
                second_pass_modified = True

                wrap_clsid: str = STEP_CLSID["Assignment"]
                wrap_braces = "{{"

                if RE_NAMESPACE_CALL.match(rt):
                    wrap_clsid = STEP_CLSID["SingleLibFunction"]
                    wrap_braces = "{{{"
                elif RE_ABORT.match(rt):
                    wrap_clsid = STEP_CLSID["Abort"]

                if wrap_clsid in TRIPLE_BRACE_CLSIDS:
                    wrap_braces = "{{{"

                new_guid = generate_instance_guid()
                final_result.append(
                    f'// {wrap_braces} 0 1 0 "{new_guid}" "{wrap_clsid}"'
                )
                final_result.append(result[ri])
                final_result.append('// }} ""')
                continue

        final_result.append(result[ri])

    if modified or second_pass_modified:
        return eol.join(final_result)
    return content


# ═══════════════════════════════════════════════════════════════════════════════
# Step Definitions
# ═══════════════════════════════════════════════════════════════════════════════

class MethodStep:
    """Definition of a method step for generation purposes.

    A ``MethodStep`` describes one compound step to be emitted into an HSL
    method file. It can optionally contain children (for Loop/If bodies)
    and else-children (for If/Else).

    Attributes:
        step_type: The compound step type name (e.g. ``"Comment"``, ``"Loop"``).
        code: The HSL code lines this step produces.
        clsid: Explicit CLSID override (auto-resolved from *step_type* if ``None``).
        device: Device prefix for device-specific steps (e.g. ``"ML_STAR"``).
        close_code: Closing block code lines (for Loop, If/Else).
        children: Child steps (for Loop body, If body).
        else_children: Else-block children (for If/Else).
        instance_guid: Pre-assigned instance GUID (auto-generated if ``None``).
    """

    def __init__(
        self,
        step_type: str,
        code: List[str],
        clsid: Optional[str] = None,
        device: Optional[str] = None,
        close_code: Optional[List[str]] = None,
        children: Optional[List["MethodStep"]] = None,
        else_children: Optional[List["MethodStep"]] = None,
        instance_guid: Optional[str] = None,
    ) -> None:
        self.step_type = step_type
        self.code = code
        self.clsid = clsid
        self.device = device
        self.close_code = close_code
        self.children = children or []
        self.else_children = else_children or []
        self.instance_guid = instance_guid

    def resolve_clsid(self) -> str:
        """Resolve the CLSID for this step.

        Resolution order:
          1. Explicit ``self.clsid``
          2. Device-specific lookup (``ML_STAR_CLSID[self.step_type]``)
          3. Generic lookup (``STEP_CLSID[self.step_type]``)

        Returns:
            The resolved CLSID string.

        Raises:
            ValueError: If *step_type* is not found in any registry and
                no explicit *clsid* was provided.
        """
        if self.clsid:
            return self.clsid
        if self.device and self.step_type in ML_STAR_CLSID:
            return ML_STAR_CLSID[self.step_type]
        if self.step_type in STEP_CLSID:
            return STEP_CLSID[self.step_type]
        raise ValueError(
            f"Unknown step type: {self.step_type}. Provide an explicit clsid."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Step Builder Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def comment_step(text: str, trace: bool = True) -> MethodStep:
    """Create a Comment step.

    Args:
        text: The comment text.
        trace: If ``True``, generates a ``MECC::TraceComment`` call; otherwise
               an empty code line.

    Returns:
        A :class:`MethodStep` configured as a Comment.
    """
    escaped = text.replace('"', '\\"').replace('\n', '\\n')
    if trace:
        code = [f'MECC::TraceComment(Translate("{escaped}"));']
    else:
        code = ['']
    return MethodStep("Comment", code)


def assignment_step(variable: str, value: str) -> MethodStep:
    """Create an Assignment step.

    Args:
        variable: Variable name to assign to.
        value: Expression to assign.

    Returns:
        A :class:`MethodStep` configured as an Assignment.
    """
    return MethodStep("Assignment", [f"{variable} = {value};"])


def for_loop_step(
    counter: str,
    count: Union[int, str],
    body: List[MethodStep],
) -> MethodStep:
    """Create a Loop (for) step.

    Args:
        counter: Loop counter variable name.
        count: Number of iterations (or expression string).
        body: Child steps to execute in the loop body.

    Returns:
        A :class:`MethodStep` configured as a for-loop.
    """
    return MethodStep(
        "Loop",
        ["{", f"for({counter} = 0; {counter} < {count};)",
         "{", f"{counter} = {counter} + 1;"],
        close_code=["}",  "}"],
        children=body,
    )


def while_loop_step(
    condition: str,
    counter: str,
    body: List[MethodStep],
) -> MethodStep:
    """Create a Loop (while) step.

    Args:
        condition: Loop continuation condition.
        counter: Loop counter variable name.
        body: Child steps to execute in the loop body.

    Returns:
        A :class:`MethodStep` configured as a while-loop.
    """
    return MethodStep(
        "Loop",
        ["{", f"{counter} = 0;", f"while ({condition})",
         "{", f"{counter} = {counter} + 1;"],
        close_code=["}",  "}"],
        children=body,
    )


def if_else_step(
    condition: str,
    then_steps: List[MethodStep],
    else_steps: Optional[List[MethodStep]] = None,
) -> MethodStep:
    """Create an If/Then/Else step.

    Args:
        condition: The boolean condition expression.
        then_steps: Steps to execute when the condition is true.
        else_steps: Steps to execute when the condition is false (optional).

    Returns:
        A :class:`MethodStep` configured as If/Then/Else.
    """
    return MethodStep(
        "IfThenElse",
        [f"if ({condition})  {{"],
        close_code=["}"],
        children=then_steps,
        else_children=else_steps or [],
    )


def submethod_call_step(fname: str, args: Optional[List[str]] = None) -> MethodStep:
    """Create a Submethod Call step.

    Args:
        fname: Function name to call.
        args: Call arguments (default: no arguments).

    Returns:
        A :class:`MethodStep` configured as a SubmethodCall.
    """
    args = args or []
    return MethodStep("SubmethodCall", [f"{fname}({', '.join(args)});"])


def library_function_step(
    namespace: str,
    fname: str,
    args: Optional[List[str]] = None,
) -> MethodStep:
    """Create a Library Function (Smart Step) call.

    Args:
        namespace: Library namespace.
        fname: Function name.
        args: Call arguments (default: no arguments).

    Returns:
        A :class:`MethodStep` configured as a SingleLibFunction.
    """
    args = args or []
    return MethodStep(
        "SingleLibFunction",
        [f"{namespace}::{fname}({', '.join(args)});"],
    )


def abort_step() -> MethodStep:
    """Create an Abort step.

    Returns:
        A :class:`MethodStep` configured as an Abort.
    """
    return MethodStep("Abort", ["abort;"])


def break_step() -> MethodStep:
    """Create a Break step.

    Returns:
        A :class:`MethodStep` configured as a Break.
    """
    return MethodStep("Break", ["break;"])


def return_step() -> MethodStep:
    """Create a Return step.

    Returns:
        A :class:`MethodStep` configured as a Return.
    """
    return MethodStep("Return", ["return;"])


def shell_step(command: str, wait: bool = True) -> MethodStep:
    """Create a Shell step.

    Args:
        command: Shell command expression.
        wait: If ``True``, wait for the command to complete.

    Returns:
        A :class:`MethodStep` configured as a Shell command.
    """
    flag = "hslTrue" if wait else "hslFalse"
    return MethodStep("Shell", [f"Shell({command}, {flag});"])


# ═══════════════════════════════════════════════════════════════════════════════
# Generation State
# ═══════════════════════════════════════════════════════════════════════════════

class GeneratedStepInfo(NamedTuple):
    """Information about a generated step (used for .med generation).

    Attributes:
        instance_guid: Hamilton-format instance GUID.
        clsid: Step type CLSID.
        row: Row number assigned during generation.
        block_index: Block index (1, 2, 3… for multi-block steps).
        code: The HSL code text.
        triple_brace: Whether this uses triple-brace markers.
    """
    instance_guid: str
    clsid: str
    row: int
    block_index: int
    code: str
    triple_brace: bool


class GenerationState:
    """Internal state for tracking row numbers during method generation.

    Attributes:
        current_row: Current row number (1-based, auto-incremented).
        column: Column number (always 1 for single-process methods).
        lines: Output lines being built.
        generated_steps: All step info records generated so far.
    """

    def __init__(self) -> None:
        self.current_row: int = 1
        self.column: int = 1
        self.lines: List[str] = []
        self.generated_steps: List[GeneratedStepInfo] = []


# ═══════════════════════════════════════════════════════════════════════════════
# Method Generation
# ═══════════════════════════════════════════════════════════════════════════════

def emit_step(state: GenerationState, step: MethodStep) -> None:
    """Emit a single step (and its children) into the generation *state*.

    Handles multi-block steps (Loop, If/Else) by recursively emitting
    children between the opening and closing blocks, sharing the same
    instance GUID across all blocks of one step.

    Args:
        state: The current generation state (mutated in place).
        step: The method step to emit.
    """
    clsid = step.resolve_clsid()
    guid = step.instance_guid or generate_instance_guid()
    triple_brace = is_triple_brace_clsid(clsid)

    # Opening marker
    open_marker = make_step_open_marker(
        state.current_row, state.column, 0, guid, clsid, triple_brace
    )
    state.lines.append(open_marker)

    # Record this step
    state.generated_steps.append(GeneratedStepInfo(
        instance_guid=guid,
        clsid=clsid,
        row=state.current_row,
        block_index=1,
        code="\n".join(step.code),
        triple_brace=triple_brace,
    ))

    # Code lines
    for code_line in step.code:
        state.lines.append(code_line)

    # Close this opening block
    state.lines.append(make_close_marker())
    state.current_row += 1

    # Children (Loop body, If body)
    for child in step.children:
        emit_step(state, child)

    # Else children
    if step.else_children:
        else_marker = make_step_open_marker(
            state.current_row, state.column, 0, guid, clsid, False
        )
        state.lines.append(else_marker)
        state.lines.append("}  else  {")
        state.lines.append(make_close_marker())

        state.generated_steps.append(GeneratedStepInfo(
            instance_guid=guid,
            clsid=clsid,
            row=state.current_row,
            block_index=2,
            code="}  else  {",
            triple_brace=False,
        ))
        state.current_row += 1

        for child in step.else_children:
            emit_step(state, child)

    # Close code (Loop end, If end)
    if step.close_code:
        close_marker = make_step_open_marker(
            state.current_row, state.column, 0, guid, clsid, False
        )
        state.lines.append(close_marker)

        block_idx = 3 if step.else_children else 2
        state.generated_steps.append(GeneratedStepInfo(
            instance_guid=guid,
            clsid=clsid,
            row=state.current_row,
            block_index=block_idx,
            code="\n".join(step.close_code),
            triple_brace=False,
        ))

        for code_line in step.close_code:
            state.lines.append(code_line)
        state.lines.append(make_close_marker())
        state.current_row += 1


def generate_hsl_method(
    steps: Optional[List[MethodStep]] = None,
    library_includes: Optional[List[str]] = None,
    template_includes: Optional[List[str]] = None,
    auto_init_code: Optional[List[str]] = None,
    auto_exit_code: Optional[List[str]] = None,
    author: str = "admin",
) -> Tuple[str, str, List[GeneratedStepInfo]]:
    """Generate a complete HSL method file with valid block markers.

    Creates both `.hsl` and `.sub` file contents with proper block markers,
    structural sections, and checksum footers.

    Args:
        steps: List of method steps for the main() body.
        library_includes: Library files to include (e.g. ``["HSLUtilLib2.hsl"]``).
        template_includes: Template header includes (defaults to
            ``["HSLMETEDLib.hs_", "HSLMECCLib.hs_"]``).
        auto_init_code: Extra code lines for the AutoInitBlock.
        auto_exit_code: Extra code lines for the AutoExitBlock.
        author: Author name for the checksum footer.

    Returns:
        A 3-tuple of ``(hsl_content, sub_content, generated_steps)`` where
        *hsl_content* and *sub_content* are complete file strings with
        checksums, and *generated_steps* tracks all emitted steps.
    """
    state = GenerationState()

    # Library includes
    if library_includes:
        for lib in library_includes:
            state.lines.append(f' namespace _Method {{ #include "{lib}" }} ')

    # LibraryInsertLine (inline)
    state.lines.append(make_inline_structural_marker(2, "LibraryInsertLine", ""))

    # VariableInsertLine (inline)
    state.lines.append(make_inline_structural_marker(2, "VariableInsertLine", ""))

    # TemplateIncludeBlock
    templates = template_includes or ["HSLMETEDLib.hs_", "HSLMECCLib.hs_"]
    state.lines.append(make_structural_open_marker(2, "TemplateIncludeBlock", ""))
    for tpl in templates:
        state.lines.append(f' namespace _Method {{ #include "{tpl}" }} ')
    state.lines.append(make_close_marker())

    # LocalSubmethodInclude
    state.lines.append(
        make_structural_open_marker(2, "LocalSubmethodInclude", "", True)
    )
    state.lines.append(
        ' namespace _Method {  #include __filename__ ".sub"  } '
    )
    state.lines.append(make_close_marker())

    # ProcessInsertLine (inline)
    state.lines.append(make_inline_structural_marker(2, "ProcessInsertLine", ""))

    # main() Begin
    state.lines.append(make_structural_open_marker(5, "main", "Begin", True))
    state.lines.append("namespace _Method { method main(  ) void {")
    state.lines.append(make_close_marker())

    # main() InitLocals
    state.lines.append(make_structural_open_marker(5, "main", "InitLocals"))
    state.lines.append(make_close_marker())

    # AutoInitBlock
    state.lines.append(make_structural_open_marker(2, "AutoInitBlock", ""))
    if auto_init_code:
        for line in auto_init_code:
            state.lines.append(line)
    state.lines.append('::RegisterAbortHandler( "OnAbort");')
    state.lines.append(make_close_marker())

    # Main steps
    if steps:
        for step in steps:
            emit_step(state, step)

    # AutoExitBlock
    state.lines.append(make_structural_open_marker(2, "AutoExitBlock", ""))
    if auto_exit_code:
        for line in auto_exit_code:
            state.lines.append(line)
    state.lines.append(make_close_marker())

    # main() End
    state.lines.append(make_structural_open_marker(5, "main", "End", True))
    state.lines.append("} }")
    state.lines.append(make_close_marker())

    # Join with \r\n (Windows line endings, required for Hamilton)
    hsl_body = "\r\n".join(state.lines) + "\r\n"

    # Add checksum
    checksum_line = generate_checksum_line(hsl_body, author=author, prefix_char="//")
    hsl_content = hsl_body + checksum_line + "\r\n"

    # Generate .sub file
    sub_lines: List[str] = []
    sub_lines.append(
        make_structural_open_marker(2, "SubmethodForwardDeclaration", "", True)
    )
    sub_lines.append("function OnAbort(  ) void ;")
    sub_lines.append(make_close_marker())

    sub_lines.append(make_structural_open_marker(5, "OnAbort", "Begin", True))
    sub_lines.append("function OnAbort(  ) void {")
    sub_lines.append(make_close_marker())

    sub_lines.append(make_structural_open_marker(5, "OnAbort", "InitLocals"))
    sub_lines.append(make_close_marker())

    sub_lines.append(make_structural_open_marker(5, "OnAbort", "End", True))
    sub_lines.append("}")
    sub_lines.append(make_close_marker())

    sub_lines.append(make_inline_structural_marker(2, "SubmethodInsertLine", ""))

    sub_body = "\r\n".join(sub_lines) + "\r\n"
    sub_checksum = generate_checksum_line(sub_body, author=author, prefix_char="//")
    sub_content = sub_body + sub_checksum + "\r\n"

    return hsl_content, sub_content, state.generated_steps


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def _print_clsids() -> None:
    """Print the full CLSID registry in a formatted table."""
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║                    Hamilton HSL CLSID Registry                          ║")
    print("╠══════════════════════════════════════════════════════════════════════════╣")
    print(f"║ {'Step Type':<25} {'CLSID':<45}{'Braces':>5} ║")
    print("╠══════════════════════════════════════════════════════════════════════════╣")
    for name, clsid in STEP_CLSID.items():
        brace_info = " {{{" if clsid in TRIPLE_BRACE_CLSIDS else "  {{"
        print(f"║ {name:<25} {clsid:<45}{brace_info:>5} ║")
    print("╠══════════════════════════════════════════════════════════════════════════╣")
    print("║ ML_STAR Device-Specific CLSIDs                                         ║")
    print("╠══════════════════════════════════════════════════════════════════════════╣")
    for name, clsid in ML_STAR_CLSID.items():
        print(f"║ {name:<25} {clsid:<50} ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")


def _run_demo(args: argparse.Namespace) -> None:
    """Run the method generation demo."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     Hamilton HSL Block Marker Generator                    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # Build steps
    if args.demo_complex:
        steps: List[MethodStep] = [
            comment_step("This is a complex demo method"),
            assignment_step("myVar", "42"),
            for_loop_step("loopCounter1", 5, [
                comment_step("Inside loop iteration"),
                assignment_step("loopVar", "loopCounter1 * 2"),
            ]),
            if_else_step("myVar > 10", [
                comment_step("myVar is greater than 10"),
            ], [
                comment_step("myVar is not greater than 10"),
            ]),
            comment_step("Method complete"),
        ]
        print(f"  Generating complex demo method: '{args.name}'")
    else:
        steps = [
            comment_step(f"Step {i + 1} of {args.steps}")
            for i in range(args.steps)
        ]
        print(f"  Generating method '{args.name}' with {args.steps} comment step(s)")

    # Generate
    hsl_content, sub_content, generated_steps = generate_hsl_method(
        steps=steps,
        author=args.author,
    )

    # Determine output directory
    out_dir = args.output or os.getcwd()
    os.makedirs(out_dir, exist_ok=True)

    hsl_path = os.path.join(out_dir, f"{args.name}.hsl")
    sub_path = os.path.join(out_dir, f"{args.name}.sub")

    # Write files
    with open(hsl_path, "w", encoding="utf-8", newline="") as f:
        f.write(hsl_content)
    with open(sub_path, "w", encoding="utf-8", newline="") as f:
        f.write(sub_content)

    print(f"  Written: {hsl_path}")
    print(f"  Written: {sub_path}")
    print()

    # Report generated steps
    print("  ┌─ Generated Steps ─────────────────────────────────────────┐")
    for info in generated_steps:
        brace = "{{{" if info.triple_brace else "{{ "
        clsid_name = "Unknown"
        for name, c in STEP_CLSID.items():
            if c == info.clsid:
                clsid_name = name
                break
        print(
            f"  │  Row {info.row:>3} {brace} Block {info.block_index}"
            f"  {clsid_name:<20} {info.instance_guid[:20]}... │"
        )
    print("  └──────────────────────────────────────────────────────────┘")
    print()

    # Verify block markers
    parsed = parse_block_markers(hsl_content)
    step_markers = [m for m in parsed if isinstance(m, StepBlockMarker)]
    struct_markers = [m for m in parsed if isinstance(m, StructuralBlockMarker)]
    print("  Verification:")
    print(f"    Step markers parsed:       {len(step_markers)}")
    print(f"    Structural markers parsed: {len(struct_markers)}")
    print(f"    Has step block markers:    {has_step_block_markers(hsl_content)}")

    # Verify renumbering is idempotent
    renumbered = renumber_block_markers(hsl_content)
    hsl_no_cksum = re.sub(
        r'^// \$\$author=.*$', '', hsl_content, flags=re.MULTILINE
    ).strip()
    ren_no_cksum = re.sub(
        r'^// \$\$author=.*$', '', renumbered, flags=re.MULTILINE
    ).strip()
    print(f"    Renumber idempotent:       {hsl_no_cksum == ren_no_cksum}")
    print()

    # Show a snippet
    file_lines = hsl_content.split("\r\n")
    print("  ┌─ File Preview (first 20 lines) ───────────────────────────┐")
    for line_no, line in enumerate(file_lines[:20], 1):
        truncated = line[:60] + "..." if len(line) > 60 else line
        print(f"  │ {line_no:>3}: {truncated:<60}│")
    if len(file_lines) > 20:
        print(
            f"  │ ... ({len(file_lines) - 20} more lines)"
            "                              │"
        )
    print("  └──────────────────────────────────────────────────────────┘")
    print()
    print("  Done.")


def main() -> None:
    """CLI entry point for the block marker generator."""
    parser = argparse.ArgumentParser(
        description="Hamilton HSL Block Marker Generator & Reconciler -- "
                    "Standalone Python Implementation"
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--name", "-n", default="GeneratedMethod",
        help="Method name (default: GeneratedMethod)",
    )
    parser.add_argument(
        "--steps", "-s", type=int, default=3,
        help="Number of comment steps to generate (default: 3)",
    )
    parser.add_argument(
        "--show-clsids", action="store_true",
        help="Print CLSID registry and exit",
    )
    parser.add_argument(
        "--demo-complex", action="store_true",
        help="Generate a complex demo with loops, if/else, etc.",
    )
    parser.add_argument(
        "--author", default="admin",
        help="Author name for checksum (default: admin)",
    )
    parser.add_argument(
        "--reconcile", metavar="FILE",
        help="Run block marker reconciliation on a .hsl file and print result",
    )

    args = parser.parse_args()

    if args.show_clsids:
        _print_clsids()
        return

    if args.reconcile:
        # Read and reconcile a file
        filepath = args.reconcile
        if not os.path.isfile(filepath):
            print(f"Error: file not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        with open(filepath, "r", encoding="latin1") as f:
            content = f.read()
        result = reconcile_block_marker_headers(content)
        if result is content:
            print("No reconciliation changes needed.")
        else:
            result = renumber_block_markers(result)
            print(result)
        return

    _run_demo(args)


if __name__ == "__main__":
    main()
