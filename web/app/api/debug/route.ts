import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    internal_api_url: process.env.INTERNAL_API_URL || "NOT_SET",
  });
}
