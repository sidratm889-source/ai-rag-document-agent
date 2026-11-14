import re
from dataclasses import dataclass

from app.rag.chunker import chunk_text
from app.rag.loader import ExtractedPage


@dataclass(frozen=True)
class StructuredChunk:
    page_number: int | None
    section_heading: str | None
    text: str


def is_heading_candidate(lines: list[str], index: int) -> bool:
    value = lines[index].strip()
    if not value or len(value) > 100:
        return False

    words = value.split()
    if len(words) > 12 or value.endswith((".", "!", "?", ";")):
        return False
    if value.startswith(("-", "*", "•")):
        return False
    if ":" in value and value.split(":", 1)[1].strip():
        return False

    letters = [character for character in value if character.isalpha()]
    if not letters:
        return False

    if re.match(r"^\d+(?:\.\d+)*[.)]?\s+\S", value):
        return True

    if all(character.isupper() for character in letters):
        return True

    title_words = [
        word for word in words
        if any(character.isalpha() for character in word)
    ]
    title_case = bool(title_words) and all(
        word[0].isupper() for word in title_words
    )
    if title_case:
        return True

    previous_is_blank = index == 0 or not lines[index - 1].strip()
    next_is_blank = index == len(lines) - 1 or not lines[index + 1].strip()
    return len(words) <= 5 and previous_is_blank and next_is_blank


def structure_document_pages(
    pages: list[ExtractedPage],
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[StructuredChunk]:
    structured_chunks = []
    active_heading = None

    for page in pages:
        lines = page.text.splitlines(keepends=True)
        section_lines = []

        def flush_section() -> None:
            section_text = "".join(section_lines)
            for chunk in chunk_text(section_text, chunk_size, overlap):
                structured_chunks.append(
                    StructuredChunk(
                        page_number=page.page_number,
                        section_heading=active_heading,
                        text=chunk,
                    )
                )
            section_lines.clear()

        for index, line in enumerate(lines):
            if is_heading_candidate(lines, index):
                flush_section()
                active_heading = line.strip()
            section_lines.append(line)

        flush_section()

    return structured_chunks
