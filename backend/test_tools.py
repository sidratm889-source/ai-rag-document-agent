from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.agent.tools import (
    _collect_section_page_texts,
    answer_document_question,
    query_business_data,
    search_document_content,
)
from app.database.models import Conversation, ConversationMessage, Document


def test_search_document_content_validates_question_and_user():
    with pytest.raises(ValueError, match="Question cannot be empty"):
        search_document_content("", user_id=1)
    with pytest.raises(ValueError, match="Question is too long"):
        search_document_content("a" * 1001, user_id=1)
    with pytest.raises(ValueError, match="Invalid user ID"):
        search_document_content("question", user_id=0)


def test_search_document_content_returns_page_and_section_metadata():
    chunk = SimpleNamespace(
        id=91,
        document_id="7",
        chunk_text="Total due: $240.",
        page_number=2,
        section_heading="Payment summary",
    )

    with patch(
        "app.agent.tools.retrieve_relevant_chunks",
        return_value=[chunk],
    ) as retrieve:
        results = search_document_content(
            "What is the total due?",
            user_id=1,
            document_id=7,
        )

    retrieve.assert_called_once_with(
        "What is the total due?",
        user_id=1,
        limit=12,
        document_id=7,
    )
    assert results == [
        {
            "document_id": "7",
            "chunk_id": 91,
            "chunk": "Total due: $240.",
            "page_number": 2,
            "section_heading": "Payment summary",
        }
    ]


def test_query_business_data_rejects_invalid_action_and_user():
    with pytest.raises(ValueError, match="Unsupported business data action"):
        query_business_data("delete_all_data", user_id=1)
    with pytest.raises(ValueError, match="Invalid user ID"):
        query_business_data("document_count", user_id=0)


def test_document_count_returns_user_count():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.scalar.return_value = 5

    with patch("app.agent.tools.SessionLocal", return_value=mock_db):
        result = query_business_data("document_count", user_id=10)

    assert result == {"document_count": 5}
    filter_mock = mock_db.query.return_value.filter
    filter_mock.assert_called_once()
    assert filter_mock.call_args.args[0].compare(Document.user_id == 10)
    mock_db.close.assert_called_once()


def test_document_list_is_scoped_to_user():
    mock_db = MagicMock()
    document = SimpleNamespace(
        id=1,
        filename="report.pdf",
        uploaded_at=None,
    )
    (
        mock_db.query.return_value.filter.return_value
        .order_by.return_value.limit.return_value.all.return_value
    ) = [document]

    with patch("app.agent.tools.SessionLocal", return_value=mock_db):
        result = query_business_data("document_list", user_id=10)

    assert result == {
        "documents": [
            {"id": 1, "filename": "report.pdf", "uploaded_at": None}
        ]
    }
    filter_mock = mock_db.query.return_value.filter
    filter_mock.assert_called_once()
    assert filter_mock.call_args.args[0].compare(Document.user_id == 10)
    mock_db.close.assert_called_once()


def test_message_count_is_scoped_to_user_conversations():
    mock_db = MagicMock()
    (
        mock_db.query.return_value.join.return_value
        .filter.return_value.scalar.return_value
    ) = 12

    with patch("app.agent.tools.SessionLocal", return_value=mock_db):
        result = query_business_data("message_count", user_id=10)

    assert result == {"message_count": 12}
    join_mock = mock_db.query.return_value.join
    join_mock.assert_called_once()
    assert join_mock.call_args.args[0] is Conversation
    assert join_mock.call_args.args[1].compare(
        Conversation.conversation_id == ConversationMessage.conversation_id
    )
    filter_mock = join_mock.return_value.filter
    filter_mock.assert_called_once()
    assert filter_mock.call_args.args[0].compare(Conversation.user_id == 10)
    mock_db.close.assert_called_once()


def test_document_answer_returns_exact_source_with_document_and_page():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        (11, "invoice.pdf"),
    ]
    retrieved = [
        {
            "document_id": "11",
            "chunk": (
                "Invoice number: INV-804.\n"
                "Issue date: 2026-03-02.\n"
                "Total due: $240."
            ),
            "page_number": 2,
            "section_heading": "Payment summary",
        }
    ]

    with patch(
        "app.agent.tools.search_document_content",
        return_value=retrieved,
    ), patch(
        "app.agent.tools.SessionLocal",
        return_value=db,
    ):
        answer = answer_document_question(
            "What is the total due?",
            user_id=1,
        )

    assert answer == (
        "Source: invoice.pdf, page 2, detected section: Payment summary\n"
        "Total due: $240."
    )
    db.close.assert_called_once()


def test_document_answer_keeps_matching_facts_from_distinct_documents_separate():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        (11, "report-a.pdf"),
        (12, "report-b.pdf"),
    ]
    retrieved = [
        {
            "document_id": "11",
            "chunk": "Revenue was $120,000.",
            "page_number": 2,
        },
        {
            "document_id": "12",
            "chunk": "Revenue was $120,000.",
            "page_number": 4,
        },
    ]

    with patch(
        "app.agent.tools.search_document_content",
        return_value=retrieved,
    ), patch(
        "app.agent.tools.SessionLocal",
        return_value=db,
    ):
        answer = answer_document_question(
            "What revenue was stated?",
            user_id=1,
        )

    assert answer == (
        "Source: report-a.pdf, page 2\nRevenue was $120,000.\n\n"
        "Source: report-b.pdf, page 4\nRevenue was $120,000."
    )


def test_document_answer_filters_retrieval_to_selected_document():
    with patch(
        "app.agent.tools.search_document_content",
        return_value=[],
    ) as search:
        answer = answer_document_question(
            "What is the total?",
            user_id=1,
            document_id=20,
        )

    search.assert_called_once_with("What is the total?", 1, 20)
    assert "selected document" in answer
    assert "guessing" in answer


def test_document_answer_does_not_invent_when_retrieval_is_empty():
    with patch(
        "app.agent.tools.search_document_content",
        return_value=[],
    ):
        answer = answer_document_question(
            "What is the invoice total?",
            user_id=1,
        )

    assert "couldn't find relevant text" in answer
    assert "guessing" in answer


def test_document_answer_returns_retrieved_excerpt_if_no_exact_line_matches():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        (11, "paper.pdf"),
    ]
    retrieved = [
        {
            "document_id": "11",
            "chunk": "The paper describes a novel experimental approach.",
            "page_number": 1,
            "section_heading": "Abstract",
        }
    ]
    with patch(
        "app.agent.tools.search_document_content",
        return_value=retrieved,
    ), patch(
        "app.agent.tools.SessionLocal",
        return_value=db,
    ):
        answer = answer_document_question(
            "Summarize this document",
            user_id=1,
        )

    assert answer == (
        "Source: paper.pdf, page 1, detected section: Abstract\n"
        "The paper describes a novel experimental approach."
    )


def test_document_answer_returns_only_matching_source_line():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        (11, "profile.pdf"),
    ]
    retrieved = [
        {
            "document_id": "11",
            "chunk": (
                "Email: sidra@example.com\n"
                "Phone: 123-456-7890\n"
                "Address: 10 Main Street."
            ),
            "page_number": 1,
            "section_heading": None,
        }
    ]

    with patch(
        "app.agent.tools.search_document_content",
        return_value=retrieved,
    ), patch(
        "app.agent.tools.SessionLocal",
        return_value=db,
    ):
        answer = answer_document_question(
            "What is the email address?",
            user_id=1,
        )

    assert answer == "Source: profile.pdf, page 1\nEmail: sidra@example.com"
    assert "Phone" not in answer
    assert "Address:" not in answer


def test_heading_question_returns_the_full_retrieved_section():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        (11, "profile.pdf"),
    ]
    section_text = (
        "SKILLS\n"
        "FRONTEND: Next.js, React.js, TypeScript.\n"
        "BACKEND: FastAPI, Python."
    )
    retrieved = [
        {
            "document_id": "11",
            "chunk": section_text,
            "page_number": 1,
            "section_heading": "SKILLS",
        }
    ]

    with patch(
        "app.agent.tools.search_document_content",
        return_value=retrieved,
    ), patch(
        "app.agent.tools.SessionLocal",
        return_value=db,
    ):
        answer = answer_document_question(
            "which skill mentioned in my uploaded document",
            user_id=1,
        )

    assert answer == (
        "Source: profile.pdf, page 1, detected section: SKILLS\n"
        f"{section_text}"
    )
    assert "Next.js" in answer
    assert "FastAPI" in answer


def test_section_collection_includes_label_value_lines_and_stops_at_next_heading():
    chunks = [
        SimpleNamespace(
            id=10,
            page_number=1,
            section_heading="SKILLS",
            chunk_text="SKILLS\nFRONTEND: React and Next.js.",
        ),
        SimpleNamespace(
            id=11,
            page_number=1,
            section_heading="DATABASE: PostgreSQL",
            chunk_text="DATABASE: PostgreSQL",
        ),
        SimpleNamespace(
            id=12,
            page_number=1,
            section_heading="EDUCATION",
            chunk_text="EDUCATION\nBachelor of Science.",
        ),
    ]

    section_pages = _collect_section_page_texts(
        chunks,
        heading="SKILLS",
        start_chunk_id=10,
    )

    assert section_pages == [
        (1, "SKILLS\nFRONTEND: React and Next.js.\nDATABASE: PostgreSQL")
    ]


@pytest.mark.parametrize(
    "filename,question,source_line",
    [
        (
            "resume.pdf",
            "What skills are listed?",
            "Skills: Python, SQL, and React.",
        ),
        (
            "invoice.pdf",
            "What is the invoice number?",
            "Invoice number: A-104.",
        ),
        (
            "paper.pdf",
            "What does the methodology say?",
            "Methodology: controlled trial with 80 participants.",
        ),
        (
            "report.pdf",
            "What revenue was stated?",
            "Revenue was $120,000.",
        ),
    ],
)
def test_document_answers_return_verbatim_facts_for_varied_documents(
    filename,
    question,
    source_line,
):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [(11, filename)]
    retrieved = [
        {
            "document_id": "11",
            "chunk": source_line,
            "page_number": 3,
        }
    ]

    with patch(
        "app.agent.tools.search_document_content",
        return_value=retrieved,
    ), patch(
        "app.agent.tools.SessionLocal",
        return_value=db,
    ):
        answer = answer_document_question(question, user_id=1)

    assert answer == f"Source: {filename}, page 3\n{source_line}"
