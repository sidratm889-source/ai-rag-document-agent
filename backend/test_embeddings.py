from app.rag.embeddings import create_embedding

text = "our restaurant opena at 10AM"

if __name__ == "__main__":
    embedding = create_embedding(text)
    print("embedding length:", len(embedding))
    print("first 5 values:", embedding[:5])