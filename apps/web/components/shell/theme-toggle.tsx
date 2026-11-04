"use client";

import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useSyncExternalStore } from "react";

import { NativeSelect } from "@/components/ui/native-select";
import { applyTheme, readTheme, saveTheme, subscribeTheme, type ThemeChoice } from "@/lib/theme";

export function ThemeToggle() {
  const t = useTranslations("Shell.theme");
  const choice = useSyncExternalStore<ThemeChoice>(subscribeTheme, readTheme, () => "system");

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => readTheme() === "system" && applyTheme("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const Icon = choice === "dark" ? MoonIcon : choice === "light" ? SunIcon : MonitorIcon;

  return (
    <NativeSelect
      aria-label={t("label")}
      value={choice}
      icon={<Icon aria-hidden="true" />}
      onChange={(event) => saveTheme(event.target.value as ThemeChoice)}
      iconOnlyOnPhone
    >
      <option value="light">{t("light")}</option>
      <option value="dark">{t("dark")}</option>
      <option value="system">{t("system")}</option>
    </NativeSelect>
  );
}
