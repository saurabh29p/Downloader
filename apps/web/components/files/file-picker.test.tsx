import { fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/test/render";

import { defaultFiles, FilePicker, galleryImages } from "./file-picker";

const choices = [
  { id: "page", label: "Reports.html", kind: "page", default: true },
  { id: "https://x.test/a.pdf", label: "a.pdf", kind: "document", default: false, size: 2048 },
  { id: "https://x.test/b.zip", label: "b.zip", kind: "archive", default: false },
];

function Harness({ images }: { images?: Map<string, string> }) {
  const [selected, setSelected] = useState(() => defaultFiles(choices));
  return (
    <>
      <FilePicker choices={choices} selected={selected} onChange={setSelected} images={images} />
      <output data-testid="ids">{[...selected].join(",")}</output>
    </>
  );
}

describe("FilePicker", () => {
  it("starts from the default choices and toggles files", () => {
    renderWithProviders(<Harness />);
    expect(screen.getByText(/1 of 3 selected/)).toBeTruthy();
    expect(screen.getByText("Archive")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("a.pdf"));
    expect(screen.getByTestId("ids").textContent).toBe("page,https://x.test/a.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Select none" }));
    expect(screen.getByTestId("ids").textContent).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Select all" }));
    expect(screen.getByText(/3 of 3 selected/)).toBeTruthy();
  });

  it("shows a thumbnail grid for galleries", () => {
    const probe = {
      handler: "gallery",
      extra: { items: [{ index: 1, url: "https://img.test/1.jpg" }] },
    } as unknown as Parameters<typeof galleryImages>[0];
    const images = galleryImages(probe)!;
    expect(images.get("1")).toBe("https://img.test/1.jpg");
    const { container } = renderWithProviders(<Harness images={new Map([["page", "u"]])} />);
    expect(container.querySelectorAll("img")).toHaveLength(1);
  });
});
