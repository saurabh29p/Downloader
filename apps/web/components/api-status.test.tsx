import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import messages from "@/messages/en.json";

import { ApiStatus } from "./api-status";

let getHealth: () => Promise<unknown> = () => new Promise(() => {});
vi.mock("@/lib/api", () => ({ getHealth: () => getHealth() }));

function renderStatus() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QueryClientProvider client={client}>
        <ApiStatus />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

describe("ApiStatus", () => {
  it("shows online when the API answers", async () => {
    getHealth = async () => ({ status: "ok" });
    renderStatus();
    expect(screen.getByRole("status")).toHaveTextContent("Checking the server…");
    expect(await screen.findByText("Server online")).toBeInTheDocument();
  });

  it("shows offline with a retry button when the API fails", async () => {
    getHealth = async () => {
      throw new Error("down");
    };
    renderStatus();
    expect(await screen.findByText("Server offline")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  });
});
