"use client";

import type { ProbeResult } from "@anyget/shared";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { ArrowRightIcon, ClipboardPasteIcon, FileTextIcon, Loader2Icon } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type FormEvent,
} from "react";

import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/navigation";
import { createJobs, probeUrl } from "@/lib/api";
import { DROP_EVENT, DROP_KEY } from "@/lib/drop";
import { errorMessage } from "@/lib/errors";
import { hostOf, parseLinks } from "@/lib/links";
import { MAIN_SECTIONS } from "@/lib/sections";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

// The preview drawer (and its dialog code) loads only when a link is checked.
const PreviewSheet = dynamic(() =>
  import("@/components/preview/preview-sheet").then((m) => m.PreviewSheet),
);

const noopSubscribe = () => () => {};
const HINTS = ["a", "b", "c", "d", "e"] as const;
const STEPS = ["reading", "formats", "ready"] as const;
type Step = (typeof STEPS)[number] | null;

/** Home's universal bar: links are checked and downloaded, anything else is searched. */
export function PasteBox() {
  const t = useTranslations("Home");
  const tSections = useTranslations("Sections");
  const router = useRouter();
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const queryClient = useQueryClient();
  const ids = { input: useId(), hint: useId(), error: useId() };
  const fileInput = useRef<HTMLInputElement>(null);

  const [text, setText] = useState("");
  const [mode, setMode] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [step, setStep] = useState<Step>(null);
  const canPaste = useSyncExternalStore(
    noopSubscribe,
    () => typeof navigator.clipboard?.readText === "function",
    () => false,
  );
  const links = useMemo(() => parseLinks(text), [text]);

  const probeMutation = useMutation({
    mutationFn: probeUrl,
    onMutate: () => {
      setStep("reading");
      // One request does both; the second step shows once the server is past the link.
      setTimeout(() => setStep((s) => (s === "reading" ? "formats" : s)), 700);
    },
    onSuccess: (result) => {
      setStep("ready");
      setProbe(result);
      setSheetOpen(true);
    },
    onError: (err) => {
      setStep(null);
      setError(errorMessage(tErrors, err));
    },
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
      setStep(null);
      setText("");
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });

  const busy = probeMutation.isPending || queueMutation.isPending;

  function addText(value: string) {
    setText((current) => (current.trim() ? `${current.trimEnd()}\n${value}` : value));
    setError(null);
  }

  // A link handed over by the share target (/share) or a bookmarklet (/?url=…),
  // or text dropped on another page; text dropped on this page arrives as an event.
  const { mutate: probeShared } = probeMutation;
  useEffect(() => {
    const shared = new URLSearchParams(window.location.search).get("url");
    let dropped: string | null = null;
    try {
      dropped = sessionStorage.getItem(DROP_KEY);
      sessionStorage.removeItem(DROP_KEY);
    } catch {
      // storage blocked: nothing was handed over
    }
    if (shared) {
      window.history.replaceState(null, "", window.location.pathname);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hand-over from the URL
      setText(shared);
      probeShared(shared);
    } else if (dropped) {
      setText(dropped);
      const found = parseLinks(dropped);
      if (found.length === 1) probeShared(found[0]!);
    }
    const onDrop = (event: Event) => {
      const value = (event as CustomEvent<string>).detail;
      setText((current) => (current.trim() ? `${current.trimEnd()}\n${value}` : value));
      setError(null);
      const found = parseLinks(value);
      if (found.length === 1) probeShared(found[0]!);
    };
    window.addEventListener(DROP_EVENT, onDrop);
    return () => window.removeEventListener(DROP_EVENT, onDrop);
  }, [probeShared]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    setError(null);
    if (links.length === 0) {
      if (!text.trim()) {
        setError(t("noLinks"));
        return;
      }
      // Not a link: search everything (or the chosen section) for it.
      const params = new URLSearchParams({ q: text.trim().slice(0, 500) });
      if (mode !== "all") params.set("section", mode);
      // In-app navigation, so audio playing in the mini-player keeps going.
      router.push(`/search?${params}`);
      return;
    }
    if (links.length === 1) probeMutation.mutate(links[0]!);
    else queueMutation.mutate({ urls: links });
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

  return (
    <>
      <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
        <label htmlFor={ids.input} className="sr-only">
          {t("pasteLabel")}
        </label>
        <div className="relative">
          <textarea
            id={ids.input}
            name="links"
            dir="auto"
            rows={2}
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setError(null);
              setStep(null);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder={t("hints.a")}
            autoComplete="off"
            spellCheck={false}
            aria-describedby={error ? `${ids.hint} ${ids.error}` : ids.hint}
            aria-invalid={error ? true : undefined}
            className="hint-host flex field-sizing-content max-h-60 min-h-28 w-full resize-none rounded-xl border border-input bg-card py-3.5 ps-4 pe-4 text-lg shadow-card outline-none placeholder:text-transparent focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40 aria-invalid:border-destructive sm:pe-40"
            data-testid="paste-input"
          />
          <span className="hint-rotator text-lg sm:end-40" aria-hidden="true">
            {HINTS.map((key) => (
              <span key={key}>{t(`hints.${key}`)}</span>
            ))}
          </span>
          <Button
            type="submit"
            variant="saffron"
            disabled={busy}
            className="mt-2 w-full sm:absolute sm:end-3 sm:bottom-3 sm:mt-0 sm:w-auto"
          >
            {busy ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <ArrowRightIcon aria-hidden="true" data-flip-rtl />
            )}
            {links.length > 1
              ? t("queueMany", { count: links.length })
              : links.length === 1
                ? t("check")
                : t("go")}
          </Button>
        </div>

        <fieldset className="flex flex-wrap gap-2">
          <legend className="sr-only">{t("modeLabel")}</legend>
          {(["all", ...MAIN_SECTIONS] as const).map((id) => (
            <label
              key={id}
              className="inline-flex h-9 cursor-pointer items-center rounded-full border bg-card px-3.5 text-sm has-checked:border-primary has-checked:bg-primary has-checked:text-primary-foreground has-focus-visible:ring-[3px] has-focus-visible:ring-ring/40"
            >
              <input
                type="radio"
                name="mode"
                value={id}
                checked={mode === id}
                onChange={() => setMode(id)}
                className="sr-only"
              />
              {id === "all" ? t("modeAll") : tSections(`${id}.title`)}
            </label>
          ))}
        </fieldset>

        <div className="flex flex-wrap items-center gap-2">
          <p id={ids.hint} className="me-auto text-sm text-muted-foreground">
            {t("pasteHint")}
          </p>
          {links.length > 0 && (
            <span
              className="rounded-md border px-2 py-0.5 font-mono text-xs"
              data-testid="detect-chip"
            >
              {links.length === 1 ? hostOf(links[0]!) : t("linkCount", { count: links.length })}
            </span>
          )}
          {canPaste && (
            <Button type="button" variant="ghost" size="sm" onClick={pasteFromClipboard}>
              <ClipboardPasteIcon aria-hidden="true" />
              {t("pasteButton")}
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => fileInput.current?.click()}
          >
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

        {step && (
          <ol
            aria-label={t("steps.label")}
            aria-live="polite"
            className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm"
            data-testid="link-steps"
            data-step={step}
          >
            {STEPS.map((name, i) => {
              const at = STEPS.indexOf(step);
              const state = i < at || step === "ready" ? "done" : i === at ? "now" : "next";
              return (
                <li
                  key={name}
                  aria-current={state === "now" ? "step" : undefined}
                  className={cn(
                    "flex items-center gap-1.5",
                    state === "next" ? "text-muted-foreground" : "font-medium",
                  )}
                >
                  {i > 0 && (
                    <span
                      aria-hidden="true"
                      className="inline-block text-muted-foreground"
                      data-flip-rtl
                    >
                      →
                    </span>
                  )}
                  <span
                    aria-hidden="true"
                    className={cn(
                      "size-2 rounded-full",
                      state === "done" && "bg-success",
                      state === "now" && "animate-pulse bg-saffron",
                      state === "next" && "bg-border",
                    )}
                  />
                  {t(`steps.${name}`)}
                </li>
              );
            })}
          </ol>
        )}

        {error && (
          <p id={ids.error} role="alert" className="text-sm font-medium text-destructive">
            {error}
          </p>
        )}
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
