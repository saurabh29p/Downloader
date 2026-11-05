import { fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { defaultSelection, toJobOptions, type Selection, type VideoExtra } from "@/lib/media";
import video from "@/test/fixtures/probe-video.json";
import { renderWithProviders } from "@/test/render";

import { FormatPicker } from "./format-picker";

const extra = video.extra as unknown as VideoExtra;
const seen: Selection[] = [];
const latest = () => seen.at(-1)!;

function Harness({ batch = false }: { batch?: boolean }) {
  const [value, setValue] = useState(() => defaultSelection(batch ? undefined : extra));
  return (
    <FormatPicker
      value={value}
      onChange={(next) => {
        seen.push(next);
        setValue(next);
      }}
      extra={batch ? undefined : extra}
    />
  );
}

describe("FormatPicker", () => {
  it("offers only the presets the video has, with sizes", () => {
    renderWithProviders(<Harness />);
    const quality = screen.getByRole("group", { name: "Quality" });
    const radios = quality.querySelectorAll("input[type=radio]");
    expect([...radios].map((r) => (r as HTMLInputElement).value)).toEqual([
      "best",
      "1080",
      "720",
      "480",
      "360",
    ]);
    expect(screen.getByLabelText(/720p/)).toBeInTheDocument();
  });

  it("chooses 720p and mp4", () => {
    renderWithProviders(<Harness />);
    fireEvent.click(screen.getByLabelText(/720p/));
    expect(latest().preset).toBe("720");
    expect(toJobOptions(latest())).toMatchObject({ preset: "720", container: "mp4" });
  });

  it("switches to audio only with mp3/m4a/opus", () => {
    renderWithProviders(<Harness />);
    fireEvent.click(screen.getByLabelText(/Audio only/));
    fireEvent.click(screen.getByLabelText("M4A"));
    expect(toJobOptions(latest())).toMatchObject({ preset: "audio", audio_format: "m4a" });
    expect(screen.getByRole("group", { name: "Quality" })).toBeDisabled();
  });

  it("picks subtitles and an exact format", () => {
    renderWithProviders(<Harness />);
    fireEvent.click(screen.getAllByLabelText("English")[0]!); // manual, not the auto caption
    fireEvent.change(screen.getByTestId("format-select"), { target: { value: "137" } });
    expect(toJobOptions(latest())).toMatchObject({ subtitles: ["en"], format_id: "137" });
  });

  it("batch mode shows every preset and no exact-format list", () => {
    renderWithProviders(<Harness batch />);
    expect(screen.getByLabelText(/2160p/)).toBeInTheDocument();
    expect(screen.queryByTestId("format-select")).not.toBeInTheDocument();
  });
});
