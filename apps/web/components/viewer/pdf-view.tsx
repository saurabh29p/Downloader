"use client";

import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ExpandIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import * as pdfjs from "pdfjs-dist";
import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { fileUrl } from "@/lib/api-viewer";

// The worker is a same-origin file from the build (CSP: worker-src 'self').
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3];
type Problem = "protected" | "malformed" | "failed";

/**
 * PDF reader (pdf.js): pages, zoom, fit to width, page number, search. The file is
 * fetched in byte ranges, so a big PDF is not downloaded whole just to show page 1.
 * Scripts inside PDFs are never run (pdf.js 5 has no scripting here and no eval).
 */
export function PdfView({ id, title }: { id: string; title: string }) {
  const t = useTranslations("Viewer");
  const field = useId();
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState<number | null>(null); // null = fit width
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<number[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    const task = pdfjs.getDocument({
      url: fileUrl(id),
      disableAutoFetch: true,
      disableStream: true,
      rangeChunkSize: 128 * 1024,
      useWasm: false, // CSP allows no WebAssembly; JPEG 2000 images just won't draw
      enableXfa: false,
    });
    let live = true;
    task.promise.then(
      (loaded) => live && setDoc(loaded),
      (error: { name?: string }) => {
        if (!live) return;
        setProblem(
          error?.name === "PasswordException"
            ? "protected"
            : error?.name === "InvalidPDFException"
              ? "malformed"
              : "failed",
        );
      },
    );
    return () => {
      live = false;
      void task.destroy();
    };
  }, [id]);

  useEffect(() => {
    if (!doc || !canvas.current || !box.current) return;
    let render: RenderTask | null = null;
    let live = true;
    void doc.getPage(page).then((p) => {
      if (!live || !canvas.current || !box.current) return;
      const base = p.getViewport({ scale: 1 });
      const fit = Math.max(0.25, (box.current.clientWidth - 32) / base.width);
      const viewport = p.getViewport({ scale: zoom ?? fit });
      const ratio = window.devicePixelRatio || 1;
      const el = canvas.current;
      el.width = Math.floor(viewport.width * ratio);
      el.height = Math.floor(viewport.height * ratio);
      el.style.width = `${Math.floor(viewport.width)}px`;
      el.style.height = `${Math.floor(viewport.height)}px`;
      render = p.render({
        canvas: el,
        viewport,
        transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
      });
      render.promise.catch(() => undefined);
    });
    return () => {
      live = false;
      render?.cancel();
    };
  }, [doc, page, zoom]);

  const pages = doc?.numPages ?? 0;
  const go = (to: number) => setPage(Math.min(Math.max(1, to), pages || 1));
  const zoomBy = (dir: 1 | -1) => {
    const now = zoom ?? 1;
    const next =
      dir > 0
        ? ZOOMS.find((z) => z > now + 0.01)
        : [...ZOOMS].reverse().find((z) => z < now - 0.01);
    setZoom(next ?? now);
  };

  const search = async (event: FormEvent) => {
    event.preventDefault();
    const words = query.trim().toLowerCase();
    if (!doc || words.length < 2) return;
    setSearching(true);
    const hits: number[] = [];
    for (let n = 1; n <= doc.numPages && hits.length < 200; n++) {
      const content = await (await doc.getPage(n)).getTextContent();
      const text = content.items
        .map((item) => ("str" in item ? item.str : ""))
        .join(" ")
        .toLowerCase();
      if (text.includes(words)) hits.push(n);
    }
    setFound(hits);
    setSearching(false);
    if (hits[0]) go(hits[0]);
  };

  const onKey = (event: KeyboardEvent) => {
    if (event.target instanceof HTMLInputElement) return;
    const actions: Record<string, () => void> = {
      ArrowRight: () => go(page + 1),
      ArrowLeft: () => go(page - 1),
      PageDown: () => go(page + 1),
      PageUp: () => go(page - 1),
      "+": () => zoomBy(1),
      "=": () => zoomBy(1),
      "-": () => zoomBy(-1),
      "0": () => setZoom(null),
    };
    const action = actions[event.key];
    if (action) {
      event.preventDefault();
      action();
    }
  };

  if (problem)
    return (
      <p role="alert" className="p-6" data-testid="pdf-problem" data-problem={problem}>
        {t(`pdf.${problem}`)}
      </p>
    );

  const tool =
    "inline-flex size-10 items-center justify-center rounded-md hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:opacity-40";

  return (
    <div className="flex h-full flex-col" onKeyDown={onKey}>
      <div
        className="flex flex-wrap items-center gap-1 border-b px-2 py-1 text-sm"
        role="toolbar"
        aria-label={t("pdfTools")}
      >
        <button
          type="button"
          className={tool}
          onClick={() => go(page - 1)}
          disabled={page <= 1}
          aria-label={t("previousPage")}
        >
          <ChevronLeftIcon className="size-5" aria-hidden="true" data-flip-rtl />
        </button>
        <label className="flex items-center gap-1">
          <span className="sr-only">{t("pageNumber")}</span>
          <input
            type="number"
            min={1}
            max={pages || 1}
            value={page}
            onChange={(e) => go(Number(e.target.value))}
            className="h-9 w-16 rounded-md border border-input bg-card px-2 text-center font-mono"
            data-testid="pdf-page"
          />
          <span className="call-number" data-testid="pdf-pages">
            / {pages || "…"}
          </span>
        </label>
        <button
          type="button"
          className={tool}
          onClick={() => go(page + 1)}
          disabled={!pages || page >= pages}
          aria-label={t("nextPage")}
        >
          <ChevronRightIcon className="size-5" aria-hidden="true" data-flip-rtl />
        </button>
        <span className="mx-1 h-6 w-px bg-border" aria-hidden="true" />
        <button type="button" className={tool} onClick={() => zoomBy(-1)} aria-label={t("zoomOut")}>
          <ZoomOutIcon className="size-5" aria-hidden="true" />
        </button>
        <span className="call-number w-12 text-center">
          {zoom == null ? t("fitWidth") : `${Math.round(zoom * 100)}%`}
        </span>
        <button type="button" className={tool} onClick={() => zoomBy(1)} aria-label={t("zoomIn")}>
          <ZoomInIcon className="size-5" aria-hidden="true" />
        </button>
        <button
          type="button"
          className={tool}
          onClick={() => setZoom(null)}
          aria-label={t("fitWidth")}
        >
          <ExpandIcon className="size-5" aria-hidden="true" />
        </button>
        <form onSubmit={search} role="search" className="ms-auto flex items-center gap-1">
          <label htmlFor={field} className="sr-only">
            {t("findInPdf")}
          </label>
          <input
            id={field}
            type="search"
            dir="auto"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setFound(null);
            }}
            placeholder={t("findInPdf")}
            className="h-9 w-40 rounded-md border border-input bg-card px-2"
            data-testid="pdf-search"
          />
        </form>
      </div>
      {(found || searching) && (
        <div
          className="flex flex-wrap items-center gap-1 border-b px-3 py-1.5 text-sm"
          aria-live="polite"
          data-testid="pdf-found"
        >
          {searching ? (
            t("searching")
          ) : found && found.length > 0 ? (
            <>
              <span className="me-1">{t("foundOnPages")}</span>
              {found.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => go(n)}
                  aria-current={n === page ? "page" : undefined}
                  className="rounded border px-2 py-0.5 font-mono text-xs aria-[current=page]:bg-primary aria-[current=page]:text-primary-foreground"
                >
                  {n}
                </button>
              ))}
            </>
          ) : (
            t("notFound")
          )}
        </div>
      )}
      <div
        ref={box}
        tabIndex={0}
        className="min-h-0 flex-1 overflow-auto bg-muted p-4 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        aria-label={t("pdfPage", { page, pages, title })}
        role="region"
        data-testid="pdf-area"
      >
        <canvas
          ref={canvas}
          className="mx-auto bg-white shadow-card"
          data-testid="pdf-canvas"
          data-page={page}
        />
      </div>
    </div>
  );
}
