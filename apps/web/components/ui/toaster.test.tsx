import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { toast, withUndo } from "@/lib/toast";

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

  it("runs the change when the toast ends, unless Undo is pressed", () => {
    vi.useFakeTimers();
    try {
      render(<Toaster closeLabel="Dismiss" />);
      const kept = { commit: vi.fn(), undo: vi.fn() };
      const undone = { commit: vi.fn(), undo: vi.fn() };
      act(() => {
        withUndo("Removed a.zip", "Undo", kept.commit, kept.undo);
        withUndo("Removed b.zip", "Undo", undone.commit, undone.undo);
      });
      act(() => screen.getAllByRole("button", { name: "Undo" })[1]!.click());
      expect(undone.undo).toHaveBeenCalledOnce();
      act(() => vi.advanceTimersByTime(6000));
      expect(kept.commit).toHaveBeenCalledOnce();
      expect(kept.undo).not.toHaveBeenCalled();
      expect(undone.commit).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
