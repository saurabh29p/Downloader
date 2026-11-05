"use client";

import type { LibraryItem } from "@anyget/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileArchiveIcon,
  FileAudioIcon,
  FileIcon,
  FileTextIcon,
  FileVideoIcon,
  ImageIcon,
  Loader2Icon,
  RefreshCwIcon,
  SearchIcon,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import { useId, useState, type FormEvent } from "react";

import { ChoicePill } from "@/components/media/choice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { listLibrary, scanLibrary, type LibraryKind } from "@/lib/api-library";
import { errorMessage } from "@/lib/errors";
import { formatBytes, isolate } from "@/lib/format";
import { toast } from "@/lib/toast";

// The preview (video/audio/PDF/EPUB players and edit actions) loads only when opened.
const ItemSheet = dynamic(() => import("@/components/library/item-sheet").then((m) => m.ItemSheet));

const KINDS: (LibraryKind | "all")[] = [
  "all",
  "video",
  "audio",
  "image",
  "pdf",
  "epub",
  "text",
  "archive",
  "other",
];
const ICONS = {
  video: FileVideoIcon,
  audio: FileAudioIcon,
  image: ImageIcon,
  pdf: FileTextIcon,
  epub: FileTextIcon,
  text: FileTextIcon,
  archive: FileArchiveIcon,
  other: FileIcon,
} as const;

export const LIBRARY_KEY = ["library"] as const;

/** Every downloaded file: search, filter by kind or tag, preview, tag and tidy up. */
export function LibraryView() {
  const t = useTranslations("Library");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  const id = useId();
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<LibraryKind | "all">("all");
  const [tag, setTag] = useState<string | null>(null);
  const [open, setOpen] = useState<LibraryItem | null>(null);
  const query = {
    q: q || undefined,
    kind: kind === "all" ? undefined : kind,
    tag: tag ?? undefined,
  };
  const list = useQuery({
    queryKey: [...LIBRARY_KEY, query],
    queryFn: () => listLibrary(query),
  });
  const scan = useMutation({
    mutationFn: scanLibrary,
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: LIBRARY_KEY });
      toast.success(t("scanned", { added: result.added, removed: result.removed }));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setQ(text.trim());
  };
  const items = list.data?.items ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
          <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button variant="outline" onClick={() => scan.mutate()} disabled={scan.isPending}>
          {scan.isPending ? (
            <Loader2Icon className="animate-spin" aria-hidden="true" />
          ) : (
            <RefreshCwIcon aria-hidden="true" />
          )}
          {t("scan")}
        </Button>
      </div>

      <form onSubmit={submit} role="search" className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor={`${id}-q`} className="sr-only">
          {t("searchLabel")}
        </label>
        <input
          id={`${id}-q`}
          type="search"
          dir="auto"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t("searchLabel")}
          className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground"
          data-testid="library-search"
        />
        <Button type="submit">
          <SearchIcon aria-hidden="true" />
          {t("search")}
        </Button>
      </form>

      <div role="radiogroup" aria-label={t("kind")} className="flex flex-wrap gap-2">
        {KINDS.map((k) => (
          <ChoicePill
            key={k}
            name={`${id}-kind`}
            value={k}
            checked={kind === k}
            onChange={() => setKind(k)}
          >
            {t(`kinds.${k}`)}
          </ChoicePill>
        ))}
      </div>
      {(list.data?.tags?.length ?? 0) > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">{t("tags")}</span>
          {list.data!.tags!.map((name) => (
            <button
              key={name}
              type="button"
              aria-pressed={tag === name}
              onClick={() => setTag(tag === name ? null : name)}
              className={
                tag === name
                  ? "min-h-11 rounded-full bg-primary px-3 text-primary-foreground"
                  : "min-h-11 rounded-full border px-3 hover:bg-accent"
              }
            >
              #{name}
            </button>
          ))}
        </div>
      )}

      {list.isPending && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      )}
      {list.isError && (
        <div className="flex flex-col gap-2">
          <p role="alert">{errorMessage(tErrors, list.error)}</p>
          <Button variant="outline" className="self-start" onClick={() => list.refetch()}>
            {t("retry")}
          </Button>
        </div>
      )}
      {list.isSuccess && items.length === 0 && (
        <p className="rounded-lg border border-dashed p-6 text-center text-muted-foreground">
          {q || kind !== "all" || tag ? t("noMatch") : t("empty")}
        </p>
      )}
      {items.length > 0 && (
        <section aria-labelledby={`${id}-files`} className="flex flex-col gap-3">
          <h2 id={`${id}-files`} className="text-sm text-muted-foreground" aria-live="polite">
            {t("count", { count: list.data?.total ?? items.length })}
          </h2>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="library-items">
            {items.map((item) => {
              const Icon = ICONS[item.kind];
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setOpen(item)}
                    className="flex w-full flex-col gap-2 rounded-lg border bg-card p-2 text-start shadow-card hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                    data-testid="library-item"
                    data-kind={item.kind}
                  >
                    <Thumb item={item} Icon={Icon} />
                    <span className="line-clamp-2 font-medium break-words" dir="auto">
                      {item.title}
                    </span>
                    <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>{t(`kinds.${item.kind}`)}</span>
                      <span>{isolate(formatBytes(item.size, locale))}</span>
                      {item.duplicate_of && <Badge variant="outline">{t("duplicate")}</Badge>}
                      {item.missing && <Badge variant="destructive">{t("missing")}</Badge>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {open && <ItemSheet item={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

export default LibraryView;

/** The item's thumbnail (video frame, PDF page, cover, image), or its kind's icon. */
function Thumb({ item, Icon }: { item: LibraryItem; Icon: (typeof ICONS)[LibraryKind] }) {
  const [failed, setFailed] = useState(false);
  if (item.thumbnail && !item.missing && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- local thumbnails
      <img
        src={item.thumbnail}
        alt=""
        loading="lazy"
        onError={() => setFailed(true)}
        className="aspect-video w-full rounded bg-muted object-cover"
        data-testid="library-thumb"
      />
    );
  }
  return (
    <span
      className="flex aspect-video w-full items-center justify-center rounded bg-muted"
      aria-hidden="true"
    >
      <Icon className="size-8 text-muted-foreground" />
    </span>
  );
}
