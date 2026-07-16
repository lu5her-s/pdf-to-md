"""
Text cleaning engine for pdf_to_md.

Provides heuristic-based cleaning: page number removal, header/footer
detection, hyphenation rejoining, whitespace collapsing, and unicode
normalization. Operates on ``PageElements`` lists.

Designed to be **conservative** — better to leave content in than
remove legit text (opt-in with ``--clean`` flag).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any

from pdf_to_md.parser import PageElement, PageElements

# ── Constants ─────────────────────────────────────────────────────────────────
HEADER_FOOTER_MIN_PAGES = 5
"""Minimum number of pages before text is considered a running header/footer."""

RUNNING_HEAD_TOP_RATIO = 0.2
"""Portion of elements from the top to consider as potential header zone."""

RUNNING_HEAD_BOTTOM_RATIO = 0.2
"""Portion of elements from the bottom to consider as potential footer zone."""


# ── Public API ────────────────────────────────────────────────────────────────


def clean_content(
    elements: PageElements,
    remove_headers: bool = True,
    remove_footers: bool = True,
    remove_page_numbers: bool = True,
    collapse_whitespace: bool = True,
    rejoin_hyphens: bool = True,
    strip_non_printable: bool = True,
    hf_profile: dict[str, Any] | None = None,
    page_number: int = 0,
    total_pages: int = 0,
) -> PageElements:
    """
    Clean a list of PageElements for a single page.

    Args:
        elements: Page elements to clean.
        remove_headers: Remove detected headers.
        remove_footers: Remove detected footers.
        remove_page_numbers: Remove standalone page numbers.
        collapse_whitespace: Collapse excessive blank lines.
        rejoin_hyphens: Rejoin hyphenated words across line breaks.
        strip_non_printable: Strip zero-width and non-printable chars.
        hf_profile: Optional header/footer profile built by
            ``build_header_footer_profile()``. If ``None``, only per-page
            heuristics are used.
        page_number: 1-based page number (for profile matching).
        total_pages: Total pages in the document (for profile matching).

    Returns:
        Cleaned page elements.
    """
    cleaned: PageElements = []

    for elem in elements:
        elem_type = elem["type"]
        content = elem["content"]

        # ── Page number removal ──────────────────────────────────────────
        if remove_page_numbers and elem_type == "paragraph":
            stripped = content.strip()
            # Pattern: just a number
            if re.match(r"^\d+$", stripped):
                continue
            # Pattern: "Page N of M"
            if re.match(r"^Page\s+\d+\s+of\s+\d+$", stripped, re.IGNORECASE):
                continue
            # Pattern: "- N -" or "— N —" (common page number styling)
            if re.match(r"^[\-\—]\s*\d+\s*[\-\—]$", stripped):
                continue
            # Pattern: "N | Page" or similar
            if re.match(r"^\d+\s*\|\s*Page$", stripped, re.IGNORECASE):
                continue

        # ── Header/footer removal (via profile) ─────────────────────────
        if hf_profile and (remove_headers or remove_footers):
            if _is_header_or_footer(
                elem, hf_profile, page_number, total_pages
            ):
                continue

        # ── Strip non-printable characters ──────────────────────────────
        if strip_non_printable:
            content = re.sub(
                r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b\u200c\u200d\ufeff]",
                "",
                content,
            )
            # Strip soft hyphens (U+00AD) but mark for rejoining
            content = content.replace("\u00ad", "")

        # ── Rejoin hyphenated words ─────────────────────────────────────
        if rejoin_hyphens:
            content = _rejoin_hyphenated_words(content)

        # ── Unicode normalization ───────────────────────────────────────
        content = unicodedata.normalize("NFC", content)

        # Update element content
        elem["content"] = content
        cleaned.append(elem)

    # ── Collapse whitespace ─────────────────────────────────────────────
    if collapse_whitespace:
        cleaned = _collapse_whitespace(cleaned)

    return cleaned


def build_header_footer_profile(
    all_pages_elements: list[PageElements],
    min_page_threshold: int = HEADER_FOOTER_MIN_PAGES,
) -> dict[str, Any]:
    """
    Build a profile of likely headers, footers, and running heads by
    analyzing element repetition across pages.

    Uses two approaches:
    1. **Position-based**: Elements consistently at the top/bottom of pages.
    2. **Content-based**: Text that repeats verbatim across 5+ pages.

    Args:
        all_pages_elements: List of ``PageElements``, one per page,
            in page order.
        min_page_threshold: Minimum pages before qualifying as header/footer.

    Returns:
        Profile dict with keys:
        - ``"headers"``: list of ``(text, page_numbers)`` for header candidates.
        - ``"footers"``: list of ``(text, page_numbers)`` for footer candidates.
        - ``"running_heads"``: list of ``(text, page_numbers)`` for running heads.
        - ``"all_header_texts"``: set of all unique header-like texts (for fast lookup).
        - ``"all_footer_texts"``: set of all unique footer-like texts (for fast lookup).
    """
    profile: dict[str, Any] = {
        "headers": [],
        "footers": [],
        "running_heads": [],
        "all_header_texts": set(),
        "all_footer_texts": set(),
    }

    if not all_pages_elements or len(all_pages_elements) < min_page_threshold:
        return profile

    num_pages = len(all_pages_elements)

    # ── Collect top/bottom candidates per page ──────────────────────────
    # top_candidates[pagenum] = [text, text, ...]  (first few elements)
    # bottom_candidates[pagenum] = [text, text, ...]  (last few elements)
    top_candidates: dict[int, list[str]] = {}
    bottom_candidates: dict[int, list[str]] = {}
    all_top_texts: list[tuple[int, str]] = []  # (page_num, text)
    all_bottom_texts: list[tuple[int, str]] = []

    for page_idx, elements in enumerate(all_pages_elements):
        page_num = page_idx + 1
        if not elements:
            continue

        # Flatten elements into text lines for line-level analysis.
        # This is critical when the profile is built from fitz text
        # extraction (one big element per page).
        all_lines: list[str] = []
        for elem in elements:
            content = elem.get("content", "") or ""
            if content:
                all_lines.extend(content.split("\n"))

        # Filter blank/short lines
        meaningful = [l.strip() for l in all_lines if l.strip() and len(l.strip()) > 3]

        if not meaningful:
            continue

        top_count = max(1, int(len(meaningful) * RUNNING_HEAD_TOP_RATIO))
        bottom_count = max(1, int(len(meaningful) * RUNNING_HEAD_BOTTOM_RATIO))

        top_lines = meaningful[:top_count]
        bottom_lines = meaningful[-bottom_count:] if bottom_count < len(meaningful) else []

        for t in top_lines:
            all_top_texts.append((page_num, t))

        for t in bottom_lines:
            all_bottom_texts.append((page_num, t))

        if top_lines:
            top_candidates[page_num] = top_lines
        if bottom_lines:
            bottom_candidates[page_num] = bottom_lines

    # ── Find repeated text in top positions (headers) ──────────────────
    header_text_page_map: dict[str, list[int]] = defaultdict(list)
    for page_num, text in all_top_texts:
        header_text_page_map[text].append(page_num)

    for text, pages in header_text_page_map.items():
        if len(pages) >= min_page_threshold:
            profile["headers"].append((text, sorted(pages)))
            profile["all_header_texts"].add(text)

    # ── Find repeated text in bottom positions (footers) ────────────────
    footer_text_page_map: dict[str, list[int]] = defaultdict(list)
    for page_num, text in all_bottom_texts:
        footer_text_page_map[text].append(page_num)

    for text, pages in footer_text_page_map.items():
        if len(pages) >= min_page_threshold:
            profile["footers"].append((text, sorted(pages)))
            profile["all_footer_texts"].add(text)

    # ── Running head detection (positional consistency) ────────────────
    # Running heads are typically single-line text at the very top of the page
    # that appears on every page (or most pages). They're usually chapter
    # titles or document names.
    running_head_candidates: dict[str, list[int]] = defaultdict(list)
    for page_num, text in all_top_texts:
        # Running heads are usually the FIRST element on a page
        if page_num in top_candidates:
            first_texts = top_candidates[page_num]
            if first_texts and first_texts[0] == text:
                running_head_candidates[text].append(page_num)

    for text, pages in running_head_candidates.items():
        if len(pages) >= min_page_threshold:
            # Check it's not already a header
            if text not in profile["all_header_texts"]:
                profile["running_heads"].append((text, sorted(pages)))

    return profile


# ── Internal Helpers ──────────────────────────────────────────────────────────


def _is_header_or_footer(
    elem: PageElement,
    hf_profile: dict[str, Any],
    page_number: int,
    total_pages: int,
) -> bool:
    """
    Check if an element matches the header/footer profile.

    Args:
        elem: Page element to check.
        hf_profile: Profile from ``build_header_footer_profile()``.
        page_number: 1-based page number.
        total_pages: Total pages in the document.

    Returns:
        ``True`` if the element should be removed.
    """
    content = elem["content"].strip()

    if not content:
        return False

    # Quick check: is this text in our header/footer set?
    if content in hf_profile.get("all_header_texts", set()):
        return True
    if content in hf_profile.get("all_footer_texts", set()):
        return True

    # Check running heads
    for text, pages in hf_profile.get("running_heads", []):
        if content == text:
            return True

    # Edge case: first page often doesn't have headers
    # Last pages may not have footers
    # Our profile handles this via page-specific matching

    return False


def _rejoin_hyphenated_words(text: str) -> str:
    """
    Rejoin words split by hyphens across line breaks.

    Handles:
    - Regular hyphens: ``word-\\n(word)`` → ``wordword``
    - Soft hyphens (U+00AD): already stripped above

    Args:
        text: Input text.

    Returns:
        Text with rejoined hyphenated words.
    """
    # Pattern: word-\nword → rejoin
    # Only if hyphen is followed by newline and then more word chars
    text = re.sub(
        r"(\w)-\n(\w)",
        lambda m: _rejoin_if_plausible(m.group(1), m.group(2)),
        text,
    )

    return text


def _rejoin_if_plausible(part1: str, part2: str) -> str:
    """
    Decide whether to rejoin two parts of a hyphenated word.

    Checks that the result is plausible: length > 2 and no doubled letters
    that suggest a compound word.

    Args:
        part1: First part (before hyphen).
        part2: Second part (after hyphen).

    Returns:
        Joined word or original with hyphen if compound.
    """
    joined = part1 + part2

    # If the joined word is too short, keep hyphen
    if len(joined) < 3:
        return f"{part1}-\n{part2}"

    # Check if it's a known compound word (ends with hyphen-pattern)
    # e.g., "well-known", "up-to-date"
    known_compounds: set[str] = {
        "well-known", "up-to-date", "down-to-earth", "part-time",
        "full-time", "high-level", "low-level", "decision-making",
        "state-of-the-art", "user-friendly", "real-world", "long-term",
        "short-term", "best-known", "first-hand", "second-hand",
        "all-in-one", "hands-on", "built-in", "in-depth",
    }
    if joined in known_compounds:
        return f"{part1}-{part2}"

    # If the hyphen was part of a compound (both parts > 3 chars),
    # keep it
    if len(part1) > 3 and len(part2) > 3:
        # Double letter at boundary suggests compound
        if part1[-1] == part2[0]:
            return f"{part1}-\n{part2}"

    return joined


def _collapse_whitespace(elements: PageElements) -> PageElements:
    """
    Collapse excessive whitespace — max 2 consecutive blank elements.

    Args:
        elements: Page elements to process.

    Returns:
        Elements with collapsed whitespace.
    """
    result: PageElements = []
    blank_count = 0

    for elem in elements:
        if elem["type"] == "blank":
            blank_count += 1
            if blank_count <= 2:
                result.append(elem)
        else:
            blank_count = 0
            result.append(elem)

    return result


def remove_page_numbers(
    elements: PageElements,
) -> PageElements:
    """
    Remove standalone page numbers from elements.

    Args:
        elements: Page elements to process.

    Returns:
        Elements with page numbers removed.
    """
    return [
        elem
        for elem in elements
        if not (
            elem["type"] == "paragraph"
            and re.match(
                r"^(?:\d+|Page\s+\d+\s+of\s+\d+|[\-\—]\s*\d+\s*[\-\—])$",
                elem["content"].strip(),
                re.IGNORECASE,
            )
        )
    ]


def normalize_unicode(elements: PageElements) -> PageElements:
    """
    Normalize all text content to NFC form.

    Args:
        elements: Page elements to normalize.

    Returns:
        Elements with NFC-normalized text.
    """
    for elem in elements:
        if elem["content"]:
            elem["content"] = unicodedata.normalize("NFC", elem["content"])
        rows = elem.get("rows")
        if rows:
            elem["rows"] = [
                [unicodedata.normalize("NFC", cell or "") for cell in row]
                for row in rows
            ]
    return elements


def strip_control_characters(text: str) -> str:
    """
    Strip control characters and zero-width/invisible Unicode characters.

    Removes:
    - ASCII control chars (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F)
    - Zero-width space (U+200B)
    - Zero-width non-joiner (U+200C)
    - Zero-width joiner (U+200D)
    - Byte order mark / BOM (U+FEFF)
    - Soft hyphen (U+00AD)

    Args:
        text: Input string.

    Returns:
        Cleaned string.
    """
    text = re.sub(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b\u200c\u200d\ufeff\u00ad]",
        "",
        text,
    )
    return text
