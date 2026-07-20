import type { Metadata, Viewport } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { PwaRegistration } from "../components/PwaRegistration";

export const metadata: Metadata = {
  title: "Bandung Aman",
  description: "Peta indikatif laporan begal dan geng motor di Bandung Raya.",
  manifest: "/manifest.webmanifest",
  icons: [{ rel: "icon", url: "/icon.svg", type: "image/svg+xml" }],
};

export const viewport: Viewport = {
  themeColor: "#0e1c33",
  colorScheme: "light",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body>
        <PwaRegistration />
        {children}
      </body>
    </html>
  );
}
