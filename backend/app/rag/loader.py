
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int | None
    text: str


def extract_pages_from_pdf(file_path: str) -> list[ExtractedPage]:
    try:
        reader = PdfReader(file_path, strict=True)
        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()
            pages.append(
                ExtractedPage(page_number, page_text or "")
            )
        return pages

    except (PdfReadError, OSError, ValueError) as error:
        raise ValueError("Could not read this PDF file.") from error


def extract_text_from_pdf(file_path: str) -> str:
    return "\n".join(
        page.text
        for page in extract_pages_from_pdf(file_path)
        if page.text
    ).strip()


def validate_extracted_pages(
    pages: list[ExtractedPage],
) -> list[ExtractedPage]:
    if not isinstance(pages, list) or not all(
        isinstance(page, ExtractedPage) for page in pages
    ):
        raise ValueError("Extracted PDF pages are invalid.")

    if not any(page.text.strip() for page in pages):
        raise ValueError("No readable text was found in this PDF.")

    return pages


def validate_extracted_text(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("Extracted PDF text must be a string.")

    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "No readable text was found in this PDF."
        )

    return cleaned_text
