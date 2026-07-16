"""
CLI argument parsing for pdf_to_md.

Uses built-in argparse. All flags defined in spec v2.0 §4.2.
"""

from __future__ import annotations

import argparse

from pdf_to_md import __version__


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse and validate command-line arguments.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        An ``argparse.Namespace`` with all parsed arguments.

    Exit codes:
        - 2: If arguments are invalid (argparse handles this).
    """
    parser = argparse.ArgumentParser(
        prog="pdf_to_md",
        description="Convert PDF (or Markdown) documents to clean Markdown.",
        epilog=(
            "Examples:\n"
            "  python -m pdf_to_md input.pdf\n"
            "  python script.py input.pdf -o output.md\n"
            "  python script.py input.pdf --clean --verbose\n"
            "  python script.py input.pdf --fast --table-strategy simple\n"
            "  python script.py input.pdf --pages 1-5,8,10-12 --chunk\n"
            "  python -m pdf_to_md note.md --clean\n"
            "  python -m pdf_to_md note.md --chunk --chunk-size 1000\n"
            "  python -m pdf_to_md doc.md --clean --chunk -o ready_for_llm.md\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
    )

    # ── Positional argument ────────────────────────────────────────────────
    parser.add_argument(
        "input",
        type=str,
        help="Path to input PDF or Markdown (.md) file",
    )

    # ── Output options ─────────────────────────────────────────────────────
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Output file path. Defaults to input path with .md extension. "
            "If a directory is given, the filename is derived from the input."
        ),
    )

    # ── Processing flags ───────────────────────────────────────────────────
    parser.add_argument(
        "-c",
        "--clean",
        action="store_true",
        default=False,
        help=(
            "Remove headers, footers, page numbers, and other artifacts "
            "from the output."
        ),
    )

    parser.add_argument(
        "--fast",
        action="store_true",
        default=False,
        help=(
            "PyMuPDF-only mode. Skip pdfplumber entirely. "
            "10-50x faster but no table structure preserved."
        ),
    )

    # ── Chunking options ────────────────────────────────────────────────────
    parser.add_argument(
        "--chunk",
        action="store_true",
        default=False,
        help="Enable chunking mode — split output by natural breaks.",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=2000,
        metavar="N",
        help="Max characters per chunk (default: 2000). Only active with --chunk.",
    )

    # ── Page selection ──────────────────────────────────────────────────────
    parser.add_argument(
        "-p",
        "--pages",
        type=str,
        default=None,
        metavar="SPEC",
        help=(
            "Page selection e.g. '1-5,8,10-12'. "
            "1-based page numbers. Default: all pages."
        ),
    )

    # ── Table strategy ─────────────────────────────────────────────────────
    parser.add_argument(
        "--table-strategy",
        type=str,
        default="markdown",
        choices=["markdown", "skip", "simple"],
        help=(
            "Table handling strategy. "
            "'markdown' (default): GFM tables. "
            "'skip': omit tables. "
            "'simple': comma/tab-separated inline."
        ),
    )

    # ── Heading options ────────────────────────────────────────────────────
    parser.add_argument(
        "--heading-detection",
        action="store_true",
        default=True,
        help=(
            "Auto-detect headings based on font size/weight. "
            "Enabled by default. Use --no-heading to disable."
        ),
    )

    parser.add_argument(
        "--no-heading",
        action="store_true",
        default=False,
        help="Skip heading detection — flat text output.",
    )

    parser.add_argument(
        "--preserve-layout",
        action="store_true",
        default=False,
        help="Preserve original line breaks (not recommended for LLM consumption).",
    )

    # ── Verbosity ──────────────────────────────────────────────────────────
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Detailed logging to stderr — page-by-page progress.",
    )

    # ── Version ────────────────────────────────────────────────────────────
    parser.add_argument(
        "--version",
        action="version",
        version=f"pdf_to_md v{__version__}",
        help="Show version and exit.",
    )

    # ── Parse ──────────────────────────────────────────────────────────────
    args = parser.parse_args(argv)

    # ── Post-parse validation ──────────────────────────────────────────────
    if args.chunk_size < 1:
        parser.error("--chunk-size must be >= 1")

    # If --no-heading is set, override heading-detection
    if args.no_heading:
        args.heading_detection = False

    return args
