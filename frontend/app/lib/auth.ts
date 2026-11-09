import { cookies } from "next/headers";

export const AUTH_COOKIE_NAME = "ai-document-assistant-session";
export const AUTH_COOKIE_MAX_AGE = 30 * 60;

export function getBackendUrl() {
  return process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";
}

export async function getAuthToken() {
  return (await cookies()).get(AUTH_COOKIE_NAME)?.value;
}

export function authCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: AUTH_COOKIE_MAX_AGE,
  };
}
