"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { useRouter } from "@/i18n/navigation";
import { DROP_EVENT, DROP_KEY } from "@/lib/drop";

const MAX_FILE = 2 * 1024 * 1024;

function wanted(event: DragEvent): boolean {
  const types = event.dataTransfer?.types ?? [];
  return types.includes("Files") || types.includes("text/uri-list");
}

/** Drop a link or a .txt list anywhere: it lands in Home's paste box and is checked. */
export function DropAnywhere() {
  const t = useTranslations("Shell");
  const router = useRouter();
  const [over, setOver] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onOver = (event: DragEvent) => {
      if (!wanted(event) || event.defaultPrevented) return;
      event.preventDefault();
      setOver(true);
      clearTimeout(timer);
      // dragover repeats while the pointer is over the page; stop seeing it = left.
      timer = setTimeout(() => setOver(false), 200);
    };
    const onDrop = async (event: DragEvent) => {
      setOver(false);
      if (!wanted(event) || event.defaultPrevented) return;
      event.preventDefault();
      const data = event.dataTransfer!;
      const file = data.files[0];
      const text =
        file && file.size <= MAX_FILE
          ? await file.text()
          : data.getData("text/uri-list") || data.getData("text");
      if (!text.trim()) return;
      if (document.querySelector("[data-testid=paste-input]")) {
        window.dispatchEvent(new CustomEvent(DROP_EVENT, { detail: text }));
        return;
      }
      try {
        sessionStorage.setItem(DROP_KEY, text.slice(0, MAX_FILE));
      } catch {
        return;
      }
      router.push("/");
    };
    window.addEventListener("dragover", onOver);
    window.addEventListener("drop", onDrop);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("dragover", onOver);
      window.removeEventListener("drop", onDrop);
    };
  }, [router]);

  if (!over) return null;
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-3 z-50 flex items-center justify-center rounded-xl border-2 border-dashed border-signal bg-background/85 font-serif text-2xl"
    >
      {t("dropHere")}
    </div>
  );
}
