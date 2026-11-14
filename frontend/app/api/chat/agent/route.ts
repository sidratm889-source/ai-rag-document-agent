import { getAuthToken, getBackendUrl } from "@/app/lib/auth";
import { NextResponse } from "next/server";
type AgentChatRequest = {
  question?: unknown;
  conversation_id?: unknown;
  document_id?: unknown;
};

export async function POST(request: Request) {
  const token = await getAuthToken();

  if (!token) {
    return Response.json({ detail: "Not authenticated." }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ detail: "Invalid request body." }, { status: 400 });
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return Response.json({ detail: "Invalid request body." }, { status: 400 });
  }

  const data = body as AgentChatRequest;
  if (
    typeof data.question !== "string" ||
    !data.question.trim() ||
    data.question.length > 1000
  ) {
    return Response.json(
      { detail: "Question must be a non-empty string of at most 1000 characters." },
      { status: 400 },
    );
  }

  const forwardedRequest: {
    question: string;
    conversation_id?: string;
    document_id?: number;
  } = {
    question: data.question,
  };

  if (data.conversation_id !== undefined && data.conversation_id !== null) {
    if (
      typeof data.conversation_id !== "string" ||
      !data.conversation_id.trim()
    ) {
      return Response.json(
        { detail: "conversation_id must be a non-empty string when provided." },
        { status: 400 },
      );
    }

    forwardedRequest.conversation_id = data.conversation_id;
  }

  if (data.document_id !== undefined && data.document_id !== null) {
    if (
      typeof data.document_id !== "number" ||
      !Number.isInteger(data.document_id) ||
      data.document_id <= 0
    ) {
      return Response.json(
        { detail: "document_id must be a positive integer when provided." },
        { status: 400 },
      );
    }

    forwardedRequest.document_id = data.document_id;
  }

  try {
    const response = await fetch(`${getBackendUrl()}/chat/agent`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(forwardedRequest),
      cache: "no-store",
    });

    let responseData: unknown;
    try {
      responseData = await response.json();
    } catch {
      return NextResponse.json(
        { detail: "The chat service returned an invalid response." },
        { status: 502 },
      );
    }

    return NextResponse.json(responseData, { status: response.status });
  } catch {
    return Response.json(
      { detail: "The chat service is unavailable. Try again shortly." },
      { status: 502 },
    );
  }
}
