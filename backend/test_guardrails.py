
import pytest

from app.agent.tools import search_document_content


def test_empty_question_is_rejected():
    with pytest.raises(ValueError):
        search_document_content("", user_id=1)


def test_whitespace_question_is_rejected():
    with pytest.raises(ValueError):
        search_document_content("", user_id=1)


def test_question_over_1000_characters_is_rejected():
    question = "a" * 1001

    with pytest.raises(ValueError):
        search_document_content(question, user_id=1)
