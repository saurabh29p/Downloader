import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { YtDlpCheck } from "./app-settings";

const base = { bundled: "2026.10.26", command: "docker compose build --pull api" };
let checked = {
  ...base,
  installed: "2026.10.26",
  latest: "2026.11.9",
  update_available: true,
  updated: null as string | null,
  restart_needed: false,
};
const updated = { ...checked, update_available: false, updated: "2026.11.9", restart_needed: true };

vi.mock("@/lib/api-library", () => ({
  checkYtDlp: async () => checked,
  updateYtDlp: async () => updated,
  getLlm: async () => ({}),
  getRetention: async () => ({}),
  getSettings: async () => ({}),
  putSettings: async () => ({}),
}));

describe("Update yt-dlp", () => {
  it("offers the update, installs it and asks for a restart", async () => {
    renderWithProviders(<YtDlpCheck />);
    expect(screen.queryByTestId("ytdlp-update")).toBeNull(); // nothing until checked
    fireEvent.click(screen.getByRole("button", { name: "Check for updates" }));
    fireEvent.click(await screen.findByTestId("ytdlp-update"));
    expect(await screen.findByTestId("ytdlp-restart")).toHaveTextContent(
      "yt-dlp 2026.11.9 is installed. Restart AnyGet to use it",
    );
    expect(screen.queryByTestId("ytdlp-update")).toBeNull();
    // Its own message (the "installed" key belongs to the install-the-app button).
    expect(screen.getAllByText(/yt-dlp 2026\.10\.26 in use\./).length).toBe(1);
  });

  it("says when the updated yt-dlp is the one running", async () => {
    checked = {
      ...checked,
      installed: "2026.11.9",
      latest: "2026.11.9",
      updated: "2026.11.9",
      update_available: false,
    };
    renderWithProviders(<YtDlpCheck />);
    fireEvent.click(screen.getByRole("button", { name: "Check for updates" }));
    expect(
      await screen.findByText("Using the updated yt-dlp from the data folder."),
    ).toBeInTheDocument();
  });
});
