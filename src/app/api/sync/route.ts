import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";
import { put, list, del } from "@vercel/blob";

/**
 * Cloud sync.
 *
 * This used to run on an Upstash Redis store reached over the network. That
 * store was uninstalled, and every call then failed with ENOTFOUND against a
 * hostname that no longer resolved — silently, for months, because the client
 * stamped "last synced" without reading the response. Vercel Blob is
 * first-party storage on the same account: there is no third-party integration
 * to lapse and no external host to disappear.
 *
 * Blob objects are readable by anyone who knows their URL, so the sync code
 * never appears in the path. The path is a keyed hash of it, which also means
 * a guessable code like "myquiz2024" no longer yields a guessable URL — a
 * little stronger than the old scheme, where guessing the code was enough.
 */

const MAX_SIZE = 512 * 1024; // 512 KB per sync code
const PREFIX = "sync/";

/** Same code always lands on the same object; the code itself never leaks into the URL. */
function pathFor(code: string): string {
  const salt = process.env.SYNC_PATH_SALT || "";
  const digest = createHash("sha256").update(`${salt}:${code}`).digest("hex");
  return `${PREFIX}${digest}.json`;
}

function badCode(code: string | undefined | null): string | null {
  if (!code || code.length < 3 || code.length > 50) {
    return "Sync code must be 3-50 characters";
  }
  return null;
}

function configured(): boolean {
  return Boolean(process.env.BLOB_READ_WRITE_TOKEN);
}

// GET /api/sync?code=mycode — Load progress from cloud
export async function GET(req: NextRequest) {
  const code = req.nextUrl.searchParams.get("code")?.trim().toLowerCase();
  const problem = badCode(code);
  if (problem) return NextResponse.json({ error: problem }, { status: 400 });

  if (!configured()) {
    return NextResponse.json(
      { error: "Cloud sync is not configured on the server." },
      { status: 503 }
    );
  }

  try {
    const pathname = pathFor(code!);
    // `list` by exact prefix rather than guessing the public URL, so the
    // response is authoritative about whether anything was ever saved.
    const found = await list({ prefix: pathname, limit: 1 });
    const blob = found.blobs.find((b) => b.pathname === pathname);
    if (!blob) return NextResponse.json({ exists: false, data: null });

    const res = await fetch(blob.url, { cache: "no-store" });
    if (!res.ok) throw new Error(`blob fetch ${res.status}`);
    const data = await res.json();
    return NextResponse.json({ exists: true, data });
  } catch (err) {
    console.error("Blob GET error:", err);
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
  const problem = badCode(code);
  if (problem) return NextResponse.json({ error: problem }, { status: 400 });

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

  if (!configured()) {
    return NextResponse.json(
      { error: "Cloud sync is not configured on the server." },
      { status: 503 }
    );
  }

  try {
    const pathname = pathFor(code!);
    await put(pathname, payload, {
      access: "public",
      contentType: "application/json",
      // One object per sync code, overwritten in place. Without both of these
      // every save would mint a new URL and the reader would find stale copies.
      addRandomSuffix: false,
      allowOverwrite: true,
      cacheControlMaxAge: 0,
    });
    return NextResponse.json({ success: true, size: payload.length });
  } catch (err) {
    console.error("Blob PUT error:", err);
    return NextResponse.json({ error: "Failed to save to cloud" }, { status: 500 });
  }
}

// DELETE /api/sync?code=mycode — Forget a sync code's cloud copy
export async function DELETE(req: NextRequest) {
  const code = req.nextUrl.searchParams.get("code")?.trim().toLowerCase();
  const problem = badCode(code);
  if (problem) return NextResponse.json({ error: problem }, { status: 400 });

  if (!configured()) {
    return NextResponse.json(
      { error: "Cloud sync is not configured on the server." },
      { status: 503 }
    );
  }

  try {
    const pathname = pathFor(code!);
    const found = await list({ prefix: pathname, limit: 1 });
    const blob = found.blobs.find((b) => b.pathname === pathname);
    if (blob) await del(blob.url);
    return NextResponse.json({ success: true, existed: Boolean(blob) });
  } catch (err) {
    console.error("Blob DELETE error:", err);
    return NextResponse.json({ error: "Failed to delete from cloud" }, { status: 500 });
  }
}
