import type { BookHit } from "@anyget/shared";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/test/render";

import { BookCard } from "./book-card";

const base: BookHit = {
  source: "gutendex",
  source_label: "Project Gutenberg",
  id: "1342",
  title: "Pride and Prejudice",
  authors: ["Austen, Jane"],
  access: "full_view",
  formats: [
    { kind: "epub", url: "https://www.gutenberg.org/ebooks/1342.epub3.images" },
    { kind: "txt", url: "https://www.gutenberg.org/ebooks/1342.txt.utf-8" },
  ],
  details_url: "https://www.gutenberg.org/ebooks/1342",
  partial: false,
};

describe("BookCard", () => {
  it("offers one download per format, best first", () => {
    renderWithProviders(<BookCard hit={base} best />);
    expect(screen.getByText("Best legal copy")).toBeTruthy();
    expect(screen.getByText("Project Gutenberg")).toBeTruthy();
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["EPUB", "Plain text"]);
  });

  it("explains when a book is not legally downloadable", () => {
    renderWithProviders(
      <BookCard
        hit={{
          ...base,
          access: "in_copyright",
          formats: [],
          library_links: [{ label: "WorldCat", url: "https://search.worldcat.org/search?q=x" }],
          buy_links: [{ label: "Bookshop", url: "https://bookshop.org/search?keywords=x" }],
        }}
      />,
    );
    expect(screen.getByText("Not legally downloadable.")).toBeTruthy();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.getByRole("link", { name: /Borrow: WorldCat/ }).getAttribute("href")).toContain(
      "worldcat",
    );
    expect(screen.getByRole("link", { name: /Buy: Bookshop/ })).toBeTruthy();
  });
});
