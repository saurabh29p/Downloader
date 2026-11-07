import type { ResultCard } from "@/lib/api-universal";

/** Cards in the AI helper's order; cards it didn't mention keep their place at the end. */
export function byOrder(cards: ResultCard[], order: string[]): ResultCard[] {
  const position = new Map(order.map((id, i) => [id, i]));
  return [...cards].sort(
    (a, b) => (position.get(a.id) ?? order.length) - (position.get(b.id) ?? order.length),
  );
}
