#!/usr/bin/env python3
"""
MED/STP File Viewer -- Tkinter GUI Application
===============================================

A standalone desktop application for viewing decoded Hamilton .med and .stp
binary files.  This provides functionality similar to the VS Code custom
editor (``hxcfgEditorProvider.ts``) but runs independently of VS Code.

Features
--------
- **Open .med or .stp files**: Browse and open binary or text-format files.
- **Auto-detect format**: Determines if a file is binary or already text.
- **Decoded text view**: Shows decoded text content with line numbers in a
  monospace font.
- **Search**: ``Ctrl+F`` search bar with next/previous navigation and
  highlight-all.
- **Section Navigation**: Sidebar listbox showing all DataDef sections --
  clicking a section jumps to it in the text view.
- **Export to Text**: Save the decoded text to a ``.txt`` file.
- **Repair**: If the file appears CRLF-corrupted, offer to repair it.
- **File Info**: Status bar showing file path, size, format, and section
  count.
- **Step Summary**: For ``.med`` files, shows a summary of all steps
  (instance GUID, step type inferred from CLSID).
- **Recently opened files**: Remembers up to 10 recently opened files
  across sessions (stored in a JSON file next to this script).

Layout
------
::

    ┌──────────────────────────────────────────────────────────────┐
    │  Menu bar: File | View | Tools                               │
    ├─────────────┬────────────────────────────────────────────────┤
    │  Section    │                                                │
    │  navigation │        Main text view (with line numbers)      │
    │  listbox    │                                                │
    │             │                                                │
    │             │                                                │
    │             │                                                │
    ├─────────────┴────────────────────────────────────────────────┤
    │  [Search bar -- hidden by default, shown with Ctrl+F]         │
    ├──────────────────────────────────────────────────────────────┤
    │  Status bar: file info                                       │
    └──────────────────────────────────────────────────────────────┘

Usage
-----
::

    python -m standalone_med_tools.gui_med_viewer
    python -m standalone_med_tools.gui_med_viewer path/to/file.med

Or run directly::

    python standalone_med_tools/gui_med_viewer.py
    python standalone_med_tools/gui_med_viewer.py path/to/file.med
"""

from __future__ import annotations

import json
import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Resolve relative import for both ``python -m`` and direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__" and __package__ is None:
    # When executed directly (``python gui_med_viewer.py``), the package
    # context is missing.  Add the parent directory to sys.path so that the
    # sibling modules can be imported by absolute name.
    _parent = str(Path(__file__).resolve().parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from hxcfgfile_codec import (  # type: ignore[import-untyped]
        HxCfgTextModel,
        build_binary_med,
        build_text_med,
        dump_binary_structure,
        parse_binary_med,
        parse_text_med,
    )
    from repair_corrupt import (  # type: ignore[import-untyped]
        detect_corruption,
        repair_crlf_corruption,
        validate_binary,
    )
else:
    from .hxcfgfile_codec import (
        HxCfgTextModel,
        build_binary_med,
        build_text_med,
        dump_binary_structure,
        parse_binary_med,
        parse_text_med,
    )
    from .repair_corrupt import (
        detect_corruption,
        repair_crlf_corruption,
        validate_binary,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_APP_TITLE: str = "Hamilton MED/STP Viewer"
"""Window title for the application."""

_FILE_TYPES: List[Tuple[str, str]] = [
    ("Hamilton Method Files", "*.med"),
    ("Hamilton Step Files", "*.stp"),
    ("Text Files", "*.txt"),
    ("All Files", "*.*"),
]
"""File type filters for the open/save dialogs."""

_MAX_RECENT: int = 10
"""Maximum number of recently-opened files to remember."""

_RECENT_FILE: Path = Path(__file__).resolve().parent / ".gui_med_viewer_recent.json"
"""Path to the JSON file storing recently-opened file paths."""

_MONOSPACE_FONT: Tuple[str, int] = ("Consolas", 10)
"""Default monospace font for the text view (family, size)."""

_LINE_NUMBER_WIDTH: int = 6
"""Character width of the line-number gutter."""

# ---------------------------------------------------------------------------
# Well-known CLSIDs for step-type inference
# ---------------------------------------------------------------------------

# Build a reverse lookup: CLSID string (upper-cased) → step type name.
# We inline the registries here to avoid importing block_markers (which may
# not always be needed).  The dictionaries are intentionally duplicated from
# block_markers.py for self-containment.

_CLSID_TO_STEP: Dict[str, str] = {}
"""Reverse lookup from CLSID string to human-readable step type name."""

_STEP_CLSIDS: Dict[str, str] = {
    "Comment":            "{F07B0071-8EFC-11d4-A3BA-002035848439}",
    "Assignment":         "{B31F3543-5D80-11d4-A5EB-0050DA737D89}",
    "MathExpression":     "{B31F3544-5D80-11d4-A5EB-0050DA737D89}",
    "IfThenElse":         "{B31F3531-5D80-11d4-A5EB-0050DA737D89}",
    "Loop":               "{B31F3532-5D80-11d4-A5EB-0050DA737D89}",
    "Break":              "{B31F3533-5D80-11d4-A5EB-0050DA737D89}",
    "Return":             "{9EC997CD-FD3B-4280-811B-49E99DCF062C}",
    "Abort":              "{930D6C31-8EFB-11d4-A3BA-002035848439}",
    "Shell":              "{B31F3545-5D80-11d4-A5EB-0050DA737D89}",
    "FileOpen":           "{B31F3534-5D80-11d4-A5EB-0050DA737D89}",
    "FileFind":           "{B31F3535-5D80-11d4-A5EB-0050DA737D89}",
    "FileRead":           "{B31F3536-5D80-11d4-A5EB-0050DA737D89}",
    "FileWrite":          "{B31F3537-5D80-11d4-A5EB-0050DA737D89}",
    "FileClose":          "{B31F3538-5D80-11d4-A5EB-0050DA737D89}",
    "UserInput":          "{B31F3539-5D80-11d4-A5EB-0050DA737D89}",
    "UserOutput":         "{21E07B31-8D2E-11d4-A3B8-002035848439}",
    "SetCurrentSeqPos":   "{B31F353A-5D80-11d4-A5EB-0050DA737D89}",
    "GetCurrentSeqPos":   "{B31F353B-5D80-11d4-A5EB-0050DA737D89}",
    "SetTotalSeqCount":   "{B31F353C-5D80-11d4-A5EB-0050DA737D89}",
    "GetTotalSeqCount":   "{B31F353D-5D80-11d4-A5EB-0050DA737D89}",
    "AlignSequences":     "{EBC6FD39-B416-4461-BD0E-312FBC5AEF1F}",
    "StartTimer":         "{B31F353E-5D80-11d4-A5EB-0050DA737D89}",
    "WaitTimer":          "{B31F353F-5D80-11d4-A5EB-0050DA737D89}",
    "ReadElapsedTime":    "{B31F3540-5D80-11d4-A5EB-0050DA737D89}",
    "ResetTimer":         "{B31F3541-5D80-11d4-A5EB-0050DA737D89}",
    "StopTimer":          "{83FFBD43-B4F2-4ECB-BE0A-1A183AC5063D}",
    "WaitForEvent":       "{D97BA841-8303-11d4-A3AC-002035848439}",
    "SetEvent":           "{90ADC087-865A-4b6c-A658-A0F3AE1E29C4}",
    "LibraryFunction":    "{B31F3542-5D80-11d4-A5EB-0050DA737D89}",
    "SingleLibFunction":  "{C1F3C015-47B3-4514-9407-AC2E65043419}",
    "SubmethodCall":      "{7C4EF7A7-39BE-406a-897F-71F3A35B4093}",
    "ComPortOpen":        "{7AC8762F-512C-4f2c-8D1F-A86A73A6FA99}",
    "ComPortRead":        "{6B1F17F6-3E69-4bbd-A8F2-3214BFB930AA}",
    "ComPortWrite":       "{6193FE29-76EE-483b-AB12-EDDF6CB95FDD}",
    "ComPortClose":       "{EB07D635-0C14-4880-8F99-4301CB1D4E3B}",
    "ArrayDeclare":       "{4900C1F7-0FB7-4033-8253-760BDB9354DC}",
    "ArraySetAt":         "{F17B7626-27CB-47f1-8477-8C4158339A6D}",
    "ArrayGetAt":         "{67A8F1C9-6546-41e9-AD2F-3C54F7818853}",
    "ArrayGetSize":       "{72EACF88-8D49-43e3-92C8-2F90E81E3260}",
    "ArrayCopy":          "{DB5A2B39-67F2-4a78-A78F-DAF3FB056366}",
    "UserErrorHandling":  "{3293659E-F71E-472f-AFB4-6A674E32B114}",
    "ThreadBegin":        "{1A4D922E-531A-405b-BF19-FFD9AF850726}",
    "ThreadWaitFor":      "{7DA7AD24-F79A-43aa-A47C-A7F0B82CCA71}",
    "SchedulerActivity":  "{4FB3C56D-3EF5-4317-8A5B-7CDFAC1CAC8F}",
    "CustomDialog":       "{998A7CCC-4374-484D-A6ED-E8A4F0EB71BA}",
    "GroupSeparator":     "{586C3429-F931-405f-9938-928E22C90BFA}",
}

_ML_STAR_CLSIDS: Dict[str, str] = {
    "ML_STAR Initialize":       "ML_STAR:{1C0C0CB0-7C87-11D3-AD83-0004ACB1DCB2}",
    "ML_STAR LoadCarrier":      "ML_STAR:{54114402-7FA2-11D3-AD85-0004ACB1DCB2}",
    "ML_STAR UnloadCarrier":    "ML_STAR:{54114400-7FA2-11D3-AD85-0004ACB1DCB2}",
    "ML_STAR TipPickUp":        "ML_STAR:{541143FA-7FA2-11D3-AD85-0004ACB1DCB2}",
    "ML_STAR Aspirate":         "ML_STAR:{541143F5-7FA2-11D3-AD85-0004ACB1DCB2}",
    "ML_STAR Dispense":         "ML_STAR:{541143F8-7FA2-11D3-AD85-0004ACB1DCB2}",
    "ML_STAR TipEject":         "ML_STAR:{541143FC-7FA2-11D3-AD85-0004ACB1DCB2}",
    "ML_STAR MoveAutoLoad":     "ML_STAR:{EA251BFB-66DE-48D1-83E5-6884B4DD8D11}",
    "ML_STAR GetLastLiqLevel":  "ML_STAR:{9FB6DFE0-4132-4d09-B502-98C722734D4C}",
}

# Populate the reverse lookup from both registries.
for _name, _clsid in _STEP_CLSIDS.items():
    _CLSID_TO_STEP[_clsid.upper()] = _name
for _name, _clsid in _ML_STAR_CLSIDS.items():
    _CLSID_TO_STEP[_clsid.upper()] = _name


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _detect_format(data: bytes) -> str:
    """Detect the file format from the first few bytes.

    Args:
        data: Raw file bytes.

    Returns:
        ``"binary"`` for HxCfgFile v3 binary containers,
        ``"text"`` for text representations, or ``"unknown"``.
    """
    if len(data) < 4:
        return "unknown"
    version = int.from_bytes(data[0:2], "little")
    type_marker = int.from_bytes(data[2:4], "little")
    if version == 3 and type_marker == 1:
        return "binary"
    if data[:10] == b"HxCfgFile,":
        return "text"
    return "unknown"


def _format_size(size: int) -> str:
    """Return a human-readable file size string.

    Args:
        size: File size in bytes.

    Returns:
        Formatted string like ``"12,345 bytes (12.1 KB)"``.
    """
    if size < 1024:
        return f"{size:,} bytes"
    elif size < 1024 * 1024:
        return f"{size:,} bytes ({size / 1024:.1f} KB)"
    else:
        return f"{size:,} bytes ({size / (1024 * 1024):.2f} MB)"


def _extract_sections(text: str) -> List[Tuple[str, int]]:
    """Extract DataDef section names and their line numbers from decoded text.

    Looks for lines matching ``DataDef,<type>,<ver>,<name>,`` and returns
    a list of ``(display_label, line_number)`` tuples.

    Args:
        text: The decoded text content.

    Returns:
        List of ``(section_label, 1-based line number)`` tuples.
    """
    sections: List[Tuple[str, int]] = []
    pattern = re.compile(r"^DataDef,(.+),$", re.MULTILINE)
    for match in pattern.finditer(text):
        line_num = text[:match.start()].count("\n") + 1
        label = match.group(1)
        sections.append((label, line_num))
    return sections


def _extract_step_summary(text: str) -> List[Dict[str, str]]:
    """Extract a step summary from decoded .med text content.

    Scans HxPars token data for patterns that look like step entries
    containing a GUID and CLSID, and returns a list of step descriptors.

    The method file stores steps in HxPars sections.  Each step's tokens
    typically include a GUID (the instance identifier) and a CLSID (the
    step type).  We look for CLSID patterns ``{XXXXXXXX-...}`` and the
    preceding GUID token.

    Args:
        text: The decoded text content of a .med file.

    Returns:
        List of dicts with keys ``"guid"``, ``"clsid"``, ``"step_type"``,
        and ``"line"`` (1-based line number).
    """
    steps: List[Dict[str, str]] = []
    # Match CLSID patterns in quoted tokens -- look for lines containing
    # a CLSID pattern like {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
    clsid_re = re.compile(
        r'"[^"]*(\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}'
        r'-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\})[^"]*"'
    )
    # GUID pattern in Hamilton format (underscores instead of hyphens in last segment)
    guid_re = re.compile(
        r'"([0-9A-Fa-f]{8}_[0-9A-Fa-f]{4}_[0-9A-Fa-f]{4}_'
        r'[0-9A-Fa-f]{16})"'
    )

    lines = text.split("\n")
    last_guid = ""
    for line_num, line in enumerate(lines, start=1):
        # Track GUIDs encountered
        guid_match = guid_re.search(line)
        if guid_match:
            last_guid = guid_match.group(1)

        # Look for CLSIDs
        clsid_match = clsid_re.search(line)
        if clsid_match:
            raw_clsid = clsid_match.group(1)
            step_type = _CLSID_TO_STEP.get(raw_clsid.upper(), "Unknown")
            # Also check ML_STAR prefixed form
            if step_type == "Unknown":
                prefixed = f"ML_STAR:{raw_clsid}"
                step_type = _CLSID_TO_STEP.get(prefixed.upper(), "Unknown")
            if step_type != "Unknown":
                steps.append({
                    "guid": last_guid,
                    "clsid": raw_clsid,
                    "step_type": step_type,
                    "line": str(line_num),
                })

    return steps


def _load_recent() -> List[str]:
    """Load the recently-opened file list from disk.

    Returns:
        A list of file paths (most recent first), up to :data:`_MAX_RECENT`.
    """
    try:
        if _RECENT_FILE.exists():
            data = json.loads(_RECENT_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(p) for p in data[:_MAX_RECENT]]
    except Exception:
        pass
    return []


def _save_recent(paths: List[str]) -> None:
    """Persist the recently-opened file list to disk.

    Args:
        paths: List of file paths (most recent first).
    """
    try:
        _RECENT_FILE.write_text(
            json.dumps(paths[:_MAX_RECENT], indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass  # Non-critical -- silently ignore write failures.


def _add_to_recent(file_path: str, recent: List[str]) -> List[str]:
    """Add *file_path* to the front of the recent-files list.

    Removes any existing occurrence and trims to :data:`_MAX_RECENT`.

    Args:
        file_path: Absolute path of the newly opened file.
        recent:    Current list of recent paths.

    Returns:
        Updated list with *file_path* at position 0.
    """
    normalised = os.path.normpath(file_path)
    new_list = [normalised] + [
        p for p in recent if os.path.normpath(p) != normalised
    ]
    return new_list[:_MAX_RECENT]


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------


class MedViewerApp:
    """Tkinter GUI for viewing decoded Hamilton .med / .stp files.

    Attributes:
        root:           The top-level Tk window.
        current_path:   Path of the currently loaded file (or ``None``).
        current_bytes:  Raw bytes of the currently loaded file (or ``None``).
        current_text:   Decoded text of the currently loaded file (or ``""``).
        current_format: Detected format (``"binary"``, ``"text"``, ``"unknown"``).
        sections:       List of ``(label, line_number)`` for DataDef sections.
        recent_files:   List of recently opened file paths.
        word_wrap:      Whether word-wrap is currently enabled.
    """

    # ------------------------------------------------------------------
    # Initialisation and UI construction
    # ------------------------------------------------------------------

    def __init__(self, root: tk.Tk, initial_file: Optional[str] = None) -> None:
        """Initialise the application and build the UI.

        Args:
            root:         The Tk root window.
            initial_file: Optional path to a file to open on startup.
        """
        self.root: tk.Tk = root
        self.root.title(_APP_TITLE)
        self.root.geometry("1100x750")
        self.root.minsize(800, 500)

        # State
        self.current_path: Optional[str] = None
        self.current_bytes: Optional[bytes] = None
        self.current_text: str = ""
        self.current_format: str = ""
        self.current_model: Optional[HxCfgTextModel] = None
        self.sections: List[Tuple[str, int]] = []
        self.recent_files: List[str] = _load_recent()
        self.word_wrap: tk.BooleanVar = tk.BooleanVar(value=False)
        self._search_visible: bool = False
        self._search_matches: List[str] = []
        self._search_index: int = -1

        # Build UI
        self._build_menu()
        self._build_toolbar()
        self._build_main_area()
        self._build_search_bar()
        self._build_status_bar()

        # Key bindings
        self.root.bind("<Control-o>", lambda e: self._open_file())
        self.root.bind("<Control-f>", lambda e: self._toggle_search())
        self.root.bind("<Control-s>", lambda e: self._export_text())
        self.root.bind("<Escape>", lambda e: self._hide_search())
        self.root.bind("<Control-w>", lambda e: self._toggle_word_wrap())

        # Open initial file if provided
        if initial_file and os.path.isfile(initial_file):
            self.root.after(100, lambda: self._load_file(initial_file))

    def _build_menu(self) -> None:
        """Construct the menu bar with File, View, and Tools menus."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # --- File menu ---
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(
            label="Open...", accelerator="Ctrl+O", command=self._open_file
        )
        file_menu.add_command(
            label="Export to Text...", accelerator="Ctrl+S", command=self._export_text
        )
        file_menu.add_separator()

        # Recent files sub-menu
        self._recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Recent Files", menu=self._recent_menu)
        self._rebuild_recent_menu()

        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # --- View menu ---
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(
            label="Search", accelerator="Ctrl+F", command=self._toggle_search
        )
        view_menu.add_checkbutton(
            label="Word Wrap",
            variable=self.word_wrap,
            command=self._apply_word_wrap,
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="Step Summary...", command=self._show_step_summary
        )

        # --- Tools menu ---
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Repair File...", command=self._repair_file)
        tools_menu.add_command(
            label="Dump Structure...", command=self._dump_structure
        )

    def _build_toolbar(self) -> None:
        """Construct an optional toolbar frame (currently minimal)."""
        self._toolbar = ttk.Frame(self.root)
        self._toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(self._toolbar, text="Open", command=self._open_file).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        ttk.Button(self._toolbar, text="Export", command=self._export_text).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        ttk.Separator(self._toolbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=4, pady=2
        )
        ttk.Button(self._toolbar, text="Search", command=self._toggle_search).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        ttk.Button(
            self._toolbar, text="Step Summary", command=self._show_step_summary
        ).pack(side=tk.LEFT, padx=2, pady=2)

    def _build_main_area(self) -> None:
        """Construct the sidebar + text view paned layout."""
        # Main paned window: sidebar | text view
        self._paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self._paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- Left sidebar: Section navigation ---
        sidebar_frame = ttk.LabelFrame(self._paned, text="Sections")
        self._paned.add(sidebar_frame, weight=0)

        self._section_listbox = tk.Listbox(
            sidebar_frame,
            width=30,
            font=("Segoe UI", 9),
            selectmode=tk.SINGLE,
            activestyle="dotbox",
        )
        section_scrollbar = ttk.Scrollbar(
            sidebar_frame, orient=tk.VERTICAL, command=self._section_listbox.yview
        )
        self._section_listbox.config(yscrollcommand=section_scrollbar.set)
        self._section_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        section_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._section_listbox.bind("<<ListboxSelect>>", self._on_section_select)

        # --- Right main area: Line numbers + Text widget ---
        text_frame = ttk.Frame(self._paned)
        self._paned.add(text_frame, weight=1)

        # Line-number gutter
        self._line_numbers = tk.Text(
            text_frame,
            width=_LINE_NUMBER_WIDTH,
            font=_MONOSPACE_FONT,
            bg="#f0f0f0",
            fg="#888888",
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=4,
            pady=4,
            takefocus=0,
            cursor="arrow",
            borderwidth=0,
        )
        self._line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        # Main text widget
        self._text = tk.Text(
            text_frame,
            font=_MONOSPACE_FONT,
            wrap=tk.NONE,
            state=tk.DISABLED,
            undo=False,
            padx=4,
            pady=4,
            relief=tk.SUNKEN,
            borderwidth=1,
        )

        # Scrollbars
        text_vscroll = ttk.Scrollbar(
            text_frame, orient=tk.VERTICAL, command=self._on_text_vscroll
        )
        text_hscroll = ttk.Scrollbar(
            text_frame, orient=tk.HORIZONTAL, command=self._text.xview
        )
        self._text.config(
            yscrollcommand=text_vscroll.set,
            xscrollcommand=text_hscroll.set,
        )

        # Grid layout for text + scrollbars
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        text_hscroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure search highlight tag
        self._text.tag_configure(
            "search_highlight", background="#FFFF00", foreground="#000000"
        )
        self._text.tag_configure(
            "search_current", background="#FF8800", foreground="#FFFFFF"
        )

    def _build_search_bar(self) -> None:
        """Construct the search bar (hidden by default)."""
        self._search_frame = ttk.Frame(self.root)
        # Not packed yet -- shown/hidden via _toggle_search / _hide_search.

        ttk.Label(self._search_frame, text="Find:").pack(side=tk.LEFT, padx=(4, 2))

        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(
            self._search_frame, textvariable=self._search_var, width=30
        )
        self._search_entry.pack(side=tk.LEFT, padx=2)
        self._search_entry.bind("<Return>", lambda e: self._search_next())
        self._search_entry.bind("<Shift-Return>", lambda e: self._search_prev())
        self._search_var.trace_add("write", lambda *_: self._on_search_changed())

        ttk.Button(
            self._search_frame, text="< Prev", width=6, command=self._search_prev
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            self._search_frame, text="Next >", width=6, command=self._search_next
        ).pack(side=tk.LEFT, padx=2)

        self._search_case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self._search_frame, text="Case sensitive", variable=self._search_case_var,
            command=self._on_search_changed,
        ).pack(side=tk.LEFT, padx=4)

        self._search_count_label = ttk.Label(self._search_frame, text="")
        self._search_count_label.pack(side=tk.LEFT, padx=4)

        ttk.Button(
            self._search_frame, text="✕", width=3, command=self._hide_search
        ).pack(side=tk.RIGHT, padx=4)

    def _build_status_bar(self) -> None:
        """Construct the status bar at the bottom of the window."""
        self._status_frame = ttk.Frame(self.root, relief=tk.SUNKEN)
        self._status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self._status_label = ttk.Label(
            self._status_frame, text="Ready -- open a .med or .stp file",
            anchor=tk.W,
            padding=(4, 2),
        )
        self._status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._section_count_label = ttk.Label(
            self._status_frame, text="", anchor=tk.E, padding=(4, 2)
        )
        self._section_count_label.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Recent files management
    # ------------------------------------------------------------------

    def _rebuild_recent_menu(self) -> None:
        """Rebuild the Recent Files sub-menu from ``self.recent_files``."""
        self._recent_menu.delete(0, tk.END)
        if not self.recent_files:
            self._recent_menu.add_command(label="(none)", state=tk.DISABLED)
            return
        for idx, path in enumerate(self.recent_files):
            display = os.path.basename(path)
            self._recent_menu.add_command(
                label=f"{idx + 1}. {display}  --  {path}",
                command=lambda p=path: self._load_file(p),
            )
        self._recent_menu.add_separator()
        self._recent_menu.add_command(
            label="Clear Recent", command=self._clear_recent
        )

    def _clear_recent(self) -> None:
        """Clear the recently-opened files list."""
        self.recent_files.clear()
        _save_recent(self.recent_files)
        self._rebuild_recent_menu()

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        """Show the file-open dialog and load a file."""
        initial_dir = ""
        if self.current_path:
            initial_dir = os.path.dirname(self.current_path)

        file_path = filedialog.askopenfilename(
            title="Open Hamilton MED/STP File",
            filetypes=_FILE_TYPES,
            initialdir=initial_dir or None,
        )
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str) -> None:
        """Load and decode a .med / .stp file.

        Handles both binary and text-format files.  If CRLF corruption
        is detected the user is prompted to repair.

        Args:
            file_path: Absolute path to the file to load.
        """
        file_path = os.path.normpath(file_path)

        if not os.path.isfile(file_path):
            messagebox.showerror("Error", f"File not found:\n{file_path}")
            return

        try:
            raw = Path(file_path).read_bytes()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to read file:\n{exc}")
            return

        self.current_path = file_path
        self.current_bytes = raw
        self.current_format = _detect_format(raw)
        self.current_model = None

        decoded_text = ""
        model: Optional[HxCfgTextModel] = None

        if self.current_format == "binary":
            # Check for corruption first
            diag = detect_corruption(raw)
            if diag["is_corrupt"]:
                answer = messagebox.askyesno(
                    "Corruption Detected",
                    f"This file appears to be CRLF-corrupted.\n\n"
                    f"CRLF pairs: {diag['crlf_pairs']}\n"
                    f"Estimated extra bytes: {diag['estimated_extra_bytes']}\n\n"
                    f"Would you like to view the repaired version?\n"
                    f"(The original file will NOT be modified.)",
                )
                if answer:
                    try:
                        repaired = repair_crlf_corruption(raw)
                        model = parse_binary_med(repaired)
                    except Exception as exc:
                        messagebox.showerror(
                            "Repair Failed",
                            f"Could not repair and decode file:\n{exc}",
                        )
                        return
                else:
                    # Try to parse anyway -- it may fail
                    try:
                        model = parse_binary_med(raw)
                    except Exception as exc:
                        messagebox.showerror(
                            "Parse Error",
                            f"Could not decode the corrupted file:\n{exc}\n\n"
                            f"Try repairing the file first via Tools > Repair.",
                        )
                        return
            else:
                # Normal binary -- decode
                try:
                    model = parse_binary_med(raw)
                except Exception as exc:
                    messagebox.showerror(
                        "Parse Error",
                        f"Failed to decode binary file:\n{exc}",
                    )
                    return

            if model is not None:
                decoded_text = build_text_med(model)
                self.current_model = model

        elif self.current_format == "text":
            # Already text -- decode latin1 and try to parse model
            decoded_text = raw.decode("latin1")
            try:
                model = parse_text_med(decoded_text)
                self.current_model = model
            except Exception:
                # Could not parse model -- still show the raw text
                self.current_model = None

        else:
            # Unknown format -- try to display as latin1 text
            decoded_text = raw.decode("latin1")

        self.current_text = decoded_text

        # Update UI
        self._display_text(decoded_text)
        self._populate_sections(decoded_text)
        self._update_status()
        self._update_title()

        # Update recent files
        self.recent_files = _add_to_recent(file_path, self.recent_files)
        _save_recent(self.recent_files)
        self._rebuild_recent_menu()

    def _export_text(self) -> None:
        """Export the decoded text to a .txt file."""
        if not self.current_text:
            messagebox.showinfo("Export", "No text to export -- open a file first.")
            return

        # Suggest a default filename
        default_name = ""
        if self.current_path:
            base = os.path.basename(self.current_path)
            default_name = base + ".txt"

        save_path = filedialog.asksaveasfilename(
            title="Export Decoded Text",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=default_name,
        )
        if save_path:
            try:
                Path(save_path).write_text(self.current_text, encoding="latin1")
                self._set_status(f"Exported to: {save_path}")
            except Exception as exc:
                messagebox.showerror("Export Error", f"Failed to write file:\n{exc}")

    # ------------------------------------------------------------------
    # Text display
    # ------------------------------------------------------------------

    def _display_text(self, text: str) -> None:
        """Display decoded text in the text widget with line numbers.

        Args:
            text: The text content to display.
        """
        # Enable editing temporarily to insert content
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)
        self._text.config(state=tk.DISABLED)

        # Update line numbers
        self._update_line_numbers()

    def _update_line_numbers(self) -> None:
        """Regenerate the line-number gutter to match the text widget."""
        self._line_numbers.config(state=tk.NORMAL)
        self._line_numbers.delete("1.0", tk.END)

        # Count lines in the text widget
        line_count = int(self._text.index("end-1c").split(".")[0])
        line_nums = "\n".join(str(i) for i in range(1, line_count + 1))
        self._line_numbers.insert("1.0", line_nums)
        self._line_numbers.config(state=tk.DISABLED)

    def _on_text_vscroll(self, *args: str) -> None:
        """Synchronise the line-number gutter with the text vertical scroll.

        Args:
            args: Scroll command arguments forwarded from the scrollbar.
        """
        self._text.yview(*args)
        self._line_numbers.yview(*args)

    def _apply_word_wrap(self) -> None:
        """Toggle word-wrap on the text widget."""
        wrap_mode = tk.WORD if self.word_wrap.get() else tk.NONE
        self._text.config(wrap=wrap_mode)

    def _toggle_word_wrap(self) -> None:
        """Toggle the word-wrap BooleanVar and apply."""
        self.word_wrap.set(not self.word_wrap.get())
        self._apply_word_wrap()

    # ------------------------------------------------------------------
    # Section navigation
    # ------------------------------------------------------------------

    def _populate_sections(self, text: str) -> None:
        """Parse sections from text and populate the sidebar listbox.

        Args:
            text: The decoded text content.
        """
        self.sections = _extract_sections(text)
        self._section_listbox.delete(0, tk.END)
        for label, _line in self.sections:
            self._section_listbox.insert(tk.END, label)

    def _on_section_select(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        """Handle a click on a section in the sidebar listbox.

        Scrolls the text widget to the selected section's line.

        Args:
            event: The Tk event (not used directly, selection is read
                   from the listbox).
        """
        selection = self._section_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(self.sections):
            _label, line_num = self.sections[idx]
            # Scroll to the line
            self._text.see(f"{line_num}.0")
            # Highlight the line briefly
            self._text.tag_remove("section_highlight", "1.0", tk.END)
            self._text.tag_configure(
                "section_highlight", background="#E0E8FF"
            )
            self._text.tag_add(
                "section_highlight",
                f"{line_num}.0",
                f"{line_num}.end+1c",
            )
            # Also sync line numbers
            self._line_numbers.see(f"{line_num}.0")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _toggle_search(self) -> None:
        """Show or hide the search bar."""
        if self._search_visible:
            self._hide_search()
        else:
            self._show_search()

    def _show_search(self) -> None:
        """Show the search bar and focus the entry."""
        if not self._search_visible:
            self._search_frame.pack(
                side=tk.BOTTOM, fill=tk.X, before=self._status_frame
            )
            self._search_visible = True
        self._search_entry.focus_set()
        self._search_entry.select_range(0, tk.END)

    def _hide_search(self) -> None:
        """Hide the search bar and clear highlights."""
        if self._search_visible:
            self._search_frame.pack_forget()
            self._search_visible = False
        self._clear_search_highlights()
        self._search_count_label.config(text="")

    def _on_search_changed(self) -> None:
        """Called when the search text changes -- highlight all matches."""
        self._highlight_all_matches()

    def _highlight_all_matches(self) -> None:
        """Find and highlight all occurrences of the search term."""
        self._clear_search_highlights()
        self._search_matches.clear()
        self._search_index = -1

        query = self._search_var.get()
        if not query:
            self._search_count_label.config(text="")
            return

        nocase = not self._search_case_var.get()

        # Find all matches
        start_pos = "1.0"
        while True:
            pos = self._text.search(
                query, start_pos, stopindex=tk.END, nocase=nocase
            )
            if not pos:
                break
            end_pos = f"{pos}+{len(query)}c"
            self._text.tag_add("search_highlight", pos, end_pos)
            self._search_matches.append(pos)
            start_pos = end_pos

        count = len(self._search_matches)
        if count == 0:
            self._search_count_label.config(text="No matches")
        else:
            self._search_count_label.config(text=f"{count} match(es)")

    def _clear_search_highlights(self) -> None:
        """Remove all search highlight tags."""
        self._text.tag_remove("search_highlight", "1.0", tk.END)
        self._text.tag_remove("search_current", "1.0", tk.END)

    def _search_next(self) -> None:
        """Jump to the next search match."""
        if not self._search_matches:
            self._highlight_all_matches()
            if not self._search_matches:
                return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        self._go_to_match(self._search_index)

    def _search_prev(self) -> None:
        """Jump to the previous search match."""
        if not self._search_matches:
            self._highlight_all_matches()
            if not self._search_matches:
                return
        self._search_index = (self._search_index - 1) % len(self._search_matches)
        self._go_to_match(self._search_index)

    def _go_to_match(self, idx: int) -> None:
        """Scroll to and highlight the match at index *idx*.

        Args:
            idx: Index into ``self._search_matches``.
        """
        # Remove previous 'current' highlight
        self._text.tag_remove("search_current", "1.0", tk.END)

        pos = self._search_matches[idx]
        query = self._search_var.get()
        end_pos = f"{pos}+{len(query)}c"

        self._text.tag_add("search_current", pos, end_pos)
        self._text.see(pos)
        self._line_numbers.see(pos)

        self._search_count_label.config(
            text=f"{idx + 1} / {len(self._search_matches)}"
        )

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        """Update the status bar text.

        Args:
            message: The status message to display.
        """
        self._status_label.config(text=message)

    def _update_status(self) -> None:
        """Update the status bar with current file info."""
        if not self.current_path:
            self._set_status("Ready -- open a .med or .stp file")
            self._section_count_label.config(text="")
            return

        size_str = _format_size(len(self.current_bytes or b""))
        fmt = self.current_format or "unknown"
        self._set_status(f"{self.current_path}  |  {size_str}  |  Format: {fmt}")

        sec_count = len(self.sections)
        self._section_count_label.config(text=f"Sections: {sec_count}")

    def _update_title(self) -> None:
        """Update the window title with the current file name."""
        if self.current_path:
            basename = os.path.basename(self.current_path)
            self.root.title(f"{basename} -- {_APP_TITLE}")
        else:
            self.root.title(_APP_TITLE)

    # ------------------------------------------------------------------
    # Tools: Repair
    # ------------------------------------------------------------------

    def _repair_file(self) -> None:
        """Attempt to repair a CRLF-corrupted file."""
        if not self.current_bytes:
            messagebox.showinfo("Repair", "No file loaded -- open a file first.")
            return

        diag = detect_corruption(self.current_bytes)
        if not diag["is_corrupt"]:
            messagebox.showinfo(
                "Repair",
                "This file does not appear to be CRLF-corrupted.\n\n"
                f"CRLF pairs: {diag['crlf_pairs']}\n"
                f"Lone LF: {diag['lone_lf']}\n"
                f"Total LF: {diag['total_lf']}",
            )
            return

        # Ask where to save the repaired file
        default_name = ""
        if self.current_path:
            base, ext = os.path.splitext(os.path.basename(self.current_path))
            default_name = f"{base}.repaired{ext}"

        save_path = filedialog.asksaveasfilename(
            title="Save Repaired File",
            defaultextension=os.path.splitext(self.current_path or ".med")[1],
            filetypes=_FILE_TYPES,
            initialfile=default_name,
        )
        if not save_path:
            return

        try:
            repaired = repair_crlf_corruption(self.current_bytes)
            Path(save_path).write_bytes(repaired)
            messagebox.showinfo(
                "Repair Complete",
                f"Repaired file saved to:\n{save_path}\n\n"
                f"Original: {len(self.current_bytes):,} bytes\n"
                f"Repaired: {len(repaired):,} bytes\n"
                f"Removed:  {len(self.current_bytes) - len(repaired):,} bytes",
            )
            # Offer to open the repaired file
            if messagebox.askyesno("Open Repaired?", "Open the repaired file now?"):
                self._load_file(save_path)
        except Exception as exc:
            messagebox.showerror("Repair Error", f"Repair failed:\n{exc}")

    # ------------------------------------------------------------------
    # Tools: Dump Structure
    # ------------------------------------------------------------------

    def _dump_structure(self) -> None:
        """Show a structural dump of the current binary file."""
        if not self.current_bytes:
            messagebox.showinfo(
                "Dump Structure", "No file loaded -- open a file first."
            )
            return

        if self.current_format != "binary":
            messagebox.showinfo(
                "Dump Structure",
                "Structure dump is only available for binary files.\n"
                f"Current format: {self.current_format}",
            )
            return

        try:
            dump = dump_binary_structure(self.current_bytes)
        except Exception as exc:
            messagebox.showerror(
                "Dump Error", f"Failed to dump structure:\n{exc}"
            )
            return

        # Show in a new top-level window
        win = tk.Toplevel(self.root)
        win.title(f"Structure Dump -- {os.path.basename(self.current_path or '?')}")
        win.geometry("800x600")
        win.minsize(500, 300)

        text = tk.Text(
            win, font=_MONOSPACE_FONT, wrap=tk.NONE, state=tk.NORMAL
        )
        vscroll = ttk.Scrollbar(win, orient=tk.VERTICAL, command=text.yview)
        hscroll = ttk.Scrollbar(win, orient=tk.HORIZONTAL, command=text.xview)
        text.config(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)

        text.insert("1.0", dump)
        text.config(state=tk.DISABLED)

        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # View: Step Summary
    # ------------------------------------------------------------------

    def _show_step_summary(self) -> None:
        """Show a summary of steps found in the decoded .med text.

        Extracts instance GUIDs and CLSIDs, resolves step type names,
        and displays them in a table in a new window.
        """
        if not self.current_text:
            messagebox.showinfo(
                "Step Summary", "No file loaded -- open a file first."
            )
            return

        steps = _extract_step_summary(self.current_text)
        if not steps:
            messagebox.showinfo(
                "Step Summary",
                "No recognised steps found in this file.\n\n"
                "Step summary works best with .med files that contain\n"
                "HxPars sections with CLSID tokens.",
            )
            return

        # Show in a new top-level window with a Treeview
        win = tk.Toplevel(self.root)
        win.title(
            f"Step Summary -- {os.path.basename(self.current_path or '?')} "
            f"({len(steps)} steps)"
        )
        win.geometry("900x500")
        win.minsize(600, 300)

        # Info label
        ttk.Label(
            win,
            text=f"Found {len(steps)} step(s) with recognised CLSIDs",
            padding=4,
        ).pack(side=tk.TOP, fill=tk.X)

        # Treeview
        columns = ("num", "step_type", "clsid", "guid", "line")
        tree = ttk.Treeview(win, columns=columns, show="headings", height=20)
        tree.heading("num", text="#")
        tree.heading("step_type", text="Step Type")
        tree.heading("clsid", text="CLSID")
        tree.heading("guid", text="Instance GUID")
        tree.heading("line", text="Line")

        tree.column("num", width=40, anchor=tk.CENTER)
        tree.column("step_type", width=160)
        tree.column("clsid", width=310)
        tree.column("guid", width=280)
        tree.column("line", width=60, anchor=tk.CENTER)

        for idx, step in enumerate(steps, start=1):
            tree.insert(
                "",
                tk.END,
                values=(
                    idx,
                    step["step_type"],
                    step["clsid"],
                    step["guid"],
                    step["line"],
                ),
            )

        # Scrollbar
        tree_scroll = ttk.Scrollbar(win, orient=tk.VERTICAL, command=tree.yview)
        tree.config(yscrollcommand=tree_scroll.set)

        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Double-click to jump to line in main view
        def _on_tree_double_click(event: tk.Event) -> None:  # type: ignore[type-arg]
            item = tree.focus()
            if item:
                values = tree.item(item, "values")
                if values and len(values) >= 5:
                    try:
                        line_num = int(values[4])
                        self._text.see(f"{line_num}.0")
                        self._line_numbers.see(f"{line_num}.0")
                    except (ValueError, IndexError):
                        pass

        tree.bind("<Double-1>", _on_tree_double_click)

        # Summary by step type
        type_counts: Dict[str, int] = {}
        for step in steps:
            t = step["step_type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        summary_text = "  |  ".join(
            f"{name}: {count}" for name, count in sorted(type_counts.items())
        )
        ttk.Label(win, text=summary_text, padding=4, wraplength=880).pack(
            side=tk.BOTTOM, fill=tk.X
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Launch the MED/STP Viewer application.

    Accepts an optional file path as the first command-line argument.
    """
    root = tk.Tk()

    # Accept optional file path from command line
    initial_file: Optional[str] = None
    if len(sys.argv) > 1:
        candidate = sys.argv[1]
        if os.path.isfile(candidate):
            initial_file = os.path.abspath(candidate)

    _app = MedViewerApp(root, initial_file=initial_file)

    root.mainloop()


if __name__ == "__main__":
    main()
