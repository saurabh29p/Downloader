"use client";

import type { ProbeResult } from "@anyget/shared";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { ClipboardPasteIcon, FileTextIcon, Loader2Icon, SearchIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type DragEvent,
  type FormEvent,
} from "react";
import { toast } from "@/lib/toast";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { createJobs, probeUrl } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { hostOf, parseLinks } from "@/lib/links";
import { JOBS_KEY } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

// The preview drawer (and its dialog code) loads only when a link is checked.
const PreviewSheet = dynamic(() =>
  import("@/components/preview/preview-sheet").then((m) => m.PreviewSheet),
);

const noopSubscribe = () => () => {};

export function PasteBox() {
  const t = useTranslations("Home");
  const locale = useLocale();
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const queryClient = useQueryClient();
  const ids = { input: useId(), hint: useId(), error: useId() };
  const fileInput = useRef<HTMLInputElement>(null);

  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const canPaste = useSyncExternalStore(
    noopSubscribe,
    () => typeof navigator.clipboard?.readText === "function",
    () => false,
  );
  const [dragging, setDragging] = useState(false);
  const links = useMemo(() => parseLinks(text), [text]);

  const probeMutation = useMutation({
    mutationFn: probeUrl,
    onSuccess: (result) => {
      setProbe(result);
      setSheetOpen(true);
    },
    onError: (err) => setError(errorMessage(tErrors, err)),
  });

  const queueMutation = useMutation({
    mutationFn: ({ urls, options }: { urls: string[]; options?: Record<string, unknown> }) =>
      createJobs(urls, options),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      if (result.jobs.length > 0) toast.success(tJobs("added", { count: result.jobs.length }));
      if (result.rejected.length > 0) {
        toast.error(tJobs("rejected", { count: result.rejected.length }), {
          description: errorMessage(tErrors, result.rejected[0]?.code),
        });
      }
      setSheetOpen(false);
      setText("");
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });

  const busy = probeMutation.isPending || queueMutation.isPending;

  // A link handed over by the share target (/share) or a bookmarklet: /?url=…
  const { mutate: probeShared } = probeMutation;
  useEffect(() => {
    const shared = new URLSearchParams(window.location.search).get("url");
    if (!shared) return;
    window.history.replaceState(null, "", window.location.pathname);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hand-over from the URL
    setText(shared);
    probeShared(shared);
  }, [probeShared]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    setError(null);
    if (links.length === 0) {
      if (!text.trim()) {
        setError(t("noLinks"));
        return;
      }
      // Not a link: search everything for it (universal search).
      const q = encodeURIComponent(text.trim().slice(0, 500));
      // A full load: the target page starts from its address.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign(`${window.location.origin}/${locale}/search?q=${q}`);
      return;
    }
    if (links.length === 1) probeMutation.mutate(links[0]!);
    else queueMutation.mutate({ urls: links });
  }

  function addText(value: string) {
    setText((current) => (current.trim() ? `${current.trimEnd()}\n${value}` : value));
    setError(null);
  }

  async function pasteFromClipboard() {
    try {
      addText(await navigator.clipboard.readText());
    } catch {
      setError(t("clipboardDenied"));
    }
  }

  async function readFile(file: File | undefined) {
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setError(t("fileTooBig"));
      return;
    }
    addText(await file.text());
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void readFile(file);
    else addText(event.dataTransfer.getData("text"));
  }

  return (
    <>
      <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
        <label htmlFor={ids.input} className="text-sm font-medium">
          {t("pasteLabel")}
        </label>
        <div
          className={cn(
            "rounded-lg transition-shadow",
            dragging && "ring-2 ring-ring ring-offset-2 ring-offset-background",
          )}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <Textarea
            id={ids.input}
            name="links"
            dir="ltr"
            rows={2}
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setError(null);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder={t("searchHint")}
            autoComplete="off"
            spellCheck={false}
            aria-describedby={error ? `${ids.hint} ${ids.error}` : ids.hint}
            aria-invalid={error ? true : undefined}
            className="max-h-60 min-h-24 text-start"
            data-testid="paste-input"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <p id={ids.hint} className="me-auto text-sm text-muted-foreground">
            {t("pasteHint")}
          </p>
          {links.length > 0 && (
            <Badge variant="outline" data-testid="detect-chip">
              {links.length === 1 ? hostOf(links[0]!) : t("linkCount", { count: links.length })}
            </Badge>
          )}
        </div>

        {error && (
          <p id={ids.error} role="alert" className="text-sm font-medium text-destructive">
            {error}
          </p>
        )}

        <div className="flex flex-col gap-2 sm:flex-row">
          <Button type="submit" disabled={busy} className="sm:order-last sm:ms-auto">
            {busy ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {links.length > 1 ? t("queueMany", { count: links.length }) : t("check")}
          </Button>
          {canPaste && (
            <Button type="button" variant="outline" onClick={pasteFromClipboard}>
              <ClipboardPasteIcon aria-hidden="true" />
              {t("pasteButton")}
            </Button>
          )}
          <Button type="button" variant="outline" onClick={() => fileInput.current?.click()}>
            <FileTextIcon aria-hidden="true" />
            {t("openFile")}
          </Button>
          <input
            ref={fileInput}
            type="file"
            accept=".txt,text/plain"
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => {
              void readFile(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
        </div>
      </form>

      {probe && (
        <PreviewSheet
          probe={probe}
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          pending={queueMutation.isPending}
          onDownload={(options) => queueMutation.mutate({ urls: [probe.normalized_url], options })}
        />
      )}
    </>
  );
}
