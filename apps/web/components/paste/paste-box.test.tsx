import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { PasteBox } from "./paste-box";

const probeUrl = vi.fn<(url: string) => Promise<unknown>>();
const createJobs = vi.fn<(urls: string[]) => Promise<unknown>>();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    probeUrl: (url: string) => probeUrl(url),
    createJobs: (urls: string[]) => createJobs(urls),
  };
});

describe("PasteBox", () => {
  it("asks for a link when empty", () => {
    renderWithProviders(<PasteBox />);
    fireEvent.click(screen.getByRole("button", { name: "Check link" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Paste a link first.");
  });

  it("probes one link and opens the preview", async () => {
    probeUrl.mockImplementation(async (url) => ({
      url,
      normalized_url: "https://files.test/a.zip",
      handler: "http",
      title: "a.zip",
      size: 2048,
      thumbnail: null,
      choices: [],
      extra: { content_type: "application/zip", resumable: true, checksums: {} },
    }));
    renderWithProviders(<PasteBox />);
    fireEvent.change(screen.getByLabelText("Links to download"), {
      target: { value: "files.test/a.zip" },
    });
    expect(screen.getByTestId("detect-chip")).toHaveTextContent("files.test");
    fireEvent.click(screen.getByRole("button", { name: "Check link" }));
    expect(await screen.findByRole("dialog")).toHaveTextContent("a.zip");
    expect(screen.getByText("\u20662 KB\u2069")).toBeInTheDocument();
    expect(probeUrl).toHaveBeenCalledWith("files.test/a.zip");
  });

  it("queues many links at once", async () => {
    createJobs.mockImplementation(async (urls) => ({
      jobs: urls.map((url, i) => ({ id: String(i), url })),
      rejected: [],
    }));
    renderWithProviders(<PasteBox />);
    fireEvent.change(screen.getByLabelText("Links to download"), {
      target: { value: "https://a.test/1\nhttps://b.test/2\nhttps://c.test/3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Queue 3 links" }));
    await waitFor(() =>
      expect(createJobs).toHaveBeenCalledWith([
        "https://a.test/1",
        "https://b.test/2",
        "https://c.test/3",
      ]),
    );
  });

  it("shows a translated API error", async () => {
    const { ApiError } = await import("@/lib/api");
    probeUrl.mockImplementation(async () => {
      throw new ApiError("blocked_url", "10.0.0.1 is private", 400);
    });
    renderWithProviders(<PasteBox />);
    fireEvent.change(screen.getByLabelText("Links to download"), {
      target: { value: "http://10.0.0.1/x" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check link" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/private or local network/);
  });
});
