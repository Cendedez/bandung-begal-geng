import { NextRequest, NextResponse } from "next/server";

const INTERNAL_API_URL =
  process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const upstream = `${INTERNAL_API_URL}/${path.join("/")}${request.nextUrl.search}`;

  // Create completely CLEAN headers, do NOT forward browser headers
  // Forwarding browser headers can trigger Ngrok's anti-abuse system
  const headers = new Headers();
  headers.set("ngrok-skip-browser-warning", "true");
  headers.set("User-Agent", "curl/7.68.0"); // Ngrok officially whitelists curl
  headers.set("Accept", "application/json");

  try {
    const upstreamResponse = await fetch(upstream, {
      method: request.method,
      headers,
      cache: "no-store",
      body: request.method !== "GET" && request.method !== "HEAD"
        ? await request.blob()
        : undefined,
    });

    const responseHeaders = new Headers(upstreamResponse.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("transfer-encoding");

    return new NextResponse(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Backend API is unreachable", details: err.message },
      { status: 502 }
    );
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
export const PATCH = handler;
