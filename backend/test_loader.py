
from unittest.mock import MagicMock, patch

import pytest
from app.rag.loader import (
    ExtractedPage,
    extract_pages_from_pdf,
    extract_text_from_pdf,
    validate_extracted_pages,
    validate_extracted_text,
)


def test_extracts_text_from_all_pages():
    fake_reader = MagicMock()
    fake_reader.pages = [
        MagicMock(),
        MagicMock(),
    ]
    fake_reader.pages[0].extract_text.return_value = "First page"
    fake_reader.pages[1].extract_text.return_value = "Second page"

    with patch("app.rag.loader.PdfReader", return_value=fake_reader):
        result = extract_text_from_pdf("sample.pdf")

    assert result == "First page\nSecond page"


def test_extracts_page_numbers_without_flattening_page_boundaries():
    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock(), MagicMock()]
    fake_reader.pages[0].extract_text.return_value = "First page"
    fake_reader.pages[1].extract_text.return_value = "Second page"

    with patch("app.rag.loader.PdfReader", return_value=fake_reader):
        pages = extract_pages_from_pdf("sample.pdf")

    assert pages == [
        ExtractedPage(page_number=1, text="First page"),
        ExtractedPage(page_number=2, text="Second page"),
    ]


def test_rejects_unreadable_pdf():
    with patch(
        "app.rag.loader.PdfReader",
        side_effect=ValueError("Invalid PDF")
    ):
        with pytest.raises(ValueError, match="Could not read this PDF file"):
            extract_text_from_pdf("broken.pdf")


def test_returns_empty_string_for_pdf_without_text():
    fake_reader = MagicMock()
    fake_reader.pages = [MagicMock()]
    fake_reader.pages[0].extract_text.return_value = None

    with patch("app.rag.loader.PdfReader", return_value=fake_reader):
        result = extract_text_from_pdf("scanned.pdf")

    assert result == ""

def test_validates_and_cleans_extracted_text():
    result = validate_extracted_text("  Restaurant opens at 10 AM  ")

    assert result == "Restaurant opens at 10 AM"


def test_rejects_empty_extracted_text():
    with pytest.raises(
        ValueError,
        match="No readable text was found"
    ):
        validate_extracted_text("   ")


def test_rejects_non_string_text():
    with pytest.raises(ValueError, match="must be a string"):
        validate_extracted_text(None)


def test_validates_pages_but_rejects_image_only_content():
    pages = [ExtractedPage(page_number=1, text="  "), ExtractedPage(2, "Text")]
    assert validate_extracted_pages(pages) == pages

    with pytest.raises(ValueError, match="No readable text"):
        validate_extracted_pages([ExtractedPage(1, "")])
