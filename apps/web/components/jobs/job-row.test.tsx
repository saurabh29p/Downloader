import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { makeJob } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

import { JobRow } from "./job-row";

vi.mock("@/lib/api", async () => ({
  ...(await vi.importActual<typeof import("@/lib/api")>("@/lib/api")),
  jobAction: async () => makeJob(),
  deleteJob: async () => undefined,
}));

function renderRow(overrides: Parameters<typeof makeJob>[0]) {
  return renderWithProviders(
    <ul>
      <JobRow job={makeJob(overrides)} />
    </ul>,
  );
}

describe("JobRow", () => {
  it("shows progress, speed and pause/cancel while downloading", () => {
    renderRow({ state: "downloading" });
    expect(screen.getByText("Downloading")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Progress of report.pdf" })).toHaveAttribute(
      "aria-valuenow",
      "50",
    );
    expect(screen.getByText("\u2066512 KB\u2069 of \u20661 MB\u2069")).toBeInTheDocument();
    expect(screen.getByText("\u2066256 KB/s\u2069")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pause: report.pdf" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Cancel: report.pdf" })).toBeEnabled();
    expect(screen.queryByRole("link", { name: /Save file/ })).not.toBeInTheDocument();
  });

  it("offers the file and removal when done", () => {
    renderRow({ state: "done", checksum_ok: true, downloaded: 1024 * 1024 });
    expect(screen.getByRole("link", { name: "Save file: report.pdf" })).toHaveAttribute(
      "href",
      "/api/jobs/job-1/file",
    );
    expect(screen.getByText("Checksum OK")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove from list: report.pdf" })).toBeEnabled();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("explains failures and offers retry", () => {
    renderRow({ state: "failed", error_code: "blocked_url", error: "10.0.0.1 is private" });
    expect(screen.getByText(/private or local network/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again: report.pdf" })).toBeEnabled();
  });

  it("resumes paused jobs", () => {
    renderRow({ state: "paused" });
    expect(screen.getByRole("button", { name: "Resume: report.pdf" })).toBeEnabled();
  });
});
