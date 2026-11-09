"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

type AuthFormProps = {
  mode: "login" | "signup";
};

type ApiResponse = {
  detail?: string;
  message?: string;
};

export default function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const isSignup = mode === "signup";
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    if (isSignup && !fullName.trim()) {
      setErrorMessage("Enter your full name.");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setErrorMessage("Enter a valid email address.");
      return;
    }

    if (!password) {
      setErrorMessage("Enter your password.");
      return;
    }

    if (isSignup && password.length < 8) {
      setErrorMessage("Password must be at least 8 characters.");
      return;
    }

    if (isSignup && password !== confirmPassword) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch(
        isSignup ? "/api/auth/signup" : "/api/auth/login",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...(isSignup ? { fullName: fullName.trim() } : {}),
            email: email.trim(),
            password,
          }),
        },
      );
      const result = (await response.json().catch(() => null)) as
        | ApiResponse
        | null;

      if (!response.ok) {
        throw new Error(result?.detail ?? "Something went wrong. Try again.");
      }

      if (isSignup) {
        setSuccessMessage(
          "Your account has been created. You can now sign in.",
        );
        setPassword("");
        setConfirmPassword("");
        return;
      }

      router.replace("/");
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Something went wrong.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 text-slate-900">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm sm:p-10">
        <Link href="/" className="mb-9 inline-flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-xl bg-blue-600 text-lg font-bold text-white">
            AI
          </span>
          <span className="text-base font-semibold tracking-tight">
            AI Document Assistant
          </span>
        </Link>

        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">
            {isSignup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {isSignup
              ? "Sign up to start working with your documents."
              : "Sign in to continue to your document workspace."}
          </p>
        </div>

        {errorMessage && (
          <div
            role="alert"
            className="mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {errorMessage}
          </div>
        )}
        {successMessage && (
          <div
            role="status"
            className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
          >
            {successMessage}
          </div>
        )}

        <form className="space-y-5" onSubmit={handleSubmit} noValidate>
          {isSignup && (
            <div>
              <label
                htmlFor="full-name"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                Full name
              </label>
              <input
                id="full-name"
                name="name"
                type="text"
                autoComplete="name"
                required
                maxLength={128}
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                placeholder="Jane Smith"
              />
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Your current account service does not save names to profiles.
              </p>
            </div>
          )}

          <div>
            <label
              htmlFor="email"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              Email address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
              placeholder="you@example.com"
            />
          </div>

          <PasswordInput
            id="password"
            label="Password"
            autoComplete={isSignup ? "new-password" : "current-password"}
            value={password}
            visible={showPassword}
            onChange={setPassword}
            onToggle={() => setShowPassword((visible) => !visible)}
          />

          {isSignup && (
            <PasswordInput
              id="confirm-password"
              label="Confirm password"
              autoComplete="new-password"
              value={confirmPassword}
              visible={showConfirmPassword}
              onChange={setConfirmPassword}
              onToggle={() =>
                setShowConfirmPassword((visible) => !visible)
              }
            />
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="flex w-full items-center justify-center rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting
              ? isSignup
                ? "Creating account..."
                : "Signing in..."
              : isSignup
                ? "Create account"
                : "Sign in"}
          </button>
        </form>

        <p className="mt-7 text-center text-sm text-slate-600">
          {isSignup ? "Already have an account?" : "New to AI Document Assistant?"}{" "}
          <Link
            href={isSignup ? "/login" : "/signup"}
            className="font-semibold text-blue-700 hover:text-blue-800"
          >
            {isSignup ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}

type PasswordInputProps = {
  id: string;
  label: string;
  autoComplete: string;
  value: string;
  visible: boolean;
  onChange: (value: string) => void;
  onToggle: () => void;
};

function PasswordInput({
  id,
  label,
  autoComplete,
  value,
  visible,
  onChange,
  onToggle,
}: PasswordInputProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-2 block text-sm font-medium text-slate-700"
      >
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          name={id}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          required
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-3 pr-16 text-sm outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
          placeholder={label}
        />
        <button
          type="button"
          onClick={onToggle}
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          className="absolute inset-y-0 right-3 my-auto h-fit rounded px-1 py-1 text-xs font-medium text-slate-500 hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
    </div>
  );
}
