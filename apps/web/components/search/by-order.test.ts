import { describe, expect, it } from "vitest";

import type { ResultCard } from "@/lib/api-universal";

import { byOrder } from "./search-view";

const card = (id: string) => ({ id }) as ResultCard;

describe("byOrder", () => {
  it("follows the AI helper's order and keeps unranked cards at the end", () => {
    const cards = [card("a"), card("b"), card("c"), card("d")];
    expect(byOrder(cards, ["c", "a"]).map((c) => c.id)).toEqual(["c", "a", "b", "d"]);
    expect(cards.map((c) => c.id)).toEqual(["a", "b", "c", "d"]); // not changed in place
  });
});
