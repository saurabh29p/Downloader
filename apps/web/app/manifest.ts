import type { MetadataRoute } from "next";

/** Web app manifest: installable app, and an Android share target that opens the preview. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "AnyGet",
    short_name: "AnyGet",
    description: "Paste any public link, get the file.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#fcfcfc",
    theme_color: "#2563eb",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    // Android "Share → AnyGet": the shared link arrives at /share, which opens the preview.
    share_target: {
      action: "/share",
      method: "GET",
      params: { title: "title", text: "text", url: "url" },
    },
  } as MetadataRoute.Manifest;
}
