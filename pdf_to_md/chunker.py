"""
Chunking engine for pdf_to_md.

Splits markdown output into bounded chunks using natural break priorities:
headings → paragraphs → sentences → character-level hard cut.

Designed for RAG ingestion and LLM context window limits.
"""

from __future__ import annotations

import re
from typing import TypedDict

WARNING_HARD_CUT = "<!-- WARNING: chunk truncated at character boundary -->"


class Chunk(TypedDict):
    """A single chunk of markdown content with metadata."""

    id: int
    """Chunk sequence number (1-based)."""
    heading: str | None
    """Section heading from the chunk (if any)."""
    content: str
    """Markdown content of this chunk."""
    page_range: tuple[int, int]
    """(start_page, end_page) — provenance for RAG citation."""
    char_count: int
    """Character count of this chunk."""


def chunk_content(
    markdown: str,
    chunk_size: int = 2000,
    page_range: tuple[int, int] = (0, 0),
) -> list[Chunk]:
    """
    Split markdown content into chunks using natural break priority.

    Priority order:
    1. **Headings** — each heading + its content = candidate chunk
    2. **Paragraphs** — double newline breaks
    3. **Sentences** — ``.!?`` boundaries
    4. **Hard cut** — character-level split (with warning comment)

    Args:
        markdown: Full markdown string.
        chunk_size: Maximum characters per chunk (default: 2000).
        page_range: Overall ``(start_page, end_page)`` for provenance.

    Returns:
        List of ``Chunk`` dicts.
    """
    if not markdown or not markdown.strip():
        return []

    chunks: list[Chunk] = []
    page_start, page_end = page_range

    # ── Phase 1: Split by headings ──────────────────────────────────────
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    # Find all heading positions
    heading_matches = list(heading_pattern.finditer(markdown))

    if not heading_matches:
        # No headings — split by paragraphs
        return _chunk_by_paragraphs(
            markdown, chunk_size, page_range, start_id=1
        )

    # Split into sections by heading
    # IMPORTANT: Content before the first heading must be preserved
    sections: list[tuple[str | None, str]] = []  # (heading_text, content)

    # ── Pre-heading content ─────────────────────────────────────────────
    first_heading_start = heading_matches[0].start()
    if first_heading_start > 0:
        pre_content = markdown[:first_heading_start].strip()
        if pre_content:
            sections.append((None, pre_content))

    # ── Heading sections ────────────────────────────────────────────────
    for i, match in enumerate(heading_matches):
        heading_text = match.group(2).strip()
        start = match.end()

        if i + 1 < len(heading_matches):
            end = heading_matches[i + 1].start()
        else:
            end = len(markdown)

        section_content = markdown[start:end].strip()
        sections.append((heading_text, section_content))

    # ── Phase 2: Build chunks from sections ────────────────────────────
    chunk_id = 1
    current_chunk_content: list[str] = []
    current_heading: str | None = None
    current_page_start = page_start

    def _flush_chunk() -> None:
        """Flush current chunk buffer."""
        nonlocal chunk_id, current_chunk_content, current_heading, current_page_start

        if not current_chunk_content:
            return

        content = "\n\n".join(current_chunk_content)
        chunks.append(
            Chunk(
                id=chunk_id,
                heading=current_heading,
                content=content,
                page_range=(current_page_start, page_end),
                char_count=len(content),
            )
        )
        chunk_id += 1
        current_chunk_content = []
        current_heading = None
        current_page_start = page_end  # Reset page tracking

    for heading_text, section_content in sections:
        # If this section alone exceeds chunk_size, split it further
        if len(section_content) > chunk_size:
            # Flush any pending content first
            _flush_chunk()

            # Set heading for this sub-chunking
            current_heading = heading_text

            # Sub-split this section
            sub_chunks = _chunk_by_paragraphs(
                section_content,
                chunk_size,
                page_range,
                start_id=chunk_id,
            )
            chunks.extend(sub_chunks)
            chunk_id += len(sub_chunks)

            # Reset after extending
            current_heading = None
            current_chunk_content = []
        else:
            # Natural break: each heading is a chunk boundary
            # 1. Pre-heading content → flush before first heading
            if (
                heading_text is not None
                and current_chunk_content
                and current_heading is None
            ):
                _flush_chunk()

            # 2. New heading → flush previous heading's section
            if (
                heading_text is not None
                and current_heading is not None
                and current_chunk_content
            ):
                _flush_chunk()

            # Check if adding this section would exceed chunk_size
            temp_content = "\n\n".join(
                current_chunk_content + [section_content]
            )
            if len(temp_content) > chunk_size and current_chunk_content:
                _flush_chunk()

            if current_heading is None and heading_text is not None:
                current_heading = heading_text

            current_chunk_content.append(section_content)

    # Flush remaining
    _flush_chunk()

    return chunks


def _chunk_by_paragraphs(
    text: str,
    chunk_size: int,
    page_range: tuple[int, int],
    start_id: int = 1,
) -> list[Chunk]:
    """
    Split text by paragraph boundaries, respecting chunk_size.

    Falls back to sentence-level and character-level if needed.

    Args:
        text: Text to split.
        chunk_size: Max chars per chunk.
        page_range: (start_page, end_page).
        start_id: Starting chunk ID.

    Returns:
        List of Chunks.
    """
    chunks: list[Chunk] = []
    page_start, page_end = page_range

    # Split by double newline (paragraphs)
    paragraphs = re.split(r"\n\n+", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        return chunks

    chunk_id = start_id
    current_chunk: list[str] = []
    current_len = 0

    def _flush() -> None:
        nonlocal chunk_id, current_chunk, current_len
        if not current_chunk:
            return
        content = "\n\n".join(current_chunk)
        chunks.append(
            Chunk(
                id=chunk_id,
                heading=None,
                content=content,
                page_range=(page_start, page_end),
                char_count=len(content),
            )
        )
        chunk_id += 1
        current_chunk = []
        current_len = 0

    for para in paragraphs:
        para_len = len(para)
        # Account for the "\n\n" separator if not the first item
        sep_cost = 2 if current_chunk else 0

        if current_len + sep_cost + para_len > chunk_size:
            if current_chunk:
                _flush()

            # If single paragraph exceeds chunk_size, sub-split
            if para_len > chunk_size:
                para_chunks = _chunk_by_sentences(
                    para, chunk_size, page_range, chunk_id
                )
                chunks.extend(para_chunks)
                chunk_id += len(para_chunks)
                continue

        current_chunk.append(para)
        current_len += para_len + (2 if len(current_chunk) > 1 else 0)

    _flush()

    return chunks


def _chunk_by_sentences(
    text: str,
    chunk_size: int,
    page_range: tuple[int, int],
    start_id: int = 1,
) -> list[Chunk]:
    """
    Split text by sentence boundaries.

    Falls back to character-level hard cut if a single sentence
    exceeds chunk_size.

    Args:
        text: Text to split.
        chunk_size: Max chars per chunk.
        page_range: (start_page, end_page).
        start_id: Starting chunk ID.

    Returns:
        List of Chunks.
    """
    chunks: list[Chunk] = []
    page_start, page_end = page_range

    # Split by sentence boundaries (., !, ? followed by space or newline)
    # Handle common abbreviations to avoid false splits
    # e.g., "Dr.", "Mr.", "Ms.", "Mrs.", "Prof.", "vs.", "etc."
    sentence_splits = re.split(
        r"(?<=[.!?])(?:(?=\s+[A-Z\"\'(])|(?=\s*$))",
        text,
    )
    # Filter empty and join back fragments if needed
    sentences: list[str] = []
    for s in sentence_splits:
        s = s.strip()
        if s:
            sentences.append(s)

    if not sentences:
        # Fallback: simple split
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

    chunk_id = start_id
    current_chunk: list[str] = []
    current_len = 0

    def _flush() -> None:
        nonlocal chunk_id, current_chunk, current_len
        if not current_chunk:
            return
        content = " ".join(current_chunk)
        chunks.append(
            Chunk(
                id=chunk_id,
                heading=None,
                content=content,
                page_range=(page_start, page_end),
                char_count=len(content),
            )
        )
        chunk_id += 1
        current_chunk = []
        current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)
        sep_cost = 1 if current_chunk else 0  # space separator

        if current_len + sep_cost + sentence_len > chunk_size:
            if current_chunk:
                _flush()

            # Single sentence exceeds chunk_size → hard cut
            if sentence_len > chunk_size:
                hard_chunks = _chunk_hard_cut(
                    sentence, chunk_size, page_range, chunk_id
                )
                chunks.extend(hard_chunks)
                chunk_id += len(hard_chunks)
                continue

        current_chunk.append(sentence)
        current_len += sentence_len + (1 if len(current_chunk) > 1 else 0)

    _flush()

    return chunks


def _chunk_hard_cut(
    text: str,
    chunk_size: int,
    page_range: tuple[int, int],
    start_id: int = 1,
) -> list[Chunk]:
    """
    Hard character-level split when no natural breaks exist.

    Adds a warning comment about truncation.

    Args:
        text: Text to split.
        chunk_size: Max chars per chunk.
        page_range: (start_page, end_page).
        start_id: Starting chunk ID.

    Returns:
        List of Chunks.
    """
    chunks: list[Chunk] = []
    page_start, page_end = page_range

    for i in range(0, len(text), chunk_size):
        segment = text[i : i + chunk_size]

        # Add warning for truncated chunks
        if i + chunk_size < len(text):
            segment = segment + "\n\n" + WARNING_HARD_CUT

        chunks.append(
            Chunk(
                id=start_id + len(chunks),
                heading=None,
                content=segment,
                page_range=(page_start, page_end),
                char_count=len(segment),
            )
        )

    return chunks


def chunk_by_headings(
    markdown: str,
    chunk_size: int = 2000,
) -> list[tuple[str | None, str]]:
    """
    Split markdown by heading boundaries.

    Args:
        markdown: Full markdown string.
        chunk_size: Not used in this function (kept for API consistency).

    Returns:
        List of ``(heading_text, content)`` tuples.
    """
    _ = chunk_size  # API consistency
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(markdown))

    if not matches:
        return [(None, markdown)]

    sections: list[tuple[str | None, str]] = []

    # Preserve pre-heading content
    first_heading_start = matches[0].start()
    if first_heading_start > 0:
        pre_content = markdown[:first_heading_start].strip()
        if pre_content:
            sections.append((None, pre_content))

    for i, match in enumerate(matches):
        heading_text = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        section_content = markdown[start:end].strip()
        sections.append((heading_text, section_content))

    return sections
