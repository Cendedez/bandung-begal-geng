"use client";

import dynamic from "next/dynamic";

const MapExperience = dynamic(() => import("../components/MapExperience"), {
  ssr: false,
  loading: () => <main className="app-loading">Menyiapkan peta Bandung Raya...</main>,
});

export default function HomePage() {
  return <MapExperience />;
}
