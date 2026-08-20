"use client";

import { useEffect, useState } from "react";
import { getSyncCode, getSyncStatus, onSyncStatusChange, SyncStatus } from "@/lib/cloud-sync";

export default function SyncIndicator() {
  const [status, setStatus] = useState<SyncStatus>("idle");
  const [hasCode, setHasCode] = useState(false);

  useEffect(() => {
    setHasCode(!!getSyncCode());
    setStatus(getSyncStatus());
    const unsub = onSyncStatusChange(setStatus);
    return unsub;
  }, []);

  if (!hasCode) return null;

  const colors: Record<SyncStatus, string> = {
    idle: "var(--success)",
    syncing: "var(--accent)",
    synced: "var(--success)",
    error: "var(--error)",
    offline: "var(--text-muted)",
  };

  const labels: Record<SyncStatus, string> = {
    idle: "Cloud sync on",
    syncing: "Syncing...",
    synced: "Synced",
    error: "Sync error",
    offline: "Offline",
  };

  // A bare dot carries a tooltip, and a phone has no hover — so a sync that
  // keeps failing looked identical to one that was fine. Say it in words.
  if (status === "error") {
    return (
      <div
        className="fixed bottom-20 right-4 z-40 flex items-center gap-1.5 px-2 py-1 animate-fade-in"
        style={{
          backgroundColor: "var(--error-bg)",
          border: "1px solid var(--error)",
          color: "var(--error)",
        }}
        title="Progress is still saved on this device, but it is not reaching the cloud."
      >
        <span className="block w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: "var(--error)" }} />
        <span className="text-[10px] font-semibold whitespace-nowrap">Sync failing</span>
      </div>
    );
  }

  return (
    <div
      className="fixed bottom-20 right-4 z-40"
      title={labels[status]}
    >
      <span
        className={`block w-3 h-3 rounded-full ${status === "syncing" ? "animate-pulse" : ""}`}
        style={{ backgroundColor: colors[status] }}
      />
    </div>
  );
}
