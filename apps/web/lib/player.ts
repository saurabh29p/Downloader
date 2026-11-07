/**
 * The app-wide audio player. One <audio> element lives in the app shell for the whole
 * visit (PlayerHost), so playback survives in-app navigation. `playTrack` must be
 * called from a click/tap: it starts playback synchronously, as phone browsers require.
 * Small on purpose: the visible mini-player controls load only when something plays.
 */
import { useSyncExternalStore } from "react";

export type Track = {
  id: string; // library item id
  title: string;
  src: string; // same-origin file URL (the session cookie authorises it; no tokens)
  artwork?: string | null;
  source?: string | null;
};

type State = { track: Track | null; resumedAt: number | null };

let state: State = { track: null, resumedAt: null };
let audio: HTMLAudioElement | null = null;
const listeners = new Set<() => void>();

function set(next: Partial<State>) {
  state = { ...state, ...next };
  for (const listener of listeners) listener();
}

export function registerAudio(element: HTMLAudioElement | null) {
  audio = element;
}

export const getAudio = () => audio;

// ----- playback ---------------------------------------------------------------------
export function playTrack(track: Track) {
  const el = audio;
  if (!el) return;
  if (state.track?.id !== track.id) {
    el.src = track.src;
    set({ track, resumedAt: null }); // the mini-player resumes a saved position
  }
  // Inside the click handler: allowed to start with sound on phones too.
  void el.play().catch(() => undefined);
}

export function stopTrack() {
  const el = audio;
  if (el) {
    el.pause(); // the mini-player saves the position on "pause"
    el.removeAttribute("src");
    el.load();
  }
  set({ track: null, resumedAt: null });
}

export function setResumed(at: number | null) {
  set({ resumedAt: at });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const EMPTY: State = { track: null, resumedAt: null };

export function usePlayer(): State {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => EMPTY,
  );
}

/** Pause every other <audio>/<video> when one starts: one player at a time. */
export function onlyOnePlayer(event: Event) {
  const started = event.target;
  if (!(started instanceof HTMLMediaElement)) return;
  for (const media of document.querySelectorAll<HTMLMediaElement>("audio, video")) {
    if (media !== started && !media.paused) media.pause();
  }
}
