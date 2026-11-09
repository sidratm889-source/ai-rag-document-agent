import { cookies } from "next/headers";
import {
  AUTH_COOKIE_NAME,
  getBackendUrl,
} from "@/app/lib/auth";

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return Response.json({ detail: "Not authenticated." }, { status: 401 });
  }

  try {
    const response = await fetch(`${getBackendUrl()}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });

    if (response.status === 401 || response.status === 403) {
      cookieStore.delete(AUTH_COOKIE_NAME);
      return Response.json(
        { detail: "Your session has expired. Please sign in again." },
        { status: 401 },
      );
    }

    const result = (await response.json().catch(() => null)) as
      | { detail?: unknown }
      | null;
    if (!response.ok) {
      return Response.json(
        {
          detail:
            typeof result?.detail === "string"
              ? result.detail
              : "Could not verify your session.",
        },
        { status: response.status },
      );
    }

    return Response.json(result);
  } catch {
    return Response.json(
      { detail: "The authentication service is unavailable." },
      { status: 502 },
    );
  }
}

export async function DELETE() {
  (await cookies()).delete(AUTH_COOKIE_NAME);
  return Response.json({ message: "Signed out successfully." });
}
