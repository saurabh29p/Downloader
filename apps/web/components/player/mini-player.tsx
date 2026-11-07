"use client";

import { PauseIcon, PlayIcon, RotateCcwIcon, RotateCwIcon, Volume2Icon, XIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { formatDuration, isolate } from "@/lib/format";
import { getAudio, setResumed, stopTrack, usePlayer, type Track } from "@/lib/player";
import { resumeFrom, savePosition } from "@/lib/positions";
import { signedOut } from "@/lib/signed-out";

const SPEEDS = [0.75, 1, 1.25, 1.5, 2] as const;
type Settable = "currentTime" | "playbackRate" | "volume" | "muted";

/** Change the shell's <audio> element (read fresh: it is not React state). */
function setMedia<K extends Settable>(key: K, value: HTMLAudioElement[K]) {
  const el = getAudio();
  if (el) el[key] = value;
}

const time = (s: number) => formatDuration(Math.max(0, Math.floor(Number.isFinite(s) ? s : 0)));

/** Re-render on the audio element's own events (it lives in PlayerHost). */
function useAudioState() {
  const [, tick] = useState(0);
  useEffect(() => {
    const el = getAudio();
    if (!el) return;
    const update = () => tick((n) => n + 1);
    const events = [
      "play",
      "pause",
      "timeupdate",
      "durationchange",
      "ratechange",
      "volumechange",
      "error",
      "ended",
      "waiting",
      "playing",
    ];
    for (const name of events) el.addEventListener(name, update);
    return () => {
      for (const name of events) el.removeEventListener(name, update);
    };
  }, []);
  return getAudio();
}

/** The persistent audio bar: title, play/pause, seek, skip, speed, volume, close. */
export function MiniPlayer({ track }: { track: Track }) {
  const t = useTranslations("Player");
  const locale = useLocale();
  const el = useAudioState();
  const { resumedAt } = usePlayer();
  const [expired, setExpired] = useState(false);
  const failed = !!el?.error;

  // Room for the bar at the bottom of the page.
  useEffect(() => {
    document.documentElement.dataset.player = "on";
    return () => {
      delete document.documentElement.dataset.player;
    };
  }, []);

  // Resume where this file was left last time (a "Start over" link undoes it).
  useEffect(() => {
    const el = getAudio();
    if (!el) return;
    const resume = () => {
      const at = resumeFrom(track.id, el.duration);
      if (at != null && el.currentTime < at) {
        el.currentTime = at;
        setResumed(at);
      }
    };
    if (el.readyState >= 1) resume();
    else el.addEventListener("loadedmetadata", resume, { once: true });
    return () => el.removeEventListener("loadedmetadata", resume);
  }, [track.id]);

  const close = () => {
    const el = getAudio();
    if (el) savePosition(track.id, el.currentTime, el.duration);
    stopTrack();
  };

  // Save the position now and then, and when paused, so it can resume later.
  useEffect(() => {
    if (!el) return;
    let last = 0;
    const save = () => {
      if (Date.now() - last < 5000 && !el.paused) return;
      last = Date.now();
      savePosition(track.id, el.currentTime, el.duration);
    };
    el.addEventListener("timeupdate", save);
    el.addEventListener("pause", save);
    return () => {
      el.removeEventListener("timeupdate", save);
      el.removeEventListener("pause", save);
    };
  }, [el, track.id]);

  // Lock screen / notification controls where the browser supports Media Session.
  useEffect(() => {
    if (!el || !("mediaSession" in navigator)) return;
    const session = navigator.mediaSession;
    session.metadata = new MediaMetadata({
      title: track.title,
      artist: track.source ?? "AnyGet",
      album: "AnyGet",
      artwork: track.artwork ? [{ src: track.artwork, sizes: "320x320", type: "image/webp" }] : [],
    });
    const handlers: [MediaSessionAction, MediaSessionActionHandler][] = [
      ["play", () => void el.play()],
      ["pause", () => el.pause()],
      [
        "stop",
        () => {
          savePosition(track.id, el.currentTime, el.duration);
          stopTrack();
        },
      ],
      [
        "seekbackward",
        (d) => (el.currentTime = Math.max(0, el.currentTime - (d.seekOffset ?? 10))),
      ],
      ["seekforward", (d) => (el.currentTime = el.currentTime + (d.seekOffset ?? 30))],
      ["seekto", (d) => d.seekTime != null && (el.currentTime = d.seekTime)],
    ];
    for (const [action, handler] of handlers) {
      try {
        session.setActionHandler(action, handler);
      } catch {
        // an action this browser does not support
      }
    }
    return () => {
      for (const [action] of handlers) {
        try {
          session.setActionHandler(action, null);
        } catch {
          // ignore
        }
      }
      session.metadata = null;
    };
  }, [el, track]);

  useEffect(() => {
    if (!el || !("mediaSession" in navigator)) return;
    navigator.mediaSession.playbackState = el.paused ? "paused" : "playing";
    if (Number.isFinite(el.duration) && el.duration > 0) {
      try {
        navigator.mediaSession.setPositionState({
          duration: el.duration,
          playbackRate: el.playbackRate,
          position: Math.min(el.currentTime, el.duration),
        });
      } catch {
        // ignore inconsistent states while seeking
      }
    }
  });

  useEffect(() => {
    if (failed) void signedOut().then(setExpired);
  }, [failed]);

  if (!el) return null;
  const duration = Number.isFinite(el.duration) ? el.duration : 0;
  const skip = (by: number) =>
    setMedia("currentTime", Math.min(Math.max(0, el.currentTime + by), duration || 1e9));

  return (
    <section
      aria-label={t("label")}
      className="fixed inset-x-3 bottom-[calc(var(--bottom-nav-height)+env(safe-area-inset-bottom)+0.5rem)] z-40 flex flex-col gap-1.5 rounded-md border bg-card p-2.5 shadow-lg md:start-[calc(var(--rail-width)+1rem)] md:end-4 md:bottom-4"
      data-testid="mini-player"
      data-state={failed ? "error" : el.paused ? "paused" : "playing"}
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => (el.paused ? void el.play() : el.pause())}
          aria-label={el.paused ? t("play") : t("pause")}
          disabled={failed}
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-saffron text-saffron-foreground disabled:opacity-50"
        >
          {el.paused ? (
            <PlayIcon className="size-5" aria-hidden="true" />
          ) : (
            <PauseIcon className="size-5" aria-hidden="true" />
          )}
        </button>
        <div className="flex min-w-0 flex-1 flex-col">
          <p className="truncate text-sm font-medium" dir="auto" title={track.title}>
            <span className="sr-only">{t("nowPlaying")} </span>
            {track.title}
          </p>
          <p className="call-number tabular-nums" dir="ltr">
            {isolate(`${time(el.currentTime)} / ${time(duration)}`)}
          </p>
        </div>
        <button
          type="button"
          onClick={() => skip(-10)}
          aria-label={t("back10")}
          className="hidden size-10 items-center justify-center rounded-md hover:bg-accent sm:inline-flex"
        >
          <RotateCcwIcon className="size-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => skip(30)}
          aria-label={t("forward30")}
          className="hidden size-10 items-center justify-center rounded-md hover:bg-accent sm:inline-flex"
        >
          <RotateCwIcon className="size-4" aria-hidden="true" />
        </button>
        <label className="sr-only" htmlFor="mini-speed">
          {t("speed")}
        </label>
        <select
          id="mini-speed"
          value={el.playbackRate}
          onChange={(e) => setMedia("playbackRate", Number(e.target.value))}
          className="h-10 rounded-md border border-input bg-card px-1.5 font-mono text-xs"
        >
          {SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}×
            </option>
          ))}
        </select>
        <span className="hidden items-center gap-1 md:flex">
          <Volume2Icon className="size-4 text-muted-foreground" aria-hidden="true" />
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={el.muted ? 0 : el.volume}
            onChange={(e) => {
              setMedia("volume", Number(e.target.value));
              setMedia("muted", Number(e.target.value) === 0);
            }}
            aria-label={t("volume")}
            className="w-20 accent-primary"
          />
        </span>
        <button
          type="button"
          onClick={close}
          aria-label={t("close")}
          className="inline-flex size-10 items-center justify-center rounded-md hover:bg-accent"
        >
          <XIcon className="size-4" aria-hidden="true" />
        </button>
      </div>
      <input
        type="range"
        min={0}
        max={duration || 0}
        step={1}
        value={Math.min(el.currentTime, duration || 0)}
        onChange={(e) => setMedia("currentTime", Number(e.target.value))}
        aria-label={t("seek")}
        aria-valuetext={`${time(el.currentTime)} / ${time(duration)}`}
        disabled={!duration}
        className="w-full accent-primary"
        dir="ltr"
      />
      {resumedAt != null && !failed && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground" role="status">
          {t("resumed", { time: time(resumedAt) })}
          <button
            type="button"
            onClick={() => {
              setMedia("currentTime", 0);
              setResumed(null);
            }}
            className="font-medium text-primary underline underline-offset-2"
          >
            {t("startOver")}
          </button>
        </p>
      )}
      {failed && (
        <p role="alert" className="text-sm text-destructive">
          {expired ? (
            <a href={`/${locale}/login`} className="underline">
              {t("signInAgain")}
            </a>
          ) : (
            <>
              {t("cantPlay")}{" "}
              <a href={`${track.src}?download=true`} className="underline">
                {t("download")}
              </a>
            </>
          )}
        </p>
      )}
    </section>
  );
}
