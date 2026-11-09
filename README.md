# AI RAG Document Agent

An AI-powered document question-answering system that allows authenticated users to upload PDF documents and interact with their content through intelligent Retrieval-Augmented Generation (RAG).

Built with **FastAPI, Next.js, PostgreSQL, pgvector, and Python**, the application retrieves relevant document content and generates context-aware answers with source citations.

## Overview

AI RAG Document Agent transforms static PDF documents into an interactive knowledge base.

Instead of manually searching through lengthy documents, users can upload PDFs and ask questions in natural language. The system retrieves relevant document chunks using vector similarity search and generates answers based on the available context.

The application also includes authentication, user-specific document access, conversation history, and response guardrails.

## Key Features

- **PDF Document Upload:** Upload and process PDF documents.
- **Retrieval-Augmented Generation (RAG):** Retrieve relevant document content before generating answers.
- **Semantic Search:** Generate embeddings and perform similarity search using PostgreSQL and pgvector.
- **AI-Powered Conversations:** Ask natural-language questions about uploaded documents.
- **Source Citations:** Provide references to relevant document content.
- **JWT Authentication:** Secure API endpoints using JSON Web Tokens.
- **User Data Isolation:** Ensure users can only access their own documents and associated information.
- **Conversation History:** Store and retrieve previous conversations and messages.
- **Context Awareness:** Support questions that refer to previous messages.
- **Response Guardrails:** Prevent unsupported answers when relevant document information is unavailable.
- **AI Agent Tools:** Use document-search tools to support intelligent question answering.
- **Local LLM Support:** Integrate with Ollama to run language models locally.

## Tech Stack

| Category | Technologies |
|---|---|
| Frontend | Next.js, React, TypeScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Vector Database | pgvector |
| ORM | SQLAlchemy |
| Authentication | JWT |
| AI Architecture | Retrieval-Augmented Generation (RAG) |
| LLM Integration | Ollama |
| Testing | Pytest, Pytest-Cov |
| API Documentation | Swagger UI / OpenAPI |
| Database Migrations | Alembic |

## System Architecture

```text
                 USER
                  |
                  v
          NEXT.JS FRONTEND
                  |
                  v
             FASTAPI
                  |
          JWT AUTHENTICATION
                  |
          +-------+--------+
          |                |
          v                v
    PDF UPLOAD         CHAT REQUEST
          |                |
          v                v
     PDF LOADER       RAG PIPELINE
          |                |
          v                v
       CHUNKING       EMBEDDING
          |                |
          v                v
       EMBEDDING     VECTOR SEARCH
          |                |
          +-------+--------+
                  |
                  v
          POSTGRESQL
             + PGVECTOR
                  |
                  v
        RELEVANT DOCUMENT
              CHUNKS
                  |
                  v
          LOCAL LLM (OLLAMA)
                  |
                  v
        GUARDRAILS & CITATIONS
                  |
                  v
          CONTEXTUAL ANSWER
                  |
                  v
              USER
```

## How It Works

### 1. Document Upload

- An authenticated user uploads a PDF document.
- The backend validates the uploaded file.
- PDF content is extracted for processing.

### 2. Text Processing

- Extracted content is divided into smaller chunks.
- Chunk overlap helps preserve context between neighboring sections.
- Each chunk is converted into a numerical embedding.

### 3. Vector Storage

- Document information and chunks are stored in PostgreSQL.
- Embeddings are stored using pgvector.
- User ownership is associated with document records.

### 4. Question Answering

- The user submits a question.
- The system generates a query embedding.
- Relevant document chunks are retrieved through vector similarity search.
- Retrieved context is passed to the language model.
- Guardrails help prevent unsupported responses.

### 5. Answer Generation

- The language model generates a context-aware response.
- Relevant source references are provided.
- Conversation history is maintained for follow-up questions.

## Project Structure

```text
ai-rag-document-agent/
│
├── backend/
│   ├── alembic/
│   │   └── versions/
│   │
│   ├── app/
│   │   ├── agent/
│   │   ├── api/
│   │   ├── database/
│   │   ├── rag/
│   │   ├── schemas/
│   │   └── services/
│   │
│   ├── tests/
│   ├── uploads/
│   ├── alembic.ini
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   ├── public/
│   ├── package.json
│   └── tsconfig.json
│
├── .coveragerc
├── .gitignore
└── README.md
```

## Getting Started

Follow these instructions to run the project locally.

### Prerequisites

Make sure you have installed:

- Python 3.11 or a compatible version supported by the project dependencies
- Node.js and npm
- PostgreSQL
- pgvector PostgreSQL extension
- Ollama (if using a local language model)

### 1. Clone the Repository

```bash
git clone https://github.com/sidratm889-source/ai-rag-document-agent.git

cd ai-rag-document-agent
```

### 2. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file inside the `backend/` directory.

Configure the required values according to the application's settings:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/your_database

JWT_SECRET_KEY=your_secure_secret_key

FRONTEND_URL=http://localhost:3000

OLLAMA_BASE_URL=http://localhost:11434

OLLAMA_CHAT_MODEL=llama3.2:1b

OLLAMA_EMBEDDING_MODEL=nomic-embed-text

PGVECTOR_DIMENSION=384
```

**Important:** Replace placeholder values with your actual database credentials and a strong secret key. Never commit `.env` files or expose credentials publicly.

### 4. Database Setup

Create a PostgreSQL database.

Make sure the pgvector extension is installed and available in your PostgreSQL instance.

Enable the extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Run the application's database initialization and migration setup according to the backend configuration.

### 5. Run the Backend

From the `backend/` directory:

```bash
uvicorn app.main:app --reload
```

Backend:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

Health check:

```text
http://localhost:8000/health
```

### 6. Configure and Run Ollama

Install Ollama and download the language model configured by the application.

Example:

```bash
ollama pull llama3.2:1b
```

Start Ollama:

```bash
ollama serve
```

Ensure the backend's LLM configuration points to the correct local Ollama endpoint.

### 7. Frontend Setup

Open another terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Frontend:

```text
http://localhost:3000
```

## API Overview

The backend exposes REST API endpoints for authentication, document management, and AI conversations.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Check application health |
| `GET /auth/me` | Retrieve authenticated user information |
| `POST /documents/upload` | Upload a PDF document |
| `POST /chat/` | Submit a chat question |
| `POST /chat/agent` | Interact with the AI agent |

For complete request and response schemas, authentication requirements, and API details, visit the Swagger documentation at `/docs`.

## Testing

The backend uses Pytest for automated testing.

Run the test suite from the backend directory:

```bash
pytest
```

Generate a coverage report:

```bash
pytest --cov=app --cov-report=term-missing
```

Generate an HTML coverage report:

```bash
pytest --cov=app --cov-report=html
```

Open the generated `htmlcov/index.html` file to inspect the coverage report.
## Test Results & Code Coverage

The backend test suite includes automated tests for API endpoints,
authentication, document processing, embeddings, retrieval, AI agents,
and response guardrails.

Latest verified test results:

| Metric | Result |
|---|---:|
| Tests Passed | 147 |
| Tests Failed | 0 |
| Tests Skipped | 0 |
| Statements Covered | 649/649 (100%) |
| Branches Covered | 122/122 (100%) |

The project uses Pytest and Pytest-Cov to measure test coverage.

## Security Considerations

Security is an important part of the application.

- JWT-based authentication for protected endpoints.
- User-specific document retrieval and access isolation.
- Environment variables for sensitive configuration.
- PDF file validation and upload size restrictions.
- Input validation for API requests.
- Context-based answer generation with guardrails.
- No intentional exposure of raw database errors through health endpoints.

## Future Improvements

Potential areas for future development include:

- Workspace-based access control.
- Role-based permissions.
- Advanced document management.
- Multi-document knowledge bases.
- More AI agent tools and integrations.
- Human approval workflows for sensitive actions.
- Audit logging and monitoring.
- AI response quality evaluation.
- Production deployment and observability.

## Author

**Sidra Tul Muntha**

Computer Science Graduate | Full-Stack Developer | AI & Backend Development Enthusiast

Interested in building practical AI-powered applications, intelligent agents, and scalable web solutions.

## License

This project is currently available for portfolio and educational purposes. A formal open-source license can be added separately if the project is intended for public reuse.

---

**Built with Python, FastAPI, Next.js, PostgreSQL, pgvector, and AI.**