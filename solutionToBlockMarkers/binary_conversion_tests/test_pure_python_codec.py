#!/usr/bin/env python3
"""Validation tests for pure-Python HxCfgFile codec.

Performs full pure-Python roundtrip checks:
    binary -> text -> binary -> text
and validates text invariance.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOLUTION_ROOT = ROOT.parent
sys.path.insert(0, str(SOLUTION_ROOT))

from hxcfgfile_codec import binary_to_text_file, text_to_binary_file

CASES = [
    "Visual_NTR_library_demo",
    "Global_Answer_Key_CH07",
    "Global_Example_Scheduled_Method_v01",
]


def run() -> int:
    results = []

    for case in CASES:
        case_dir = ROOT / case
        original_bin = case_dir / f"{case}.original.med"
        py_text = case_dir / f"{case}.pycodec_text.med"
        py_bin = case_dir / f"{case}.pycodec_roundtrip.med"
        py_text_2 = case_dir / f"{case}.pycodec_roundtrip_text.med"

        binary_to_text_file(original_bin, py_text)

        text_to_binary_file(py_text, py_bin)
        binary_to_text_file(py_bin, py_text_2)
        original_text = py_text.read_text(encoding="latin1")
        roundtrip_text = py_text_2.read_text(encoding="latin1")
        roundtrip_text_equal = original_text == roundtrip_text

        results.append(
            {
                "case": case,
                "pure_python_roundtrip_text_equal": roundtrip_text_equal,
                "text_size": len(original_text),
                "original_binary_size": original_bin.stat().st_size,
                "pycodec_binary_size": py_bin.stat().st_size,
            }
        )

    out_path = ROOT / "pure_python_codec_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(out_path)
    print(json.dumps(results, indent=2))

    failed = [r for r in results if not r["pure_python_roundtrip_text_equal"]]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
