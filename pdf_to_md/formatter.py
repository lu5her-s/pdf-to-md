"""
Markdown formatting engine for pdf_to_md.

Converts ``PageElements`` into Markdown strings. Handles heading detection,
paragraph formatting, table formatting (GFM), list detection, and image
placeholder comments.

Also performs secondary heading detection: paragraphs with font-size
metadata from pdfplumber are re-classified as headings when font size
significantly exceeds the body text size.
"""

from __future__ import annotations

import re
from typing import Any

from pdf_to_md.parser import PageElement, PageElements

# ── Font-size based heading thresholds ────────────────────────────────────────
HEADING_FONT_MULTIPLIER = 1.3
"""
A font size this many times larger than the estimated body size is
considered a heading.
"""

HEADING_MIN_FONT_SIZE_DIFF = 2.0
"""
Minimum absolute difference in points between element font and body font
to be considered a heading.
"""


def to_markdown(
    elements: PageElements,
    heading_detection: bool = True,
    table_strategy: str = "markdown",
    preserve_layout: bool = False,
    body_font_size: float | None = None,
) -> str:
    """
    Convert a list of PageElements into a Markdown string for one page.

    Args:
        elements: Page elements to format.
        heading_detection: If ``True``, render headings with ``#`` prefix
            and perform secondary font-based heading detection.
        table_strategy: ``"markdown"`` (GFM tables), ``"skip"``, or ``"simple"``.
        preserve_layout: If ``True``, keep original line breaks.
        body_font_size: Estimated body font size (passed from parser).
            Used for font-size based heading detection.

    Returns:
        Markdown-formatted string.
    """
    parts: list[str] = []

    # ── Secondary heading detection ──────────────────────────────────────
    # Scan paragraphs with font metadata and re-classify as headings
    # if font size suggests heading.
    processed = _preprocess_headings(
        elements, heading_detection, body_font_size
    )

    for elem in processed:
        md = _element_to_markdown(
            elem,
            heading_detection=heading_detection,
            table_strategy=table_strategy,
            preserve_layout=preserve_layout,
        )
        if md:
            parts.append(md)

    return "\n\n".join(parts)


def _preprocess_headings(
    elements: PageElements,
    heading_detection: bool,
    body_font_size: float | None,
) -> PageElements:
    """
    Secondary heading detection pass.

    Examines paragraph elements that have font-size metadata and
    re-classifies them as headings if the font size significantly
    exceeds the body text size.

    Args:
        elements: Original page elements.
        heading_detection: Whether heading detection is enabled.
        body_font_size: Estimated body font size.

    Returns:
        Elements with re-classified headings.
    """
    if not heading_detection or body_font_size is None:
        return elements

    result: PageElements = []

    for elem in elements:
        if elem["type"] == "paragraph":
            metadata = elem.get("metadata") or {}
            font_size = _get_font_size_from_metadata(metadata)

            if font_size is not None and font_size > 0:
                if _is_heading_by_font_size(font_size, body_font_size):
                    # Re-classify as heading
                    level = _heading_level_from_font(
                        font_size, body_font_size
                    )
                    new_elem: PageElement = PageElement(
                        type="heading",
                        level=level,
                        content=elem["content"],
                        rows=elem.get("rows"),
                        page_number=elem["page_number"],
                        bbox=elem.get("bbox"),
                        list_style=elem.get("list_style"),
                        metadata={
                            **(metadata or {}),
                            "detection": "font-size",
                            "original_type": "paragraph",
                            "font_size": font_size,
                            "body_font_size": body_font_size,
                        },
                    )
                    result.append(new_elem)
                    continue

        result.append(elem)

    return result


def _get_font_size_from_metadata(metadata: dict[str, Any]) -> float | None:
    """
    Extract the most representative font size from element metadata.

    Args:
        metadata: Element metadata dict.

    Returns:
        Font size in points, or ``None`` if unavailable.
    """
    # Direct font_size from pdfplumber char analysis
    if "font_size" in metadata:
        return float(metadata["font_size"])

    # Font size array — use max (headings tend to have biggest size)
    if "font_sizes" in metadata and metadata["font_sizes"]:
        sizes = metadata["font_sizes"]
        if isinstance(sizes, (list, tuple)) and sizes:
            return float(max(sizes))

    # Font name may imply heading (e.g., "Bold" in name)
    font_name = metadata.get("font_name", "")
    if font_name and ("Bold" in font_name or "Heading" in font_name):
        return 999.0  # sentinel: definitely a heading

    return None


def _is_heading_by_font_size(
    font_size: float, body_font_size: float
) -> bool:
    """
    Determine if a font size indicates a heading compared to body text.

    Args:
        font_size: Element's font size.
        body_font_size: Estimated body font size.

    Returns:
        ``True`` if the element appears to be a heading.
    """
    # Headings are typically larger than body text
    if font_size <= body_font_size:
        return False

    # Check ratio threshold
    ratio = font_size / body_font_size if body_font_size > 0 else 1.0
    if ratio >= HEADING_FONT_MULTIPLIER:
        return True

    # Check absolute difference
    if font_size - body_font_size >= HEADING_MIN_FONT_SIZE_DIFF:
        return True

    return False


def _heading_level_from_font(
    font_size: float, body_font_size: float
) -> int:
    """
    Estimate heading level from font size relative to body text.

    Args:
        font_size: Element's font size.
        body_font_size: Estimated body font size.

    Returns:
        Heading level (1-6).
    """
    if body_font_size <= 0:
        return 3  # default

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


def _element_to_markdown(
    elem: PageElement,
    heading_detection: bool,
    table_strategy: str,
    preserve_layout: bool,
) -> str:
    """Convert a single PageElement to Markdown."""
    elem_type = elem["type"]
    content = elem["content"]
    level = elem.get("level")
    rows = elem.get("rows")
    list_style = elem.get("list_style")

    if elem_type == "blank":
        return ""

    if elem_type == "heading":
        if heading_detection and level is not None:
            prefix = "#" * min(level, 6)
            # Ensure space after heading markers
            return f"{prefix} {content}"
        else:
            # Flat text — bold as pseudo-heading
            return f"**{content}**"

    if elem_type == "paragraph":
        if preserve_layout:
            return content
        # Normal paragraph: reflow lines
        lines = content.split("\n")
        # Remove empty lines
        lines = [l for l in lines if l.strip()]
        if not lines:
            return ""
        # Single paragraph: merge into one line
        merged = " ".join(lines)
        # Clean up excessive spaces within the paragraph
        merged = re.sub(r" {2,}", " ", merged)
        return merged

    if elem_type == "list":
        # Already formatted in parser
        # Ensure proper list formatting with consistent markup
        if list_style == "ordered":
            # Replace generic "- " with "1. " etc if needed
            return content
        return content

    if elem_type == "table":
        if table_strategy == "skip":
            return ""
        if table_strategy == "simple":
            # Tab-separated inline
            if rows:
                return "\n".join(
                    "\t".join(cell or "" for cell in row) for row in rows
                )
            return content
        # "markdown" strategy — GFM tables
        if rows:
            return _format_table_gfm(rows)
        return content

    if elem_type == "image":
        # Metadata comment (images not extracted)
        meta = elem.get("metadata") or {}
        bbox_str = ""
        if elem.get("bbox"):
            bbox_str = f", bbox={elem['bbox']}"
        return (
            f"<!-- image: page={elem['page_number']}{bbox_str} -->"
        )

    return content


def _format_table_gfm(rows: list[list[str]]) -> str:
    """
    Format table rows as GitHub-Flavored Markdown.

    Args:
        rows: List of rows, each row is a list of cell strings.

    Returns:
        GFM table string.
    """
    if not rows:
        return ""

    # Normalize column count
    num_cols = max(len(row) for row in rows)

    # Pad rows to same column count
    normalized: list[list[str]] = []
    for row in rows:
        padded = list(row) + [""] * (num_cols - len(row))
        normalized.append(padded)

    # Compute column widths
    col_widths = [
        max(len(cell or "") for cell in col)
        for col in zip(*normalized)
    ]

    lines: list[str] = []

    # Header row
    header = "| " + " | ".join(
        (normalized[0][i] or "").ljust(col_widths[i])
        for i in range(num_cols)
    ) + " |"
    lines.append(header)

    # Separator row
    sep = "| " + " | ".join("-" * col_widths[i] for i in range(num_cols)) + " |"
    lines.append(sep)

    # Data rows
    for row in normalized[1:]:
        data = "| " + " | ".join(
            (row[i] or "").ljust(col_widths[i])
            for i in range(num_cols)
        ) + " |"
        lines.append(data)

    return "\n".join(lines) + "\n"


def format_heading(text: str, level: int = 1) -> str:
    """Format a heading string."""
    level = max(1, min(6, level))
    return f"{'#' * level} {text}"


def format_paragraph(text: str) -> str:
    """Format a paragraph."""
    return text.strip()


def format_list(items: list[str], ordered: bool = False) -> str:
    """Format a list."""
    if ordered:
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
    return "\n".join(f"- {item}" for item in items)


def estimate_body_font_size(elements: PageElements) -> float | None:
    """
    Estimate the body text font size from a page's elements.

    Uses the most common font size among paragraph elements.

    Args:
        elements: Page elements to analyze.

    Returns:
        Estimated body font size in points, or ``None`` if unknown.
    """
    font_sizes: list[float] = []

    for elem in elements:
        metadata = elem.get("metadata") or {}
        fs = _get_font_size_from_metadata(metadata)
        if fs is not None and fs > 0:
            font_sizes.append(fs)

    if not font_sizes:
        return None

    from collections import Counter

    size_counter = Counter(font_sizes)
    # Return the most common size (likely body text)
    return size_counter.most_common(1)[0][0]
