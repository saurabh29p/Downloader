import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";

// Pages that aren't in the main navigation. Server-rendered (no client JS): Home lists
// the sources, the Sections page lists everything (its "Tools" part, /sections#tools).
export const SOURCES = [
  { href: "/books", key: "books" },
  { href: "/libraries", key: "libraries" },
  { href: "/archive", key: "archive" },
  { href: "/wayback", key: "wayback" },
  { href: "/code", key: "code" },
  { href: "/images", key: "images" },
] as const;

export const TOOLS = [
  ...SOURCES,
  { href: "/watch", key: "watch" },
  { href: "/connections", key: "connections" },
] as const;

export function ToolsList({ items }: { items: readonly (typeof TOOLS)[number][] }) {
  const t = useTranslations("Home");
  return (
    <ul className="grid grid-cols-1 gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
      {items.map(({ href, key }) => (
        <li key={href} className="border-b border-dashed">
          <Link href={href} className="flex min-h-11 flex-col py-2.5 hover:text-primary">
            <span className="font-medium">{t(`source.${key}.title`)}</span>
            <span className="text-sm text-muted-foreground">{t(`source.${key}.text`)}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
