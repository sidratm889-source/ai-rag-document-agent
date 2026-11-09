import { Suspense } from "react";
import { redirect } from "next/navigation";
import { getAuthToken, getBackendUrl } from "@/app/lib/auth";
import DashboardClient from "@/app/dashboard-client";

type AuthenticatedUser = {
  email?: string;
};

export default function Home() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-slate-950 text-sm text-slate-300">
          Checking your session...
        </main>
      }
    >
      <ProtectedDashboard />
    </Suspense>
  );
}

async function ProtectedDashboard() {
  const token = await getAuthToken();
  if (!token) {
    redirect("/login");
  }

  let response: Response;
  try {
    response = await fetch(`${getBackendUrl()}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-center text-sm text-slate-300">
        The authentication service is unavailable. Please try again shortly.
      </main>
    );
  }

  if (response.status === 401 || response.status === 403) {
    redirect("/login");
  }

  if (!response.ok) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-center text-sm text-slate-300">
        We could not verify your session. Please try again shortly.
      </main>
    );
  }

  const user = (await response.json()) as AuthenticatedUser;
  return <DashboardClient userEmail={user.email ?? ""} />;
}
