"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

/** Shown in Settings when the visitor is signed in with the owner's session. */
export function SignOut() {
  const t = useTranslations("Login");
  const locale = useLocale();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api
      .GET("/api/auth/me")
      .then(({ data }) => {
        if (live && data?.method === "session") setEmail(data.email ?? "");
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  if (email === null) return null;
  const signOut = async () => {
    await api.POST("/api/auth/logout").catch(() => undefined);
    // A full load on purpose: it drops every cached query of the old session.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/${locale}/login`);
  };
  return (
    <section className="flex flex-col gap-2 rounded-lg border p-4" aria-labelledby="account-title">
      <h2 id="account-title" className="text-lg font-semibold">
        {t("account")}
      </h2>
      {email ? (
        <p className="text-sm text-muted-foreground">
          {t("signedInAs")} <span dir="ltr">{email}</span>
        </p>
      ) : null}
      <Button variant="outline" className="self-start" onClick={() => void signOut()}>
        {t("signOut")}
      </Button>
    </section>
  );
}
