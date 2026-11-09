import { getAuthToken, getBackendUrl } from "@/app/lib/auth";

type AgentChatRequest = {
  question?: unknown;
  conversation_id?: unknown;
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

  const forwardedRequest: { question: string; conversation_id?: string } = {
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

    return new Response(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("Content-Type") ?? "application/json",
      },
    });
  } catch {
    return Response.json(
      { detail: "The chat service is unavailable. Try again shortly." },
      { status: 502 },
    );
  }
}
