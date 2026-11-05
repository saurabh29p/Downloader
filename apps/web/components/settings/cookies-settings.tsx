"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUpIcon, Trash2Icon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { deleteCookies, getCookiesStatus, putCookies } from "@/lib/api-settings";
import { errorMessage } from "@/lib/errors";
import { toast } from "@/lib/toast";

const KEY = ["settings", "cookies"] as const;

/** Upload or remove a cookies.txt. The file's content never comes back from the server. */
export function CookiesSettings() {
  const t = useTranslations("Settings");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const status = useQuery({ queryKey: KEY, queryFn: getCookiesStatus });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      if (file.size > 1024 * 1024) throw new Error("too big");
      return putCookies(await file.text());
    },
    onSuccess: (data) => {
      queryClient.setQueryData(KEY, data);
      toast.success(t("cookiesSaved"));
    },
    onError: (err) =>
      toast.error(
        err instanceof Error && err.message === "too big"
          ? t("cookiesTooBig")
          : errorMessage(tErrors, err),
      ),
  });
  const remove = useMutation({
    mutationFn: deleteCookies,
    onSuccess: () => {
      queryClient.setQueryData(KEY, { present: false, updated_at: null, lines: null });
      toast.success(t("cookiesRemoved"));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });

  return (
    <section
      aria-labelledby="cookies-heading"
      className="flex flex-col gap-3 rounded-lg border bg-card p-4 shadow-card sm:p-5"
    >
      <h2 id="cookies-heading" className="text-lg font-semibold">
        {t("cookiesTitle")}
      </h2>
      <p className="text-sm text-muted-foreground">{t("cookiesHelp")}</p>
      <p className="text-sm text-muted-foreground">{t("cookiesLegal")}</p>
      <div aria-live="polite">
        {status.isPending ? (
          <Skeleton className="h-6 w-48" />
        ) : status.data?.present ? (
          <p className="text-sm" data-testid="cookies-status">
            {t("cookiesPresent", {
              count: status.data.lines ?? 0,
              date: status.data.updated_at
                ? new Intl.DateTimeFormat(locale, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(status.data.updated_at))
                : "",
            })}
          </p>
        ) : (
          <p className="text-sm" data-testid="cookies-status">
            {t("cookiesNone")}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button type="button" onClick={() => input.current?.click()} disabled={upload.isPending}>
          <FileUpIcon aria-hidden="true" />
          {status.data?.present ? t("cookiesReplace") : t("cookiesUpload")}
        </Button>
        {status.data?.present && (
          <Button
            type="button"
            variant="outline"
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
          >
            <Trash2Icon aria-hidden="true" />
            {t("cookiesRemove")}
          </Button>
        )}
        <input
          ref={input}
          type="file"
          accept=".txt,text/plain"
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) upload.mutate(file);
            event.target.value = "";
          }}
        />
      </div>
    </section>
  );
}
