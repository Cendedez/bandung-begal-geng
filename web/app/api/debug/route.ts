import { NextResponse } from "next/server";

const INTERNAL_API_URL =
  process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  const masked = INTERNAL_API_URL.replace(/^(https?:\/\/[^/]{8}).*/, "$1***");
  
  let backendStatus = "unknown";
  let backendBody = "";
  try {
    const res = await fetch(`${INTERNAL_API_URL}/health`, {
      headers: { "ngrok-skip-browser-warning": "true" },
      signal: AbortSignal.timeout(5000),
    });
    backendStatus = `${res.status} ${res.statusText}`;
    backendBody = await res.text();
  } catch (err: unknown) {
    backendStatus = `error: ${err instanceof Error ? err.message : String(err)}`;
  }

  return NextResponse.json({
    env_internal_api_url: masked,
    full_url: INTERNAL_API_URL,
    backend_health: backendStatus,
    backend_response: backendBody,
    timestamp: new Date().toISOString(),
    vercel_region: process.env.VERCEL_REGION ?? "unknown",
  });
}
