/** Section ids in display order (the API holds their sources, presets and links). */
export const MAIN_SECTIONS = ["movies", "books", "music", "video", "declassified", "more"] as const;
export const MORE_SECTIONS = ["maps", "newspapers", "photos", "manuscripts"] as const;
export const ALL_SECTIONS = [...MAIN_SECTIONS, ...MORE_SECTIONS] as const;
export type SectionId = (typeof ALL_SECTIONS)[number];

export function isSection(id: string): id is SectionId {
  return (ALL_SECTIONS as readonly string[]).includes(id);
}
