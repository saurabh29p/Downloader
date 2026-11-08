"use client";

import dynamic from "next/dynamic";
import { useEffect } from "react";

import { onlyOnePlayer, registerAudio, usePlayer } from "@/lib/player";

// The visible controls load the first time something plays.
const MiniPlayer = dynamic(() => import("./mini-player").then((m) => m.MiniPlayer), {
  ssr: false,
});

/**
 * Lives in the app layout, so it is never unmounted by in-app navigation: the <audio>
 * element (and what it is playing) survives page changes.
 */
export function PlayerHost() {
  const { track } = usePlayer();

  useEffect(() => {
    document.addEventListener("play", onlyOnePlayer, true);
    return () => document.removeEventListener("play", onlyOnePlayer, true);
  }, []);

  return (
    <>
      <audio ref={registerAudio} preload="metadata" hidden data-testid="app-audio" />
      {track && <MiniPlayer track={track} />}
    </>
  );
}
