"use client";

import { DownloadIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";

type InstallPrompt = Event & { prompt: () => Promise<void>; userChoice: Promise<unknown> };
declare global {
  interface Window {
    __anygetInstall?: InstallPrompt;
  }
}

const subscribe = (callback: () => void) => {
  window.addEventListener("anyget:installable", callback);
  window.addEventListener("appinstalled", callback);
  return () => {
    window.removeEventListener("anyget:installable", callback);
    window.removeEventListener("appinstalled", callback);
  };
};
const standalone = () => window.matchMedia?.("(display-mode: standalone)").matches ?? false;
const state = () => (standalone() ? "installed" : window.__anygetInstall ? "ready" : "manual");

/** Install AnyGet as an app (adds it to the phone's share menu on Android). */
export function InstallApp() {
  const t = useTranslations("Settings");
  const status = useSyncExternalStore(subscribe, state, () => "manual");
  const install = async () => {
    const prompt = window.__anygetInstall;
    if (!prompt) return;
    await prompt.prompt();
    await prompt.userChoice;
    window.__anygetInstall = undefined;
    window.dispatchEvent(new Event("anyget:installable"));
  };
  return (
    <section className="flex flex-col gap-2" aria-labelledby="install-title">
      <h3 id="install-title" className="font-medium">
        {t("installTitle")}
      </h3>
      <p className="text-sm text-muted-foreground">{t("installHelp")}</p>
      {status === "installed" ? (
        <p role="status" className="text-sm font-medium">
          {t("installed")}
        </p>
      ) : status === "ready" ? (
        <Button className="self-start" onClick={() => void install()}>
          <DownloadIcon aria-hidden="true" />
          {t("installButton")}
        </Button>
      ) : (
        <p className="text-sm">{t("installManual")}</p>
      )}
    </section>
  );
}
