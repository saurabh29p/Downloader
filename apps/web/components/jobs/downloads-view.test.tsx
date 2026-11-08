import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { makeJob } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

import { DownloadsView } from "./downloads-view";

let resolveList: (jobs: unknown[]) => void = () => undefined;
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listJobs: () => new Promise((resolve) => (resolveList = resolve)),
  };
});
vi.mock("@/components/shell/job-events-bridge", () => ({ useConnection: () => "reconnecting" }));
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe("DownloadsView while loading or reconnecting", () => {
  it("shows no counts (never a false 0) until the list arrives", async () => {
    renderWithProviders(<DownloadsView />);
    const all = screen.getByRole("button", { name: /^All/ });
    expect(all).toHaveTextContent(/^All$/);
    expect(screen.queryByText("Nothing here yet")).not.toBeInTheDocument();
    resolveList([makeJob({ id: "a", state: "done" })]);
    expect(await screen.findByRole("button", { name: /^All\s?1$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Done\s?1$/ })).toBeInTheDocument();
  });
});
