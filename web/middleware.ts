import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  // For API proxy requests, add ngrok bypass header
  if (request.nextUrl.pathname.startsWith("/api/")) {
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set("ngrok-skip-browser-warning", "true");

    return NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: "/api/:path*",
};
