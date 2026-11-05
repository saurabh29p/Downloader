"use client";

import type { SettingsUpdate, SettingsView } from "@anyget/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2Icon, Loader2Icon, SaveIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { checkYtDlp, getSettings, putSettings } from "@/lib/api-library";
import { errorMessage } from "@/lib/errors";
import { isolate } from "@/lib/format";
import { toast } from "@/lib/toast";

const KEY = ["settings", "app"] as const;
const SECRET_NAMES = [
  "github_token",
  "hf_token",
  "civitai_token",
  "kaggle_username",
  "kaggle_key",
  "europeana_key",
  "dpla_key",
  "trove_key",
  "digitalnz_key",
  "bhl_key",
  "ddb_key",
] as const;
type Secret = (typeof SECRET_NAMES)[number];

const input =
  "h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground";

/** Settings saved on the server: folders, speed and limits, network, API keys, yt-dlp. */
export function AppSettings() {
  const t = useTranslations("Settings");
  const tErrors = useTranslations("Errors");
  const settings = useQuery({ queryKey: KEY, queryFn: getSettings });
  // Same height as the form, so nothing jumps when it arrives.
  if (settings.isPending) return <Skeleton className="h-[166rem] sm:h-[115rem]" aria-busy="true" />;
  if (settings.isError)
    return (
      <div className="flex flex-col gap-2">
        <p role="alert">{errorMessage(tErrors, settings.error)}</p>
        <Button variant="outline" className="self-start" onClick={() => settings.refetch()}>
          {t("retry")}
        </Button>
      </div>
    );
  return <SettingsForm initial={settings.data} />;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-4 rounded-lg border p-4">
      <legend className="px-1 text-lg font-semibold">{title}</legend>
      {children}
    </fieldset>
  );
}

function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}

export function example(template: string): string {
  const parts = template
    .replaceAll("{type}", "videos")
    .replaceAll("{source}", "youtube.com")
    .replaceAll("{year}", "2026")
    .replaceAll("{month}", "11")
    .replaceAll("{title}", "My playlist")
    .split("/")
    .filter(Boolean);
  return [...parts, "video.mp4"].join("/");
}

function SettingsForm({ initial }: { initial: SettingsView }) {
  const t = useTranslations("Settings");
  const tErrors = useTranslations("Errors");
  const id = useId();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    folder_template: initial.folder_template,
    max_concurrent_downloads: initial.max_concurrent_downloads,
    max_per_host: initial.max_per_host,
    rate_limit_kbps: initial.rate_limit_kbps,
    proxy: initial.proxy,
    contact_email: initial.contact_email,
    watch_enabled: initial.watch_enabled,
    host_limits: Object.entries(initial.host_limits ?? {})
      .map(([host, n]) => `${host}=${n}`)
      .join(", "),
  });
  const [secrets, setSecrets] = useState<Partial<Record<Secret, string>>>({});
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((cur) => ({ ...cur, [key]: value }));
  const save = useMutation({
    mutationFn: (body: SettingsUpdate) => putSettings(body),
    onSuccess: (view) => {
      queryClient.setQueryData(KEY, view);
      setSecrets({});
      toast.success(t("saved"));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const host_limits = Object.fromEntries(
      form.host_limits
        .split(",")
        .map((pair) => pair.split("=").map((s) => s.trim()))
        .filter(([host, n]) => host && n)
        .map(([host, n]) => [host, Number(n)]),
    );
    const body: SettingsUpdate = { ...form, host_limits };
    for (const [name, value] of Object.entries(secrets)) {
      if (value !== undefined) (body as Record<string, unknown>)[name] = value;
    }
    save.mutate(body);
  };
  const view = queryClient.getQueryData<SettingsView>(KEY) ?? initial;

  return (
    <form onSubmit={submit} className="flex flex-col gap-6" data-testid="app-settings">
      <Section title={t("downloads")}>
        <Field id={`${id}-dir`} label={t("folder")} hint={t("folderHint")}>
          <input
            id={`${id}-dir`}
            value={initial.downloads_dir}
            readOnly
            dir="ltr"
            className={`${input} bg-muted`}
          />
        </Field>
        <Field
          id={`${id}-tpl`}
          label={t("template")}
          hint={
            <>
              {t("templateHint")} <span dir="ltr">{isolate(example(form.folder_template))}</span>
            </>
          }
        >
          <input
            id={`${id}-tpl`}
            value={form.folder_template}
            onChange={(e) => set("folder_template", e.target.value)}
            placeholder="{type}/{source}"
            dir="ltr"
            aria-describedby={`${id}-tpl-hint`}
            className={input}
            data-testid="folder-template"
          />
        </Field>
      </Section>

      <Section title={t("speed")}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field id={`${id}-conc`} label={t("concurrent")}>
            <input
              id={`${id}-conc`}
              type="number"
              min={1}
              max={16}
              value={form.max_concurrent_downloads}
              onChange={(e) => set("max_concurrent_downloads", Number(e.target.value))}
              className={input}
            />
          </Field>
          <Field id={`${id}-host`} label={t("perHost")}>
            <input
              id={`${id}-host`}
              type="number"
              min={1}
              max={16}
              value={form.max_per_host}
              onChange={(e) => set("max_per_host", Number(e.target.value))}
              className={input}
            />
          </Field>
          <Field id={`${id}-rate`} label={t("rateLimit")} hint={t("rateLimitHint")}>
            <input
              id={`${id}-rate`}
              type="number"
              min={0}
              value={form.rate_limit_kbps}
              onChange={(e) => set("rate_limit_kbps", Number(e.target.value))}
              aria-describedby={`${id}-rate-hint`}
              className={input}
            />
          </Field>
        </div>
        <Field id={`${id}-limits`} label={t("hostLimits")} hint={t("hostLimitsHint")}>
          <input
            id={`${id}-limits`}
            value={form.host_limits}
            onChange={(e) => set("host_limits", e.target.value)}
            dir="ltr"
            aria-describedby={`${id}-limits-hint`}
            className={input}
          />
        </Field>
      </Section>

      <Section title={t("network")}>
        <Field id={`${id}-proxy`} label={t("proxy")} hint={t("proxyHint")}>
          <input
            id={`${id}-proxy`}
            value={form.proxy}
            onChange={(e) => set("proxy", e.target.value)}
            placeholder="socks5://127.0.0.1:1080"
            dir="ltr"
            aria-describedby={`${id}-proxy-hint`}
            className={input}
          />
        </Field>
        {(view.restart_needed ?? []).length > 0 && (
          <p role="status" className="text-sm font-medium">
            {t("restartNeeded")}
          </p>
        )}
        <Field id={`${id}-email`} label={t("contactEmail")} hint={t("contactEmailHint")}>
          <input
            id={`${id}-email`}
            type="email"
            value={form.contact_email}
            onChange={(e) => set("contact_email", e.target.value)}
            dir="ltr"
            aria-describedby={`${id}-email-hint`}
            className={input}
          />
        </Field>
        <label className="flex min-h-11 items-center gap-3 text-sm">
          <input
            type="checkbox"
            checked={form.watch_enabled}
            onChange={(e) => set("watch_enabled", e.target.checked)}
            className="size-5 accent-primary"
          />
          {t("watchEnabled")}
        </label>
      </Section>

      <Section title={t("keys")}>
        <p className="text-sm text-muted-foreground">{t("keysHint")}</p>
        <div className="grid gap-4 sm:grid-cols-2">
          {SECRET_NAMES.map((name) => {
            const isSet = view.secrets?.[name] ?? false;
            return (
              <Field
                key={name}
                id={`${id}-${name}`}
                label={t(`keyNames.${name}`)}
                hint={
                  isSet ? (
                    <span className="inline-flex items-center gap-1">
                      <CheckCircle2Icon className="size-4 text-success" aria-hidden="true" />
                      {t("keySet")}
                    </span>
                  ) : (
                    t("keyNotSet")
                  )
                }
              >
                <div className="flex gap-2">
                  <input
                    id={`${id}-${name}`}
                    type="password"
                    autoComplete="off"
                    value={secrets[name] ?? ""}
                    onChange={(e) => setSecrets((cur) => ({ ...cur, [name]: e.target.value }))}
                    placeholder={isSet ? "••••••••" : ""}
                    aria-describedby={`${id}-${name}-hint`}
                    className={input}
                  />
                  {isSet && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => save.mutate({ [name]: "" } as SettingsUpdate)}
                      aria-label={`${t("clearKey")}: ${t(`keyNames.${name}`)}`}
                    >
                      {t("clearKey")}
                    </Button>
                  )}
                </div>
              </Field>
            );
          })}
        </div>
      </Section>

      <div className="sticky bottom-20 flex justify-end sm:bottom-4">
        <Button type="submit" disabled={save.isPending} className="shadow-lg">
          {save.isPending ? (
            <Loader2Icon className="animate-spin" aria-hidden="true" />
          ) : (
            <SaveIcon aria-hidden="true" />
          )}
          {t("save")}
        </Button>
      </div>
      <YtDlpCheck />
    </form>
  );
}

function YtDlpCheck() {
  const t = useTranslations("Settings");
  const check = useQuery({ queryKey: ["settings", "ytdlp"], queryFn: checkYtDlp, enabled: false });
  return (
    <Section title={t("ytdlp")}>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="outline"
          onClick={() => check.refetch()}
          disabled={check.isFetching}
        >
          {check.isFetching && <Loader2Icon className="animate-spin" aria-hidden="true" />}
          {t("checkUpdates")}
        </Button>
        {check.data && (
          <p className="text-sm" role="status">
            {t("installed", { version: check.data.installed ?? "?" })}{" "}
            {check.data.update_available ? (
              <Badge>{t("updateAvailable", { version: check.data.latest ?? "?" })}</Badge>
            ) : check.data.latest ? (
              t("upToDate")
            ) : (
              t("couldNotCheck")
            )}
          </p>
        )}
      </div>
      {check.data?.update_available && (
        <p className="text-sm text-muted-foreground">
          {t("updateHow")} <code dir="ltr">{check.data.command}</code>
        </p>
      )}
    </Section>
  );
}

export default AppSettings;
