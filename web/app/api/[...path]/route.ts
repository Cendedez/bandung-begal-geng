import { NextRequest, NextResponse } from "next/server";

const INTERNAL_API_URL =
  process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  
  // FORCE https:// because if the env var uses http://, Ngrok will respond with a 308 redirect to https://.
  // When Node/Next.js fetch follows a redirect, IT DROPS ALL CUSTOM HEADERS (security feature).
  // This causes the ngrok-skip-browser-warning to be lost, and the abuse page is returned.
  let rawUpstream = INTERNAL_API_URL;
  if (rawUpstream.includes("ngrok-free.app")) {
    rawUpstream = rawUpstream.replace(/^http:\/\//, "https://");
  }
  const upstream = `${rawUpstream}/${path.join("/")}${request.nextUrl.search}`;

  // Use a plain object for headers! Next.js edge fetch sometimes drops custom headers
  // if they are passed inside a Headers class instance due to internal sanitization bugs.
  const customHeaders = {
    "ngrok-skip-browser-warning": "true",
    "user-agent": "curl/7.68.0", // Force curl user-agent
    "accept": "application/json"
  };

  try {
    const upstreamResponse = await fetch(upstream, {
      method: request.method,
      headers: customHeaders,
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
