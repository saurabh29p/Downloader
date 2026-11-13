import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { SourceStatusList } from "./source-status";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe("SourceStatusList", () => {
  it("sends a source that needs a key to its Connections entry, not to an env variable", () => {
    renderWithProviders(
      <SourceStatusList
        sources={[
          {
            name: "gutendex",
            label: "Project Gutenberg",
            region: "global",
            status: "ok",
            count: 3,
          },
          {
            name: "dpla",
            label: "DPLA",
            region: "americas",
            status: "needs_key",
            count: 0,
            message: "set ANYGET_DPLA_KEY",
          },
        ]}
      />,
    );
    expect(screen.getByRole("link", { name: "Add a key in Connections" })).toHaveAttribute(
      "href",
      "/connections#dpla",
    );
    expect(screen.queryByText(/ANYGET_DPLA_KEY/)).not.toBeInTheDocument();
  });
});
