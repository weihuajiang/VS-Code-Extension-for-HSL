"""
Hamilton MED Tools -- Standalone Python Package

This package provides standalone Python tools for working with Hamilton
.med (Method Editor Data) and .stp (Step Parameters) binary files,
HSL block markers, CRC-32 checksums, and .hsl/.sub method file generation.

These tools were extracted from the HSL VS Code Extension to provide
independent, portable functionality without any VS Code dependency.

Modules:
    hxcfgfile_codec   -- Binary ↔ text codec for HxCfgFile v3 containers
    checksum          -- CRC-32 checksum computation for Hamilton files
    block_markers     -- Block marker parsing, generation, and validation
    med_generator     -- .med text builder from .hsl block marker data
    stp_generator     -- .stp file generation for device step parameters
    repair_corrupt    -- Repair tool for CRLF-corrupted binary files

GUI Apps:
    gui_codec_tester        -- Tkinter app for binary ↔ text conversion testing
    gui_block_marker_tester -- Tkinter app for block marker parsing/viewing
    gui_med_viewer          -- Tkinter app for viewing decoded .med/.stp files

Requirements: Python 3.8+ (no external dependencies)
"""

__version__ = "1.0.0"
__author__ = "HSL Extension Team"
