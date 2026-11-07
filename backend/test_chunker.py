from app.rag.chunker import chunk_text
from app.rag.chunker import chunk_text



text = """
Architected a multi-role web platform supporting three distinct
user types — admin, instructor, and student — each with scoped,
permission-gated dashboards implemented via Firebase
Authentication and role-based access control (RBAC).
"""
chunks = chunk_text(text, chunk_size = 100, overlap = 20)
for i, chunk  in enumerate(chunks, start = 1):
   print(f"\n---Chunk{i}---")
   print(chunk)
   def test_chunk_text_skips_whitespace_chunk():
    result = chunk_text("   ", chunk_size=3, overlap=1)

    assert result == []