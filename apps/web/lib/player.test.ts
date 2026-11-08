import { afterEach, describe, expect, it, vi } from "vitest";

import { getAudio, onlyOnePlayer, playTrack, registerAudio, stopTrack } from "./player";
import { resumeFrom, savePosition, savedPosition } from "./positions";

function fakeMedia(tag: "audio" | "video") {
  const el = document.createElement(tag);
  let paused = true;
  Object.defineProperty(el, "paused", { get: () => paused });
  el.play = vi.fn(async () => {
    paused = false;
  });
  el.pause = vi.fn(() => {
    paused = true;
  });
  document.body.append(el);
  return el;
}

afterEach(() => {
  stopTrack();
  registerAudio(null);
  document.body.innerHTML = "";
  localStorage.clear();
});

describe("app-wide audio player", () => {
  it("plays a track on the one shell <audio> element, and stops it", () => {
    const audio = fakeMedia("audio");
    registerAudio(audio);
    playTrack({ id: "a", title: "Tone", src: "/api/library/a/file" });
    expect(getAudio()).toBe(audio);
    expect(audio.getAttribute("src")).toBe("/api/library/a/file");
    expect(audio.play).toHaveBeenCalledOnce(); // started inside the tap
    stopTrack();
    expect(audio.pause).toHaveBeenCalled();
    expect(audio.getAttribute("src")).toBeNull();
  });

  it("pauses every other player when one starts", () => {
    const audio = fakeMedia("audio");
    const video = fakeMedia("video");
    void audio.play();
    void video.play();
    const event = new Event("play");
    Object.defineProperty(event, "target", { value: video });
    onlyOnePlayer(event);
    expect(audio.pause).toHaveBeenCalled();
    expect(video.pause).not.toHaveBeenCalled();
  });
});

describe("saved positions", () => {
  it("resumes after 10 s, but not near the end or at the start", () => {
    savePosition("x", 75, 600);
    expect(savedPosition("x")).toBe(75);
    expect(resumeFrom("x", 600)).toBe(75);
    savePosition("x", 4, 600); // too early to be worth resuming
    expect(resumeFrom("x", 600)).toBeNull();
    savePosition("x", 598, 600); // finished
    expect(savedPosition("x")).toBeNull();
  });
});
