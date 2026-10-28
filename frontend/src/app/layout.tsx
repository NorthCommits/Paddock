import type { Metadata, Viewport } from "next";
import "@fontsource-variable/sora";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource/instrument-serif";
import { Warm } from "@/components/warm";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Paddock", template: "%s | Paddock" },
  description: "A shared workspace for people and their own AI agents.",
  icons: {
    icon: [
      { url: "/brand/icon.svg", type: "image/svg+xml" },
      { url: "/brand/favicon-32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: "/brand/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f3ee" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1115" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('paddock-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}",
          }}
        />
      </head>
      <body className="font-sans">
        <nav aria-label="Skip links"><a href="#main" className="skip-link">Skip to content</a></nav>
        <Warm />
        {children}
      </body>
    </html>
  );
}
