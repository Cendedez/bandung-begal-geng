import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const runtime = "nodejs";

const INTERNAL_API_URL =
  process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;

  // Use https:// for Ngrok because redirects can drop custom upstream headers.
  let rawUpstream = INTERNAL_API_URL.replace(/\/+$/, "");
  if (rawUpstream.includes("ngrok-free.app")) {
    rawUpstream = rawUpstream.replace(/^http:\/\//, "https://");
  }
  const upstream = `${rawUpstream}/${path.join("/")}${request.nextUrl.search}`;

  // Keep these as a plain object so the tunnel headers are passed verbatim.
  const customHeaders: Record<string, string> = {
    "ngrok-skip-browser-warning": "true",
    "user-agent": "curl/7.68.0", // Force curl user-agent
    "accept": "application/json",
  };
  const contentType = request.headers.get("content-type");
  if (contentType) customHeaders["content-type"] = contentType;

  try {
    const upstreamResponse = await fetch(upstream, {
      method: request.method,
      headers: customHeaders,
      cache: "no-store",
      body: request.method !== "GET" && request.method !== "HEAD"
        ? await request.blob()
        : undefined,
    });

    const upstreamContentType = upstreamResponse.headers.get("content-type") ?? "";
    const expectsJson = path[0] === "v1" || path[0] === "health" || path[0] === "debug";
    if (upstreamResponse.ok && expectsJson && !upstreamContentType.toLowerCase().includes("application/json")) {
      const preview = await upstreamResponse.text();
      return NextResponse.json(
        {
          error: "Backend API returned a non-JSON response",
          details: preview.includes("ERR_NGROK_")
            ? "Ngrok warning page was returned. Check that the deployed proxy injects ngrok-skip-browser-warning."
            : preview.slice(0, 240),
        },
        {
          status: 502,
          headers: { "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate" },
        },
      );
    }

    const responseHeaders = new Headers(upstreamResponse.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");
    responseHeaders.delete("transfer-encoding");
    responseHeaders.set("Cache-Control", "no-store, no-cache, max-age=0, must-revalidate");

    return new NextResponse(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown upstream error";
    return NextResponse.json(
      { error: "Backend API is unreachable", details: message },
      {
        status: 502,
        headers: { "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate" },
      }
    );
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
export const PATCH = handler;
