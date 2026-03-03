#!/usr/bin/env python3
"""
block_marker_generator.py — Hamilton HSL Block Marker Generator (Reference Implementation)

A standalone Python implementation of the Hamilton HSL block marker generation algorithm.
This serves as:
  1. A reference implementation for understanding the algorithm
  2. A test tool for generating block markers independently of the TypeScript VS Code extension
  3. SDK documentation in executable form

This program can:
  - Generate complete method .hsl files with valid block markers
  - Generate companion .sub files
  - Compute CRC-32 checksums matching Hamilton's format
  - Create GUIDs in Hamilton's underscore format
  - Look up step CLSIDs

Usage:
  python block_marker_generator.py                    # Generate a demo method
  python block_marker_generator.py --output dir       # Write to specified directory
  python block_marker_generator.py --steps 5          # Generate with N comment steps
  python block_marker_generator.py --show-clsids      # Print CLSID registry

Requirements: Python 3.8+ (no external dependencies)
"""

import uuid
import struct
import re
import os
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Tuple, Optional, NamedTuple


# ─── CLSID Registry ─────────────────────────────────────────────────────────────

STEP_CLSID = {
    # General steps
    "Comment": "{F07B0071-8EFC-11d4-A3BA-002035848439}",
    "Assignment": "{B31F3543-5D80-11d4-A5EB-0050DA737D89}",
    "MathExpression": "{B31F3544-5D80-11d4-A5EB-0050DA737D89}",
    "IfThenElse": "{B31F3531-5D80-11d4-A5EB-0050DA737D89}",
    "Loop": "{B31F3532-5D80-11d4-A5EB-0050DA737D89}",
    "Break": "{B31F3533-5D80-11d4-A5EB-0050DA737D89}",
    "Return": "{9EC997CD-FD3B-4280-811B-49E99DCF062C}",
    "Abort": "{930D6C31-8EFB-11d4-A3BA-002035848439}",
    "Shell": "{B31F3545-5D80-11d4-A5EB-0050DA737D89}",

    # File operations
    "FileOpen": "{B31F3534-5D80-11d4-A5EB-0050DA737D89}",
    "FileFind": "{B31F3535-5D80-11d4-A5EB-0050DA737D89}",
    "FileRead": "{B31F3536-5D80-11d4-A5EB-0050DA737D89}",
    "FileWrite": "{B31F3537-5D80-11d4-A5EB-0050DA737D89}",
    "FileClose": "{B31F3538-5D80-11d4-A5EB-0050DA737D89}",

    # Dialogs
    "UserInput": "{B31F3539-5D80-11d4-A5EB-0050DA737D89}",
    "UserOutput": "{21E07B31-8D2E-11d4-A3B8-002035848439}",

    # Sequences
    "SetCurrentSeqPos": "{B31F353A-5D80-11d4-A5EB-0050DA737D89}",
    "GetCurrentSeqPos": "{B31F353B-5D80-11d4-A5EB-0050DA737D89}",
    "SetTotalSeqCount": "{B31F353C-5D80-11d4-A5EB-0050DA737D89}",
    "GetTotalSeqCount": "{B31F353D-5D80-11d4-A5EB-0050DA737D89}",
    "AlignSequences": "{EBC6FD39-B416-4461-BD0E-312FBC5AEF1F}",

    # Timers
    "StartTimer": "{B31F353E-5D80-11d4-A5EB-0050DA737D89}",
    "WaitTimer": "{B31F353F-5D80-11d4-A5EB-0050DA737D89}",
    "ReadElapsedTime": "{B31F3540-5D80-11d4-A5EB-0050DA737D89}",
    "ResetTimer": "{B31F3541-5D80-11d4-A5EB-0050DA737D89}",
    "StopTimer": "{83FFBD43-B4F2-4ECB-BE0A-1A183AC5063D}",

    # Events
    "WaitForEvent": "{D97BA841-8303-11d4-A3AC-002035848439}",
    "SetEvent": "{90ADC087-865A-4b6c-A658-A0F3AE1E29C4}",

    # Function calls
    "LibraryFunction": "{B31F3542-5D80-11d4-A5EB-0050DA737D89}",
    "SingleLibFunction": "{C1F3C015-47B3-4514-9407-AC2E65043419}",
    "SubmethodCall": "{7C4EF7A7-39BE-406a-897F-71F3A35B4093}",

    # COM Port
    "ComPortOpen": "{7AC8762F-512C-4f2c-8D1F-A86A73A6FA99}",
    "ComPortRead": "{6B1F17F6-3E69-4bbd-A8F2-3214BFB930AA}",
    "ComPortWrite": "{6193FE29-76EE-483b-AB12-EDDF6CB95FDD}",
    "ComPortClose": "{EB07D635-0C14-4880-8F99-4301CB1D4E3B}",

    # Array operations
    "ArrayDeclare": "{4900C1F7-0FB7-4033-8253-760BDB9354DC}",
    "ArraySetAt": "{F17B7626-27CB-47f1-8477-8C4158339A6D}",
    "ArrayGetAt": "{67A8F1C9-6546-41e9-AD2F-3C54F7818853}",
    "ArrayGetSize": "{72EACF88-8D49-43e3-92C8-2F90E81E3260}",
    "ArrayCopy": "{DB5A2B39-67F2-4a78-A78F-DAF3FB056366}",

    # Error handling
    "UserErrorHandling": "{3293659E-F71E-472f-AFB4-6A674E32B114}",

    # Threading
    "ThreadBegin": "{1A4D922E-531A-405b-BF19-FFD9AF850726}",
    "ThreadWaitFor": "{7DA7AD24-F79A-43aa-A47C-A7F0B82CCA71}",

    # Scheduler
    "SchedulerActivity": "{4FB3C56D-3EF5-4317-8A5B-7CDFAC1CAC8F}",

    # Custom Dialog
    "CustomDialog": "{998A7CCC-4374-484D-A6ED-E8A4F0EB71BA}",

    # Group Separator (invisible)
    "GroupSeparator": "{586C3429-F931-405f-9938-928E22C90BFA}",
}

# ML_STAR device-specific CLSIDs
ML_STAR_CLSID = {
    "Initialize": "ML_STAR:{1C0C0CB0-7C87-11D3-AD83-0004ACB1DCB2}",
    "TipPickUp": "ML_STAR:{541143FA-7FA2-11D3-AD85-0004ACB1DCB2}",
    "Aspirate": "ML_STAR:{541143F5-7FA2-11D3-AD85-0004ACB1DCB2}",
    "Dispense": "ML_STAR:{541143F8-7FA2-11D3-AD85-0004ACB1DCB2}",
    "TipEject": "ML_STAR:{541143FC-7FA2-11D3-AD85-0004ACB1DCB2}",
    "MoveAutoLoad": "ML_STAR:{EA251BFB-66DE-48D1-83E5-6884B4DD8D11}",
    "GetLastLiquidLevel": "ML_STAR:{9FB6DFE0-4132-4d09-B502-98C722734D4C}",
}

# CLSIDs that use triple-brace {{{ (scope-creating / external reference steps)
TRIPLE_BRACE_CLSIDS = {
    STEP_CLSID["SingleLibFunction"],  # {C1F3C015-47B3-4514-9407-AC2E65043419}
    STEP_CLSID["SubmethodCall"],       # {7C4EF7A7-39BE-406a-897F-71F3A35B4093}
    STEP_CLSID["Return"],              # {9EC997CD-FD3B-4280-811B-49E99DCF062C}
}


# ─── GUID Utilities ─────────────────────────────────────────────────────────────

def generate_instance_guid() -> str:
    """
    Generate a new random GUID in Hamilton underscore format.
    
    Standard UUID:  550e8400-e29b-41d4-a716-446655440000
    Hamilton GUID:  550e8400_e29b_41d4_a716446655440000
    
    Pattern: xxxxxxxx_xxxx_xxxx_xxxxxxxxxxxxxxxx (8_4_4_16)
    """
    u = uuid.uuid4()
    s = str(u)  # e.g. "550e8400-e29b-41d4-a716-446655440000"
    parts = s.split("-")  # ["550e8400", "e29b", "41d4", "a716", "446655440000"]
    return f"{parts[0]}_{parts[1]}_{parts[2]}_{parts[3]}{parts[4]}"


def hamilton_guid_to_standard(h_guid: str) -> str:
    """Convert Hamilton underscore GUID to standard format."""
    parts = h_guid.split("_")
    last = parts[3]
    return f"{parts[0]}-{parts[1]}-{parts[2]}-{last[:4]}-{last[4:]}"


def standard_guid_to_hamilton(std_guid: str) -> str:
    """Convert standard GUID to Hamilton underscore format."""
    clean = std_guid.replace("{", "").replace("}", "")
    parts = clean.split("-")
    return f"{parts[0]}_{parts[1]}_{parts[2]}_{parts[3]}{parts[4]}"


# ─── CRC-32 Checksum ────────────────────────────────────────────────────────────

def crc32_hamilton(data: bytes) -> str:
    """
    Compute CRC-32 matching Hamilton's algorithm.
    
    Polynomial: 0xEDB88320 (standard CRC-32, reflected/LSB-first)
    Initial value: 0xFFFFFFFF
    Final XOR: 0xFFFFFFFF
    
    Returns: 8-character lowercase hex string
    """
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return format(crc ^ 0xFFFFFFFF, '08x')


def compute_hsl_checksum(content_before: str, prefix: str) -> str:
    """
    Compute the CRC-32 checksum for an HSL file.
    
    Args:
        content_before: All file content before the checksum line
        prefix: The checksum line from start up to and including "checksum="
    
    Returns: 8-character lowercase hex checksum string
    
    IMPORTANT: Must use latin1 encoding, NOT utf-8, to handle non-ASCII bytes.
    """
    data = (content_before + prefix).encode("latin1")
    return crc32_hamilton(data)


def generate_checksum_line(content_before: str, author: str = "admin",
                           valid: int = 0) -> str:
    """Generate a complete checksum footer line for an HSL file."""
    now = datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M")
    
    prefix = f"// $$author={author}$$valid={valid}$$time={time_str}$$checksum="
    checksum = compute_hsl_checksum(content_before, prefix)
    suffix = "$$length="
    
    line_without_length = f"{prefix}{checksum}{suffix}"
    # Total length = line + 3 (NNN) + 2 ($$) + 2 (\r\n)
    total_length = len(line_without_length) + 3 + 2 + 2
    length_str = str(total_length).zfill(3)
    
    return f"{prefix}{checksum}{suffix}{length_str}$$"


# ─── Block Marker Detection ─────────────────────────────────────────────────────

# Regex to detect step block markers
RE_STEP_MARKER = re.compile(
    r'^//\s*\{\{\{?\s+\d+\s+\d+\s+\d+\s+"[^"]+"\s+"[^"]+"', re.MULTILINE
)

# Regex to parse step opening markers
RE_STEP_OPEN = re.compile(
    r'^//\s*(\{\{\{?)\s+(\d+)\s+(\d+)\s+(\d+)\s+"([^"]+)"\s+"([^"]+)"\s*$'
)

# Regex to parse structural opening markers
RE_STRUCTURAL_OPEN = re.compile(
    r'^//\s*(\{\{\{?)\s+(\d+)\s+"([^"]+)"\s+"([^"]*)"\s*$'
)

# Regex to parse inline structural markers
RE_INLINE_STRUCTURAL = re.compile(
    r'^/\*\s*(\{\{\{?)\s+(\d+)\s+"([^"]+)"\s+"([^"]*)"\s*\*/\s*//\s*\}\}\s*""\s*$'
)

# Closing marker
RE_CLOSE = re.compile(r'^//\s*\}\}\s*""\s*$')

# Checksum/footer line
RE_CHECKSUM = re.compile(
    r'^//\s*\$\$author=([^$]*)\$\$valid=(\d+)\$\$time=([^$]*)\$\$checksum=([0-9a-fA-F]{8})\$\$length=(\d{3})\$\$\s*$'
)


def has_step_block_markers(content: str) -> bool:
    """
    Quick check: does content contain step block markers?
    
    Used as a guard to prevent processing library files.
    Library files (like ArrayTable.hsl) never have step block markers;
    method files (like Method1.hsl) always have them.
    """
    return bool(RE_STEP_MARKER.search(content))


# ─── Block Marker Types ─────────────────────────────────────────────────────────

class StepBlockMarker(NamedTuple):
    """A parsed compound step block marker."""
    row: int
    column: int
    sublevel: int
    instance_guid: str
    step_clsid: str
    triple_brace: bool
    code_lines: List[str]


class StructuralBlockMarker(NamedTuple):
    """A parsed structural block marker."""
    block_type: int
    section_name: str
    qualifier: str
    triple_brace: bool
    inline: bool
    code_lines: List[str]


# ─── Block Marker Parsing ───────────────────────────────────────────────────────

def parse_block_markers(content: str):
    """
    Parse all block markers from an HSL file's text content.
    Returns a list of StepBlockMarker and StructuralBlockMarker objects.
    """
    lines = content.split('\n')
    # Normalize \r\n
    lines = [line.rstrip('\r') for line in lines]
    markers = []
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
            code_lines = []
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


# ─── Block Marker Generation ────────────────────────────────────────────────────

def is_triple_brace_clsid(clsid: str) -> bool:
    """Whether a CLSID should use triple-brace markers."""
    return clsid in TRIPLE_BRACE_CLSIDS


def make_step_open_marker(row: int, column: int, sublevel: int,
                           instance_guid: str, step_clsid: str,
                           triple_brace: bool = False) -> str:
    """Generate an opening block marker line for a compound step."""
    braces = "{{{" if triple_brace else "{{"
    return f'// {braces} {row} {column} {sublevel} "{instance_guid}" "{step_clsid}"'


def make_structural_open_marker(block_type: int, section_name: str,
                                 qualifier: str,
                                 triple_brace: bool = False) -> str:
    """Generate an opening structural block marker line."""
    braces = "{{{" if triple_brace else "{{"
    return f'// {braces} {block_type} "{section_name}" "{qualifier}"'


def make_inline_structural_marker(block_type: int, section_name: str,
                                   qualifier: str) -> str:
    """Generate an inline structural block marker (single-line with close)."""
    return f'/* {{{{ {block_type} "{section_name}" "{qualifier}" */ // }}}} ""'


def make_close_marker() -> str:
    """Generate a closing block marker line."""
    return '// }} ""'


# ─── Row Renumbering ─────────────────────────────────────────────────────────────

def renumber_block_markers(content: str) -> str:
    """
    Renumber all step block marker rows sequentially starting from 1.
    Only modifies the row number in each step opening marker; all other content
    (code, structural markers, GUIDs, CLSIDs) is preserved exactly.
    
    Safe to call on any .hsl content — if there are no step markers,
    the content is returned unchanged.
    """
    counter = [0]  # Use list for closure mutability
    
    def replace_row(match):
        counter[0] += 1
        return f"{match.group(1)}{counter[0]}{match.group(2)}"
    
    pattern = re.compile(
        r'^(//\s*\{\{\{?\s+)\d+(\s+\d+\s+\d+\s+"[^"]+"\s+"[^"]+")',
        re.MULTILINE
    )
    return pattern.sub(replace_row, content)


# ─── Step Definitions ───────────────────────────────────────────────────────────

class MethodStep:
    """Definition of a method step for generation purposes."""
    
    def __init__(self, step_type: str, code: List[str],
                 clsid: Optional[str] = None,
                 device: Optional[str] = None,
                 close_code: Optional[List[str]] = None,
                 children: Optional[List['MethodStep']] = None,
                 else_children: Optional[List['MethodStep']] = None,
                 instance_guid: Optional[str] = None):
        self.step_type = step_type
        self.code = code
        self.clsid = clsid
        self.device = device
        self.close_code = close_code
        self.children = children or []
        self.else_children = else_children or []
        self.instance_guid = instance_guid
    
    def resolve_clsid(self) -> str:
        if self.clsid:
            return self.clsid
        if self.device and self.step_type in ML_STAR_CLSID:
            return ML_STAR_CLSID[self.step_type]
        if self.step_type in STEP_CLSID:
            return STEP_CLSID[self.step_type]
        raise ValueError(f"Unknown step type: {self.step_type}. Provide an explicit clsid.")


# ─── Step Builder Helpers ────────────────────────────────────────────────────────

def comment_step(text: str, trace: bool = True) -> MethodStep:
    """Create a Comment step."""
    escaped = text.replace('"', '\\"').replace('\n', '\\n')
    if trace:
        code = [f'MECC::TraceComment(Translate("{escaped}"));']
    else:
        code = ['']
    return MethodStep("Comment", code)


def assignment_step(variable: str, value: str) -> MethodStep:
    """Create an Assignment step."""
    return MethodStep("Assignment", [f"{variable} = {value};"])


def for_loop_step(counter: str, count, body: List[MethodStep]) -> MethodStep:
    """Create a Loop (for) step."""
    return MethodStep(
        "Loop",
        ["{", f"for({counter} = 0; {counter} < {count};)", "{", f"{counter} = {counter} + 1;"],
        close_code=["}",  "}"],
        children=body,
    )


def while_loop_step(condition: str, counter: str,
                     body: List[MethodStep]) -> MethodStep:
    """Create a Loop (while) step."""
    return MethodStep(
        "Loop",
        ["{", f"{counter} = 0;", f"while ({condition})", "{", f"{counter} = {counter} + 1;"],
        close_code=["}",  "}"],
        children=body,
    )


def if_else_step(condition: str, then_steps: List[MethodStep],
                  else_steps: Optional[List[MethodStep]] = None) -> MethodStep:
    """Create an If/Then/Else step."""
    return MethodStep(
        "IfThenElse",
        [f"if ({condition})  {{"],
        close_code=["}"],
        children=then_steps,
        else_children=else_steps or [],
    )


def submethod_call_step(fname: str, args: List[str]) -> MethodStep:
    """Create a Submethod Call step."""
    return MethodStep("SubmethodCall", [f"{fname}({', '.join(args)});"])


def library_function_step(namespace: str, fname: str,
                           args: List[str]) -> MethodStep:
    """Create a Library Function (Smart Step) call."""
    return MethodStep("SingleLibFunction", [f"{namespace}::{fname}({', '.join(args)});"])


def abort_step() -> MethodStep:
    return MethodStep("Abort", ["abort;"])


def break_step() -> MethodStep:
    return MethodStep("Break", ["break;"])


def return_step() -> MethodStep:
    return MethodStep("Return", ["return;"])


def shell_step(command: str, wait: bool = True) -> MethodStep:
    """Create a Shell step."""
    flag = "hslTrue" if wait else "hslFalse"
    return MethodStep("Shell", [f"Shell({command}, {flag});"])


# ─── Generation State ───────────────────────────────────────────────────────────

class GeneratedStepInfo(NamedTuple):
    """Information about a generated step (for .med generation)."""
    instance_guid: str
    clsid: str
    row: int
    block_index: int
    code: str
    triple_brace: bool


class GenerationState:
    """Internal state for tracking row numbers during generation."""
    
    def __init__(self):
        self.current_row = 1
        self.column = 1
        self.lines: List[str] = []
        self.generated_steps: List[GeneratedStepInfo] = []


# ─── Method Generation ──────────────────────────────────────────────────────────

def emit_step(state: GenerationState, step: MethodStep) -> None:
    """Emit a single step (and its children if applicable) into the generation state."""
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
    """
    Generate a complete HSL method file with valid block markers.
    
    Returns:
        Tuple of (hsl_content, sub_content, generated_steps)
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
    state.lines.append(make_structural_open_marker(2, "LocalSubmethodInclude", "", True))
    state.lines.append(' namespace _Method {  #include __filename__ ".sub"  } ')
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
    checksum_line = generate_checksum_line(hsl_body, author)
    hsl_content = hsl_body + checksum_line + "\r\n"
    
    # Generate .sub file
    sub_lines = []
    sub_lines.append(make_structural_open_marker(2, "SubmethodForwardDeclaration", "", True))
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
    sub_checksum = generate_checksum_line(sub_body, author)
    sub_content = sub_body + sub_checksum + "\r\n"
    
    return hsl_content, sub_content, state.generated_steps


# ─── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Hamilton HSL Block Marker Generator — Reference Implementation"
    )
    parser.add_argument("--output", "-o", default=None,
                        help="Output directory (default: current directory)")
    parser.add_argument("--name", "-n", default="GeneratedMethod",
                        help="Method name (default: GeneratedMethod)")
    parser.add_argument("--steps", "-s", type=int, default=3,
                        help="Number of comment steps to generate (default: 3)")
    parser.add_argument("--show-clsids", action="store_true",
                        help="Print CLSID registry and exit")
    parser.add_argument("--demo-complex", action="store_true",
                        help="Generate a complex demo with loops, if/else, etc.")
    parser.add_argument("--author", default="admin",
                        help="Author name for checksum (default: admin)")
    args = parser.parse_args()
    
    if args.show_clsids:
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║              Hamilton HSL CLSID Registry                    ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print(f"║ {'Step Type':<30} {'CLSID':<40} ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        for name, clsid in STEP_CLSID.items():
            triple = " {{{" if clsid in TRIPLE_BRACE_CLSIDS else "   "
            print(f"║ {name:<30} {clsid:<37}{triple} ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print("║ ML_STAR Device-Specific CLSIDs                              ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        for name, clsid in ML_STAR_CLSID.items():
            print(f"║ {name:<30} {clsid:<30} ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        return
    
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     Hamilton HSL Block Marker Generator                    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    # Build steps
    if args.demo_complex:
        steps = [
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
            comment_step(f"Step {i+1} of {args.steps}")
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
    
    # Report
    print("  ┌─ Generated Steps ─────────────────────────────────────────┐")
    for info in generated_steps:
        brace = "{{{" if info.triple_brace else "{{ "
        clsid_name = "Unknown"
        for name, c in STEP_CLSID.items():
            if c == info.clsid:
                clsid_name = name
                break
        print(f"  │  Row {info.row:>3} {brace} Block {info.block_index}"
              f"  {clsid_name:<20} {info.instance_guid[:20]}... │")
    print("  └──────────────────────────────────────────────────────────┘")
    print()
    
    # Verify block markers
    parsed = parse_block_markers(hsl_content)
    step_markers = [m for m in parsed if isinstance(m, StepBlockMarker)]
    struct_markers = [m for m in parsed if isinstance(m, StructuralBlockMarker)]
    print(f"  Verification:")
    print(f"    Step markers parsed:       {len(step_markers)}")
    print(f"    Structural markers parsed: {len(struct_markers)}")
    print(f"    Has step block markers:    {has_step_block_markers(hsl_content)}")
    
    # Verify renumbering is idempotent
    renumbered = renumber_block_markers(hsl_content)
    # Strip checksum lines for comparison (since renumbering doesn't change checksums)
    hsl_no_cksum = re.sub(r'^// \$\$author=.*$', '', hsl_content, flags=re.MULTILINE).strip()
    ren_no_cksum = re.sub(r'^// \$\$author=.*$', '', renumbered, flags=re.MULTILINE).strip()
    print(f"    Renumber idempotent:       {hsl_no_cksum == ren_no_cksum}")
    print()
    
    # Show a snippet
    lines = hsl_content.split("\r\n")
    print("  ┌─ File Preview (first 20 lines) ───────────────────────────┐")
    for i, line in enumerate(lines[:20], 1):
        truncated = line[:60] + "..." if len(line) > 60 else line
        print(f"  │ {i:>3}: {truncated:<60}│")
    if len(lines) > 20:
        print(f"  │ ... ({len(lines) - 20} more lines)                              │")
    print("  └──────────────────────────────────────────────────────────┘")
    print()
    print("  Done.")


if __name__ == "__main__":
    main()
