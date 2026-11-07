import os

from ollama import Client

client = Client(host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))


def create_embedding(text: str) -> list[float]:
    model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    expected_dimension = int(os.getenv("PGVECTOR_DIMENSION", "384"))
    response = client.embed(
        model=model,
        input=text,
        dimensions=expected_dimension,
    )
    embedding = response["embeddings"][0]

    if len(embedding) != expected_dimension:
        raise ValueError(
            f"Embedding dimension mismatch: Ollama model '{model}' returned {len(embedding)} dimensions, "
            f"but this database is configured for {expected_dimension}. "
            "Create a new vector column/table for the new embedding model or update your pgvector schema before inserting new rows."
        )

    return embedding