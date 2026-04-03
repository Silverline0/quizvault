/**
 * Cloud sync module — auto-saves progress to Upstash Redis after each answer.
 *
 * Design:
 * - Debounced: waits 2s after last change before syncing (batches rapid answers)
 * - Non-blocking: sync failures don't affect the quiz experience
 * - Auto-load on startup if a sync code is saved
 * - Tiny indicator in the UI shows sync status
 */

import { UserProgress } from "./types";

const SYNC_CODE_KEY = "quizvault_sync_code";
const LAST_SYNC_KEY = "quizvault_last_sync";
const DEBOUNCE_MS = 2000;

export type SyncStatus = "idle" | "syncing" | "synced" | "error" | "offline";

type SyncListener = (status: SyncStatus) => void;

let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let listeners: SyncListener[] = [];
let currentStatus: SyncStatus = "idle";

// ── Status management ────────────────────────────────────────────

function setStatus(status: SyncStatus) {
  currentStatus = status;
  listeners.forEach((fn) => fn(status));
}

export function getSyncStatus(): SyncStatus {
  return currentStatus;
}

export function onSyncStatusChange(fn: SyncListener): () => void {
  listeners.push(fn);
  return () => {
    listeners = listeners.filter((l) => l !== fn);
  };
}

// ── Sync code management ─────────────────────────────────────────

export function getSyncCode(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SYNC_CODE_KEY);
}

export function setSyncCode(code: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(SYNC_CODE_KEY, code.trim().toLowerCase());
}

export function clearSyncCode(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SYNC_CODE_KEY);
  localStorage.removeItem(LAST_SYNC_KEY);
}

export function getLastSyncTime(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(LAST_SYNC_KEY);
}

// ── Auto-sync (debounced) ────────────────────────────────────────

export function triggerAutoSync(progress: UserProgress): void {
  const code = getSyncCode();
  if (!code) return; // no sync code set, skip silently

  // Debounce: reset timer on each call
  if (debounceTimer) clearTimeout(debounceTimer);

  debounceTimer = setTimeout(async () => {
    setStatus("syncing");
    try {
      const res = await fetch("/api/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, data: progress }),
      });

      if (!res.ok) {
        const err = await res.json();
        console.warn("[CloudSync] Save failed:", err.error);
        setStatus("error");
        return;
      }

      const now = new Date().toLocaleString();
      localStorage.setItem(LAST_SYNC_KEY, now);
      setStatus("synced");

      // Reset to idle after 3s so the indicator doesn't stay green forever
      setTimeout(() => {
        if (currentStatus === "synced") setStatus("idle");
      }, 3000);
    } catch {
      console.warn("[CloudSync] Network error");
      setStatus("error");
    }
  }, DEBOUNCE_MS);
}

// ── Load from cloud ──────────────────────────────────────────────

export async function loadFromCloud(): Promise<UserProgress | null> {
  const code = getSyncCode();
  if (!code) return null;

  try {
    const res = await fetch(`/api/sync?code=${encodeURIComponent(code)}`);
    if (!res.ok) return null;

    const result = await res.json();
    if (!result.exists || !result.data) return null;

    const data = result.data as UserProgress;
    if (!data.answers || !Array.isArray(data.answers)) return null;

    localStorage.setItem(LAST_SYNC_KEY, new Date().toLocaleString());
    return data;
  } catch {
    console.warn("[CloudSync] Load failed");
    return null;
  }
}
