
"use client";

import { useState } from "react";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [fileName, setFileName] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
const [uploadMessage, setUploadMessage] = useState("");
const [isUploading, setIsUploading] = useState(false);
const [messages, setMessages] = useState<ChatMessage[]>([]);
const [conversationId, setConversationId] = useState<string | null>(null);
const [isAsking, setIsAsking] = useState(false);
const [errorMessage, setErrorMessage] = useState("");
type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 px-6 py-5">
        <div className="mx-auto max-w-5xl">
          <h1 className="text-2xl font-bold">
            AI Document Agent
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Upload documents and ask questions about their content.
          </p>
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
                const response = await fetch(
                  "http://127.0.0.1:8000/documents/upload",
                  {
                    method: "POST",
                    body: formData,
                  }
                );

                const data = await response.json();

                if (!response.ok) {
                  throw new Error(data.detail || "Upload failed.");
                }

                setUploadMessage(
                  `Uploaded successfully: ${data.filename} (ID: ${data.document_id})`
                );
              } catch (error) {
                setUploadMessage(
                  error instanceof Error ? error.message : "Upload failed."
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
              <p className="mt-3 text-sm text-red-400">
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
  setAnswer("");
  setMessages((previous) => [
    ...previous,
    { role: "user", content: trimmedQuestion },
  ]);

  try {
    const activeConversationId =
      conversationId ??
      window.localStorage.getItem("ai-rag-document-agent:conversation-id");
    const response = await fetch("http://127.0.0.1:8000/chat/agent", {
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
      window.localStorage.setItem(
        "ai-rag-document-agent:conversation-id",
        data.conversation_id
      );
    } catch (storageError) {
      setErrorMessage(
        storageError instanceof Error
          ? `Could not save the conversation for the next visit: ${storageError.message}`
          : "Could not save the conversation for the next visit."
      );
    }
    setAnswer(data.answer);
    setMessages((previous) => [
      ...previous,
      { role: "assistant", content: data.answer },
    ]);
    setQuestion("");
  } catch (error) {
    setErrorMessage(
      error instanceof Error
        ? error.message
        : "Something went wrong."
    );
  } finally {
    setIsAsking(false);
  }
}}>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask something about your PDF..."
              className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none focus:border-blue-500"
            />

            <button
              type="submit"
              disabled={!question.trim()}
              className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-medium hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isAsking ? "Thinking..." : "Ask AI"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
