"""
pdf_to_md — PDF to Markdown CLI converter.

A deterministic (no LLM/AI) Python CLI tool that converts PDF documents
to clean Markdown. Designed for pipeline integration — output can be
consumed directly by LLMs, RAG systems, or documentation workflows.

Uses pdfplumber as primary parser with PyMuPDF (fitz) as a strategic
fallback for text extraction performance.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import NoReturn

# Version string (semantic versioning)
__version__ = "0.1.0"
__author__ = "Pao (Builder) @ Louis Ecosystem"
__description__ = "PDF to Markdown CLI converter — deterministic, no LLM"


# ── Scanned PDF detection threshold ──────────────────────────────────────────
SCANNED_PAGE_THRESHOLD = 0.8
"""
If this fraction of pages yield fewer than MIN_CHARS_PER_PAGE characters,
the document is likely scanned and a warning is emitted.
"""
MIN_CHARS_PER_PAGE = 50


def main(argv: list[str] | None = None) -> NoReturn:
    """
    Main entry point for the pdf_to_md converter.

    Orchestrates the full pipeline:
        parse → (clean) → format → (chunk) → write

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Never returns — calls sys.exit() with appropriate exit code.
    """
    from pdf_to_md.cli import parse_args
    from pdf_to_md.parser import parse_pdf, extract_metadata, parse_page_spec

    args = parse_args(argv)

    # ── Resolve paths ──────────────────────────────────────────────────────
    pdf_path = Path(args.input)

    if not pdf_path.exists():
        print(f"Error: File not found — {pdf_path}", file=sys.stderr)
        sys.exit(1)

    if not pdf_path.is_file():
        print(f"Error: Not a file — {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Check file extension
    is_md = pdf_path.suffix.lower() in (".md", ".markdown")
    SUPPORTED_EXTENSIONS = (".pdf", ".md", ".markdown")
    if pdf_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        print(
            f"Error: Unsupported file format — {pdf_path}\n"
            f"       Supported: PDF, Markdown (.md, .markdown)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Default output
    if args.output is None:
        if args.clean:
            # When --clean is used, append _cleaned to avoid overwriting
            output_path = pdf_path.with_stem(pdf_path.stem + "_cleaned").with_suffix(".md")
        elif is_md:
            # Avoid overwriting the input .md file
            output_path = pdf_path.with_stem(pdf_path.stem + "_processed").with_suffix(".md")
        else:
            output_path = pdf_path.with_suffix(".md")
    else:
        output_path = Path(args.output)
        # Detect directory intent:
        # 1. Already an existing directory
        # 2. Has no file extension (e.g. /some/path/outdir)
        # 3. Original argument had trailing slash (via args._output_raw)
        is_dir_intent = (
            output_path.is_dir()
            or not output_path.suffix
        )
        if is_dir_intent:
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                print(f"Error: Permission denied — {output_path}", file=sys.stderr)
                sys.exit(4)
            output_path = output_path / f"{pdf_path.stem}.md"
        else:
            # Ensure parent directory exists
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                print(f"Error: Permission denied — {output_path.parent}", file=sys.stderr)
                sys.exit(4)

    # ── Resolve pages ──────────────────────────────────────────────────────
    page_list: list[int] | None = None
    if args.pages is not None:
        try:
            page_list = parse_page_spec(args.pages)
        except ValueError as exc:
            print(f"Error: Invalid page specification — {exc}", file=sys.stderr)
            sys.exit(2)

    # ── Verbose logging ────────────────────────────────────────────────────
    if args.verbose:
        print(f"[pdf_to_md] Input:  {pdf_path}", file=sys.stderr)
        print(f"[pdf_to_md] Output: {output_path}", file=sys.stderr)
        print(f"[pdf_to_md] Pages:  {page_list or 'all'}", file=sys.stderr)
        print(f"[pdf_to_md] Fast:   {args.fast}", file=sys.stderr)
        print(f"[pdf_to_md] Clean:  {args.clean}", file=sys.stderr)
        print(f"[pdf_to_md] Table:  {args.table_strategy}", file=sys.stderr)
        print(f"[pdf_to_md] Chunk:  {args.chunk} (size={args.chunk_size})", file=sys.stderr)
        sys.stderr.flush()

    # ── Extract metadata (PDF only) ────────────────────────────────────────
    metadata: dict = {}
    if not is_md:
        try:
            metadata = extract_metadata(pdf_path)
            if args.verbose:
                print(f"[pdf_to_md] Metadata: {metadata}", file=sys.stderr)
                sys.stderr.flush()

            # Check for encrypted PDF
            if metadata.get("is_encrypted"):
                print(
                    "Error: Password-protected PDF detected.\n"
                    "This tool does not support encrypted PDFs.\n"
                    "Please decrypt the file first (e.g., using qpdf).",
                    file=sys.stderr,
                )
                sys.exit(5)

        except Exception as exc:
            if args.verbose:
                print(
                    f"[pdf_to_md] Warning: metadata extraction failed — {exc}",
                    file=sys.stderr,
                )
            metadata = {}

    # ── Pipeline setup (branch: .md vs .pdf) ───────────────────────────────
    start_time = time.monotonic()
    total_pages = 0
    total_chars = 0
    empty_page_count = 0
    actual_page_numbers: list[int] = []  # Track actual pages processed
    effective_preserve_layout: bool = args.preserve_layout

    try:
        if is_md:
            # ── Markdown input: read directly, skip PDF parser ──────────────
            if args.verbose:
                print(f"[pdf_to_md] Reading markdown: {pdf_path}", file=sys.stderr)
                sys.stderr.flush()

            md_text = pdf_path.read_text(encoding="utf-8")
            from pdf_to_md.parser import PageElement

            page_elements: list = [
                PageElement(
                    type="paragraph",
                    level=None,
                    content=md_text,
                    rows=None,
                    page_number=1,
                    bbox=None,
                    list_style=None,
                    metadata={"source": "md_input"},
                )
            ]

            def _md_gen():
                yield page_elements

            gen = _md_gen()
            hf_profile = None
            body_font_size: float | None = None
            effective_preserve_layout = True
            page_list = None  # No page selection for .md
        else:
            # ── PDF input ──────────────────────────────────────────────────
            gen = parse_pdf(
                pdf_path=pdf_path,
                pages=page_list,
                table_strategy=args.table_strategy,
                fast=args.fast,
            )

            # ── OPTIONAL: First pass for header/footer profile (clean mode) ──
            hf_profile = None
            if args.clean:
                # Collect all page elements first to build cross-page profile
                if args.verbose:
                    print(
                        "[pdf_to_md] Building header/footer profile "
                        "(first pass)...",
                        file=sys.stderr,
                    )
                    sys.stderr.flush()

                all_page_elements: list = []
                from pdf_to_md.cleaner import build_header_footer_profile

                try:
                    # Quick scan: use fitz to collect page text for profiling
                    import fitz

                    quick_doc = fitz.open(str(pdf_path))
                    try:
                        quick_elements: list = []
                        for idx in range(quick_doc.page_count):
                            if page_list and (idx + 1) not in page_list:
                                continue
                            page_text = quick_doc[idx].get_text("text") or ""
                            page_text = page_text.strip()
                            if page_text:
                                quick_elements.append([
                                    {
                                        "type": "paragraph",
                                        "content": page_text,
                                        "page_number": idx + 1,
                                    }
                                ])
                            else:
                                quick_elements.append([])

                        if len(quick_elements) >= 5:
                            hf_profile = build_header_footer_profile(
                                quick_elements,
                            )
                            if args.verbose:
                                header_count = len(
                                    hf_profile.get("headers", [])
                                )
                                footer_count = len(
                                    hf_profile.get("footers", [])
                                )
                                running_count = len(
                                    hf_profile.get("running_heads", [])
                                )
                                print(
                                    f"[pdf_to_md] Profile: {header_count} headers, "
                                    f"{footer_count} footers, "
                                    f"{running_count} running heads",
                                    file=sys.stderr,
                                )
                                sys.stderr.flush()
                    finally:
                        quick_doc.close()
                except Exception as exc:
                    if args.verbose:
                        print(
                            f"[pdf_to_md] Warning: profile building failed — {exc}",
                            file=sys.stderr,
                        )

                # Re-create the generator for the actual pipeline
                gen = parse_pdf(
                    pdf_path=pdf_path,
                    pages=page_list,
                    table_strategy=args.table_strategy,
                    fast=args.fast,
                )

            # ── Estimate body font size for heading detection ────────────────
            body_font_size: float | None = None
            if not args.fast and not args.no_heading:
                try:
                    import pdfplumber

                    with pdfplumber.open(str(pdf_path)) as plumber_doc:
                        first_idx = (page_list[0] - 1) if page_list else 0
                        if 0 <= first_idx < len(plumber_doc.pages):
                            first_page = plumber_doc.pages[first_idx]
                            chars = first_page.chars
                            if chars:
                                from collections import Counter

                                font_sizes = [c["size"] for c in chars if c.get("size", 0) > 0]
                                if font_sizes:
                                    body_font_size = Counter(font_sizes).most_common(1)[0][0]
                                    if args.verbose:
                                        print(
                                            f"[pdf_to_md] Body font size: ~{body_font_size:.1f}pt",
                                            file=sys.stderr,
                                        )
                                        sys.stderr.flush()
                except Exception:
                    pass

        # ── Open output file and write progressively ──────────────────────
        with open(output_path, "w", encoding="utf-8") as f:
            for page_idx, page_elements in enumerate(gen):
                first_req_page = page_list[0] if page_list else 1
                page_number = page_idx + first_req_page
                actual_page_numbers.append(page_number)
                total_pages += 1

                # Verbose progress
                if args.verbose:
                    if total_pages == 1 or total_pages % 100 == 0:
                        print(
                            f"[pdf_to_md] Page {page_number} — "
                            f"{len(page_elements)} elements",
                            file=sys.stderr,
                        )
                        sys.stderr.flush()

                # ── Detect empty/scanned pages ──────────────────────────
                total_text_len = sum(
                    len(e.get("content", "") or "")
                    for e in page_elements
                )
                if total_text_len < MIN_CHARS_PER_PAGE:
                    empty_page_count += 1

                # ── Clean (optional) ──────────────────────────────────────
                if args.clean:
                    from pdf_to_md.cleaner import clean_content

                    page_elements = clean_content(
                        page_elements,
                        remove_headers=True,
                        remove_footers=True,
                        remove_page_numbers=True,
                        hf_profile=hf_profile,
                        page_number=page_number,
                        total_pages=total_pages,
                    )

                # ── Format to Markdown ────────────────────────────────────
                from pdf_to_md.formatter import to_markdown

                page_md = to_markdown(
                    page_elements,
                    heading_detection=not args.no_heading,
                    table_strategy=args.table_strategy,
                    preserve_layout=effective_preserve_layout,
                    body_font_size=body_font_size,
                )

                total_chars += len(page_md)
                f.write(page_md)

                # Add page separator
                f.write("\n\n")

        # ── Scanned PDF warning (PDF only) ────────────────────────────────
        if not is_md and total_pages > 0:
            empty_ratio = empty_page_count / total_pages
            if empty_ratio >= SCANNED_PAGE_THRESHOLD:
                scanned_warning = (
                    "⚠️  Warning: This PDF appears to be scanned (image-based).\n"
                    "   No extractable text was found on most pages.\n"
                    "   Consider using OCR (e.g., OCRmyPDF) before running this tool.\n"
                )
                if args.verbose:
                    print(f"[pdf_to_md] {scanned_warning}", file=sys.stderr)
                else:
                    print(scanned_warning, file=sys.stderr)
                sys.stderr.flush()

        # ── Chunking (optional — operates on full markdown) ───────────────
        if args.chunk:
            if args.verbose:
                print("[pdf_to_md] Chunking output...", file=sys.stderr)
                sys.stderr.flush()

            full_md = output_path.read_text(encoding="utf-8")

            from pdf_to_md.chunker import chunk_content

            if actual_page_numbers:
                first_page_actual = min(actual_page_numbers)
                last_page_actual = max(actual_page_numbers)
            else:
                first_page_actual = 1
                last_page_actual = 1

            chunks = chunk_content(
                markdown=full_md,
                chunk_size=args.chunk_size,
                page_range=(first_page_actual, last_page_actual),
            )

            # Re-write with chunk markers
            with open(output_path, "w", encoding="utf-8") as f:
                for chunk in chunks:
                    f.write(f"<!-- chunk-id: {chunk['id']} -->\n")
                    if chunk["heading"]:
                        f.write(
                            f"<!-- chunk-heading: {chunk['heading']} -->\n"
                        )
                    pr = chunk["page_range"]
                    f.write(
                        f"<!-- chunk-page-range: "
                        f"{pr[0]}-{pr[1]} -->\n"
                    )
                    f.write(chunk["content"])
                    f.write("\n\n")

            if args.verbose:
                print(
                    f"[pdf_to_md] Created {len(chunks)} chunks",
                    file=sys.stderr,
                )
                sys.stderr.flush()

    except FileNotFoundError:
        print(
            f"Error: File not found — {pdf_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    except PermissionError:
        print(
            f"Error: Permission denied reading — {pdf_path}",
            file=sys.stderr,
        )
        sys.exit(4)

    except RuntimeError as exc:
        error_msg = str(exc)
        if "encrypted" in error_msg.lower() or "password" in error_msg.lower():
            print(
                "Error: Password-protected PDF detected.\n"
                "This tool does not support encrypted PDFs.\n"
                "Please decrypt the file first (e.g., using qpdf).",
                file=sys.stderr,
            )
            sys.exit(5)
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc(file=sys.stderr)
            sys.exit(3)

    except Exception as exc:
        if is_md:
            prefix = "Markdown processing"
        else:
            prefix = "PDF parsing"
        print(f"Error: {prefix} failed — {exc}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc(file=sys.stderr)
        sys.exit(3)

    # ── Done ──────────────────────────────────────────────────────────────
    elapsed = time.monotonic() - start_time

    if args.verbose:
        print(
            f"[pdf_to_md] Done! {total_pages} pages, "
            f"{total_chars:,} chars in {elapsed:.2f}s",
            file=sys.stderr,
        )
        print(f"[pdf_to_md] Output: {output_path.resolve()}", file=sys.stderr)
        sys.stderr.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
