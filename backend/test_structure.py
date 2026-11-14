from app.rag.loader import ExtractedPage
from app.rag.structure import structure_document_pages


def test_detects_headings_from_distinct_document_layouts():
    pages = [
        ExtractedPage(
            1,
            "SKILLS\nPython and SQL.\n",
        ),
        ExtractedPage(
            2,
            "Invoice Details\nInvoice number: A-104.\nTotal: $86.\n",
        ),
        ExtractedPage(
            3,
            "2. Methodology\nThe study used a controlled trial.\n",
        ),
        ExtractedPage(
            4,
            "Revenue Overview\nRevenue was $120,000.\n",
        ),
    ]

    chunks = structure_document_pages(pages)

    assert [chunk.section_heading for chunk in chunks] == [
        "SKILLS",
        "Invoice Details",
        "2. Methodology",
        "Revenue Overview",
    ]
    assert [chunk.page_number for chunk in chunks] == [1, 2, 3, 4]
    assert "Invoice number: A-104." in chunks[1].text
    assert "The study used a controlled trial." in chunks[2].text


def test_unheaded_text_is_preserved_without_inventing_a_section():
    source = (
        "This document contains a plain paragraph without a heading.\n"
        "The original wording remains available for retrieval."
    )

    chunks = structure_document_pages([ExtractedPage(7, source)])

    assert len(chunks) == 1
    assert chunks[0].page_number == 7
    assert chunks[0].section_heading is None
    assert chunks[0].text == source


def test_section_context_continues_across_pages_without_repeating_heading():
    pages = [
        ExtractedPage(1, "Experimental Results\nFirst observation.\n"),
        ExtractedPage(2, "Second observation.\n"),
    ]

    chunks = structure_document_pages(pages)

    assert [chunk.section_heading for chunk in chunks] == [
        "Experimental Results",
        "Experimental Results",
    ]
    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert chunks[1].text == "Second observation."


def test_heading_detection_keeps_label_value_lines_in_the_current_section():
    page = ExtractedPage(
        1,
        (
            "SKILLS\n"
            "FRONTEND: React and Next.js.\n"
            "BACKEND: Python and FastAPI.\n"
            "DATABASE: PostgreSQL.\n"
        ),
    )

    chunks = structure_document_pages([page])

    assert len(chunks) == 1
    assert chunks[0].section_heading == "SKILLS"
    assert "FRONTEND: React and Next.js." in chunks[0].text
    assert "DATABASE: PostgreSQL." in chunks[0].text


def test_chunking_preserves_non_whitespace_source_characters():
    source = "alpha beta gamma delta epsilon " * 20

    chunks = structure_document_pages(
        [ExtractedPage(1, source)],
        chunk_size=40,
        overlap=8,
    )

    reconstructed = " ".join(chunk.text for chunk in chunks)
    for token in source.split():
        assert token in reconstructed
