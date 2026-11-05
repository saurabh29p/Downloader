"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLinkIcon, Loader2Icon, UploadIcon } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useId, useState, type ChangeEvent, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  importCookies,
  listConnections,
  removeConnection,
  saveConnection,
  testConnection,
  type Connection,
  type ConnectionsView as View,
} from "@/lib/api-connections";
import { errorMessage } from "@/lib/errors";
import { toast } from "@/lib/toast";

const KEY = ["connections"] as const;
const input =
  "h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground";

const BADGE = {
  connected: "success",
  expired: "destructive",
  server: "secondary",
  not_connected: "outline",
} as const;

function useSave() {
  const queryClient = useQueryClient();
  const tErrors = useTranslations("Errors");
  return {
    done: (view: View) => queryClient.setQueryData(KEY, view),
    refresh: () => queryClient.invalidateQueries({ queryKey: KEY }),
    fail: (err: unknown) => toast.error(errorMessage(tErrors, err)),
  };
}

/** Your own accounts: cookies for sign-in sites, keys for APIs. Values never come back. */
export function ConnectionsView() {
  const t = useTranslations("Connections");
  const tErrors = useTranslations("Errors");
  const id = useId();
  const list = useQuery({ queryKey: KEY, queryFn: listConnections });
  const save = useSave();
  const importAll = useMutation({
    mutationFn: async (file: File) => importCookies(await file.text()),
    onSuccess: (result) => {
      save.done(result.view);
      const names = result.view.sites
        .filter((s) => result.imported.includes(s.id))
        .map((s) => s.label);
      toast.success(t("imported", { sites: names.join(", ") }));
    },
    onError: save.fail,
  });

  if (list.isPending) {
    return <Skeleton className="h-[150rem] sm:h-[110rem]" aria-busy="true" />;
  }
  if (list.isError) {
    return (
      <div className="flex flex-col gap-2">
        <p role="alert">{errorMessage(tErrors, list.error)}</p>
        <Button variant="outline" className="self-start" onClick={() => list.refetch()}>
          {t("retry")}
        </Button>
      </div>
    );
  }
  const view = list.data;
  const cookieSites = view.sites.filter((s) => s.kind === "cookies");
  const keySites = view.sites.filter((s) => s.kind === "key");

  return (
    <div className="flex flex-col gap-8">
      {view.key_source === "file" && (
        <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
          {t("keyFile")}
        </p>
      )}

      <section aria-labelledby={`${id}-import`} className="flex flex-col gap-3">
        <h2 id={`${id}-import`} className="text-lg font-semibold">
          {t("importTitle")}
        </h2>
        <p className="max-w-prose text-sm text-muted-foreground">{t("importHelp")}</p>
        <details className="max-w-prose rounded-md border p-3 text-sm">
          <summary className="min-h-11 cursor-pointer content-center font-medium">
            {t("howTitle")}
          </summary>
          <ol className="mt-2 list-decimal space-y-1 ps-5">
            <li>{t("how1")}</li>
            <li>{t("how2")}</li>
            <li>{t("how3")}</li>
            <li>{t("how4")}</li>
          </ol>
        </details>
        <FilePick
          label={t("importButton")}
          busy={importAll.isPending}
          onFile={(file) => importAll.mutate(file)}
          testId="import-cookies"
        />
      </section>

      <section aria-labelledby={`${id}-cookies`} className="flex flex-col gap-3">
        <h2 id={`${id}-cookies`} className="text-lg font-semibold">
          {t("cookieSites")}
        </h2>
        <ul className="grid gap-3 lg:grid-cols-2" data-testid="cookie-sites">
          {cookieSites.map((site) => (
            <SiteCard key={site.id} site={site} />
          ))}
        </ul>
      </section>

      <section aria-labelledby={`${id}-keys`} className="flex flex-col gap-3">
        <h2 id={`${id}-keys`} className="text-lg font-semibold">
          {t("keySites")}
        </h2>
        <p className="max-w-prose text-sm text-muted-foreground">{t("keysHelp")}</p>
        <ul className="grid gap-3 lg:grid-cols-2" data-testid="key-sites">
          {keySites.map((site) => (
            <SiteCard key={site.id} site={site} />
          ))}
        </ul>
      </section>
    </div>
  );
}

function FilePick({
  label,
  busy,
  onFile,
  testId,
}: {
  label: string;
  busy: boolean;
  onFile: (file: File) => void;
  testId: string;
}) {
  const change = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) onFile(file);
  };
  return (
    <label className="inline-flex h-11 cursor-pointer items-center gap-2 self-start rounded-md border bg-card px-4 text-sm font-medium shadow-xs focus-within:ring-[3px] focus-within:ring-ring/50 hover:bg-accent">
      {busy ? (
        <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
      ) : (
        <UploadIcon className="size-4" aria-hidden="true" />
      )}
      {label}
      <input
        type="file"
        accept=".txt,text/plain"
        className="sr-only"
        onChange={change}
        disabled={busy}
        data-testid={testId}
      />
    </label>
  );
}

function SiteCard({ site }: { site: Connection }) {
  const t = useTranslations("Connections");
  const format = useFormatter();
  const save = useSave();
  const id = useId();
  const [values, setValues] = useState<Record<string, string>>({});
  const [proxy, setProxy] = useState("");
  const connected = site.status === "connected" || site.status === "expired";

  const upload = useMutation({
    mutationFn: async (file: File) => saveConnection(site.id, { cookies: await file.text() }),
    onSuccess: (view) => {
      save.done(view);
      toast.success(t("saved", { site: site.label }));
    },
    onError: save.fail,
  });
  const keys = useMutation({
    mutationFn: () => saveConnection(site.id, { fields: values }),
    onSuccess: (view) => {
      setValues({});
      save.done(view);
      toast.success(t("saved", { site: site.label }));
    },
    onError: save.fail,
  });
  const setSiteProxy = useMutation({
    mutationFn: () => saveConnection(site.id, { proxy: proxy.trim() || null }),
    onSuccess: (view) => {
      setProxy("");
      save.done(view);
      toast.success(t("proxySaved"));
    },
    onError: save.fail,
  });
  const test = useMutation({
    mutationFn: () => testConnection(site.id),
    onSuccess: (result) => {
      void save.refresh();
      const message = t(`test.${result.result as "ok"}`, { site: site.label });
      if (result.ok) toast.success(message);
      else toast.error(message);
    },
    onError: save.fail,
  });
  const remove = useMutation({
    mutationFn: () => removeConnection(site.id),
    onSuccess: () => {
      void save.refresh();
      toast.success(t("removed", { site: site.label }));
    },
    onError: save.fail,
  });

  const date = (value?: string | null) =>
    value ? format.dateTime(new Date(value), { dateStyle: "medium" }) : "";
  const submitKeys = (event: FormEvent) => {
    event.preventDefault();
    keys.mutate();
  };

  return (
    <li
      id={site.id}
      className="flex scroll-mt-24 flex-col gap-3 rounded-lg border bg-card p-4 shadow-card target:ring-2 target:ring-primary"
      data-testid="connection"
      data-site={site.id}
      data-status={site.status}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">{site.label}</h3>
        <Badge variant={BADGE[site.status]}>{t(`status.${site.status}`)}</Badge>
      </div>
      {connected && (
        <p className="text-sm text-muted-foreground">
          {t("connectedOn", { date: date(site.connected_on) })}
          {site.expires_on ? ` · ${t("expiresOn", { date: date(site.expires_on) })}` : ""}
          {site.proxy ? ` · ${t("viaProxy")}` : ""}
        </p>
      )}

      {site.kind === "cookies" ? (
        <FilePick
          label={connected ? t("replaceCookies") : t("uploadCookies")}
          busy={upload.isPending}
          onFile={(file) => upload.mutate(file)}
          testId={`upload-${site.id}`}
        />
      ) : (
        <form onSubmit={submitKeys} className="flex flex-col gap-2">
          {site.fields.map((field) => (
            <label key={field} className="flex flex-col gap-1 text-sm font-medium">
              {t(`fields.${field as "token"}`)}
              <input
                type="password"
                autoComplete="off"
                spellCheck={false}
                dir="ltr"
                value={values[field] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [field]: e.target.value }))}
                placeholder={connected ? t("keepCurrent") : ""}
                className={input}
                data-testid={`${site.id}-${field}`}
              />
            </label>
          ))}
          <Button
            type="submit"
            variant="outline"
            className="self-start"
            disabled={keys.isPending || site.fields.some((f) => !values[f]?.trim())}
          >
            {t("saveKey")}
          </Button>
        </form>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {connected && (
          <>
            <Button variant="outline" size="sm" onClick={() => test.mutate()}>
              {test.isPending && <Loader2Icon className="animate-spin" aria-hidden="true" />}
              {t("testButton")}
            </Button>
            <Button variant="outline" size="sm" onClick={() => remove.mutate()}>
              {t("remove")}
            </Button>
          </>
        )}
        {site.help_url && (
          <a
            href={site.help_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-primary"
          >
            {site.kind === "cookies" ? t("helpCookies") : t("helpKey")}
            <ExternalLinkIcon className="size-4" aria-hidden="true" />
          </a>
        )}
      </div>

      {connected && site.kind === "cookies" && (
        <details className="text-sm">
          <summary className="min-h-11 cursor-pointer content-center font-medium">
            {t("proxyTitle")}
          </summary>
          <form
            className="mt-2 flex flex-col gap-2 sm:flex-row"
            onSubmit={(e) => {
              e.preventDefault();
              setSiteProxy.mutate();
            }}
          >
            <label htmlFor={`${id}-proxy`} className="sr-only">
              {t("proxyTitle")}
            </label>
            <input
              id={`${id}-proxy`}
              dir="ltr"
              value={proxy}
              onChange={(e) => setProxy(e.target.value)}
              placeholder="socks5://127.0.0.1:1080"
              className={input}
            />
            <Button type="submit" variant="outline" disabled={setSiteProxy.isPending}>
              {proxy.trim() ? t("proxySave") : t("proxyClear")}
            </Button>
          </form>
        </details>
      )}
    </li>
  );
}

export default ConnectionsView;
