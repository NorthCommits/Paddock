import type { MetadataRoute } from "next";

// Lets a phone or computer install Paddock as an app: its own window, icon and start page.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Paddock",
    short_name: "Paddock",
    description: "A shared workspace for people and their own AI agents.",
    start_url: "/pages",
    scope: "/",
    display: "standalone",
    background_color: "#f5f3ee",
    theme_color: "#f5f3ee",
    icons: [
      { src: "/brand/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/brand/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/brand/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
