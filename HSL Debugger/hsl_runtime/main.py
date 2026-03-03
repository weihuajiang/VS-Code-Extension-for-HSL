"""
HSL Debugger - Main Entry Point
================================
SIMULATION ONLY - Never connects to Hamilton hardware.
Replaces HXRun.exe and HxHSLMetEd.exe for testing/debugging HSL methods.

Usage:
    python -m hsl_runtime.main <path-to-hsl-file> [options]

Options:
    --verbose    Show detailed trace output
    --quiet      Suppress trace output
    --dump-ast   Print the AST instead of executing
    --dump-tokens Print tokens instead of parsing
"""

import sys
import os
import argparse
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hsl_runtime.preprocessor import Preprocessor
from hsl_runtime.lexer import Lexer
from hsl_runtime.parser import Parser
from hsl_runtime.interpreter import Interpreter, TraceOutput


def main():
    parser = argparse.ArgumentParser(
        description="HSL Debugger - Simulation Runtime for Hamilton HSL files",
        epilog="SIMULATION ONLY - Never connects to Hamilton hardware."
    )
    parser.add_argument("hsl_file", help="Path to the HSL file to execute")
    parser.add_argument("--verbose", action="store_true", default=True,
                        help="Show detailed trace output (default)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress trace output")
    parser.add_argument("--dump-ast", action="store_true",
                        help="Print the AST instead of executing")
    parser.add_argument("--dump-tokens", action="store_true",
                        help="Print tokens instead of parsing")
    parser.add_argument("--dump-preprocessed", action="store_true",
                        help="Print preprocessed source instead of parsing")
    parser.add_argument("--max-iterations", type=int, default=100000,
                        help="Maximum loop iterations (safety limit)")
    parser.add_argument("--hamilton-dir", type=str,
                        default=r"C:\Program Files (x86)\Hamilton",
                        help="Hamilton installation directory")

    args = parser.parse_args()

    hsl_path = os.path.abspath(args.hsl_file)
    if not os.path.exists(hsl_path):
        print(f"Error: File not found: {hsl_path}")
        sys.exit(1)

    verbose = not args.quiet

    print("=" * 60)
    print("  HSL Debugger - Simulation Runtime v0.1")
    print("  SIMULATION ONLY - No hardware interaction")
    print("=" * 60)
    print(f"  File:    {hsl_path}")
    print(f"  Hamilton: {args.hamilton_dir}")
    print()

    # === Phase 1: Preprocess ===
    print("[1/4] Preprocessing...")
    t0 = time.time()
    try:
        preprocessor = Preprocessor(hamilton_dir=args.hamilton_dir)
        source = preprocessor.preprocess_file(hsl_path)
        t1 = time.time()
        print(f"  Done ({t1 - t0:.3f}s)")
        print(f"  Defines: {len(preprocessor.defines)}")
        print(f"  Included files: {len(preprocessor.included_files)}")

        if args.dump_preprocessed:
            print("\n=== PREPROCESSED SOURCE ===")
            for i, line in enumerate(source.split('\n'), 1):
                print(f"{i:6d}: {line}")
            print("=== END PREPROCESSED SOURCE ===")
            return 0
    except Exception as e:
        print(f"  Preprocessor error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1

    # === Phase 2: Tokenize ===
    print("[2/4] Tokenizing...")
    t0 = time.time()
    try:
        lexer = Lexer(source, filename=hsl_path)
        tokens = lexer.tokenize()
        t1 = time.time()
        print(f"  Done ({t1 - t0:.3f}s)")
        print(f"  Tokens: {len(tokens)}")

        if args.dump_tokens:
            print("\n=== TOKENS ===")
            for tok in tokens:
                print(f"  {tok}")
            print("=== END TOKENS ===")
            return 0
    except Exception as e:
        print(f"  Lexer error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1

    # === Phase 3: Parse ===
    print("[3/4] Parsing...")
    t0 = time.time()
    try:
        p = Parser(tokens, filename=hsl_path)
        program = p.parse()
        t1 = time.time()
        print(f"  Done ({t1 - t0:.3f}s)")
        print(f"  Declarations: {len(program.declarations)}")
        if p.errors:
            print(f"  Parser warnings/errors: {len(p.errors)}")
            for err in p.errors[:10]:
                print(f"    - {err}")

        if args.dump_ast:
            print("\n=== AST ===")
            _dump_ast(program, indent=0)
            print("=== END AST ===")
            return 0
    except Exception as e:
        print(f"  Parser error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1

    # === Phase 4: Execute (Simulation) ===
    print("[4/4] Executing (SIMULATION)...")
    print("-" * 40)
    t0 = time.time()
    try:
        trace = TraceOutput(verbose=verbose)
        interp = Interpreter(trace=trace)
        interp._max_iterations = args.max_iterations
        interp.execute(program)
        t1 = time.time()
        print("-" * 40)
        print(f"  Execution complete ({t1 - t0:.3f}s)")
        print(f"  Trace messages: {len(trace.messages)}")
        print(f"  Functions found: {len(interp.functions)}")
        print(f"  Namespaces: {list(interp.namespaces.keys())}")
    except Exception as e:
        print(f"  Runtime error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1

    print()
    print("=" * 60)
    print("  Simulation finished successfully")
    print("=" * 60)
    return 0


def _dump_ast(node, indent=0):
    """Recursively print AST for debugging."""
    prefix = "  " * indent
    if node is None:
        return

    if isinstance(node, list):
        for item in node:
            _dump_ast(item, indent)
        return

    name = type(node).__name__
    attrs = {}

    if hasattr(node, '__dict__'):
        for k, v in node.__dict__.items():
            if k.startswith('_'):
                continue
            if isinstance(v, list):
                attrs[k] = f"[{len(v)} items]"
            elif isinstance(v, str):
                attrs[k] = repr(v) if len(v) < 60 else repr(v[:57] + "...")
            elif v is None:
                continue
            elif hasattr(v, '__dict__') and not isinstance(v, (int, float, bool)):
                attrs[k] = type(v).__name__
            else:
                attrs[k] = repr(v)

    attr_str = ", ".join(f"{k}={v}" for k, v in attrs.items())
    print(f"{prefix}{name}({attr_str})")

    if hasattr(node, '__dict__'):
        for k, v in node.__dict__.items():
            if k.startswith('_'):
                continue
            if isinstance(v, list):
                for item in v:
                    if hasattr(item, '__dict__') and not isinstance(item, (int, float, str, bool)):
                        _dump_ast(item, indent + 1)
            elif hasattr(v, '__dict__') and not isinstance(v, (int, float, str, bool)):
                _dump_ast(v, indent + 1)


if __name__ == "__main__":
    sys.exit(main())
