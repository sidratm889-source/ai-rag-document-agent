import { cookies } from "next/headers";
import {
  AUTH_COOKIE_NAME,
  getBackendUrl,
} from "@/app/lib/auth";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;

  if (!token) {
    return Response.json({ detail: "Please sign in to upload documents." }, {
      status: 401,
    });
  }

  try {
    const formData = await request.formData();
    const response = await fetch(`${getBackendUrl()}/documents/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
      cache: "no-store",
    });
    const result = await response.json().catch(() => null);

    if (response.status === 401 || response.status === 403) {
      cookieStore.delete(AUTH_COOKIE_NAME);
    }

    return Response.json(
      result ?? { detail: "The document service returned an invalid response." },
      { status: response.status },
    );
  } catch {
    return Response.json(
      { detail: "The document service is unavailable. Try again shortly." },
      { status: 502 },
    );
  }
}
