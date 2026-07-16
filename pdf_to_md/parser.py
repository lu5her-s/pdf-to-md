"""
Hybrid PDF parsing engine for pdf_to_md.

Implements a generator-based, page-at-a-time pipeline using pdfplumber
as the primary parser and PyMuPDF (fitz) as a fast-text fallback.

Architecture (per An's review):
    1. Open pdfplumber once → batch-detect tables across all selected pages
    2. Route each page: tables → pdfplumber, no tables → fitz
    3. Fallback chain: pdfplumber → fitz → warning
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from pathlib import Path
from typing import Any, Generator, Literal, TypedDict

# ──────────────────────────────────────────────────────────────────────────────
# Type Definitions
# ──────────────────────────────────────────────────────────────────────────────


class PageElement(TypedDict):
    """A single content element extracted from a PDF page."""

    type: Literal["heading", "paragraph", "table", "list", "image", "blank"]
    """Element type."""
    level: int | None
    """Heading level (1-6). ``None`` for non-headings."""
    content: str
    """Text content."""
    rows: list[list[str]] | None
    """Table rows (only for ``type == "table"``)."""
    page_number: int
    """1-based page number. CRITICAL for RAG citation."""
    bbox: tuple[float, float, float, float] | None
    """Bounding box ``(x0, y0, x1, y1)``. Optional."""
    list_style: Literal["bullet", "ordered", "none"] | None
    """List style (only for ``type == "list"``)."""
    metadata: dict[str, Any] | None
    """Additional metadata (font info, etc.)."""


# A list of PageElements represents all content from one page.
PageElements = list[PageElement]


# ──────────────────────────────────────────────────────────────────────────────
# Metadata Extraction
# ──────────────────────────────────────────────────────────────────────────────


def extract_metadata(pdf_path: Path) -> dict[str, Any]:
    """
    Extract document metadata via PyMuPDF.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dict with keys: ``title``, ``author``, ``subject``, ``keywords``,
        ``page_count``, ``format``, ``is_encrypted``.
    """
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        warnings.warn(f"Cannot open PDF for metadata: {exc}")
        return {
            "title": None,
            "author": None,
            "subject": None,
            "keywords": None,
            "page_count": 0,
            "format": None,
            "is_encrypted": False,
        }

    metadata: dict[str, Any] = {}

    try:
        # Check encryption first
        metadata["is_encrypted"] = doc.is_encrypted
        metadata["page_count"] = doc.page_count

        # Extract standard metadata
        if doc.metadata:
            meta = doc.metadata
            metadata["title"] = meta.get("title", None)
            metadata["author"] = meta.get("author", None)
            metadata["subject"] = meta.get("subject", None)
            metadata["keywords"] = meta.get("keywords", None)
            metadata["format"] = meta.get("format", None)
        else:
            for key in ("title", "author", "subject", "keywords", "format"):
                metadata[key] = None

        # File-level info
        metadata["filename"] = pdf_path.name
        metadata["size_bytes"] = pdf_path.stat().st_size

    finally:
        doc.close()

    return metadata


# ──────────────────────────────────────────────────────────────────────────────
# PyMuPDF Text Extraction (fast path)
# ──────────────────────────────────────────────────────────────────────────────


def extract_text_fitz(
    pdf_path: Path,
    page_number: int,
) -> str:
    """
    Extract text from a single page using PyMuPDF (fitz).

    This is the "fast path" — 10-50x faster than pdfplumber but without
    table structure detection. Used for text-only pages.

    Args:
        pdf_path: Path to the PDF file.
        page_number: 0-based page index.

    Returns:
        Extracted text string (NFC-normalized).

    Raises:
        RuntimeError: If text extraction fails entirely.
    """
    import fitz

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise RuntimeError(f"Cannot open PDF with PyMuPDF: {exc}") from exc

    try:
        if page_number < 0 or page_number >= doc.page_count:
            return ""

        page = doc[page_number]
        text = page.get_text("text")

        # NFD → NFC normalization
        text = unicodedata.normalize("NFC", text)

        return text or ""
    finally:
        doc.close()


def extract_text_fitz_with_fonts(
    pdf_path: Path,
    page_number: int,
) -> tuple[str, dict[int, dict[str, Any]]]:
    """
    Extract text with per-line font metadata using PyMuPDF.

    Returns both the plain text and a mapping of line indices (in the
    returned text) to font metadata (font name, size, weight).

    Args:
        pdf_path: Path to the PDF file.
        page_number: 0-based page index.

    Returns:
        ``(text, line_font_map)`` where ``line_font_map`` maps 0-based
        line number to ``{"font": str, "size": float}``.

    Raises:
        RuntimeError: If text extraction fails.
    """
    import fitz

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise RuntimeError(f"Cannot open PDF with PyMuPDF: {exc}") from exc

    try:
        if page_number < 0 or page_number >= doc.page_count:
            return "", {}

        page = doc[page_number]
        blocks = page.get_text("dict") or {}
        all_spans: list[dict[str, Any]] = []

        for block in blocks.get("blocks", []):
            if block.get("type") != 0:  # text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = (span.get("text") or "").strip()
                    if text:
                        all_spans.append({
                            "text": text,
                            "font": span.get("font", ""),
                            "size": span.get("size", 0),
                            "bbox": span.get("bbox", (0, 0, 0, 0)),
                        })

        # Sort spans by reading order (y then x)
        all_spans.sort(key=lambda s: (s["bbox"][1], s["bbox"][0]))

        # Build text lines and font map
        text_lines: list[str] = []
        line_font_map: dict[int, dict[str, Any]] = {}

        for i, span in enumerate(all_spans):
            text_lines.append(unicodedata.normalize("NFC", span["text"]))
            line_font_map[i] = {
                "font": span["font"],
                "size": span["size"],
                "x": span["bbox"][0],
                "y": span["bbox"][1],
            }

        text = "\n".join(text_lines)
        return text, line_font_map

    finally:
        doc.close()


# ──────────────────────────────────────────────────────────────────────────────
# pdfplumber Table Extraction
# ──────────────────────────────────────────────────────────────────────────────


def extract_tables_plumber(
    pdf_page: Any,  # pdfplumber.page.Page
    table_strategy: str = "markdown",
) -> list[PageElement]:
    """
    Extract tables from a pdfplumber page object.

    Args:
        pdf_page: A pdfplumber ``Page`` object.
        table_strategy: One of ``"markdown"``, ``"skip"``, ``"simple"``.

    Returns:
        List of ``PageElement`` dicts (one per detected table).
    """
    elements: list[PageElement] = []

    if table_strategy == "skip":
        return elements

    try:
        tables = pdf_page.find_tables()
    except Exception:
        # pdfplumber can throw on malformed pages
        return elements

    for table in tables:
        rows: list[list[str]] = []
        for row in table.extract():
            cleaned_row: list[str] = []
            for cell in row or []:
                cell_text = unicodedata.normalize("NFC", (cell or "").strip())
                cleaned_row.append(cell_text)
            rows.append(cleaned_row)

        if not rows:
            continue

        # Build a text representation for the ``content`` field
        if table_strategy == "simple":
            content_lines: list[str] = []
            for row in rows:
                content_lines.append("\t".join(row))
            content = "\n".join(content_lines)
        else:
            # markdown — build a basic representation
            content = "\n".join(" | ".join(row) for row in rows)

        elements.append(
            PageElement(
                type="table",
                level=None,
                content=content,
                rows=rows,
                page_number=pdf_page.page_number + 1,
                bbox=_get_table_bbox(table),
                list_style=None,
                metadata={
                    "table_strategy": table_strategy,
                    "row_count": len(rows),
                    "col_count": len(rows[0]) if rows else 0,
                },
            )
        )

    return elements


def _get_table_bbox(table: Any) -> tuple[float, float, float, float] | None:
    """Extract bounding box from a pdfplumber Table object."""
    try:
        bbox = table.bbox
        return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    except (AttributeError, IndexError, TypeError, ValueError):
        return None


# ──────────────────────────────────────────────────────────────────────────────
# pdfplumber Text + Element Extraction
# ──────────────────────────────────────────────────────────────────────────────


def _extract_text_and_elements_plumber(
    pdf_page: Any,
    page_number: int,
    table_strategy: str,
    font_hints: dict[str, Any] | None = None,
) -> PageElements:
    """
    Extract text and structural elements from a pdfplumber page.

    Converts pdfplumber's ``chars`` and ``lines`` into ``PageElement``
    objects with type classification (heading, paragraph, list, blank).

    Args:
        pdf_page: A pdfplumber ``Page`` object.
        page_number: 1-based page number.
        table_strategy: Table handling strategy.
        font_hints: Optional font size distribution hints for heading detection.

    Returns:
        List of ``PageElement`` dicts for the page.
    """
    elements: PageElements = []

    # ── Tables first ────────────────────────────────────────────────────
    if table_strategy != "skip":
        table_elements = extract_tables_plumber(pdf_page, table_strategy)
        elements.extend(table_elements)

    # ── Text extraction via pdfplumber ──────────────────────────────────
    try:
        # Extract text with positioning
        text = pdf_page.extract_text() or ""
        text = unicodedata.normalize("NFC", text)
    except Exception:
        text = ""

    if not text.strip():
        if not elements:
            elements.append(
                PageElement(
                    type="blank",
                    level=None,
                    content="",
                    rows=None,
                    page_number=page_number,
                    bbox=None,
                    list_style=None,
                    metadata=None,
                )
            )
        return elements

    # ── Paragraph-level splitting via shared text block parser ───────
    parsed = _parse_text_blocks(
        text, page_number, source="pdfplumber", font_hints=font_hints
    )
    elements.extend(parsed)

    return elements


def _looks_like_heading(text: str, is_strict: bool = False) -> bool:
    """
    Heuristic: short, no sentence-ending punctuation, title-case.

    Uses **conservative** heuristics to minimize false positives on
    running headers, page numbers, and metadata lines.

    Args:
        text: Text to check.
        is_strict: If ``True``, apply stricter limits.

    Returns:
        ``True`` if the text looks like a heading.
    """
    if len(text) > 200 or len(text) < 2:
        return False
    words = text.split()
    word_count = len(words)

    if is_strict:
        max_words = 6
    else:
        max_words = 12

    # ── Reject very short text (likely running header/footer) ───────
    if word_count <= 2:
        # 1-2 word text is rarely a heading unless all-caps
        if not text.isupper():
            return False
        # All-caps 1-2 words might be a heading, but only if not a page number
        if re.match(r"^[\d\s\-—]+$", text):
            return False

    # ── Reject page number-like patterns ────────────────────────────
    # "Page 2 of 2", "Page N", "- N -", etc.
    if re.match(r"^Page\s+\d+(\s+of\s+\d+)?$", text, re.IGNORECASE):
        return False
    if re.match(r"^[\-\—]\s*\d+\s*[\-\—]$", text):
        return False

    # ── Reject text with terminal/clause-ending punctuation ─────────
    stripped = text.rstrip()
    ends_with_terminal = (
        stripped.endswith((".", "!", "?"))   # sentence end
        or stripped.endswith((":", ";", ","))  # clause end
        or stripped.endswith("-")              # hyphenated break
        or stripped.endswith("—")              # em dash
    )
    if ends_with_terminal:
        return False

    # ── All caps short line (most reliable signal) ──────────────────
    if text.isupper() and 2 <= word_count <= max_words:
        return True

    # ── Title case heading ──────────────────────────────────────────
    # At least 3 words, first letter capital, not a sentence fragment
    if 3 <= word_count <= max_words:
        if text[0].isupper():
            # Must have at least one lowercase letter (not all-caps)
            has_lower = any(c.islower() for c in text)
            if has_lower:
                return True

    return False


def _guess_heading_level(text: str) -> int:
    """Guess heading level based on text characteristics."""
    words = text.split()
    word_count = len(words)

    if word_count <= 3 and text.isupper():
        return 1
    if word_count <= 5 and text[0].isupper():
        return 2
    return 3


def _try_classify_as_heading(
    para: str,
    lines: list[str],
    font_hints: dict[str, Any],
    elements: PageElements,
    page_number: int,
) -> None:
    """Classify a single line as heading based on font hints."""
    _ = lines  # reserved for future line-level analysis
    if "max_font_size" in font_hints and "body_font_size" in font_hints:
        # Would check font size — placeholder for font analysis
        pass


def _try_extract_list(text: str, page_number: int) -> list[PageElement]:
    """Try to parse text as a list."""
    elements: list[PageElement] = []
    lines = text.split("\n")

    list_items: list[str] = []
    style: Literal["bullet", "ordered", "none"] = "none"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Bullet: starts with - or * or • or similar
        bullet_match = re.match(r"^[\-\*•◦‣⁃]\s+(.+)$", line)
        if bullet_match:
            if style == "none":
                style = "bullet"
            if style == "bullet":
                list_items.append(bullet_match.group(1))
            continue

        # Ordered: starts with number. or number)
        ordered_match = re.match(r"^(\d+)[\.\)]\s+(.+)$", line)
        if ordered_match:
            if style == "none":
                style = "ordered"
            if style == "ordered":
                list_items.append(ordered_match.group(2))
            continue

        # If we found list items but then a non-list line, break out
        if list_items and style != "none":
            break

    if list_items and style != "none":
        content = "\n".join(f"- {item}" for item in list_items)
        elements.append(
            PageElement(
                type="list",
                level=None,
                content=content,
                rows=None,
                page_number=page_number,
                bbox=None,
                list_style=style,
                metadata={"item_count": len(list_items)},
            )
        )

    return elements


# ──────────────────────────────────────────────────────────────────────────────
# Page Range Parsing
# ──────────────────────────────────────────────────────────────────────────────


def parse_page_spec(spec: str) -> list[int]:
    """
    Parse a page range specification string.

    Supports syntax like: ``1-5,8,10-12``

    Args:
        spec: Page range string.

    Returns:
        Sorted list of 1-based page numbers.
    """
    pages: set[int] = set()

    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            if start < 1 or end < 1:
                raise ValueError(f"Page numbers must be >= 1: {part!r}")
            if start > end:
                raise ValueError(f"Invalid range (start > end): {part!r}")
            pages.update(range(start, end + 1))
        else:
            page = int(part)
            if page < 1:
                raise ValueError(f"Page numbers must be >= 1: {part!r}")
            pages.add(page)

    return sorted(pages)


# ──────────────────────────────────────────────────────────────────────────────
# Core Generator: parse_pdf
# ──────────────────────────────────────────────────────────────────────────────


def parse_pdf(
    pdf_path: Path,
    pages: list[int] | None = None,
    table_strategy: str = "markdown",
    fast: bool = False,
) -> Generator[PageElements, None, None]:
    """
    Parse a PDF and yield one page's content at a time.

    **Hybrid routing:**
    1. If ``fast=True`` → use PyMuPDF for all pages (no pdfplumber).
    2. Otherwise, open pdfplumber once, batch-detect tables.
    3. Route: tables detected → pdfplumber full extraction; else → fitz text.
    4. Fallback: pdfplumber fails → fitz. Both fail → warning + blank.

    Args:
        pdf_path: Path to the input PDF.
        pages: Optional list of 1-based page numbers to extract.
            ``None`` means all pages.
        table_strategy: Table handling strategy.
        fast: If ``True``, skip pdfplumber entirely (PyMuPDF only).

    Yields:
        ``PageElements`` — one list per page.
    """
    import fitz

    # ── Check if file exists and is readable ────────────────────────────────
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # ── Open with PyMuPDF first for page count & encryption check ──────────
    try:
        fitz_doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise RuntimeError(f"Cannot open PDF: {exc}") from exc

    try:
        total_pages = fitz_doc.page_count

        # Encryption check
        if fitz_doc.is_encrypted:
            raise RuntimeError(
                "Password-protected PDF detected. "
                "This tool does not support encrypted PDFs. "
                "Please decrypt the file first."
            )

        # Resolve page range
        if pages is not None:
            page_indices = [p - 1 for p in pages if 1 <= p <= total_pages]
        else:
            page_indices = list(range(total_pages))

        if not page_indices:
            return  # No pages to process

        # ── Batch table detection (skip if fast mode) ───────────────────
        pages_with_tables: set[int] = set()

        if not fast:
            try:
                import pdfplumber

                with pdfplumber.open(str(pdf_path)) as plumber_doc:
                    for idx in page_indices:
                        try:
                            page = plumber_doc.pages[idx]
                            tables = page.find_tables()
                            if tables:
                                pages_with_tables.add(idx)
                        except Exception:
                            # Silently skip pages that fail table detection
                            pass

            except ImportError:
                warnings.warn("pdfplumber not installed. Falling back to PyMuPDF only.")
                fast = True
            except Exception as exc:
                warnings.warn(f"pdfplumber table detection failed: {exc}. Falling back.")
                fast = True

        # ── Process each page ──────────────────────────────────────────
        for idx in page_indices:
            page_number = idx + 1  # 1-based for the user

            if fast:
                # Fast mode: PyMuPDF only
                elements = _process_page_fast(
                    pdf_path, idx, page_number, table_strategy
                )
            elif idx in pages_with_tables:
                # Tables detected → pdfplumber full extraction
                elements = _process_page_plumber(
                    pdf_path, idx, page_number, table_strategy
                )
            else:
                # No tables → PyMuPDF fast text
                elements = _process_page_fast(
                    pdf_path, idx, page_number, table_strategy
                )

            yield elements

    finally:
        fitz_doc.close()


def _split_block_on_headings(block: list[str]) -> list[list[str]]:
    """
    Split a block of lines into sub-blocks at heading-like lines.

    Only splits on **strong** heading signals to minimize false positives
    on running headers and page numbers:
    - All-caps lines (e.g., "CHAPTER ONE")
    - Lines with at least 3 words and title case (e.g., "Test Document Title")
    - Lines ending with colon (e.g., "Bullet items:")

    Short lines (<= 2 words) are NOT split on unless they're all-caps.

    Args:
        block: List of text lines.

    Returns:
        List of sub-blocks (each a list of strings).
    """
    # Only split if the block has multiple lines
    if len(block) < 2:
        return [block]

    sub_blocks: list[list[str]] = []
    current: list[str] = []

    for line in block:
        stripped = line.strip()
        if not stripped:
            current.append(line)
            continue

        words = stripped.split()
        word_count = len(words)
        is_strong_heading = False

        # Strong heading signal 1: all-caps with 2+ words
        if stripped.isupper() and word_count >= 2:
            is_strong_heading = True

        # Strong heading signal 2: 3+ words, title case, no terminal punctuation
        elif (
            word_count >= 3
            and stripped[0].isupper()
            and not stripped.rstrip().endswith((".", "!", "?", ":", ";", ",", "-", "—"))
        ):
            is_strong_heading = True

        if is_strong_heading:
            # Flush previous content
            if current:
                sub_blocks.append(current)
                current = []
            # Start new sub-block with heading line
            current.append(stripped)
        else:
            current.append(line)

    if current:
        sub_blocks.append(current)

    # If no split happened, return original block
    return sub_blocks if len(sub_blocks) > 1 else [block]


def _classify_and_add(
    text: str,
    elements: PageElements,
    page_number: int,
    source: str,
) -> None:
    """Classify a single text string and add it to elements."""
    text = text.strip()
    if not text:
        return
    # Only classify as heading if strong signal (3+ words all-caps, or
    # 3+ words with title case and no terminal punctuation)
    words = text.split()
    is_heading = (
        (text.isupper() and len(words) >= 2)
        or (len(words) >= 3 and _looks_like_heading(text, is_strict=True))
    )
    if is_heading:
        elements.append(_make_heading(text, page_number, source))
    else:
        elements.append(_make_paragraph(text, page_number, source))


def _parse_text_blocks(
    text: str,
    page_number: int,
    source: str = "fitz",
    font_hints: dict[str, Any] | None = None,
) -> PageElements:
    """
    Parse raw text into PageElements by grouping lines into logical blocks.

    Groups consecutive non-empty lines into blocks separated by blank lines.
    For each block, detects headings, lists (bullet/ordered), and paragraphs.
    Lists within a block are extracted without discarding surrounding text.

    Args:
        text: Raw extracted text.
        page_number: 1-based page number.
        source: Source label ("fitz" or "pdfplumber").
        font_hints: Optional font hints for heading detection.

    Returns:
        List of PageElements for the text.
    """
    elements: PageElements = []
    lines = text.split("\n")

    # ── Group consecutive non-blank lines into blocks ──────────────────
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped:
            current_block.append(stripped)
        else:
            if current_block:
                blocks.append(current_block)
                current_block = []

    if current_block:
        blocks.append(current_block)

    # ── Process each block ─────────────────────────────────────────────
    for block in blocks:
        # ── Sub-split: break block on heading-like lines ────────────────
        sub_blocks = _split_block_on_headings(block)

        for sub_block in sub_blocks:
            sub_text = "\n".join(sub_block)
            is_single = len(sub_block) == 1

            # ── Extract heading from first line if it looks like one ──
            # When sub_block starts with a heading line followed by text,
            # split heading out (e.g., ["Page 2 Heading", "body text..."])
            heading_text: str | None = None
            remaining_lines: list[str] = sub_block

            if not is_single:
                first_line = sub_block[0]
                words = first_line.split()
                is_heading_first_line = (
                    (first_line.isupper() and len(words) >= 2)
                    or (len(words) >= 3 and _looks_like_heading(first_line))
                )
                if is_heading_first_line:
                    heading_text = first_line
                    remaining_lines = sub_block[1:]

            # ── List detection on remaining lines ─────────────────────
            list_info = _extract_list_from_block(remaining_lines, page_number)
            if list_info is not None:
                pre_text, list_elem, post_text = list_info
                if heading_text:
                    elements.append(_make_heading(heading_text, page_number, source))
                if pre_text:
                    _classify_and_add(pre_text, elements, page_number, source)
                if list_elem:
                    elements.append(list_elem)
                if post_text:
                    _classify_and_add(post_text, elements, page_number, source)
                continue

            # ── If heading was extracted, add it ──────────────────────
            if heading_text is not None:
                elements.append(_make_heading(heading_text, page_number, source))
                if remaining_lines:
                    remaining_text = "\n".join(remaining_lines)
                    elements.append(
                        _make_paragraph(remaining_text, page_number, source)
                    )
                continue

            # ── Heading detection (single line) ──────────────────────
            if is_single:
                line_text = sub_block[0]

                # Font-based heading detection (primary)
                if font_hints and line_text:
                    _try_classify_as_heading(
                        line_text, sub_block, font_hints, elements, page_number
                    )
                    # Check if a heading was already added
                    if elements and elements[-1].get("page_number") == page_number:
                        if elements[-1]["type"] == "heading":
                            continue

                # Conservative heuristic heading detection (fallback)
                words = line_text.split()
                is_fallback_heading = (
                    (line_text.isupper() and len(words) >= 2)
                    or (len(words) >= 3 and _looks_like_heading(line_text))
                )
                if is_fallback_heading:
                    elements.append(_make_heading(line_text, page_number, source))
                    continue

            # ── Default: paragraph ────────────────────────────────────
            elements.append(_make_paragraph(sub_text, page_number, source))

    return elements


def _extract_list_from_block(
    block: list[str],
    page_number: int,
) -> tuple[str | None, PageElement | None, str | None] | None:
    """
    Extract list items from a block of lines.

    Returns ``(pre_text, list_element, post_text)`` where:
    - ``pre_text``: text before the first list item (or ``None``)
    - ``list_element``: a ``PageElement`` of type ``"list"`` (or ``None``)
    - ``post_text``: text after the last list item (or ``None``)

    Returns ``None`` if no list items are found.
    """
    list_line_indices: list[int] = []
    list_style: Literal["bullet", "ordered", "none"] = "none"

    for i, line in enumerate(block):
        # Bullet detection
        bullet_match = re.match(r"^[\-\*•◦‣⁃]\s+(.+)$", line)
        if bullet_match:
            if list_style == "none":
                list_style = "bullet"
            if list_style == "bullet":
                list_line_indices.append(i)
            continue

        # Ordered detection
        ordered_match = re.match(r"^(\d+)[\.\)]\s+(.+)$", line)
        if ordered_match:
            if list_style == "none":
                list_style = "ordered"
            if list_style == "ordered":
                list_line_indices.append(i)
            continue

    if not list_line_indices or list_style == "none":
        return None

    # Extract list items
    list_items: list[str] = []
    for i in list_line_indices:
        line = block[i]
        if list_style == "bullet":
            item = re.match(r"^[\-\*•◦‣⁃]\s+(.+)$", line).group(1)
        else:
            item = re.match(r"^(\d+)[\.\)]\s+(.+)$", line).group(2)
        list_items.append(item)

    # Build list content
    if list_style == "bullet":
        list_content = "\n".join(f"- {item}" for item in list_items)
    else:
        list_content = "\n".join(
            f"{j+1}. {item}" for j, item in enumerate(list_items)
        )

    list_element = PageElement(
        type="list",
        level=None,
        content=list_content,
        rows=None,
        page_number=page_number,
        bbox=None,
        list_style=list_style,
        metadata={"item_count": len(list_items), "source": "parser"},
    )

    # Pre-text: lines before the first list item
    pre_text: str | None = None
    first_list_idx = list_line_indices[0]
    if first_list_idx > 0:
        pre_lines = block[:first_list_idx]
        pre_text = "\n".join(pre_lines)

    # Post-text: lines after the last list item
    post_text: str | None = None
    last_list_idx = list_line_indices[-1]
    if last_list_idx < len(block) - 1:
        post_lines = block[last_list_idx + 1:]
        post_text = "\n".join(post_lines)

    return (pre_text, list_element, post_text)


def _make_heading(text: str, page_number: int, source: str) -> PageElement:
    """Create a heading PageElement."""
    return PageElement(
        type="heading",
        level=_guess_heading_level(text),
        content=text,
        rows=None,
        page_number=page_number,
        bbox=None,
        list_style=None,
        metadata={"source": source, "detection": "heuristic"},
    )


def _make_paragraph(text: str, page_number: int, source: str) -> PageElement:
    """Create a paragraph PageElement."""
    return PageElement(
        type="paragraph",
        level=None,
        content=text,
        rows=None,
        page_number=page_number,
        bbox=None,
        list_style=None,
        metadata={"source": source},
    )


def _process_page_fast(
    pdf_path: Path,
    idx: int,
    page_number: int,
    table_strategy: str,
) -> PageElements:
    """
    Process a page using PyMuPDF only (fast path).

    Uses ``get_text("dict")`` to extract text with font metadata,
    enabling font-size-based heading detection in the formatter.

    Args:
        pdf_path: Path to the PDF.
        idx: 0-based page index.
        page_number: 1-based page number.
        table_strategy: Table handling strategy (only 'skip' or 'simple' meaningful here).

    Returns:
        List of PageElements for this page.
    """
    elements: PageElements = []

    try:
        text, line_font_map = extract_text_fitz_with_fonts(pdf_path, idx)
        text = text.strip()
    except RuntimeError:
        text = ""
        line_font_map = {}

    if not text:
        elements.append(
            PageElement(
                type="blank",
                level=None,
                content="",
                rows=None,
                page_number=page_number,
                bbox=None,
                list_style=None,
                metadata={"warning": "no text found, OCR not available"},
            )
        )
        return elements

    # Extract font metadata for font-based heading detection
    font_metadata: dict[str, Any] | None = None
    if line_font_map:
        # Collect font sizes from the page
        all_sizes = [info["size"] for info in line_font_map.values() if info["size"] > 0]
        if all_sizes:
            from collections import Counter
            size_counter = Counter(all_sizes)
            body_size = size_counter.most_common(1)[0][0]

            # Find max font size
            max_size = max(all_sizes)

            font_metadata = {
                "body_font_size": body_size,
                "max_font_size": max_size,
                "font_sizes": all_sizes,
            }

    # Process text blocks with font hints
    elements.extend(
        _parse_text_blocks(
            text,
            page_number,
            source="fitz",
            font_hints=font_metadata,
        )
    )

    # If we have line font info, split elements with mixed font sizes
    # and attach font metadata for formatter heading detection
    if line_font_map:
        try:
            elements = _split_and_tag_elements(elements, line_font_map)
        except Exception:
            pass  # Non-fatal if splitting fails

    return elements


def _split_and_tag_elements(
    elements: PageElements,
    line_font_map: dict[int, dict[str, Any]],
) -> PageElements:
    """
    Split multi-line paragraph elements that contain mixed font sizes
    into separate heading/paragraph elements. Also attaches font metadata.

    This is critical for accurate heading detection: when a large-font
    heading line is grouped with body text lines (no blank line separator),
    they must be split so the formatter can detect the heading by font size.

    Args:
        elements: Page elements to process.
        line_font_map: Mapping of line index to font info.

    Returns:
        Updated page elements with split elements and font metadata.
    """
    result: PageElements = []
    line_index = 0

    for elem in elements:
        if elem["type"] not in ("paragraph", "heading"):
            result.append(elem)
            # Still advance line_index for non-text elements
            content = elem.get("content", "")
            if content:
                line_index += len(content.split("\n"))
            continue

        content = elem.get("content", "")
        if not content:
            line_index += 1
            result.append(elem)
            continue

        lines = content.split("\n")
        num_lines = len(lines)

        # Collect font info for each line
        line_fonts: list[dict[str, Any] | None] = []
        for i in range(line_index, line_index + num_lines):
            if i in line_font_map:
                line_fonts.append(line_font_map[i])
            else:
                line_fonts.append(None)

        # Determine body font size: most common size among paragraphs
        body_size: float | None = None
        all_sizes = [lf["size"] for lf in line_fonts if lf and lf["size"] > 0]
        if all_sizes:
            from collections import Counter
            body_size = Counter(all_sizes).most_common(1)[0][0]

        # Check if this element has mixed font sizes significant enough to split
        has_mixed_sizes = False
        if len(set(s for s in all_sizes if s)) > 1:
            # Check if max is significantly larger than body
            max_size = max(all_sizes)
            min_size = min(all_sizes)
            if body_size and max_size > body_size * 1.3 and max_size - min_size > 2:
                has_mixed_sizes = True

        if not has_mixed_sizes:
            # No split needed — just attach font metadata
            if all_sizes:
                metadata = elem.get("metadata") or {}
                if isinstance(metadata, dict):
                    metadata["font_sizes"] = all_sizes
                    metadata["font_size"] = max(all_sizes)
                    elem["metadata"] = metadata
            result.append(elem)
            line_index += num_lines
            continue

        # ── Split element by font size changes ────────────────────────
        # Group consecutive lines with similar font size
        current_group: list[str] = []
        current_size: float | None = None
        current_fonts: list[float] = []

        def _flush_group() -> None:
            nonlocal current_group, current_size, current_fonts
            if not current_group:
                return
            group_text = "\n".join(current_group)
            avg_size = sum(current_fonts) / len(current_fonts) if current_fonts else 0

            # Determine if this group is a heading (font >> body)
            is_heading = (
                body_size
                and avg_size > body_size * 1.3
                and avg_size - body_size > 1
            )

            group_meta = {
                "font_size": max(current_fonts) if current_fonts else 0,
                "font_sizes": current_fonts,
            }

            if is_heading:
                level = _heading_level_from_font_ratio(
                    max(current_fonts) if current_fonts else 0,
                    body_size or 11.0,
                )
                result.append(
                    PageElement(
                        type="heading",
                        level=level,
                        content=group_text,
                        rows=None,
                        page_number=elem["page_number"],
                        bbox=None,
                        list_style=None,
                        metadata={
                            **group_meta,
                            "source": "fitz",
                            "detection": "font-size-split",
                        },
                    )
                )
            else:
                result.append(
                    PageElement(
                        type="paragraph",
                        level=None,
                        content=group_text,
                        rows=None,
                        page_number=elem["page_number"],
                        bbox=None,
                        list_style=None,
                        metadata=group_meta,
                    )
                )

            current_group = []
            current_size = None
            current_fonts = []

        for line_idx, line in enumerate(lines):
            font_info = line_fonts[line_idx]
            line_size = font_info["size"] if font_info and font_info["size"] > 0 else 0

            # Check if font size changes significantly (vs current group)
            size_changed = False
            if current_size is not None and line_size > 0:
                ratio = line_size / current_size if current_size > 0 else 1
                if ratio > 1.3 or ratio < 0.7:
                    size_changed = True

            if size_changed and current_group:
                _flush_group()

            current_group.append(line)
            current_size = line_size if line_size > 0 else current_size
            if line_size > 0:
                current_fonts.append(line_size)

        _flush_group()
        line_index += num_lines

    return result


def _heading_level_from_font_ratio(
    font_size: float,
    body_font_size: float,
) -> int:
    """Estimate heading level from font size ratio."""
    if body_font_size <= 0:
        return 3
    ratio = font_size / body_font_size
    if ratio >= 2.5:
        return 1
    elif ratio >= 2.0:
        return 2
    elif ratio >= 1.6:
        return 3
    elif ratio >= 1.3:
        return 4
    elif ratio >= 1.1:
        return 5
    else:
        return 6


def _process_page_plumber(
    pdf_path: Path,
    idx: int,
    page_number: int,
    table_strategy: str,
) -> PageElements:
    """
    Process a page using pdfplumber (full extraction with table support).

    Falls back to PyMuPDF if pdfplumber fails.

    Args:
        pdf_path: Path to the PDF.
        idx: 0-based page index.
        page_number: 1-based page number.
        table_strategy: Table handling strategy.

    Returns:
        List of PageElements for this page.
    """
    import pdfplumber

    try:
        with pdfplumber.open(str(pdf_path)) as plumber_doc:
            if idx < 0 or idx >= len(plumber_doc.pages):
                return [
                    PageElement(
                        type="blank",
                        level=None,
                        content="",
                        rows=None,
                        page_number=page_number,
                        bbox=None,
                        list_style=None,
                        metadata={"warning": "page index out of range"},
                    )
                ]

            pdf_page = plumber_doc.pages[idx]

            # Attempt full extraction with table hints
            try:
                # Collect font size hints (for heading detection)
                font_hints = _collect_font_hints(pdf_page)

                elements = _extract_text_and_elements_plumber(
                    pdf_page,
                    page_number,
                    table_strategy,
                    font_hints=font_hints,
                )

                if elements:
                    # Tag elements with plumber source
                    for elem in elements:
                        if elem["metadata"] is None:
                            elem["metadata"] = {}
                        elem["metadata"]["source"] = "pdfplumber"

                    return elements

            except Exception:
                # pdfplumber failed → fall through to fitz
                pass

    except Exception as exc:
        warnings.warn(f"pdfplumber failed on page {page_number}: {exc}")

    # Fallback: PyMuPDF
    return _process_page_fast(pdf_path, idx, page_number, table_strategy)


def _collect_font_hints(pdf_page: Any) -> dict[str, Any]:
    """
    Collect font size/weight information from a pdfplumber page for heading detection.

    Args:
        pdf_page: A pdfplumber ``Page`` object.

    Returns:
        Dict with font size distribution, or empty dict if unavailable.
    """
    hints: dict[str, Any] = {}

    try:
        chars = pdf_page.chars
        if not chars:
            return hints

        font_sizes: list[float] = []
        font_names: set[str] = set()

        for char in chars:
            size = char.get("size", 0)
            if size > 0:
                font_sizes.append(size)
            font_name = char.get("fontname", "")
            if font_name:
                font_names.add(font_name)

        if font_sizes:
            hints["all_font_sizes"] = sorted(font_sizes)
            hints["max_font_size"] = max(font_sizes)
            hints["min_font_size"] = min(font_sizes)
            hints["avg_font_size"] = sum(font_sizes) / len(font_sizes)

            # Estimate body font size (most common size)
            from collections import Counter

            size_counter = Counter(font_sizes)
            hints["body_font_size"] = size_counter.most_common(1)[0][0]

        hints["font_names"] = list(font_names)

    except Exception:
        pass

    return hints
