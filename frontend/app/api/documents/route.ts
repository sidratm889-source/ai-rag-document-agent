import { cookies } from "next/headers";
import {
  AUTH_COOKIE_NAME,
  getBackendUrl,
} from "@/app/lib/auth";

export async function GET(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return Response.json({ detail: "Please sign in to view documents." }, {
      status: 401,
    });
  }

  try {
    const query = new URL(request.url).search;
    const response = await fetch(`${getBackendUrl()}/documents${query}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });

    if (response.status === 401 || response.status === 403) {
      cookieStore.delete(AUTH_COOKIE_NAME);
    }

    let result: unknown;
    try {
      result = await response.json();
    } catch {
      return Response.json(
        { detail: "The document service returned an invalid response." },
        { status: 502 },
      );
    }

    return Response.json(
      result,
      { status: response.status },
    );
  } catch {
    return Response.json(
      { detail: "The document service is unavailable. Try again shortly." },
      { status: 502 },
    );
  }
}
