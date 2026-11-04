import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { toast } from "@/lib/toast";

import { Toaster } from "./toaster";

describe("Toaster", () => {
  it("announces success politely and errors assertively, as list items", () => {
    render(<Toaster closeLabel="Dismiss" />);
    act(() => {
      toast.success("Downloaded a.zip");
      toast.error("Download failed: b.zip", { description: "server error" });
    });
    expect(screen.getByRole("status")).toHaveTextContent("Downloaded a.zip");
    expect(screen.getByRole("alert")).toHaveTextContent("Download failed: b.zip");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    act(() => screen.getAllByRole("button", { name: "Dismiss" })[0]!.click());
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });
});
