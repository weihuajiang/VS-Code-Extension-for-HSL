"""
HSL Preprocessor
================
Handles #include, #define, #ifdef/#ifndef/#endif, #pragma once directives.
Resolves file includes relative to Hamilton's Library and Methods directories.

SIMULATION ONLY - No hardware interaction.
"""

import os
import re
from pathlib import Path
from typing import Optional


class PreprocessorError(Exception):
    """Error during preprocessing."""
    def __init__(self, message: str, file: str = "", line: int = 0):
        self.file = file
        self.line = line
        super().__init__(f"{file}({line}): Preprocessor error: {message}")


class Preprocessor:
    """HSL Preprocessor - resolves includes, defines, and conditional compilation."""

    # Default Hamilton installation paths
    DEFAULT_HAMILTON_DIR = r"C:\Program Files (x86)\Hamilton"

    def __init__(self, hamilton_dir: Optional[str] = None):
        self.hamilton_dir = hamilton_dir or self.DEFAULT_HAMILTON_DIR
        self.search_paths = [
            os.path.join(self.hamilton_dir, "Library"),
            os.path.join(self.hamilton_dir, "Methods"),
            os.path.join(self.hamilton_dir, "Methods", "Library Demo Methods"),
            os.path.join(self.hamilton_dir, "Bin"),
        ]
        self.defines: dict[str, str] = {}
        self.pragma_once_files: set[str] = set()
        self.included_files: set[str] = set()
        self.include_stack: list[str] = []
        self.source_map: list[tuple[str, int]] = []  # (original_file, original_line)
        self._current_file = ""
        self._max_include_depth = 50

        # Always define HSL_RUNTIME for simulation mode
        self.defines["HSL_RUNTIME"] = "1"

    def add_search_path(self, path: str):
        """Add a directory to the include search path."""
        if path not in self.search_paths:
            self.search_paths.insert(0, path)

    def resolve_include(self, include_path: str, relative_to: str = "") -> Optional[str]:
        """Resolve an include path to an absolute file path."""
        # Handle __filename__ token
        if "__filename__" in include_path:
            if relative_to:
                base = os.path.splitext(relative_to)[0]
                include_path = include_path.replace('__filename__', f'"{base}"')
                # Clean up double quotes from the replacement
                include_path = include_path.replace('""', '')
                include_path = include_path.strip('"')
                # Handle concatenation like __filename__ ".sub"
                parts = include_path.split('" "')
                if len(parts) == 1:
                    include_path = include_path.strip('"')

        # Clean path
        include_path = include_path.strip('"').strip("'").strip()

        # Try relative to current file first
        if relative_to:
            rel_dir = os.path.dirname(relative_to)
            candidate = os.path.normpath(os.path.join(rel_dir, include_path))
            if os.path.isfile(candidate):
                return candidate

        # Try each search path
        for search_dir in self.search_paths:
            candidate = os.path.normpath(os.path.join(search_dir, include_path))
            if os.path.isfile(candidate):
                return candidate

        # Try the include path as absolute
        if os.path.isabs(include_path) and os.path.isfile(include_path):
            return include_path

        return None

    def preprocess_file(self, filepath: str) -> str:
        """Preprocess an HSL file, resolving all includes and directives."""
        filepath = os.path.normpath(os.path.abspath(filepath))
        if not os.path.isfile(filepath):
            raise PreprocessorError(f"File not found: {filepath}")

        # Add the file's directory to search paths
        file_dir = os.path.dirname(filepath)
        self.add_search_path(file_dir)

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        return self.preprocess(content, filepath)

    def preprocess(self, source: str, filepath: str = "<string>") -> str:
        """Preprocess HSL source code."""
        self._current_file = filepath
        filepath_norm = os.path.normpath(filepath)

        # Check pragma once
        if filepath_norm in self.pragma_once_files:
            return ""

        # Check include depth
        if len(self.include_stack) >= self._max_include_depth:
            raise PreprocessorError(
                f"Maximum include depth ({self._max_include_depth}) exceeded",
                filepath, 0
            )

        self.include_stack.append(filepath_norm)
        self.included_files.add(filepath_norm)

        lines = source.split('\n')
        output_lines = []
        condition_stack: list[bool] = []  # Stack of if/ifdef conditions: True = active

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Handle preprocessor directives
            if stripped.startswith('#'):
                directive_result = self._handle_directive(
                    stripped, filepath, line_num, condition_stack
                )
                if directive_result is not None:
                    output_lines.append(directive_result)
                    self.source_map.append((filepath, line_num))
                else:
                    # Add empty line to preserve line numbering
                    output_lines.append("")
                    self.source_map.append((filepath, line_num))
                continue

            # If we're in a false conditional block, skip
            if condition_stack and not all(condition_stack):
                output_lines.append("")
                self.source_map.append((filepath, line_num))
                continue

            # Handle inline includes: namespace _Method { #include "file.hsl" }
            inline_include = re.match(
                r'(.*?)\s*#include\s+(".*?"|<.*?>|__filename__\s*"[^"]*")\s*(.*)',
                line
            )
            if inline_include:
                prefix = inline_include.group(1).strip()
                inc_path = inline_include.group(2)
                suffix = inline_include.group(3).strip()
                
                resolved = self._resolve_and_read_include(inc_path, filepath, line_num)

                if prefix:
                    output_lines.append(prefix)
                    self.source_map.append((filepath, line_num))
                if resolved:
                    for res_line in resolved.split('\n'):
                        output_lines.append(res_line)
                        self.source_map.append((filepath, line_num))
                if suffix and suffix != '}':
                    output_lines.append(suffix)
                    self.source_map.append((filepath, line_num))
                elif suffix == '}':
                    output_lines.append(suffix)
                    self.source_map.append((filepath, line_num))
                continue

            # Perform macro substitution
            processed_line = self._substitute_defines(line)
            output_lines.append(processed_line)
            self.source_map.append((filepath, line_num))

        self.include_stack.pop()
        return '\n'.join(output_lines)

    def _handle_directive(self, line: str, filepath: str, line_num: int,
                          condition_stack: list[bool]) -> Optional[str]:
        """Handle a preprocessor directive. Returns replacement text or None."""

        # #pragma once
        if line.startswith('#pragma once') or line.startswith('#pragma\tonce'):
            self.pragma_once_files.add(os.path.normpath(filepath))
            return None

        # #pragma warning (ignore)
        if line.startswith('#pragma'):
            return None

        # #define
        m = re.match(r'#define\s+(\w+)\s*(.*)', line)
        if m:
            if condition_stack and not all(condition_stack):
                return None
            name = m.group(1)
            value = m.group(2).strip()
            self.defines[name] = value
            return None

        # #undef
        m = re.match(r'#undef\s+(\w+)', line)
        if m:
            if condition_stack and not all(condition_stack):
                return None
            self.defines.pop(m.group(1), None)
            return None

        # #ifdef
        m = re.match(r'#ifdef\s+(\w+)', line)
        if m:
            symbol = m.group(1)
            condition_stack.append(symbol in self.defines)
            return None

        # #ifndef
        m = re.match(r'#ifndef\s+(\w+)', line)
        if m:
            symbol = m.group(1)
            condition_stack.append(symbol not in self.defines)
            return None

        # #else
        if line.strip() == '#else':
            if condition_stack:
                condition_stack[-1] = not condition_stack[-1]
            return None

        # #endif
        if line.strip().startswith('#endif'):
            if condition_stack:
                condition_stack.pop()
            return None

        # #if (simplified - treat as ifdef for common patterns)
        m = re.match(r'#if\s+defined\s*\(\s*(\w+)\s*\)', line)
        if m:
            symbol = m.group(1)
            condition_stack.append(symbol in self.defines)
            return None

        # #include (standalone)
        m = re.match(r'#include\s+(".*?"|<.*?>|__filename__\s*"[^"]*")', line)
        if m:
            if condition_stack and not all(condition_stack):
                return None
            inc_path = m.group(1)
            return self._resolve_and_read_include(inc_path, filepath, line_num)

        # Unknown directive - pass through as comment
        return f"/* preprocessor: {line} */"

    def _resolve_and_read_include(self, inc_path: str, filepath: str,
                                   line_num: int) -> str:
        """Resolve an include path and return preprocessed contents."""
        # Handle __filename__ ".sub" pattern
        if '__filename__' in inc_path:
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            # Extract the suffix (e.g., ".sub")
            suffix_match = re.search(r'"([^"]*)"', inc_path.replace('__filename__', ''))
            if suffix_match:
                resolved_name = base_name + suffix_match.group(1)
            else:
                resolved_name = base_name
            resolved = self.resolve_include(resolved_name, filepath)
        else:
            cleaned = inc_path.strip('"').strip('<').strip('>')
            resolved = self.resolve_include(cleaned, filepath)

        if resolved is None:
            # Non-fatal: return a comment noting the missing include
            cleaned = inc_path.strip('"').strip('<').strip('>')
            return f"/* [PREPROCESSOR] Include not found: {cleaned} */"

        resolved_norm = os.path.normpath(resolved)

        # Check pragma once
        if resolved_norm in self.pragma_once_files:
            return ""

        try:
            with open(resolved, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return self.preprocess(content, resolved)
        except Exception as e:
            return f"/* [PREPROCESSOR] Error including {resolved}: {e} */"

    def _substitute_defines(self, line: str) -> str:
        """Substitute defined macros in a line (simple text replacement)."""
        # Only do simple whole-word substitution for non-empty defines
        for name, value in self.defines.items():
            if value and name in line:
                # Only replace whole words
                line = re.sub(r'\b' + re.escape(name) + r'\b', value, line)
        return line
