"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type ListedDocument = {
  id: number;
  filename: string;
  uploaded_at: string | null;
};

type DocumentListResponse = {
  items: ListedDocument[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isDocumentListResponse(
  value: unknown,
): value is DocumentListResponse {
  if (!isRecord(value) || !Array.isArray(value.items)) return false;

  const { page, page_size, total, total_pages } = value;
  return (
    typeof page === "number" &&
    Number.isInteger(page) &&
    page >= 1 &&
    typeof page_size === "number" &&
    Number.isInteger(page_size) &&
    page_size >= 1 &&
    typeof total === "number" &&
    Number.isInteger(total) &&
    total >= 0 &&
    typeof total_pages === "number" &&
    Number.isInteger(total_pages) &&
    total_pages === Math.ceil(total / page_size) &&
    value.items.every(
      (item: unknown) =>
        isRecord(item) &&
        typeof item.id === "number" &&
        Number.isInteger(item.id) &&
        typeof item.filename === "string" &&
        (item.uploaded_at === null || typeof item.uploaded_at === "string"),
    )
  );
}

type DashboardClientProps = {
  userEmail: string;
};

export default function DashboardClient({ userEmail }: DashboardClientProps) {
  const router = useRouter();
  const conversationStorageKey = userEmail.trim()
    ? `ai-rag-document-agent:conversation-id:${encodeURIComponent(userEmail.trim().toLowerCase())}`
    : null;
  const [question, setQuestion] = useState("");
  const [fileName, setFileName] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadMessage, setUploadMessage] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isAsking, setIsAsking] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [documents, setDocuments] = useState<ListedDocument[]>([]);
  const [documentSearchInput, setDocumentSearchInput] = useState("");
  const [documentSearch, setDocumentSearch] = useState("");
  const [documentPage, setDocumentPage] = useState(1);
  const [documentOrder, setDocumentOrder] = useState<"asc" | "desc">("desc");
  const [documentTotal, setDocumentTotal] = useState(0);
  const [documentTotalPages, setDocumentTotalPages] = useState(0);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(true);
  const [documentError, setDocumentError] = useState("");
  const [documentRefreshKey, setDocumentRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({
      page: String(documentPage),
      page_size: "10",
      search: documentSearch,
      sort: "uploaded_at",
      order: documentOrder,
    });

    async function loadDocuments() {
      setIsLoadingDocuments(true);
      setDocumentError("");

      try {
        const response = await fetch(`/api/documents?${params.toString()}`, {
          signal: controller.signal,
        });
        const data: unknown = await response.json();

        if (!response.ok) {
          const detail = isRecord(data) && typeof data.detail === "string"
            ? data.detail
            : "Could not load documents.";
          throw new Error(detail);
        }

        if (!isDocumentListResponse(data)) {
          throw new Error("The document service returned an invalid response.");
        }

        setDocuments(data.items);
        setDocumentTotal(data.total);
        setDocumentTotalPages(data.total_pages);
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return;
        setDocumentError(
          error instanceof Error ? error.message : "Could not load documents.",
        );
      } finally {
        if (!controller.signal.aborted) {
          setIsLoadingDocuments(false);
        }
      }
    }

    void loadDocuments();
    return () => controller.abort();
  }, [documentOrder, documentPage, documentRefreshKey, documentSearch]);

  async function handleLogout() {
    setIsLoggingOut(true);
    setErrorMessage("");

    try {
      const response = await fetch("/api/auth/session", { method: "DELETE" });
      if (!response.ok) {
        throw new Error("Could not sign out. Please try again.");
      }
      router.replace("/login");
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Could not sign out.",
      );
      setIsLoggingOut(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 px-6 py-5">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold">AI Document Assistant</h1>
            <p className="mt-1 text-sm text-slate-400">
              Upload documents and ask questions about their content.
            </p>
          </div>
          <div className="flex items-center justify-between gap-4 sm:justify-end">
            <span className="max-w-48 truncate text-sm text-slate-400">
              {userEmail}
            </span>
            <button
              type="button"
              onClick={handleLogout}
              disabled={isLoggingOut}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-200 transition hover:bg-slate-800 disabled:opacity-50"
            >
              {isLoggingOut ? "Signing out..." : "Sign out"}
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-5xl gap-6 p-6 md:grid-cols-3">
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5 md:col-span-1">
          <h2 className="text-lg font-semibold">Your Document</h2>

          <label className="mt-4 block text-sm text-slate-300">
            Select a PDF
          </label>

          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              setSelectedFile(file);
              setFileName(file?.name ?? "");
              setUploadMessage("");
            }}
            className="mt-2 w-full text-sm text-slate-300"
          />

          <p className="mt-3 break-words text-sm text-slate-400">
            {fileName || "No document selected"}
          </p>

          <button
            type="button"
            disabled={!selectedFile || isUploading}
            onClick={async () => {
              if (!selectedFile) return;

              const formData = new FormData();
              formData.append("file", selectedFile);

              setIsUploading(true);
              setUploadMessage("");

              try {
                const response = await fetch("/api/documents/upload", {
                  method: "POST",
                  body: formData,
                });

                const data = await response.json();

                if (!response.ok) {
                  throw new Error(data.detail || "Upload failed.");
                }

                setUploadMessage(
                  `Uploaded successfully: ${data.filename} (ID: ${data.document_id})`,
                );
                setDocumentPage(1);
                setDocumentRefreshKey((key) => key + 1);
              } catch (error) {
                setUploadMessage(
                  error instanceof Error ? error.message : "Upload failed.",
                );
              } finally {
                setIsUploading(false);
              }
            }}
            className="mt-4 w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-medium disabled:opacity-50"
          >
            {isUploading ? "Uploading..." : "Upload PDF"}
          </button>

          <p className="mt-3 break-words text-sm text-slate-300">
            {uploadMessage}
          </p>
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5 md:col-span-2">
          <h2 className="text-lg font-semibold">Ask your document</h2>
          {conversationId && (
            <p className="mt-2 break-all text-xs text-slate-500">
              Conversation ID: {conversationId}
            </p>
          )}

          <div className="mt-5 min-h-56 rounded-lg bg-slate-950 p-4">
            {isAsking && (
              <p className="text-sm text-blue-400">
                Searching your documents...
              </p>
            )}

            {errorMessage && (
              <p role="alert" className="mt-3 text-sm text-red-400">
                {errorMessage}
              </p>
            )}

            <div className="flex flex-col gap-4">
              {messages.length === 0 && (
                <p className="text-sm text-slate-500">
                  Upload a document and ask your first question.
                </p>
              )}

              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`max-w-[90%] rounded-xl p-4 ${
                    message.role === "user"
                      ? "ml-auto bg-blue-600 text-white"
                      : "mr-auto bg-slate-800 text-slate-100"
                  }`}
                >
                  <p className="mb-2 text-xs font-semibold uppercase opacity-70">
                    {message.role === "user" ? "You" : "AI Agent"}
                  </p>

                  <p className="whitespace-pre-wrap text-sm leading-6">
                    {message.content}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <form
            className="mt-4 flex flex-col gap-3 sm:flex-row"
            onSubmit={async (event) => {
              event.preventDefault();

              const trimmedQuestion = question.trim();
              if (!trimmedQuestion || isAsking) return;

              setIsAsking(true);
              setErrorMessage("");
              setMessages((previous) => [
                ...previous,
                { role: "user", content: trimmedQuestion },
              ]);

              try {
                const activeConversationId =
                  conversationId ??
                  (conversationStorageKey
                    ? window.localStorage.getItem(conversationStorageKey)
                    : null);
                const response = await fetch("/api/chat/agent", {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                  },
                  body: JSON.stringify({
                    question: trimmedQuestion,
                    conversation_id: activeConversationId,
                  }),
                });

                const data = await response.json();

                if (!response.ok) {
                  throw new Error(data.detail || "Could not get an answer.");
                }

                if (typeof data.conversation_id !== "string") {
                  throw new Error("The server did not return a conversation ID.");
                }

                setConversationId(data.conversation_id);
                try {
                  if (conversationStorageKey) {
                    window.localStorage.setItem(
                      conversationStorageKey,
                      data.conversation_id,
                    );
                  }
                } catch (storageError) {
                  setErrorMessage(
                    storageError instanceof Error
                      ? `Could not save the conversation for the next visit: ${storageError.message}`
                      : "Could not save the conversation for the next visit.",
                  );
                }
                setMessages((previous) => [
                  ...previous,
                  { role: "assistant", content: data.answer },
                ]);
                setQuestion("");
              } catch (error) {
                setErrorMessage(
                  error instanceof Error ? error.message : "Something went wrong.",
                );
              } finally {
                setIsAsking(false);
              }
            }}
          >
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask something about your PDF..."
              className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none focus:border-blue-500"
            />

            <button
              type="submit"
              disabled={!question.trim() || isAsking}
              className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-medium hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isAsking ? "Thinking..." : "Ask AI"}
            </button>
          </form>
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5 md:col-span-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Document library</h2>
              <p className="mt-1 text-sm text-slate-400">
                {documentTotal} {documentTotal === 1 ? "document" : "documents"}
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setDocumentPage(1);
                setDocumentOrder((order) => order === "desc" ? "asc" : "desc");
              }}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 transition hover:bg-slate-800"
            >
              Upload date: {documentOrder === "desc" ? "Newest first" : "Oldest first"}
            </button>
          </div>

          <form
            className="mt-4 flex flex-col gap-3 sm:flex-row"
            onSubmit={(event: FormEvent<HTMLFormElement>) => {
              event.preventDefault();
              setDocumentPage(1);
              setDocumentSearch(documentSearchInput.trim());
              setDocumentRefreshKey((key) => key + 1);
            }}
          >
            <input
              value={documentSearchInput}
              onChange={(event) => setDocumentSearchInput(event.target.value)}
              placeholder="Search filenames..."
              aria-label="Search document filenames"
              className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-medium hover:bg-blue-500"
            >
              Search
            </button>
          </form>

          {documentError && (
            <p role="alert" className="mt-4 text-sm text-red-400">
              {documentError}
            </p>
          )}

          <div className="mt-4 overflow-x-auto">
            {isLoadingDocuments ? (
              <p className="py-8 text-center text-sm text-slate-400">
                Loading documents...
              </p>
            ) : documents.length === 0 ? (
              <p className="py-8 text-center text-sm text-slate-400">
                {documentSearch
                  ? "No documents match that filename."
                  : "No documents uploaded yet."}
              </p>
            ) : (
              <table className="w-full min-w-96 text-left text-sm">
                <thead className="border-b border-slate-800 text-xs uppercase text-slate-500">
                  <tr>
                    <th scope="col" className="px-3 py-3 font-medium">Filename</th>
                    <th scope="col" className="px-3 py-3 font-medium">Uploaded</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {documents.map((document) => (
                    <tr key={document.id}>
                      <td className="max-w-0 truncate px-3 py-3 text-slate-200">
                        {document.filename}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-slate-400">
                        {document.uploaded_at
                          ? new Date(document.uploaded_at).toLocaleString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-4">
            <button
              type="button"
              disabled={documentPage <= 1 || isLoadingDocuments}
              onClick={() => setDocumentPage((page) => page - 1)}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-slate-400">
              Page {documentTotal === 0 ? 0 : documentPage} of {documentTotalPages}
            </span>
            <button
              type="button"
              disabled={
                documentPage >= documentTotalPages || isLoadingDocuments
              }
              onClick={() => setDocumentPage((page) => page + 1)}
              className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}
