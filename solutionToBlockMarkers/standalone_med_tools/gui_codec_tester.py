#!/usr/bin/env python3
"""
HxCfgFile v3 Codec Tester -- Tkinter GUI Application
=====================================================

A graphical tool for testing the HxCfgFile v3 binary ↔ text conversion codec
used by Hamilton .med and .stp instrument method files.

Features:
    - Browse and load binary .med / .stp files
    - Convert binary → text and display the result
    - Edit text and convert back to binary, saving to disk
    - Roundtrip verification (binary → text → binary) with byte comparison
    - Batch roundtrip testing across an entire folder
    - Structural dump of the binary container format
    - File info panel with size, hex preview, and format detection
    - Status bar for operation feedback

Usage::

    python -m standalone_med_tools.gui_codec_tester

Or run directly::

    python standalone_med_tools/gui_codec_tester.py
"""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Resolve relative import for both ``python -m`` and direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__" and __package__ is None:
    # When executed directly (``python gui_codec_tester.py``), the package
    # context is missing.  Add the parent directory to sys.path so that the
    # sibling module can be imported by absolute name.
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
        roundtrip_verify,
    )
else:
    from .hxcfgfile_codec import (
        HxCfgTextModel,
        build_binary_med,
        build_text_med,
        dump_binary_structure,
        parse_binary_med,
        parse_text_med,
        roundtrip_verify,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_APP_TITLE: str = "HxCfgFile v3 Codec Tester"
_FILE_TYPES: List[Tuple[str, str]] = [
    ("Hamilton Method Files", "*.med"),
    ("Hamilton Step Files", "*.stp"),
    ("All Files", "*.*"),
]
_HEX_PREVIEW_BYTES: int = 64
"""Number of leading bytes to show in the hex dump preview."""


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _format_hex_preview(data: bytes, max_bytes: int = _HEX_PREVIEW_BYTES) -> str:
    """Return a formatted hex dump of the first *max_bytes* of *data*.

    Each line contains 16 bytes shown as space-separated hex pairs,
    followed by the printable ASCII representation.

    Args:
        data:      Raw bytes to format.
        max_bytes: Maximum number of bytes to include.

    Returns:
        A multi-line hex dump string.
    """
    snippet = data[:max_bytes]
    lines: List[str] = []
    for offset in range(0, len(snippet), 16):
        chunk = snippet[offset : offset + 16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
        lines.append(f"  {offset:04X}  {hex_part:<48s}  {ascii_part}")
    if len(data) > max_bytes:
        lines.append(f"  ... ({len(data) - max_bytes:,} more bytes)")
    return "\n".join(lines)


def _detect_format(data: bytes) -> str:
    """Detect the file format from the first few bytes.

    Args:
        data: Raw file bytes.

    Returns:
        A human-readable description of the detected format.
    """
    if len(data) < 4:
        return "Too small to identify"
    version = int.from_bytes(data[0:2], "little")
    type_marker = int.from_bytes(data[2:4], "little")
    if version == 3 and type_marker == 1:
        return "HxCfgFile v3 binary container"
    if data[:10] == b"HxCfgFile,":
        return "HxCfgFile text representation"
    return f"Unknown (first bytes: {data[:4].hex()})"


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------


class CodecTesterApp:
    """Tkinter GUI for testing the HxCfgFile v3 binary ↔ text codec.

    This class builds the entire UI and wires up callbacks for file
    selection, conversion, roundtrip testing, batch testing, and
    structural dumping.

    Attributes:
        root:          The top-level Tk window.
        current_path:  Path of the currently loaded file (or ``None``).
        current_bytes: Raw bytes of the currently loaded file (or ``None``).
    """

    def __init__(self, root: tk.Tk) -> None:
        """Initialise the application and build the UI.

        Args:
            root: The Tk root window.
        """
        self.root: tk.Tk = root
        self.root.title(_APP_TITLE)
        self.root.geometry("1000x720")
        self.root.minsize(700, 480)

        self.current_path: Optional[Path] = None
        self.current_bytes: Optional[bytes] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct all widgets and lay them out."""

        # ── Top frame: file path entry + Browse button ────────────────
        top_frame = ttk.Frame(self.root, padding=6)
        top_frame.pack(fill=tk.X, side=tk.TOP)

        ttk.Label(top_frame, text="File:").pack(side=tk.LEFT)

        self._path_var = tk.StringVar()
        path_entry = ttk.Entry(top_frame, textvariable=self._path_var, width=80)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))

        ttk.Button(top_frame, text="Browse…", command=self._browse_file).pack(
            side=tk.LEFT
        )

        # ── File info frame ───────────────────────────────────────────
        info_frame = ttk.LabelFrame(self.root, text="File Info", padding=6)
        info_frame.pack(fill=tk.X, padx=6, pady=(0, 4))

        self._info_text = tk.Text(
            info_frame, height=5, wrap=tk.NONE, state=tk.DISABLED,
            font=("Consolas", 9),
        )
        info_scroll_x = ttk.Scrollbar(
            info_frame, orient=tk.HORIZONTAL, command=self._info_text.xview
        )
        self._info_text.configure(xscrollcommand=info_scroll_x.set)
        self._info_text.pack(fill=tk.X, expand=False)
        info_scroll_x.pack(fill=tk.X)

        # ── Middle frame: large scrollable text area ──────────────────
        mid_frame = ttk.Frame(self.root, padding=6)
        mid_frame.pack(fill=tk.BOTH, expand=True)

        self._text_area = tk.Text(
            mid_frame, wrap=tk.NONE, undo=True,
            font=("Consolas", 10),
        )
        scroll_y = ttk.Scrollbar(
            mid_frame, orient=tk.VERTICAL, command=self._text_area.yview
        )
        scroll_x = ttk.Scrollbar(
            mid_frame, orient=tk.HORIZONTAL, command=self._text_area.xview
        )
        self._text_area.configure(
            yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set
        )
        self._text_area.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        mid_frame.rowconfigure(0, weight=1)
        mid_frame.columnconfigure(0, weight=1)

        # ── Button row ────────────────────────────────────────────────
        btn_frame = ttk.Frame(self.root, padding=6)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, before=mid_frame)

        buttons = [
            ("To Text", self._on_to_text),
            ("To Binary", self._on_to_binary),
            ("Roundtrip", self._on_roundtrip),
            ("Batch Roundtrip", self._on_batch_roundtrip),
            ("Dump Structure", self._on_dump_structure),
        ]
        for label, command in buttons:
            ttk.Button(btn_frame, text=label, command=command).pack(
                side=tk.LEFT, padx=(0, 6)
            )

        # ── Status bar ────────────────────────────────────────────────
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
    # Status helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        """Update the status bar text.

        Args:
            message: The message to display.
        """
        self._status_var.set(message)
        self.root.update_idletasks()

    def _set_text(self, content: str) -> None:
        """Replace all content in the main text area.

        Args:
            content: The text to display.
        """
        self._text_area.delete("1.0", tk.END)
        self._text_area.insert("1.0", content)

    def _get_text(self) -> str:
        """Return the current content of the main text area.

        Returns:
            The text area content (without a trailing newline added by Tk).
        """
        return self._text_area.get("1.0", tk.END).rstrip("\n")

    # ------------------------------------------------------------------
    # File info panel
    # ------------------------------------------------------------------

    def _update_file_info(self, path: Path, data: bytes) -> None:
        """Populate the file info panel with metadata about *data*.

        Shows file size, detected format, and a hex preview of the
        leading bytes.

        Args:
            path: The file path (used for display).
            data: The raw file bytes.
        """
        fmt = _detect_format(data)
        info_lines = [
            f"Path:   {path}",
            f"Size:   {len(data):,} bytes  ({len(data):#x})",
            f"Format: {fmt}",
            "",
            "Hex preview:",
            _format_hex_preview(data),
        ]
        info_str = "\n".join(info_lines)

        self._info_text.configure(state=tk.NORMAL)
        self._info_text.delete("1.0", tk.END)
        self._info_text.insert("1.0", info_str)
        self._info_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # File browser
    # ------------------------------------------------------------------

    def _browse_file(self) -> None:
        """Open a file dialog and load the selected .med/.stp file."""
        filepath = filedialog.askopenfilename(
            title="Select a Hamilton .med or .stp file",
            filetypes=_FILE_TYPES,
        )
        if not filepath:
            return

        path = Path(filepath)
        try:
            data = path.read_bytes()
        except OSError as exc:
            messagebox.showerror("File Error", f"Could not read file:\n{exc}")
            return

        self.current_path = path
        self.current_bytes = data
        self._path_var.set(str(path))
        self._update_file_info(path, data)
        self._set_status(f"Loaded: {path.name}  ({len(data):,} bytes)")

    # ------------------------------------------------------------------
    # Conversion callbacks
    # ------------------------------------------------------------------

    def _on_to_text(self) -> None:
        """Convert the loaded binary file to text and display it.

        The binary file bytes are parsed into an ``HxCfgTextModel`` and
        then rendered as the human-readable text format.  The result is
        shown in the main text area.
        """
        if self.current_bytes is None:
            messagebox.showwarning("No File", "Please load a file first.")
            return

        try:
            model: HxCfgTextModel = parse_binary_med(self.current_bytes)
            text: str = build_text_med(model)
        except Exception as exc:
            messagebox.showerror("Conversion Error", f"Binary → text failed:\n{exc}")
            self._set_status("ERROR: binary → text conversion failed.")
            return

        self._set_text(text)
        self._set_status(
            f"Converted to text: {len(text):,} chars  "
            f"({len(model.hxpars_sections)} HxPars sections, "
            f"{sum(len(s.tokens) for s in model.hxpars_sections):,} tokens)"
        )

    def _on_to_binary(self) -> None:
        """Convert the text in the text area to binary and save to a file.

        The user is prompted for a save location.  The text is parsed
        back into an ``HxCfgTextModel`` and then encoded as the binary
        HxCfgFile v3 container.
        """
        text = self._get_text()
        if not text.strip():
            messagebox.showwarning("Empty Text", "The text area is empty.")
            return

        # Suggest a default filename
        default_name = ""
        if self.current_path:
            stem = self.current_path.stem
            suffix = self.current_path.suffix  # .med or .stp
            default_name = f"{stem}_rebuilt{suffix}"

        save_path = filedialog.asksaveasfilename(
            title="Save binary file",
            initialfile=default_name,
            defaultextension=".med",
            filetypes=_FILE_TYPES,
        )
        if not save_path:
            return

        try:
            model: HxCfgTextModel = parse_text_med(text)
            binary_data: bytes = build_binary_med(model)
        except Exception as exc:
            messagebox.showerror("Conversion Error", f"Text → binary failed:\n{exc}")
            self._set_status("ERROR: text → binary conversion failed.")
            return

        try:
            Path(save_path).write_bytes(binary_data)
        except OSError as exc:
            messagebox.showerror("Save Error", f"Could not write file:\n{exc}")
            return

        self._set_status(
            f"Saved binary: {Path(save_path).name}  ({len(binary_data):,} bytes)"
        )

    def _on_roundtrip(self) -> None:
        """Run a roundtrip test on the loaded binary file.

        Performs binary → text → binary conversion and compares the
        rebuilt bytes with the original.  Reports PASS or FAIL with
        size information.
        """
        if self.current_path is None or self.current_bytes is None:
            messagebox.showwarning("No File", "Please load a file first.")
            return

        try:
            success, message = roundtrip_verify(self.current_path)
        except Exception as exc:
            messagebox.showerror("Roundtrip Error", f"Roundtrip failed:\n{exc}")
            self._set_status("ERROR: roundtrip test failed.")
            return

        self._set_text(message)

        if success:
            self._set_status(f"ROUNDTRIP PASS -- {self.current_path.name}")
        else:
            self._set_status(f"ROUNDTRIP FAIL -- {self.current_path.name}")

    def _on_batch_roundtrip(self) -> None:
        """Run roundtrip tests on all .med and .stp files in a folder.

        The user selects a folder.  Every matching file is tested in a
        background thread, and results are displayed in the text area
        as they arrive.  A summary line is appended at the end.
        """
        folder = filedialog.askdirectory(title="Select folder for batch roundtrip")
        if not folder:
            return

        folder_path = Path(folder)
        files: List[Path] = sorted(
            p
            for p in folder_path.rglob("*")
            if p.suffix.lower() in (".med", ".stp") and p.is_file()
        )

        if not files:
            messagebox.showinfo(
                "No Files", "No .med or .stp files found in the selected folder."
            )
            return

        self._set_text("")
        self._set_status(f"Batch roundtrip: 0 / {len(files)} …")

        # Run in a background thread to keep the UI responsive.
        thread = threading.Thread(
            target=self._batch_worker,
            args=(files,),
            daemon=True,
        )
        thread.start()

    def _batch_worker(self, files: List[Path]) -> None:
        """Background worker for batch roundtrip testing.

        Results are posted to the UI via ``root.after()`` to ensure
        thread safety.

        Args:
            files: List of binary file paths to test.
        """
        total = len(files)
        passed = 0
        failed = 0
        errors = 0

        header = (
            f"{'#':<5} {'Result':<8} {'Size':>12}  {'File'}\n"
            f"{'-' * 5} {'-' * 8} {'-' * 12}  {'-' * 40}\n"
        )
        self.root.after(0, self._append_text, header)

        for idx, file_path in enumerate(files, start=1):
            try:
                success, message = roundtrip_verify(file_path)
                size = file_path.stat().st_size
                if success:
                    result_str = "PASS"
                    passed += 1
                else:
                    result_str = "FAIL"
                    failed += 1
            except Exception as exc:
                result_str = "ERROR"
                size = 0
                errors += 1
                message = str(exc)

            line = f"{idx:<5} {result_str:<8} {size:>12,}  {file_path.name}\n"
            status = f"Batch roundtrip: {idx} / {total} …"
            self.root.after(0, self._append_text, line)
            self.root.after(0, self._set_status, status)

        # Summary
        summary = (
            f"\n{'=' * 60}\n"
            f"Batch roundtrip complete: {total} files tested\n"
            f"  PASS:  {passed}\n"
            f"  FAIL:  {failed}\n"
            f"  ERROR: {errors}\n"
        )
        final_status = (
            f"Batch complete -- {passed} passed, {failed} failed, {errors} errors"
        )
        self.root.after(0, self._append_text, summary)
        self.root.after(0, self._set_status, final_status)

    def _append_text(self, text: str) -> None:
        """Append text to the main text area and auto-scroll to the end.

        This method is safe to call from ``root.after()`` in a background
        thread context.

        Args:
            text: The text to append.
        """
        self._text_area.insert(tk.END, text)
        self._text_area.see(tk.END)

    # ------------------------------------------------------------------
    # Structure dump
    # ------------------------------------------------------------------

    def _on_dump_structure(self) -> None:
        """Display the parsed binary structure of the loaded file.

        Calls ``dump_binary_structure()`` from the codec module and
        shows the result in the main text area.
        """
        if self.current_bytes is None:
            messagebox.showwarning("No File", "Please load a file first.")
            return

        try:
            dump: str = dump_binary_structure(self.current_bytes)
        except Exception as exc:
            messagebox.showerror("Dump Error", f"Structure dump failed:\n{exc}")
            self._set_status("ERROR: structure dump failed.")
            return

        self._set_text(dump)
        self._set_status(f"Structure dump: {self.current_path.name if self.current_path else '(unknown)'}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Create the Tk root window, instantiate the app, and enter the mainloop."""
    root = tk.Tk()
    _app = CodecTesterApp(root)  # noqa: F841 -- reference kept by Tk
    root.mainloop()


if __name__ == "__main__":
    main()
