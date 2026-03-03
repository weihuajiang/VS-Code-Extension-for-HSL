#!/usr/bin/env python3
"""
Block Marker Tester — Tkinter GUI Application
===============================================

A graphical tool for testing Hamilton HSL block marker parsing, generation,
validation, renumbering, and reconciliation.

Features:
    - Browse and load .hsl / .sub files
    - Parse block markers and display them in a structured tree view
    - Validate block markers (row numbering, GUID format, CLSID recognition,
      brace correctness, open/close balance)
    - Renumber block marker rows and show the diff
    - Reconcile block marker headers and show changes made
    - Generate demo .hsl methods with configurable step count
    - Display the full CLSID lookup table (STEP_CLSID + ML_STAR_CLSID)
    - Verify the CRC-32 checksum of the loaded file
    - Statistics panel (step count, unique GUIDs, structural sections, etc.)

Usage::

    python -m standalone_med_tools.gui_block_marker_tester

Or run directly::

    python standalone_med_tools/gui_block_marker_tester.py
"""

from __future__ import annotations

import difflib
import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Resolve relative import for both ``python -m`` and direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__" and __package__ is None:
    # When executed directly (``python gui_block_marker_tester.py``), the
    # package context is missing.  Add the parent directory to sys.path so
    # that sibling modules can be imported by absolute name.
    _parent = str(Path(__file__).resolve().parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from block_markers import (  # type: ignore[import-untyped]
        STEP_CLSID,
        ML_STAR_CLSID,
        TRIPLE_BRACE_CLSIDS,
        SINGLE_STATEMENT_CLSIDS,
        StepBlockMarker,
        StructuralBlockMarker,
        parse_block_markers,
        renumber_block_markers,
        reconcile_block_marker_headers,
        generate_hsl_method,
        has_step_block_markers,
        comment_step,
        assignment_step,
        for_loop_step,
        if_else_step,
        hamilton_guid_to_standard,
        RE_STEP_OPEN,
        RE_CLOSE,
    )
    from checksum import (  # type: ignore[import-untyped]
        verify_file_checksum,
    )
else:
    from .block_markers import (
        STEP_CLSID,
        ML_STAR_CLSID,
        TRIPLE_BRACE_CLSIDS,
        SINGLE_STATEMENT_CLSIDS,
        StepBlockMarker,
        StructuralBlockMarker,
        parse_block_markers,
        renumber_block_markers,
        reconcile_block_marker_headers,
        generate_hsl_method,
        has_step_block_markers,
        comment_step,
        assignment_step,
        for_loop_step,
        if_else_step,
        hamilton_guid_to_standard,
        RE_STEP_OPEN,
        RE_CLOSE,
    )
    from .checksum import (
        verify_file_checksum,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_APP_TITLE: str = "Hamilton HSL Block Marker Tester"
_FILE_TYPES: List[Tuple[str, str]] = [
    ("Hamilton HSL Files", "*.hsl"),
    ("Hamilton Sub Files", "*.sub"),
    ("All Files", "*.*"),
]

# GUID pattern: 8_4_4_16 hex digits with underscores
_RE_HAMILTON_GUID = re.compile(
    r'^[0-9a-f]{8}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{16}$',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Reverse CLSID lookup
# ---------------------------------------------------------------------------

def _build_clsid_name_map() -> Dict[str, str]:
    """Build a reverse lookup mapping CLSID string → human-readable name.

    Merges both :data:`STEP_CLSID` and :data:`ML_STAR_CLSID` registries.

    Returns:
        Dictionary mapping CLSID (with braces/prefix) to step type name.
    """
    name_map: Dict[str, str] = {}
    for name, clsid in STEP_CLSID.items():
        name_map[clsid] = name
    for name, clsid in ML_STAR_CLSID.items():
        name_map[clsid] = f"ML_STAR:{name}"
    return name_map


_CLSID_NAME_MAP: Dict[str, str] = _build_clsid_name_map()


def _clsid_display_name(clsid: str) -> str:
    """Return the human-readable name for a CLSID, or the raw CLSID if unknown.

    Args:
        clsid: A CLSID string (e.g. ``"{F07B0071-...}"`` or ``"ML_STAR:{...}"``).

    Returns:
        Human name like ``"Comment"`` or the raw CLSID if not found.
    """
    return _CLSID_NAME_MAP.get(clsid, clsid)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_markers(
    content: str,
    markers: List,
) -> List[Tuple[str, str, str]]:
    """Run validation checks on parsed block markers and raw content.

    Checks performed:
        1. Sequential row numbering (step markers only)
        2. Hamilton GUID format correctness
        3. CLSID recognition (known vs unknown)
        4. Brace style correctness (triple-brace vs double-brace)
        5. Open/close marker balance

    Args:
        content: Raw HSL file content.
        markers: List of parsed block markers.

    Returns:
        List of ``(level, label, message)`` tuples where *level* is one of
        ``"PASS"``, ``"FAIL"``, ``"WARN"``.
    """
    results: List[Tuple[str, str, str]] = []

    step_markers = [m for m in markers if isinstance(m, StepBlockMarker)]
    struct_markers = [m for m in markers if isinstance(m, StructuralBlockMarker)]

    # ── 1. Row numbering ──────────────────────────────────────────────
    if step_markers:
        rows = [m.row for m in step_markers]
        expected = list(range(1, len(step_markers) + 1))
        if rows == expected:
            results.append(("PASS", "Row Numbering",
                            f"Sequential 1–{len(step_markers)}"))
        else:
            gaps = [i + 1 for i, (a, b) in
                    enumerate(zip(rows, expected)) if a != b]
            gap_str = ", ".join(str(g) for g in gaps[:10])
            if len(gaps) > 10:
                gap_str += f"… ({len(gaps)} total)"
            results.append(("FAIL", "Row Numbering",
                            f"Mismatch at position(s): {gap_str}"))
    else:
        results.append(("WARN", "Row Numbering", "No step markers found"))

    # ── 2. GUID format ────────────────────────────────────────────────
    bad_guids: List[str] = []
    for m in step_markers:
        if not _RE_HAMILTON_GUID.match(m.instance_guid):
            bad_guids.append(m.instance_guid[:30])
    if bad_guids:
        results.append(("FAIL", "GUID Format",
                        f"{len(bad_guids)} invalid: {', '.join(bad_guids[:5])}"))
    else:
        guid_count = len(step_markers)
        results.append(("PASS", "GUID Format",
                        f"All {guid_count} GUIDs valid Hamilton format"))

    # ── 3. CLSID recognition ─────────────────────────────────────────
    unknown_clsids: Set[str] = set()
    for m in step_markers:
        if m.step_clsid not in _CLSID_NAME_MAP:
            unknown_clsids.add(m.step_clsid)
    if unknown_clsids:
        results.append(("WARN", "CLSID Recognition",
                        f"{len(unknown_clsids)} unknown: "
                        + ", ".join(sorted(unknown_clsids)[:3])))
    else:
        results.append(("PASS", "CLSID Recognition",
                        "All CLSIDs recognized"))

    # ── 4. Brace correctness ─────────────────────────────────────────
    brace_errors: List[str] = []
    for m in step_markers:
        should_triple = m.step_clsid in TRIPLE_BRACE_CLSIDS
        if should_triple and not m.triple_brace:
            name = _clsid_display_name(m.step_clsid)
            brace_errors.append(f"Row {m.row} ({name}): expected {{{{ got {{")
        # Note: we don't flag double-brace used where triple is expected
        # in the closing block of multi-block steps, only the opening block.
    if brace_errors:
        results.append(("WARN", "Brace Correctness",
                        f"{len(brace_errors)} issue(s): {brace_errors[0]}"))
    else:
        results.append(("PASS", "Brace Correctness",
                        "All brace styles correct"))

    # ── 5. Open/close balance ─────────────────────────────────────────
    lines = content.split('\n')
    open_count = 0
    close_count = 0
    for line in lines:
        stripped = line.strip()
        if RE_STEP_OPEN.match(stripped):
            open_count += 1
        if RE_CLOSE.match(stripped):
            close_count += 1
    if open_count == close_count:
        results.append(("PASS", "Open/Close Balance",
                        f"{open_count} opens, {close_count} closes"))
    else:
        results.append(("FAIL", "Open/Close Balance",
                        f"{open_count} opens vs {close_count} closes "
                        f"(delta: {open_count - close_count})"))

    # ── 6. Has step block markers ─────────────────────────────────────
    if has_step_block_markers(content):
        results.append(("PASS", "Step Markers Present",
                        "File contains step block markers (method file)"))
    else:
        results.append(("WARN", "Step Markers Present",
                        "No step markers — likely a library or empty file"))

    return results


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def _compute_statistics(
    content: str,
    markers: List,
) -> List[Tuple[str, str]]:
    """Compute summary statistics for the loaded file and its markers.

    Args:
        content: Raw HSL file content.
        markers: List of parsed block markers.

    Returns:
        List of ``(label, value)`` pairs for display.
    """
    step_markers = [m for m in markers if isinstance(m, StepBlockMarker)]
    struct_markers = [m for m in markers if isinstance(m, StructuralBlockMarker)]

    unique_guids: Set[str] = set()
    unique_clsids: Set[str] = set()
    triple_brace_count = 0
    for m in step_markers:
        unique_guids.add(m.instance_guid)
        unique_clsids.add(m.step_clsid)
        if m.triple_brace:
            triple_brace_count += 1

    # Section names from structural markers
    section_names: Set[str] = set()
    for m in struct_markers:
        section_names.add(m.section_name)

    inline_count = sum(1 for m in struct_markers if m.inline)

    lines = content.split('\n')
    line_count = len(lines)

    stats: List[Tuple[str, str]] = [
        ("Total Lines", str(line_count)),
        ("File Size", f"{len(content):,} chars"),
        ("Step Markers", str(len(step_markers))),
        ("Structural Markers", str(len(struct_markers))),
        ("  Inline Structural", str(inline_count)),
        ("Unique GUIDs", str(len(unique_guids))),
        ("Unique CLSIDs", str(len(unique_clsids))),
        ("Triple-Brace Steps", str(triple_brace_count)),
        ("Structural Sections", ", ".join(sorted(section_names)) or "(none)"),
    ]
    return stats


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------


class BlockMarkerTesterApp:
    """Tkinter GUI for testing Hamilton HSL block marker operations.

    This class builds the entire UI and wires up callbacks for file
    loading, parsing, validation, renumbering, reconciliation, method
    generation, CLSID display, and checksum verification.

    Attributes:
        root:            The top-level Tk window.
        current_path:    Path of the currently loaded file (or ``None``).
        current_content: Text content of the currently loaded file (or ``None``).
        parsed_markers:  List of parsed block markers from the current file.
    """

    def __init__(self, root: tk.Tk) -> None:
        """Initialise the application and build the UI.

        Args:
            root: The Tk root window.
        """
        self.root: tk.Tk = root
        self.root.title(_APP_TITLE)
        self.root.geometry("1200x780")
        self.root.minsize(900, 600)

        self.current_path: Optional[Path] = None
        self.current_content: Optional[str] = None
        self.parsed_markers: List = []

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct all widgets and lay them out.

        Layout (top to bottom):
            1. File path entry + Browse button
            2. PanedWindow — left tree view | right text area
            3. Statistics frame
            4. Button bar
            5. Status bar
        """
        # ── Top frame: file path entry + Browse button ────────────────
        top_frame = ttk.Frame(self.root, padding=6)
        top_frame.pack(fill=tk.X, side=tk.TOP)

        ttk.Label(top_frame, text="File:").pack(side=tk.LEFT)

        self._path_var = tk.StringVar()
        path_entry = ttk.Entry(top_frame, textvariable=self._path_var, width=90)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))

        ttk.Button(top_frame, text="Browse\u2026", command=self._browse_file).pack(
            side=tk.LEFT
        )

        # ── Main PanedWindow (left tree | right text) ─────────────────
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 2))

        # Left: Treeview showing parsed markers
        left_frame = ttk.LabelFrame(paned, text="Parsed Block Markers", padding=4)
        paned.add(left_frame, weight=1)

        tree_columns = ("type", "details")
        self._tree = ttk.Treeview(
            left_frame, columns=tree_columns, show="headings", selectmode="browse"
        )
        self._tree.heading("type", text="Type")
        self._tree.heading("details", text="Details")
        self._tree.column("type", width=120, minwidth=80)
        self._tree.column("details", width=350, minwidth=150)

        tree_vsb = ttk.Scrollbar(
            left_frame, orient=tk.VERTICAL, command=self._tree.yview
        )
        tree_hsb = ttk.Scrollbar(
            left_frame, orient=tk.HORIZONTAL, command=self._tree.xview
        )
        self._tree.configure(
            yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set
        )
        self._tree.grid(row=0, column=0, sticky="nsew")
        tree_vsb.grid(row=0, column=1, sticky="ns")
        tree_hsb.grid(row=1, column=0, sticky="ew")
        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)

        # Bind tree selection to show code in text area
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Right: Text area for file content / results
        right_frame = ttk.LabelFrame(paned, text="Content / Results", padding=4)
        paned.add(right_frame, weight=2)

        self._text_area = tk.Text(
            right_frame, wrap=tk.NONE, undo=True, font=("Consolas", 10),
        )
        text_vsb = ttk.Scrollbar(
            right_frame, orient=tk.VERTICAL, command=self._text_area.yview
        )
        text_hsb = ttk.Scrollbar(
            right_frame, orient=tk.HORIZONTAL, command=self._text_area.xview
        )
        self._text_area.configure(
            yscrollcommand=text_vsb.set, xscrollcommand=text_hsb.set
        )
        self._text_area.grid(row=0, column=0, sticky="nsew")
        text_vsb.grid(row=0, column=1, sticky="ns")
        text_hsb.grid(row=1, column=0, sticky="ew")
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)

        # Configure text tags for color-coded validation results
        self._text_area.tag_configure("pass", foreground="#228B22")    # green
        self._text_area.tag_configure("fail", foreground="#DC143C")    # red
        self._text_area.tag_configure("warn", foreground="#DAA520")    # goldenrod
        self._text_area.tag_configure("heading", font=("Consolas", 11, "bold"))
        self._text_area.tag_configure("info", foreground="#4169E1")    # royal blue

        # ── Statistics frame ──────────────────────────────────────────
        stats_frame = ttk.LabelFrame(self.root, text="Statistics", padding=4)
        stats_frame.pack(fill=tk.X, padx=6, pady=(0, 2))

        self._stats_text = tk.Text(
            stats_frame, height=3, wrap=tk.NONE, state=tk.DISABLED,
            font=("Consolas", 9),
        )
        stats_hsb = ttk.Scrollbar(
            stats_frame, orient=tk.HORIZONTAL, command=self._stats_text.xview
        )
        self._stats_text.configure(xscrollcommand=stats_hsb.set)
        self._stats_text.pack(fill=tk.X, expand=False)
        stats_hsb.pack(fill=tk.X)

        # ── Button bar ────────────────────────────────────────────────
        btn_frame = ttk.Frame(self.root, padding=6)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        buttons: List[Tuple[str, object]] = [
            ("Parse", self._on_parse),
            ("Validate", self._on_validate),
            ("Renumber", self._on_renumber),
            ("Reconcile", self._on_reconcile),
            ("Generate", self._on_generate),
            ("CLSIDs", self._on_show_clsids),
            ("Verify CRC", self._on_verify_crc),
        ]
        for label, command in buttons:
            ttk.Button(btn_frame, text=label, command=command).pack(
                side=tk.LEFT, padx=(0, 6)
            )

        # ── Status bar (very bottom) ─────────────────────────────────
        self._status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(
            self.root,
            textvariable=self._status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 2),
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ------------------------------------------------------------------
    # Status / text helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        """Update the status bar text.

        Args:
            message: The message to display.
        """
        self._status_var.set(message)
        self.root.update_idletasks()

    def _set_text(self, content: str) -> None:
        """Replace all content in the main text area (right panel).

        Args:
            content: The text to display.
        """
        self._text_area.delete("1.0", tk.END)
        self._text_area.insert("1.0", content)

    def _clear_text(self) -> None:
        """Clear the main text area."""
        self._text_area.delete("1.0", tk.END)

    def _append_text(self, text: str, tag: Optional[str] = None) -> None:
        """Append text to the main text area, optionally with a tag.

        Args:
            text: The text to append.
            tag:  Optional Tk text tag for formatting (e.g. ``"pass"``).
        """
        if tag:
            self._text_area.insert(tk.END, text, tag)
        else:
            self._text_area.insert(tk.END, text)

    def _update_stats(self, stats: List[Tuple[str, str]]) -> None:
        """Update the statistics panel.

        Args:
            stats: List of ``(label, value)`` pairs.
        """
        lines: List[str] = []
        for label, value in stats:
            lines.append(f"{label}: {value}")
        text = "  |  ".join(lines)

        self._stats_text.configure(state=tk.NORMAL)
        self._stats_text.delete("1.0", tk.END)
        self._stats_text.insert("1.0", text)
        self._stats_text.configure(state=tk.DISABLED)

    def _clear_stats(self) -> None:
        """Clear the statistics panel."""
        self._stats_text.configure(state=tk.NORMAL)
        self._stats_text.delete("1.0", tk.END)
        self._stats_text.configure(state=tk.DISABLED)

    def _clear_tree(self) -> None:
        """Remove all items from the tree view."""
        for item in self._tree.get_children():
            self._tree.delete(item)

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _populate_tree(self, markers: List) -> None:
        """Populate the tree view with parsed block markers.

        Step markers display row, GUID (truncated), and CLSID name.
        Structural markers display section name and qualifier.

        Args:
            markers: List of parsed :class:`StepBlockMarker` and
                     :class:`StructuralBlockMarker` objects.
        """
        self._clear_tree()
        for idx, marker in enumerate(markers):
            if isinstance(marker, StepBlockMarker):
                type_str = f"Step (row {marker.row})"
                clsid_name = _clsid_display_name(marker.step_clsid)
                brace = "{{{" if marker.triple_brace else "{{"
                guid_short = marker.instance_guid[:20] + "\u2026"
                details = (
                    f"{brace} {clsid_name}  |  "
                    f"GUID: {guid_short}  |  "
                    f"Col: {marker.column}  Sub: {marker.sublevel}  |  "
                    f"Code: {len(marker.code_lines)} line(s)"
                )
            else:
                inline_tag = " [inline]" if marker.inline else ""
                type_str = f"Structural (L{marker.block_type}){inline_tag}"
                qual = f' "{marker.qualifier}"' if marker.qualifier else ""
                details = (
                    f'"{marker.section_name}"{qual}  |  '
                    f"Code: {len(marker.code_lines)} line(s)"
                )
            self._tree.insert("", tk.END, iid=str(idx), values=(type_str, details))

    def _on_tree_select(self, _event: tk.Event) -> None:
        """Handle tree view selection — show the selected marker's code.

        When a marker is selected in the tree, its code lines are
        displayed in the right-hand text area.
        """
        selection = self._tree.selection()
        if not selection:
            return
        try:
            idx = int(selection[0])
        except (ValueError, IndexError):
            return
        if idx < 0 or idx >= len(self.parsed_markers):
            return

        marker = self.parsed_markers[idx]
        self._clear_text()

        # Header info
        if isinstance(marker, StepBlockMarker):
            clsid_name = _clsid_display_name(marker.step_clsid)
            brace = "{{{" if marker.triple_brace else "{{"
            self._append_text(f"Step Block Marker — Row {marker.row}\n", "heading")
            self._append_text(f"  Brace Style:  {brace}\n", "info")
            self._append_text(f"  Column:       {marker.column}\n", "info")
            self._append_text(f"  Sublevel:     {marker.sublevel}\n", "info")
            self._append_text(f"  CLSID:        {marker.step_clsid}\n", "info")
            self._append_text(f"  CLSID Name:   {clsid_name}\n", "info")
            self._append_text(f"  GUID:         {marker.instance_guid}\n", "info")
            try:
                std_guid = hamilton_guid_to_standard(marker.instance_guid)
                self._append_text(f"  GUID (std):   {std_guid}\n", "info")
            except Exception:
                pass
        else:
            inline_tag = " [inline]" if marker.inline else ""
            self._append_text(
                f"Structural Block Marker{inline_tag}\n", "heading"
            )
            self._append_text(f"  Level:     {marker.block_type}\n", "info")
            self._append_text(f"  Section:   {marker.section_name}\n", "info")
            self._append_text(f"  Qualifier: {marker.qualifier}\n", "info")

        # Code lines
        if marker.code_lines:
            self._append_text(f"\n{'─' * 60}\n")
            self._append_text(f"Code ({len(marker.code_lines)} lines):\n\n")
            for line in marker.code_lines:
                self._append_text(line.rstrip('\r') + "\n")
        else:
            self._append_text("\n(no code lines)\n")

    # ------------------------------------------------------------------
    # File browser
    # ------------------------------------------------------------------

    def _browse_file(self) -> None:
        """Open a file dialog and load the selected .hsl/.sub file."""
        filepath = filedialog.askopenfilename(
            title="Select a Hamilton .hsl or .sub file",
            filetypes=_FILE_TYPES,
        )
        if not filepath:
            return
        self._load_file(filepath)

    def _load_file(self, filepath: str) -> None:
        """Load a file from disk and update the UI.

        Args:
            filepath: Absolute or relative path to the file.
        """
        path = Path(filepath)
        try:
            content = path.read_text(encoding="latin1")
        except OSError as exc:
            messagebox.showerror("File Error", f"Could not read file:\n{exc}")
            return

        self.current_path = path
        self.current_content = content
        self.parsed_markers = []
        self._path_var.set(str(path))
        self._clear_tree()
        self._clear_stats()

        # Show file content in text area
        self._set_text(content)
        self._set_status(
            f"Loaded: {path.name}  "
            f"({len(content):,} chars, {len(content.splitlines()):,} lines)"
        )

    # ------------------------------------------------------------------
    # Parse callback
    # ------------------------------------------------------------------

    def _on_parse(self) -> None:
        """Parse block markers from the loaded file and populate the tree.

        Also computes and displays statistics.
        """
        if self.current_content is None:
            messagebox.showwarning("No File", "Please load a file first.")
            return

        try:
            self.parsed_markers = parse_block_markers(self.current_content)
        except Exception as exc:
            messagebox.showerror("Parse Error",
                                 f"Failed to parse block markers:\n{exc}")
            self._set_status("ERROR: parse failed.")
            return

        self._populate_tree(self.parsed_markers)

        # Show statistics
        stats = _compute_statistics(self.current_content, self.parsed_markers)
        self._update_stats(stats)

        step_count = sum(
            1 for m in self.parsed_markers if isinstance(m, StepBlockMarker)
        )
        struct_count = sum(
            1 for m in self.parsed_markers if isinstance(m, StructuralBlockMarker)
        )
        self._set_text(self.current_content)
        self._set_status(
            f"Parsed: {len(self.parsed_markers)} markers "
            f"({step_count} step, {struct_count} structural)"
        )

    # ------------------------------------------------------------------
    # Validate callback
    # ------------------------------------------------------------------

    def _on_validate(self) -> None:
        """Run validation checks and display color-coded results.

        Results are shown in the right text area with green (PASS),
        red (FAIL), or yellow (WARN) highlighting.
        """
        if self.current_content is None:
            messagebox.showwarning("No File", "Please load a file first.")
            return

        # Ensure markers are parsed
        if not self.parsed_markers:
            try:
                self.parsed_markers = parse_block_markers(self.current_content)
                self._populate_tree(self.parsed_markers)
            except Exception as exc:
                messagebox.showerror("Parse Error",
                                     f"Failed to parse:\n{exc}")
                return

        results = _validate_markers(self.current_content, self.parsed_markers)

        self._clear_text()
        self._append_text("Block Marker Validation Results\n", "heading")
        self._append_text("=" * 60 + "\n\n")

        pass_count = 0
        fail_count = 0
        warn_count = 0

        for level, label, message in results:
            tag = level.lower()
            icon = {"PASS": "\u2714", "FAIL": "\u2718", "WARN": "\u26A0"}.get(
                level, " "
            )
            self._append_text(f"  {icon} [{level}] ", tag)
            self._append_text(f"{label}: {message}\n", tag)
            if level == "PASS":
                pass_count += 1
            elif level == "FAIL":
                fail_count += 1
            else:
                warn_count += 1

        self._append_text(f"\n{'─' * 60}\n")
        summary = f"Summary: {pass_count} passed, {fail_count} failed, {warn_count} warnings"
        self._append_text(summary + "\n")
        self._set_status(summary)

    # ------------------------------------------------------------------
    # Renumber callback
    # ------------------------------------------------------------------

    def _on_renumber(self) -> None:
        """Renumber block marker rows and display the diff.

        Shows a unified diff between the original and renumbered content
        in the right text area.
        """
        if self.current_content is None:
            messagebox.showwarning("No File", "Please load a file first.")
            return

        try:
            renumbered = renumber_block_markers(self.current_content)
        except Exception as exc:
            messagebox.showerror("Renumber Error",
                                 f"Renumbering failed:\n{exc}")
            return

        if renumbered == self.current_content:
            self._clear_text()
            self._append_text("Renumber Result\n", "heading")
            self._append_text("=" * 60 + "\n\n")
            self._append_text("No changes — rows are already sequential.\n", "pass")
            self._set_status("Renumber: no changes needed.")
            return

        # Generate unified diff
        orig_lines = self.current_content.splitlines(keepends=True)
        new_lines = renumbered.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines, new_lines,
            fromfile="original", tofile="renumbered", lineterm=""
        )
        diff_text = "\n".join(diff)

        self._clear_text()
        self._append_text("Renumber Diff\n", "heading")
        self._append_text("=" * 60 + "\n\n")

        # Color-code the diff
        for line in diff_text.split("\n"):
            if line.startswith("---") or line.startswith("+++"):
                self._append_text(line + "\n", "info")
            elif line.startswith("-"):
                self._append_text(line + "\n", "fail")
            elif line.startswith("+"):
                self._append_text(line + "\n", "pass")
            elif line.startswith("@@"):
                self._append_text(line + "\n", "warn")
            else:
                self._append_text(line + "\n")

        changed_count = sum(1 for l in diff_text.split("\n")
                            if l.startswith("+") and not l.startswith("+++"))
        self._set_status(f"Renumber: {changed_count} line(s) changed.")

    # ------------------------------------------------------------------
    # Reconcile callback
    # ------------------------------------------------------------------

    def _on_reconcile(self) -> None:
        """Run reconcileBlockMarkerHeaders and display changes.

        Shows a unified diff between original and reconciled content.
        The reconciled content is also renumbered.
        """
        if self.current_content is None:
            messagebox.showwarning("No File", "Please load a file first.")
            return

        try:
            reconciled = reconcile_block_marker_headers(self.current_content)
        except Exception as exc:
            messagebox.showerror("Reconcile Error",
                                 f"Reconciliation failed:\n{exc}")
            return

        if reconciled is self.current_content:
            self._clear_text()
            self._append_text("Reconcile Result\n", "heading")
            self._append_text("=" * 60 + "\n\n")
            self._append_text(
                "No changes — block markers are already correct.\n", "pass"
            )
            self._set_status("Reconcile: no changes needed.")
            return

        # Also renumber after reconciliation
        try:
            reconciled = renumber_block_markers(reconciled)
        except Exception:
            pass  # If renumbering fails, show reconciled output as-is

        # Generate diff
        orig_lines = self.current_content.splitlines(keepends=True)
        new_lines = reconciled.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines, new_lines,
            fromfile="original", tofile="reconciled", lineterm=""
        )
        diff_text = "\n".join(diff)

        self._clear_text()
        self._append_text("Reconcile Diff (with renumbering)\n", "heading")
        self._append_text("=" * 60 + "\n\n")

        if not diff_text.strip():
            self._append_text(
                "Content differs (object identity) but text is identical.\n",
                "warn",
            )
        else:
            for line in diff_text.split("\n"):
                if line.startswith("---") or line.startswith("+++"):
                    self._append_text(line + "\n", "info")
                elif line.startswith("-"):
                    self._append_text(line + "\n", "fail")
                elif line.startswith("+"):
                    self._append_text(line + "\n", "pass")
                elif line.startswith("@@"):
                    self._append_text(line + "\n", "warn")
                else:
                    self._append_text(line + "\n")

        changed_count = sum(1 for l in diff_text.split("\n")
                            if l.startswith("+") and not l.startswith("+++"))
        self._set_status(f"Reconcile: {changed_count} line(s) added/changed.")

    # ------------------------------------------------------------------
    # Generate callback
    # ------------------------------------------------------------------

    def _on_generate(self) -> None:
        """Generate a demo HSL method and display the content.

        Prompts the user for the number of steps, then generates a
        demo method with a mix of step types, showing the result in
        the text area and populating the tree.
        """
        # Prompt for step count
        step_count_str = simpledialog.askstring(
            "Generate Demo Method",
            "Number of steps (1–100):",
            initialvalue="5",
            parent=self.root,
        )
        if not step_count_str:
            return
        try:
            step_count = int(step_count_str)
            step_count = max(1, min(step_count, 100))
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a number 1–100.")
            return

        # Build a mix of step types for the demo
        steps = []
        for i in range(step_count):
            remainder = i % 5
            if remainder == 0:
                steps.append(comment_step(f"Demo step {i + 1}"))
            elif remainder == 1:
                steps.append(assignment_step(f"var{i + 1}", str(i * 10)))
            elif remainder == 2:
                steps.append(for_loop_step(f"counter{i + 1}", 3, [
                    comment_step(f"Inside loop at step {i + 1}"),
                ]))
            elif remainder == 3:
                steps.append(if_else_step(f"var{i} > 0", [
                    comment_step(f"Condition true at step {i + 1}"),
                ], [
                    comment_step(f"Condition false at step {i + 1}"),
                ]))
            else:
                steps.append(comment_step(f"Final comment step {i + 1}"))

        try:
            hsl_content, sub_content, generated_info = generate_hsl_method(
                steps=steps, author="BlockMarkerTester"
            )
        except Exception as exc:
            messagebox.showerror("Generation Error",
                                 f"Method generation failed:\n{exc}")
            return

        # Update internal state with generated content
        self.current_content = hsl_content
        self.current_path = None
        self._path_var.set("(generated)")

        # Parse and populate
        self.parsed_markers = parse_block_markers(hsl_content)
        self._populate_tree(self.parsed_markers)
        stats = _compute_statistics(hsl_content, self.parsed_markers)
        self._update_stats(stats)

        # Show generated content
        self._clear_text()
        self._append_text("Generated HSL Method\n", "heading")
        self._append_text("=" * 60 + "\n\n")
        self._append_text(
            f"Generated {step_count} step(s) → "
            f"{len(generated_info)} block marker(s)\n\n", "info"
        )
        self._append_text("─── .hsl content ───\n\n")
        self._append_text(hsl_content)
        self._append_text("\n\n─── .sub content ───\n\n")
        self._append_text(sub_content)

        self._set_status(
            f"Generated: {step_count} step(s), "
            f"{len(self.parsed_markers)} markers, "
            f"{len(hsl_content):,} chars"
        )

    # ------------------------------------------------------------------
    # CLSID registry callback
    # ------------------------------------------------------------------

    def _on_show_clsids(self) -> None:
        """Display the full CLSID lookup table in the text area.

        Shows both STEP_CLSID and ML_STAR_CLSID registries, with
        brace style and membership in TRIPLE_BRACE_CLSIDS and
        SINGLE_STATEMENT_CLSIDS sets noted.
        """
        self._clear_text()
        self._append_text("Hamilton HSL CLSID Registry\n", "heading")
        self._append_text("=" * 80 + "\n\n")

        # General step CLSIDs
        self._append_text("General Step CLSIDs\n", "heading")
        self._append_text("-" * 80 + "\n")
        self._append_text(
            f"{'Name':<25} {'CLSID':<48} {'Braces':>6} {'Single':>6}\n"
        )
        self._append_text("-" * 80 + "\n")

        for name, clsid in STEP_CLSID.items():
            brace = "{{{"  if clsid in TRIPLE_BRACE_CLSIDS else " {{"
            single = "  Yes" if clsid in SINGLE_STATEMENT_CLSIDS else "    -"
            self._append_text(f"{name:<25} {clsid:<48} {brace:>6} {single:>6}\n")

        self._append_text(f"\n  Total: {len(STEP_CLSID)} entries\n\n")

        # ML_STAR CLSIDs
        self._append_text("ML_STAR Device-Specific CLSIDs\n", "heading")
        self._append_text("-" * 80 + "\n")
        self._append_text(f"{'Name':<25} {'CLSID':<55}\n")
        self._append_text("-" * 80 + "\n")

        for name, clsid in ML_STAR_CLSID.items():
            self._append_text(f"{name:<25} {clsid:<55}\n")

        self._append_text(f"\n  Total: {len(ML_STAR_CLSID)} entries\n")
        self._append_text(
            f"  Combined: {len(STEP_CLSID) + len(ML_STAR_CLSID)} CLSIDs\n"
        )

        self._set_status(
            f"CLSID Registry: {len(STEP_CLSID)} general + "
            f"{len(ML_STAR_CLSID)} ML_STAR = "
            f"{len(STEP_CLSID) + len(ML_STAR_CLSID)} total"
        )

    # ------------------------------------------------------------------
    # Checksum verification callback
    # ------------------------------------------------------------------

    def _on_verify_crc(self) -> None:
        """Verify the CRC-32 checksum of the loaded file.

        Uses :func:`verify_file_checksum` from the checksum module and
        displays color-coded results.
        """
        if self.current_path is None:
            messagebox.showwarning(
                "No File",
                "Checksum verification requires a file on disk.\n"
                "Load a .hsl or .sub file first.",
            )
            return

        try:
            result = verify_file_checksum(str(self.current_path))
        except Exception as exc:
            messagebox.showerror("Checksum Error",
                                 f"Verification failed:\n{exc}")
            return

        self._clear_text()
        self._append_text("CRC-32 Checksum Verification\n", "heading")
        self._append_text("=" * 60 + "\n\n")
        self._append_text(f"  File:     {self.current_path.name}\n", "info")
        self._append_text(f"  Author:   {result['author']}\n", "info")
        self._append_text(f"  Time:     {result['time']}\n", "info")
        self._append_text(f"  Stored:   {result['stored_checksum']}\n", "info")
        self._append_text(f"  Computed: {result['computed_checksum']}\n", "info")
        self._append_text("\n")

        if result.get("error"):
            self._append_text(
                f"  \u2718 ERROR: {result['error']}\n", "fail"
            )
            self._set_status(f"CRC: ERROR — {result['error']}")
        elif result["valid"]:
            self._append_text(
                "  \u2714 VALID — Checksum matches.\n", "pass"
            )
            self._set_status(
                f"CRC: VALID ({result['stored_checksum']})"
            )
        else:
            self._append_text(
                "  \u2718 MISMATCH — Stored and computed checksums differ.\n",
                "fail",
            )
            self._set_status(
                f"CRC: MISMATCH (stored={result['stored_checksum']}, "
                f"computed={result['computed_checksum']})"
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Create the Tk root window, instantiate the app, and enter the mainloop."""
    root = tk.Tk()
    _app = BlockMarkerTesterApp(root)  # noqa: F841 — reference kept by Tk
    root.mainloop()


if __name__ == "__main__":
    main()
