"use client";

import type { ProbeResult } from "@anyget/shared";
import { DownloadIcon, Loader2Icon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { formatBytes, isolate } from "@/lib/format";
import { hostOf } from "@/lib/links";

type Props = {
  probe: ProbeResult | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDownload: () => void;
  pending: boolean;
};

export function PreviewSheet({ probe, open, onOpenChange, onDownload, pending }: Props) {
  const t = useTranslations("Preview");
  const locale = useLocale();
  if (!probe) return null;
  const extra = probe.extra as {
    content_type?: string | null;
    resumable?: boolean;
    checksums?: Record<string, string>;
  };
  const checksums = Object.keys(extra.checksums ?? {});
  const handlerLabel = probe.handler === "http" ? t("handlers.http") : probe.handler;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent closeLabel={t("close")} data-testid="preview-sheet">
        <SheetHeader>
          <Badge variant="secondary">{handlerLabel}</Badge>
          <SheetTitle dir="auto">{probe.title}</SheetTitle>
          <SheetDescription>{hostOf(probe.normalized_url)}</SheetDescription>
        </SheetHeader>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm">
          <dt className="text-muted-foreground">{t("size")}</dt>
          <dd className="tabular-nums">
            {probe.size ? isolate(formatBytes(probe.size, locale)) : t("unknown")}
          </dd>
          <dt className="text-muted-foreground">{t("type")}</dt>
          <dd dir="ltr" className="text-start">
            {extra.content_type || t("unknown")}
          </dd>
          <dt className="text-muted-foreground">{t("resumable")}</dt>
          <dd>{extra.resumable ? t("yes") : t("no")}</dd>
          {checksums.length > 0 && (
            <>
              <dt className="text-muted-foreground">{t("checksum")}</dt>
              <dd>{t("checksumWillVerify", { algos: checksums.join(", ").toUpperCase() })}</dd>
            </>
          )}
          <dt className="text-muted-foreground">{t("source")}</dt>
          <dd dir="ltr" className="text-start break-all">
            {probe.normalized_url}
          </dd>
        </dl>

        <SheetFooter>
          <SheetClose asChild>
            <Button variant="outline">{t("cancel")}</Button>
          </SheetClose>
          <Button onClick={onDownload} disabled={pending} autoFocus>
            {pending ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <DownloadIcon aria-hidden="true" />
            )}
            {t("download")}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
