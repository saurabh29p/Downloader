import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import type { SectionId } from "@/lib/sections";

/** Server-rendered section cards (no client JS). */
export function SectionsGrid({
  ids,
  headingId,
}: {
  ids: readonly SectionId[];
  headingId?: string;
}) {
  const t = useTranslations("Sections");
  return (
    <ul
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
      aria-labelledby={headingId}
      data-testid="sections-grid"
    >
      {ids.map((id) => (
        <li key={id}>
          <Link
            href={`/sections/${id}`}
            className="flex min-h-11 flex-col gap-1 rounded-lg border bg-card p-4 shadow-card hover:bg-accent"
          >
            <span className="font-medium">{t(`${id}.title`)}</span>
            <span className="text-sm text-muted-foreground">{t(`${id}.text`)}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
