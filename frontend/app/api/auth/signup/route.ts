import { getBackendUrl } from "@/app/lib/auth";

type SignupRequest = {
  fullName?: unknown;
  email?: unknown;
  password?: unknown;
};

export async function POST(request: Request) {
  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return Response.json({ detail: "Invalid request body." }, { status: 400 });
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return Response.json({ detail: "Invalid request body." }, { status: 400 });
  }

  const data = body as SignupRequest;
  if (
    typeof data.fullName !== "string" ||
    !data.fullName.trim() ||
    typeof data.email !== "string" ||
    !data.email.trim() ||
    typeof data.password !== "string" ||
    !data.password
  ) {
    return Response.json(
      { detail: "Full name, email, and password are required." },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(`${getBackendUrl()}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: data.email.trim(),
        password: data.password,
      }),
      cache: "no-store",
    });
    const result = (await response.json().catch(() => null)) as
      | { detail?: unknown }
      | null;

    if (!response.ok) {
      return Response.json(
        {
          detail:
            typeof result?.detail === "string"
              ? result.detail
              : "Could not create your account.",
        },
        { status: response.status },
      );
    }

    return Response.json(
      { message: "Your account has been created. You can now sign in." },
      { status: response.status },
    );
  } catch {
    return Response.json(
      { detail: "The authentication service is unavailable. Try again shortly." },
      { status: 502 },
    );
  }
}
