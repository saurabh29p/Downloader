"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { PALETTE_EVENT } from "@/components/shell/nav-links";

// The dialog code loads only the first time someone opens the palette.
const CommandDialog = dynamic(() => import("./command-dialog"), { ssr: false });

/** Ctrl/⌘ + K opens a quick menu: go to a page, switch theme. */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setLoaded(true);
        setOpen((value) => !value);
      }
    };
    const onOpen = () => {
      setLoaded(true);
      setOpen(true);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener(PALETTE_EVENT, onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(PALETTE_EVENT, onOpen);
    };
  }, []);

  return loaded ? <CommandDialog open={open} onOpenChange={setOpen} /> : null;
}
