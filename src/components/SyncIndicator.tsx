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
