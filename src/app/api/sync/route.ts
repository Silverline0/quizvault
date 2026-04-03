import { NextRequest, NextResponse } from "next/server";
import { getRedis } from "@/lib/redis";

const PREFIX = "quizvault:progress:";
const MAX_SIZE = 512 * 1024; // 512 KB max per sync code
const TTL = 60 * 60 * 24 * 365; // 1 year expiry

// GET /api/sync?code=mycode — Load progress from cloud
export async function GET(req: NextRequest) {
  const code = req.nextUrl.searchParams.get("code")?.trim().toLowerCase();
  if (!code || code.length < 3 || code.length > 50) {
    return NextResponse.json(
      { error: "Sync code must be 3-50 characters" },
      { status: 400 }
    );
  }

  const redis = getRedis();
  if (!redis) {
    return NextResponse.json(
      { error: "Cloud sync not configured. Set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN." },
      { status: 503 }
    );
  }

  try {
    const data = await redis.get(PREFIX + code);
    if (!data) {
      return NextResponse.json({ exists: false, data: null });
    }
    return NextResponse.json({ exists: true, data });
  } catch (err) {
    console.error("Redis GET error:", err);
    return NextResponse.json({ error: "Failed to load from cloud" }, { status: 500 });
  }
}

// POST /api/sync — Save progress to cloud
export async function POST(req: NextRequest) {
  let body: { code?: string; data?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const code = body.code?.toString().trim().toLowerCase();
  if (!code || code.length < 3 || code.length > 50) {
    return NextResponse.json(
      { error: "Sync code must be 3-50 characters" },
      { status: 400 }
    );
  }

  if (!body.data) {
    return NextResponse.json({ error: "No data provided" }, { status: 400 });
  }

  const payload = JSON.stringify(body.data);
  if (payload.length > MAX_SIZE) {
    return NextResponse.json(
      { error: `Data too large (${Math.round(payload.length / 1024)}KB, max 512KB)` },
      { status: 413 }
    );
  }

  const redis = getRedis();
  if (!redis) {
    return NextResponse.json(
      { error: "Cloud sync not configured" },
      { status: 503 }
    );
  }

  try {
    await redis.set(PREFIX + code, body.data, { ex: TTL });
    return NextResponse.json({ success: true, size: payload.length });
  } catch (err) {
    console.error("Redis SET error:", err);
    return NextResponse.json({ error: "Failed to save to cloud" }, { status: 500 });
  }
}
