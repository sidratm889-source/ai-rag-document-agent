import { cookies } from "next/headers";
import {
  AUTH_COOKIE_NAME,
  authCookieOptions,
  getBackendUrl,
} from "@/app/lib/auth";

type LoginRequest = {
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

  const data = body as LoginRequest;
  if (
    typeof data.email !== "string" ||
    !data.email.trim() ||
    typeof data.password !== "string" ||
    !data.password
  ) {
    return Response.json(
      { detail: "Email and password are required." },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(`${getBackendUrl()}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: data.email.trim(),
        password: data.password,
      }),
      cache: "no-store",
    });
    const result = (await response.json().catch(() => null)) as
      | { detail?: unknown; access_token?: unknown }
      | null;

    if (!response.ok) {
      return Response.json(
        {
          detail:
            typeof result?.detail === "string"
              ? result.detail
              : "Could not sign in.",
        },
        { status: response.status },
      );
    }

    if (typeof result?.access_token !== "string") {
      return Response.json(
        { detail: "The authentication service returned an invalid response." },
        { status: 502 },
      );
    }

    (await cookies()).set(
      AUTH_COOKIE_NAME,
      result.access_token,
      authCookieOptions(),
    );

    return Response.json({ message: "Signed in successfully." });
  } catch {
    return Response.json(
      { detail: "The authentication service is unavailable. Try again shortly." },
      { status: 502 },
    );
  }
}
