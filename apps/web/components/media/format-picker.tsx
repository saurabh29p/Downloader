"use client";

import { useLocale, useTranslations } from "next-intl";
import { useId, useMemo } from "react";

import { CheckRow, ChoicePill } from "@/components/media/choice";
import { NativeSelect } from "@/components/ui/native-select";
import { formatBytes, isolate } from "@/lib/format";
import {
  BATCH_PRESETS,
  type AudioFormat,
  type Container,
  type Selection,
  type VideoExtra,
} from "@/lib/media";

type Props = {
  value: Selection;
  onChange: (value: Selection) => void;
  /** Probe of one video; omit for a batch (playlist) where formats are not known yet. */
  extra?: VideoExtra;
};

const AUDIO_FORMATS: AudioFormat[] = ["mp3", "m4a", "opus"];
const CONTAINERS: Container[] = ["mp4", "mkv", "webm"];

function useLanguageName() {
  const locale = useLocale();
  return useMemo(() => {
    let names: Intl.DisplayNames | null = null;
    try {
      names = new Intl.DisplayNames([locale], { type: "language" });
    } catch {
      names = null;
    }
    return (code: string) => {
      try {
        return names?.of(code) ?? code;
      } catch {
        return code;
      }
    };
  }, [locale]);
}

/** Quality, audio-only, container, exact format, subtitles and extras for yt-dlp downloads. */
export function FormatPicker({ value, onChange, extra }: Props) {
  const t = useTranslations("Media");
  const locale = useLocale();
  const languageName = useLanguageName();
  const id = useId();
  const set = (patch: Partial<Selection>) => onChange({ ...value, ...patch });

  const presets = (extra?.presets ?? BATCH_PRESETS).filter(
    (p): p is Selection["preset"] => p !== "audio",
  );
  const videoFormats = extra?.formats.filter((f) => f.kind !== "audio") ?? [];
  const audioSize = extra?.preset_sizes.audio;

  return (
    <div className="flex flex-col gap-5" data-testid="format-picker">
      <fieldset className="flex flex-col gap-2" disabled={value.audioOnly}>
        <legend className="mb-2 text-sm font-medium">{t("quality")}</legend>
        <div className="flex flex-wrap gap-2">
          {presets.map((preset) => {
            const size = extra?.preset_sizes[preset];
            return (
              <ChoicePill
                key={preset}
                name={`${id}-quality`}
                value={preset}
                checked={!value.audioOnly && value.preset === preset && !value.formatId}
                disabled={value.audioOnly}
                onChange={() => set({ preset, formatId: null })}
                hint={size ? isolate(formatBytes(size, locale)) : undefined}
              >
                {preset === "best" ? t("best") : isolate(`${preset}p`)}
              </ChoicePill>
            );
          })}
        </div>
      </fieldset>

      <div className="flex flex-col gap-2">
        <CheckRow checked={value.audioOnly} onChange={(audioOnly) => set({ audioOnly })}>
          {t("audioOnly")}
          {audioSize ? (
            <span className="text-muted-foreground">
              {" "}
              · {isolate(formatBytes(audioSize, locale))}
            </span>
          ) : null}
        </CheckRow>
        {value.audioOnly && (
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">{t("audioFormat")}</legend>
            <div className="flex flex-wrap gap-2">
              {AUDIO_FORMATS.map((format) => (
                <ChoicePill
                  key={format}
                  name={`${id}-audio`}
                  value={format}
                  checked={value.audioFormat === format}
                  onChange={() => set({ audioFormat: format })}
                >
                  {format.toUpperCase()}
                </ChoicePill>
              ))}
            </div>
          </fieldset>
        )}
      </div>

      {!value.audioOnly && (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <label className="flex items-center gap-2 text-sm font-medium">
            {t("container")}
            <NativeSelect
              value={value.container}
              onChange={(event) => set({ container: event.target.value as Container })}
              className="border-input bg-card"
            >
              {CONTAINERS.map((container) => (
                <option key={container} value={container}>
                  {container.toUpperCase()}
                </option>
              ))}
            </NativeSelect>
          </label>
          {videoFormats.length > 0 && (
            <label className="flex items-center gap-2 text-sm font-medium">
              {t("exactFormat")}
              <NativeSelect
                value={value.formatId ?? ""}
                onChange={(event) => set({ formatId: event.target.value || null })}
                className="max-w-64 border-input bg-card"
                data-testid="format-select"
              >
                <option value="">{t("automatic")}</option>
                {videoFormats.map((f) => (
                  <option key={f.id} value={f.id}>
                    {[
                      f.label,
                      f.vcodec,
                      f.ext.toUpperCase(),
                      f.size ? formatBytes(f.size, locale) : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </option>
                ))}
              </NativeSelect>
            </label>
          )}
        </div>
      )}

      {extra && (extra.subtitles.length > 0 || extra.auto_captions.length > 0) && (
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-sm font-medium">{t("subtitles")}</legend>
          {extra.subtitles.map((lang) => (
            <CheckRow
              key={lang}
              checked={value.subtitles.includes(lang)}
              onChange={(on) =>
                set({
                  subtitles: on
                    ? [...value.subtitles, lang]
                    : value.subtitles.filter((l) => l !== lang),
                })
              }
            >
              {languageName(lang)}
            </CheckRow>
          ))}
          {extra.auto_captions.length > 0 && (
            <details className="text-sm">
              <summary className="flex min-h-11 cursor-pointer items-center">
                {t("autoCaptions", { count: extra.auto_captions.length })}
              </summary>
              <div className="grid max-h-56 grid-cols-1 overflow-y-auto ps-2 sm:grid-cols-2">
                {extra.auto_captions.map((lang) => (
                  <CheckRow
                    key={`auto-${lang}`}
                    checked={value.autoSubtitles && value.subtitles.includes(lang)}
                    onChange={(on) => {
                      const others = value.subtitles.filter((l) => l !== lang);
                      set({
                        subtitles: on ? [...others, lang] : others,
                        autoSubtitles: on || (value.autoSubtitles && others.length > 0),
                      });
                    }}
                  >
                    {languageName(lang)}
                  </CheckRow>
                ))}
              </div>
            </details>
          )}
          {value.subtitles.length > 0 && !value.audioOnly && (
            <div
              className="mt-2 flex flex-wrap gap-2"
              role="radiogroup"
              aria-label={t("subtitlesMode")}
            >
              {(["srt", "embed"] as const).map((mode) => (
                <ChoicePill
                  key={mode}
                  name={`${id}-subs`}
                  value={mode}
                  checked={value.subtitlesMode === mode}
                  onChange={() => set({ subtitlesMode: mode })}
                >
                  {t(mode === "srt" ? "subtitlesSrt" : "subtitlesEmbed")}
                </ChoicePill>
              ))}
            </div>
          )}
        </fieldset>
      )}

      <fieldset className="flex flex-col">
        <legend className="mb-1 text-sm font-medium">{t("extras")}</legend>
        <CheckRow
          checked={value.embedThumbnail}
          onChange={(embedThumbnail) => set({ embedThumbnail })}
          disabled={!value.audioOnly && value.container === "webm"}
        >
          {t("embedThumbnail")}
        </CheckRow>
        <CheckRow
          checked={value.embedMetadata}
          onChange={(embedMetadata) => set({ embedMetadata })}
        >
          {t("embedMetadata")}
        </CheckRow>
        {(!extra || extra.chapters > 0) && (
          <CheckRow checked={value.chapters} onChange={(chapters) => set({ chapters })}>
            {extra ? t("chaptersCount", { count: extra.chapters }) : t("chapters")}
          </CheckRow>
        )}
        <CheckRow checked={value.infoJson} onChange={(infoJson) => set({ infoJson })}>
          {t("infoJson")}
        </CheckRow>
      </fieldset>
    </div>
  );
}

export default FormatPicker;
