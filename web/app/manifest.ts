import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Bandung Aman",
    short_name: "Bandung Aman",
    description: "Peta indikatif laporan begal dan geng motor di Bandung Raya.",
    start_url: "/",
    display: "standalone",
    background_color: "#f6f7f3",
    theme_color: "#0e1c33",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
  };
}
