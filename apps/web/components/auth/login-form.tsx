"use client";

import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { safeNext } from "@/lib/auth-gate";

const input =
  "h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground";

type Problem = "wrong" | "limited" | "noOwner" | "network" | null;

/** Email + password sign-in for the owner. Success reloads into the page asked for. */
export function LoginForm({ next }: { next: string }) {
  const t = useTranslations("Login");
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setProblem(null);
    try {
      const { response } = await api.POST("/api/auth/login", {
        body: {
          email: String(form.get("email") ?? ""),
          password: String(form.get("password") ?? ""),
        },
      });
      if (response.ok) {
        window.location.assign(safeNext(next));
        return;
      }
      setProblem(
        response.status === 429 ? "limited" : response.status === 503 ? "noOwner" : "wrong",
      );
    } catch {
      setProblem("network");
    }
    setBusy(false);
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" data-testid="login-form">
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-email`} className="text-sm font-medium">
          {t("email")}
        </label>
        <input
          id={`${id}-email`}
          name="email"
          type="email"
          autoComplete="username"
          required
          dir="ltr"
          className={input}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-password`} className="text-sm font-medium">
          {t("password")}
        </label>
        <input
          id={`${id}-password`}
          name="password"
          type="password"
          autoComplete="current-password"
          required
          dir="ltr"
          className={input}
        />
      </div>
      <p role="alert" aria-live="assertive" className="min-h-5 text-sm text-destructive">
        {problem ? t(problem) : ""}
      </p>
      <Button type="submit" disabled={busy}>
        {busy ? t("signingIn") : t("submit")}
      </Button>
    </form>
  );
}
