#!/usr/bin/env python3
"""
smt_generator.py -- Hamilton .smt (Sub-Method Template) Generator for HSL Libraries

Generates a companion ``.smt`` file for an HSL library (``.hsl``) so that the
Hamilton VENUS Method Editor displays function descriptions and parameter
descriptions in its tooltips and step insertion dialogs - exactly like the
built-in SmartStep sub-method libraries.

Architecture
============
1. Parse the ``.hsl`` file to extract all forward function declarations
2. Parse parameter lists to determine names, types, and directions
3. Optionally load a JSON descriptions file for function/parameter docs
4. Build the ``HxMetEd_Submethods`` HxPars section with full metadata
5. Construct a minimal HxCfgFile v3 container (text format)
6. Write binary ``.smt`` via the pure-Python hxcfgfile_codec

Usage
=====
::

    python -m standalone_med_tools.smt_generator MyLibrary.hsl
    python -m standalone_med_tools.smt_generator MyLibrary.hsl --descriptions MyLibrary.descriptions.json
    python -m standalone_med_tools.smt_generator MyLibrary.hsl --output MyLibrary.smt

The optional JSON descriptions file format::

    {
        "functions": {
            "MyFunction": {
                "description": "Does something useful.",
                "parameters": {
                    "inputParam": "The input value.",
                    "outputResult": "The computed result."
                }
            }
        }
    }

Requirements: Python 3.8+ (no external dependencies)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
)

# ---- Conditional imports for standalone vs package use ----
try:
    from .hxcfgfile_codec import (
        HxCfgTextModel,
        HxParsSection,
        NamedSection,
        build_binary_med,
        build_text_med,
        parse_text_med,
        ACTIVITY_SECTION_NAME,
        ACTIVITY_KEY,
    )
    from .checksum import generate_checksum_line
except ImportError:
    from hxcfgfile_codec import (  # type: ignore[no-redef]
        HxCfgTextModel,
        HxParsSection,
        NamedSection,
        build_binary_med,
        build_text_med,
        parse_text_med,
        ACTIVITY_SECTION_NAME,
        ACTIVITY_KEY,
    )
    from checksum import generate_checksum_line  # type: ignore[no-redef]


# ==============================================================================
# Field ID Constants (from HxCommandKeys / med_format_analysis.md)
# ==============================================================================

# HxMetEd_Submethods field IDs
FID_SUBMETHODS_CONTAINER = "-533725162"   # Container for all submethod entries
FID_SUBMETHOD_NAME       = "-533725161"   # Function name string
FID_SUBMETHOD_DESC       = "-533725170"   # Function description string
FID_IS_SYSTEM_METHOD     = "-533725172"   # 1 = system method, 0 = user method
FID_UNKNOWN_171          = "-533725171"   # Always 0 in observed files
FID_PARAMS_CONTAINER     = "-533725169"   # Container for parameter entries
FID_PARAM_NAME           = "-533725168"   # Parameter name string
FID_PARAM_DESC           = "-533725167"   # Parameter description string
FID_PARAM_TYPE           = "-533725165"   # HSL type code (int)
FID_PARAM_DIRECTION      = "-533725166"   # Direction: 1=in, 2=in/out, 3=out
FID_PARAM_DEFAULT_NAME   = "-533725163"   # Default value / labware name
FID_PARAM_DEFAULT_OBJ    = "-533725164"   # Default value / labware object

# HxMetEdData field IDs
FID_METEDDATA_FLAG1      = "-533725180"   # Always 1
FID_METEDDATA_FLAG2      = "-533725181"   # Version/capability flag
FID_METEDDATA_COMPILER   = "-533725182"   # Compiler options container

# HSL type codes for parameter type field
HSL_TYPE_VARIABLE     = 1    # variable (scalar)
HSL_TYPE_STRING       = 2    # string
HSL_TYPE_DEVICE       = 5    # device &
HSL_TYPE_SEQUENCE     = 7    # sequence &
HSL_TYPE_OBJECT       = 9    # object
HSL_TYPE_TIMER        = 11   # timer
HSL_TYPE_EVENT        = 13   # event
HSL_TYPE_FILE         = 15   # file
HSL_TYPE_RESOURCE     = 17   # resource
HSL_TYPE_DIALOG       = 19   # dialog
HSL_TYPE_VARIABLE_ARR = 65   # variable[]

# Parameter direction codes
DIR_IN    = 1  # input parameter (by value)
DIR_INOUT = 2  # input/output parameter (by reference: &)
DIR_OUT   = 3  # output parameter (by reference: &, typically array)

# Map from HSL type keyword to type code
TYPE_KEYWORD_MAP: Dict[str, int] = {
    "variable":  HSL_TYPE_VARIABLE,
    "string":    HSL_TYPE_STRING,
    "device":    HSL_TYPE_DEVICE,
    "sequence":  HSL_TYPE_SEQUENCE,
    "object":    HSL_TYPE_OBJECT,
    "timer":     HSL_TYPE_TIMER,
    "event":     HSL_TYPE_EVENT,
    "file":      HSL_TYPE_FILE,
    "resource":  HSL_TYPE_RESOURCE,
    "dialog":    HSL_TYPE_DIALOG,
}


# ==============================================================================
# HSL Function Parser
# ==============================================================================

@property
def _dummy():
    """Prevent dataclass decorator from being needed."""
    pass


class HslParam:
    """Parsed HSL function parameter."""
    __slots__ = ("name", "type_code", "direction", "is_array", "raw_type")

    def __init__(
        self,
        name: str,
        type_code: int,
        direction: int,
        is_array: bool = False,
        raw_type: str = "",
    ):
        self.name = name
        self.type_code = type_code
        self.direction = direction
        self.is_array = is_array
        self.raw_type = raw_type

    def __repr__(self) -> str:
        dirs = {1: "in", 2: "in/out", 3: "out"}
        arr = "[]" if self.is_array else ""
        return f"HslParam({self.raw_type}{arr} {self.name}, dir={dirs.get(self.direction, '?')})"


class HslFunction:
    """Parsed HSL function declaration."""
    __slots__ = ("name", "params", "return_type", "is_private", "namespace")

    def __init__(
        self,
        name: str,
        params: List[HslParam],
        return_type: str = "void",
        is_private: bool = False,
        namespace: str = "",
    ):
        self.name = name
        self.params = params
        self.return_type = return_type
        self.is_private = is_private
        self.namespace = namespace

    def __repr__(self) -> str:
        ns = f"{self.namespace}::" if self.namespace else ""
        priv = "private " if self.is_private else ""
        return f"HslFunction({priv}{ns}{self.name}({len(self.params)} params) -> {self.return_type})"


# Regex for function declarations.
# Matches TWO patterns:
#   1. Forward declarations: [private] function Name(params) ReturnType;
#   2. Stub implementations: [private] function Name(params) ReturnType {return(0);}
# Pattern 2 is used by Hamilton system libraries (HSLStrLib, HSLArrLib, etc.)
# that use `#ifndef HSL_RUNTIME` guards with inline stub bodies.
_RE_FUNC_DECL = re.compile(
    r"^[ \t]*"
    r"(?:(private)\s+)?"
    r"function\s+"
    r"(\w+)"
    r"\s*\("
    r"([^)]*)"
    r"\)\s*"
    r"(\w+)\s*"
    r"(?:;|\{[^}]*\})",
    re.MULTILINE,
)

# Regex to match namespace blocks
_RE_NAMESPACE = re.compile(
    r"^\s*namespace\s+(\w+)\s*\{",
    re.MULTILINE,
)

# Regex for a single parameter in the parameter list
# Matches: type [&] name [[]  []]
_RE_PARAM = re.compile(
    r"(\w+)"            # type keyword
    r"\s*"
    r"(&)?"             # optional reference marker
    r"\s+"
    r"(\w+)"            # parameter name
    r"\s*"
    r"(\[\s*\])?"       # optional array brackets
)


def _parse_param_list(param_str: str) -> List[HslParam]:
    """Parse a comma-separated HSL parameter list string."""
    params: List[HslParam] = []
    if not param_str.strip():
        return params

    # Split on commas, but be careful about nested brackets
    parts = [p.strip() for p in param_str.split(",")]

    for part in parts:
        if not part:
            continue
        m = _RE_PARAM.match(part)
        if not m:
            continue

        type_kw = m.group(1).lower()
        is_ref = m.group(2) is not None
        name = m.group(3)
        is_array = m.group(4) is not None

        type_code = TYPE_KEYWORD_MAP.get(type_kw, HSL_TYPE_VARIABLE)

        # Determine direction
        if is_array:
            type_code = HSL_TYPE_VARIABLE_ARR
            # Arrays passed by reference are typically output
            direction = DIR_OUT if is_ref else DIR_IN
        elif is_ref:
            # Reference parameters (device &, sequence &) are in/out
            direction = DIR_INOUT
        else:
            direction = DIR_IN

        params.append(HslParam(
            name=name,
            type_code=type_code,
            direction=direction,
            is_array=is_array,
            raw_type=type_kw,
        ))

    return params


def parse_hsl_functions(hsl_content: str) -> List[HslFunction]:
    """Parse all forward function declarations from HSL source code.

    Only captures forward declarations (ending with ;), not definitions
    (ending with {}).  This avoids duplicate entries since HSL requires
    both a declaration and a definition with matching signatures.
    """
    functions: List[HslFunction] = []

    # First, find all namespace boundaries
    # Simple approach: track which namespace each function line falls in
    namespace_ranges: List[Tuple[int, int, str]] = []

    for ns_match in _RE_NAMESPACE.finditer(hsl_content):
        ns_name = ns_match.group(1)
        ns_start = ns_match.start()
        # Find the matching closing brace (simple brace counting)
        depth = 0
        pos = ns_match.end()
        while pos < len(hsl_content):
            ch = hsl_content[pos]
            if ch == "{":
                depth += 1
            elif ch == "}":
                if depth == 0:
                    namespace_ranges.append((ns_start, pos, ns_name))
                    break
                depth -= 1
            pos += 1

    def _find_namespace(char_pos: int) -> str:
        for ns_start, ns_end, ns_name in namespace_ranges:
            if ns_start <= char_pos <= ns_end:
                return ns_name
        return ""

    seen_names = set()

    for m in _RE_FUNC_DECL.finditer(hsl_content):
        is_private = m.group(1) is not None
        func_name = m.group(2)
        param_str = m.group(3)
        return_type = m.group(4)
        namespace = _find_namespace(m.start())

        # Deduplicate by qualified name
        qualified = f"{namespace}::{func_name}" if namespace else func_name
        if qualified in seen_names:
            continue
        seen_names.add(qualified)

        params = _parse_param_list(param_str)

        functions.append(HslFunction(
            name=func_name,
            params=params,
            return_type=return_type,
            is_private=is_private,
            namespace=namespace,
        ))

    return functions


# ==============================================================================
# Descriptions Loader
# ==============================================================================

class DescriptionsData:
    """Container for function and parameter descriptions."""

    def __init__(self, data: Optional[Dict] = None):
        self._functions: Dict[str, Dict] = {}
        if data and "functions" in data:
            self._functions = data["functions"]

    def get_function_desc(self, func_name: str) -> str:
        entry = self._functions.get(func_name, {})
        return entry.get("description", "")

    def get_param_desc(self, func_name: str, param_name: str) -> str:
        entry = self._functions.get(func_name, {})
        params = entry.get("parameters", {})
        return params.get(param_name, "")


def load_descriptions(json_path: Optional[Path]) -> DescriptionsData:
    """Load descriptions from a JSON file, or return empty descriptions."""
    if json_path is None or not json_path.exists():
        return DescriptionsData()
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return DescriptionsData(data)


def generate_descriptions_template(
    functions: List[HslFunction],
    output_path: Path,
) -> None:
    """Generate a template JSON descriptions file from parsed functions."""
    template = {"functions": {}}
    for func in functions:
        entry = {
            "description": "",
            "parameters": {},
        }
        for param in func.params:
            entry["parameters"][param.name] = ""
        template["functions"][func.name] = entry

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=4)


# ==============================================================================
# SMT Builder
# ==============================================================================

# Minimal ActivityData base64 blob.  This is the smallest valid flowchart
# document that the VENUS Method Editor accepts.  It was extracted from a
# minimal .smt file and contains an empty activity graph.
_MINIMAL_ACTIVITY_BLOB = (
    "AgAAAAAAAAAAAAAAAAAAAKAPAACgDwAAAAAHAAAA"
)


def _build_submethods_tokens(
    functions: List[HslFunction],
    descriptions: DescriptionsData,
    is_system: bool = True,
) -> List[str]:
    """Build the token list for the HxMetEd_Submethods HxPars section.

    The structure mirrors what the Hamilton Method Editor produces:

    ::

        (-533725162             # submethods container open
          (0                    # submethod index 0
            (-533725169         # parameters container open
              (0                # parameter index 0
                1-533725163, "" # default labware name
                1-533725164, "" # default labware object
                3-533725165, N  # type code
                3-533725166, D  # direction code
                1-533725167, "" # parameter description
                1-533725168, nm # parameter name
              )                 # parameter close
              ...
            )                   # parameters container close
            1-533725170, ""     # function description
            3-533725171, 0      # unknown (always 0)
            1-533725161, name   # function name
            3-533725172, 0/1    # is system method
          )                     # submethod close
          ...
        )                       # submethods container close
    """
    tokens: List[str] = []

    # Open submethods container
    tokens.append(f"({FID_SUBMETHODS_CONTAINER}")

    system_flag = "1" if is_system else "0"

    for func_idx, func in enumerate(functions):
        # Open submethod entry
        tokens.append(f"({func_idx}")

        # Open parameters container
        tokens.append(f"({FID_PARAMS_CONTAINER}")

        for param_idx, param in enumerate(func.params):
            # Open parameter entry
            tokens.append(f"({param_idx}")

            # Default labware name/object (for device params, use the param name)
            if param.type_code == HSL_TYPE_DEVICE:
                tokens.append(f"1{FID_PARAM_DEFAULT_NAME}")
                tokens.append(param.name)
                tokens.append(f"1{FID_PARAM_DEFAULT_OBJ}")
                tokens.append(param.name)
            else:
                tokens.append(f"1{FID_PARAM_DEFAULT_NAME}")
                tokens.append("")
                tokens.append(f"1{FID_PARAM_DEFAULT_OBJ}")
                tokens.append("")

            # Type code
            tokens.append(f"3{FID_PARAM_TYPE}")
            tokens.append(str(param.type_code))

            # Direction
            tokens.append(f"3{FID_PARAM_DIRECTION}")
            tokens.append(str(param.direction))

            # Parameter description
            tokens.append(f"1{FID_PARAM_DESC}")
            tokens.append(descriptions.get_param_desc(func.name, param.name))

            # Parameter name
            tokens.append(f"1{FID_PARAM_NAME}")
            tokens.append(param.name)

            # Close parameter entry
            tokens.append(")")

        # Close parameters container
        tokens.append(")")

        # Function description
        tokens.append(f"1{FID_SUBMETHOD_DESC}")
        tokens.append(descriptions.get_function_desc(func.name))

        # Unknown field (always 0)
        tokens.append(f"3{FID_UNKNOWN_171}")
        tokens.append("0")

        # Function name
        tokens.append(f"1{FID_SUBMETHOD_NAME}")
        tokens.append(func.name)

        # Is system method
        tokens.append(f"3{FID_IS_SYSTEM_METHOD}")
        tokens.append(system_flag)

        # Close submethod entry
        tokens.append(")")

    # Close submethods container
    tokens.append(")")

    return tokens


def _build_meted_data_tokens() -> List[str]:
    """Build the token list for the HxMetEdData section.

    This section stores Method Editor metadata (version, compiler flags).
    """
    return [
        "1Version",
        "4.4.0.7740",
        f"3{FID_METEDDATA_FLAG1}",
        "1",
        f"3{FID_METEDDATA_FLAG2}",
        "1045",
        f"({FID_METEDDATA_COMPILER}",
        "3SchedCompCmd",
        "0",
        "3SampleTracker",
        "0",
        "3CustomDialogCompCmd",
        "0",
        "3GRUCompCmd",
        "0",
        ")",
        ")",
    ]


def build_smt_model(
    functions: List[HslFunction],
    descriptions: DescriptionsData,
    author: str = "admin",
    is_system: bool = True,
) -> HxCfgTextModel:
    """Build a complete HxCfgTextModel for an .smt file.

    The minimal valid .smt contains:
    1. ActivityData named section (flowchart blob)
    2. HxMetEdData HxPars section (editor metadata)
    3. HxMetEd_Submethods HxPars section (function declarations + descriptions)
    4. Footer checksum line
    """
    # Named section: ActivityData
    activity_section = NamedSection(
        name=ACTIVITY_SECTION_NAME,
        key=ACTIVITY_KEY,
        value=_MINIMAL_ACTIVITY_BLOB,
        field_type=1,
    )

    # HxPars section: HxMetEdData
    meted_data = HxParsSection(
        key="HxMetEdData",
        tokens=_build_meted_data_tokens(),
        prefix="HxPars",
        version=3,
    )

    # HxPars section: HxMetEd_Submethods
    submethods = HxParsSection(
        key="HxMetEd_Submethods",
        tokens=_build_submethods_tokens(functions, descriptions, is_system),
        prefix="HxPars",
        version=3,
    )

    # Build a temporary footer (will be recalculated)
    timestamp = datetime.now()
    time_str = timestamp.strftime("%Y-%m-%d %H:%M")
    placeholder_footer = (
        f"* $$author={author}$$valid=1$$time={time_str}"
        f"$$checksum=00000000$$length=000$$"
    )

    model = HxCfgTextModel(
        named_sections=[activity_section],
        hxpars_sections=[meted_data, submethods],
        footer_line=placeholder_footer,
    )

    # Build text to calculate correct checksum
    text = build_text_med(model)

    # Split off the placeholder footer, recalculate
    footer_idx = text.rfind("* $$author=")
    if footer_idx < 0:
        raise ValueError("Could not find footer in generated text")

    content_before = text[:footer_idx]
    real_footer = generate_checksum_line(
        content_before,
        author=author,
        valid=1,
        prefix_char="*",
        timestamp=timestamp,
    )
    model.footer_line = real_footer

    return model


# ==============================================================================
# Main Entry Point
# ==============================================================================

def generate_smt(
    hsl_path: Path,
    output_path: Optional[Path] = None,
    descriptions_path: Optional[Path] = None,
    author: str = "admin",
    text_format: bool = False,
    template_only: bool = False,
) -> Path:
    """Generate an .smt file for an HSL library.

    Args:
        hsl_path: Path to the .hsl source file
        output_path: Path for the output .smt file (default: same name as .hsl)
        descriptions_path: Optional path to JSON descriptions file
        author: Author name for the checksum footer
        text_format: If True, write text format instead of binary
        template_only: If True, only generate the descriptions template JSON

    Returns:
        Path to the generated file
    """
    # Read HSL source
    hsl_content = hsl_path.read_text(encoding="latin1")

    # Parse functions
    functions = parse_hsl_functions(hsl_content)
    if not functions:
        print(f"WARNING: No function declarations found in {hsl_path.name}")

    # Filter out private functions (they shouldn't appear in the SMT)
    public_functions = [f for f in functions if not f.is_private]

    print(f"Found {len(functions)} functions ({len(public_functions)} public)")
    for func in public_functions:
        ns = f"{func.namespace}::" if func.namespace else ""
        params_str = ", ".join(
            f"{p.raw_type}{'[]' if p.is_array else ''} {p.name}"
            for p in func.params
        )
        print(f"  {ns}{func.name}({params_str}) -> {func.return_type}")

    # Default output path
    if output_path is None:
        output_path = hsl_path.with_suffix(".smt")

    # Template-only mode: generate JSON template and exit
    if template_only:
        template_path = hsl_path.with_suffix(".descriptions.json")
        generate_descriptions_template(public_functions, template_path)
        print(f"Generated descriptions template: {template_path}")
        return template_path

    # Load descriptions
    descriptions = load_descriptions(descriptions_path)

    # Build model
    model = build_smt_model(
        public_functions,
        descriptions,
        author=author,
    )

    # Write output
    if text_format:
        text = build_text_med(model)
        output_path.write_text(text, encoding="latin1", newline="")
        print(f"Generated text-format SMT: {output_path}")
    else:
        binary = build_binary_med(model)
        output_path.write_bytes(binary)
        print(f"Generated binary SMT: {output_path}")

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate .smt companion files for HSL libraries"
    )
    parser.add_argument(
        "hsl_file",
        type=Path,
        help="Path to the .hsl library source file",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output .smt file path (default: same name as .hsl with .smt extension)",
    )
    parser.add_argument(
        "--descriptions", "-d",
        type=Path,
        default=None,
        help="Path to JSON descriptions file",
    )
    parser.add_argument(
        "--author",
        type=str,
        default="admin",
        help="Author name for the checksum footer (default: admin)",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Write text format instead of binary",
    )
    parser.add_argument(
        "--template",
        action="store_true",
        help="Generate a JSON descriptions template file and exit",
    )

    args = parser.parse_args()

    if not args.hsl_file.exists():
        print(f"ERROR: File not found: {args.hsl_file}", file=sys.stderr)
        return 1

    # Auto-discover descriptions file if not specified
    desc_path = args.descriptions
    if desc_path is None:
        auto_desc = args.hsl_file.with_suffix(".descriptions.json")
        if auto_desc.exists():
            desc_path = auto_desc
            print(f"Auto-discovered descriptions file: {desc_path}")

    try:
        generate_smt(
            hsl_path=args.hsl_file,
            output_path=args.output,
            descriptions_path=desc_path,
            author=args.author,
            text_format=args.text,
            template_only=args.template,
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
