DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("Chunk size must be greater than zero.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("Overlap must be non-negative and smaller than chunk size.")

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            preferred_start = start + (chunk_size // 2)
            newline = text.rfind("\n", preferred_start, end)
            space = text.rfind(" ", preferred_start, end)
            boundary = max(newline, space)
            if boundary > start:
                end = boundary + 1

        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        if end == len(text):
            break
        start = end - overlap

    return chunks