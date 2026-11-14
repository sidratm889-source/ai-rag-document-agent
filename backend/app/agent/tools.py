import re

from sqlalchemy import String, cast, func, select

from app.database.connection import SessionLocal
from app.database.models import (
    Conversation,
    ConversationMessage,
    Document,
    DocumentChunk,
)
from app.rag.retriever import retrieve_relevant_chunks
from app.rag.structure import is_heading_candidate


QUERY_STOP_WORDS = {
    "about",
    "all",
    "an",
    "and",
    "are",
    "can",
    "did",
    "do",
    "does",
    "for",
    "from",
    "give",
    "how",
    "in",
    "is",
    "it",
    "me",
    "mention",
    "mentioned",
    "my",
    "document",
    "documents",
    "file",
    "files",
    "pdf",
    "uploaded",
    "listed",
    "of",
    "on",
    "please",
    "show",
    "tell",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
}


def _normalize_match_word(word: str) -> str:
    if len(word) > 5 and word.endswith("ies"):
        return f"{word[:-3]}y"
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _find_relevant_source_matches(
    question: str,
    text: str,
) -> list[tuple[int, str]]:
    query_words = {
        _normalize_match_word(word.casefold())
        for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", question)
        if word.casefold() not in QUERY_STOP_WORDS
    }
    if re.search(r"\bemail\s+address\b", question, re.IGNORECASE):
        query_words.discard("address")
    if not query_words:
        return []

    source_parts = re.split(r"\n+|(?<=[.!?])\s+|\s*[|;]\s*", text)
    matches = []
    for part in source_parts:
        candidate = part.strip()
        if not candidate:
            continue
        candidate_words = {
            _normalize_match_word(word.casefold())
            for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", candidate)
        }
        overlap = query_words.intersection(candidate_words)
        if overlap:
            matches.append((len(overlap), candidate))
    return matches


def _question_matches_heading(question: str, heading: str) -> bool:
    question_words = {
        _normalize_match_word(word.casefold())
        for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", question)
        if word.casefold() not in QUERY_STOP_WORDS
    }
    heading_words = {
        _normalize_match_word(word.casefold())
        for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", heading)
    }
    return bool(question_words.intersection(heading_words))


def _source_label(
    filename: str,
    page_number: int | None,
    section_heading: str | None = None,
) -> str:
    parts = [filename]
    if page_number is not None:
        parts.append(f"page {page_number}")
    if section_heading:
        parts.append(f"detected section: {section_heading}")
    return ", ".join(parts)


def _format_source_text(
    filename: str,
    page_number: int | None,
    section_heading: str | None,
    text: str,
) -> str:
    label = _source_label(filename, page_number, section_heading)
    return f"Source: {label}\n{text}"


def _merge_chunk_texts(chunks: list[str]) -> str:
    if not chunks:
        return ""

    merged = chunks[0]
    for chunk in chunks[1:]:
        overlap = max(
            (
                size
                for size in range(1, min(50, len(merged), len(chunk)) + 1)
                if merged.endswith(chunk[:size])
            ),
            default=0,
        )
        merged += chunk[overlap:] if overlap else f"\n{chunk}"
    return merged


def _collect_section_page_texts(
    chunks: list[DocumentChunk],
    heading: str,
    start_chunk_id: int,
) -> list[tuple[int | None, str]]:
    start_index = next(
        (
            index
            for index, chunk in enumerate(chunks)
            if chunk.id == start_chunk_id
        ),
        None,
    )
    if start_index is None:
        return []

    while start_index > 0:
        previous = chunks[start_index - 1]
        first_line = next(
            (
                line.strip()
                for line in previous.chunk_text.splitlines()
                if line.strip()
            ),
            "",
        )
        if (
            previous.section_heading != heading
            and first_line
            and is_heading_candidate([first_line], 0)
        ):
            break
        start_index -= 1

    page_chunks: dict[int | None, list[str]] = {}
    for index in range(start_index, len(chunks)):
        chunk = chunks[index]
        first_line = next(
            (
                line.strip()
                for line in chunk.chunk_text.splitlines()
                if line.strip()
            ),
            "",
        )
        if (
            index > start_index
            and chunk.section_heading != heading
            and first_line
            and is_heading_candidate([first_line], 0)
        ):
            break
        page_chunks.setdefault(chunk.page_number, []).append(chunk.chunk_text)

    return [
        (page_number, _merge_chunk_texts(source_chunks))
        for page_number, source_chunks in page_chunks.items()
    ]


def _load_section_page_texts(
    user_id: int,
    document_id: int,
    heading: str,
    start_chunk_id: int | None,
) -> list[tuple[int | None, str]]:
    if start_chunk_id is None:
        return []

    db = SessionLocal()
    try:
        chunks = db.execute(
            select(DocumentChunk)
            .join(
                Document,
                cast(Document.id, String) == DocumentChunk.document_id,
            )
            .where(
                Document.user_id == user_id,
                Document.id == document_id,
            )
            .order_by(DocumentChunk.id)
        ).scalars().all()
        return _collect_section_page_texts(chunks, heading, start_chunk_id)
    finally:
        db.close()


def search_document_content(
    question: str,
    user_id: int,
    document_id: int | None = None,
):
    if not isinstance(question, str):
        raise ValueError("Question must be a string.")

    question = question.strip()
    if not question:
        raise ValueError("Question cannot be empty.")
    if len(question) > 1000:
        raise ValueError("Question is too long.")
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("Invalid user ID.")
    if document_id is not None and (
        not isinstance(document_id, int) or document_id <= 0
    ):
        raise ValueError("Invalid document ID.")

    retrieval_options = {"user_id": user_id, "limit": 12}
    if document_id is not None:
        retrieval_options["document_id"] = document_id
    results = retrieve_relevant_chunks(question, **retrieval_options)
    formatted_results = []
    for result in results:
        formatted_result = {
            "document_id": result.document_id,
            "chunk": result.chunk_text,
        }
        chunk_id = getattr(result, "id", None)
        if chunk_id is not None:
            formatted_result["chunk_id"] = chunk_id
        page_number = getattr(result, "page_number", None)
        section_heading = getattr(result, "section_heading", None)
        if page_number is not None:
            formatted_result["page_number"] = page_number
        if section_heading is not None:
            formatted_result["section_heading"] = section_heading
        formatted_results.append(formatted_result)
    return formatted_results


def answer_document_question(
    question: str,
    user_id: int,
    document_id: int | None = None,
) -> str:
    if not isinstance(question, str):
        raise ValueError("Question must be a string.")

    question = question.strip()
    if not question:
        raise ValueError("Question cannot be empty.")

    results = search_document_content(question, user_id, document_id)
    if not results:
        scope = "the selected document" if document_id else "your documents"
        return (
            f"I couldn't find relevant text in {scope}, "
            "so I can't answer without guessing."
        )

    document_ids = {
        int(result["document_id"])
        for result in results
    }
    db = SessionLocal()
    try:
        filenames = dict(
            db.query(Document.id, Document.filename)
            .filter(
                Document.user_id == user_id,
                Document.id.in_(document_ids),
            )
            .all()
        )
    finally:
        db.close()

    matches = []
    heading_matches = []
    for result in results:
        filename = filenames.get(
            int(result["document_id"]),
            "uploaded document",
        )
        heading = result.get("section_heading")
        if heading and _question_matches_heading(question, heading):
            section_texts = _load_section_page_texts(
                user_id,
                int(result["document_id"]),
                heading,
                result.get("chunk_id"),
            )
            if not section_texts:
                section_texts = [
                    (result.get("page_number"), result["chunk"])
                ]
            heading_matches.extend(
                (
                    int(result["document_id"]),
                    page_number,
                    heading,
                    filename,
                    source_text,
                )
                for page_number, source_text in section_texts
            )
        for score, source_text in _find_relevant_source_matches(
            question,
            result["chunk"],
        ):
            matches.append(
                (
                    score,
                    int(result["document_id"]),
                    result.get("page_number"),
                    result.get("section_heading"),
                    filename,
                    source_text,
                )
            )

    if heading_matches:
        excerpts = [
            (
                document_id,
                page_number,
                section_heading,
                _format_source_text(
                    filename,
                    page_number,
                    section_heading,
                    source_text,
                ),
            )
            for (
                document_id,
                page_number,
                section_heading,
                filename,
                source_text,
            ) in heading_matches
        ]
    elif matches:
        highest_score = max(match[0] for match in matches)
        excerpts = [
            (
                document_id,
                page_number,
                section_heading,
                _format_source_text(
                    filename,
                    page_number,
                    section_heading,
                    source_text,
                ),
            )
            for (
                score,
                document_id,
                page_number,
                section_heading,
                filename,
                source_text,
            ) in matches
            if score == highest_score
        ]
    else:
        excerpts = [
            (
                int(result["document_id"]),
                result.get("page_number"),
                result.get("section_heading"),
                _format_source_text(
                    filename,
                    result.get("page_number"),
                    result.get("section_heading"),
                    result["chunk"],
                ),
            )
            for result in results[:3]
            for filename in [
                filenames.get(
                    int(result["document_id"]),
                    "uploaded document",
                )
            ]
        ]

    unique_excerpts = []
    seen = set()
    for document_id, page_number, section_heading, excerpt in excerpts:
        key = (document_id, page_number, section_heading, excerpt)
        if key not in seen:
            seen.add(key)
            unique_excerpts.append(excerpt)
    return "\n\n".join(unique_excerpts)


def query_business_data(action: str, user_id: int):
    if not isinstance(action, str):
        raise ValueError("Action must be a string.")

    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("Invalid user ID.")

    allowed_actions = {
        "document_count",
        "document_list",
        "conversation_count",
        "recent_conversations",
        "message_count",
    }

    if action not in allowed_actions:
        raise ValueError("Unsupported business data action.")

    db = SessionLocal()

    try:
        if action == "document_count":
            count = db.query(func.count(Document.id)).filter(
                Document.user_id == user_id
            ).scalar()
            return {"document_count": count or 0}

        if action == "document_list":
            documents = db.query(Document).filter(
                Document.user_id == user_id
            ).order_by(Document.uploaded_at.desc()).limit(10).all()

            return {
                "documents": [
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "uploaded_at": (
                            doc.uploaded_at.isoformat()
                            if doc.uploaded_at else None
                        ),
                    }
                    for doc in documents
                ]
            }

        if action == "conversation_count":
            count = db.query(func.count(Conversation.id)).filter(
                Conversation.user_id == user_id
            ).scalar()
            return {"conversation_count": count or 0}

        if action == "recent_conversations":
            conversations = db.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(
                Conversation.created_at.desc()
            ).limit(5).all()

            return {
                "conversations": [
                    {
                        "conversation_id": conv.conversation_id,
                        "created_at": (
                            conv.created_at.isoformat()
                            if conv.created_at else None
                        ),
                    }
                    for conv in conversations
                ]
            }

        count = (
            db.query(func.count(ConversationMessage.id))
            .join(
                Conversation,
                Conversation.conversation_id
                == ConversationMessage.conversation_id,
            )
            .filter(Conversation.user_id == user_id)
            .scalar()
        )
        return {"message_count": count or 0}
    finally:
        db.close()
