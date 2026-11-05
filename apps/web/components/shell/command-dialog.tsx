"use client";

import { Command } from "cmdk";
import {
  ArchiveIcon,
  ClapperboardIcon,
  CodeIcon,
  DownloadIcon,
  HistoryIcon,
  HomeIcon,
  ImagesIcon,
  MonitorIcon,
  MoonIcon,
  SettingsIcon,
  SunIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { saveTheme } from "@/lib/theme";

const itemClass =
  "flex min-h-11 cursor-default items-center gap-3 rounded-md px-3 text-sm outline-none select-none data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground [&_svg]:size-4";
const groupClass =
  "px-1 py-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground";

export default function CommandDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("Command");
  const router = useRouter();
  const run = (action: () => void) => {
    onOpenChange(false);
    action();
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label={t("title")}
      overlayClassName="fixed inset-0 z-50 bg-black/50"
      contentClassName="fixed start-1/2 top-[15vh] z-50 w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 rtl:translate-x-1/2 overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-lg"
    >
      <Command.Input
        placeholder={t("placeholder")}
        className="h-12 w-full border-b bg-transparent px-4 text-base outline-none placeholder:text-muted-foreground"
      />
      <Command.List className="max-h-80 overflow-y-auto p-1">
        <Command.Empty className="px-4 py-6 text-center text-sm text-muted-foreground">
          {t("empty")}
        </Command.Empty>
        <Command.Group heading={t("pages")} className={groupClass}>
          <Command.Item className={itemClass} onSelect={() => run(() => router.push("/"))}>
            <HomeIcon aria-hidden="true" />
            {t("goHome")}
          </Command.Item>
          <Command.Item className={itemClass} onSelect={() => run(() => router.push("/youtube"))}>
            <ClapperboardIcon aria-hidden="true" />
            {t("goYoutube")}
          </Command.Item>
          <Command.Item className={itemClass} onSelect={() => run(() => router.push("/archive"))}>
            <ArchiveIcon aria-hidden="true" />
            {t("goArchive")}
          </Command.Item>
          <Command.Item className={itemClass} onSelect={() => run(() => router.push("/wayback"))}>
            <HistoryIcon aria-hidden="true" />
            {t("goWayback")}
          </Command.Item>
          <Command.Item className={itemClass} onSelect={() => run(() => router.push("/code"))}>
            <CodeIcon aria-hidden="true" />
            {t("goCode")}
          </Command.Item>
          <Command.Item className={itemClass} onSelect={() => run(() => router.push("/images"))}>
            <ImagesIcon aria-hidden="true" />
            {t("goImages")}
          </Command.Item>
          <Command.Item className={itemClass} onSelect={() => run(() => router.push("/downloads"))}>
            <DownloadIcon aria-hidden="true" />
            {t("goDownloads")}
          </Command.Item>
          <Command.Item className={itemClass} onSelect={() => run(() => router.push("/settings"))}>
            <SettingsIcon aria-hidden="true" />
            {t("goSettings")}
          </Command.Item>
        </Command.Group>
        <Command.Group heading={t("theme")} className={groupClass}>
          <Command.Item className={itemClass} onSelect={() => run(() => saveTheme("light"))}>
            <SunIcon aria-hidden="true" />
            {t("themeLight")}
          </Command.Item>
          <Command.Item className={itemClass} onSelect={() => run(() => saveTheme("dark"))}>
            <MoonIcon aria-hidden="true" />
            {t("themeDark")}
          </Command.Item>
          <Command.Item className={itemClass} onSelect={() => run(() => saveTheme("system"))}>
            <MonitorIcon aria-hidden="true" />
            {t("themeSystem")}
          </Command.Item>
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
