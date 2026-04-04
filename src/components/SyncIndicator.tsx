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

  // Don't show anything if no sync code is configured
  if (!hasCode) return null;

  const config: Record<SyncStatus, { color: string; icon: string; label: string }> = {
    idle: { color: "var(--text-muted)", icon: "●", label: "Cloud sync on" },
    syncing: { color: "var(--accent)", icon: "↑", label: "Syncing..." },
    synced: { color: "var(--success)", icon: "✓", label: "Synced" },
    error: { color: "var(--error)", icon: "!", label: "Sync error" },
    offline: { color: "var(--text-muted)", icon: "○", label: "Offline" },
  };

  const c = config[status];

  return (
    <div
      className="fixed bottom-20 right-4 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium shadow-lg z-40 transition-all duration-300"
      style={{
        backgroundColor: "var(--bg-card)",
        border: "1px solid var(--border)",
        color: c.color,
        opacity: status === "idle" ? 0.6 : 1,
      }}
      title={c.label}
    >
      <span
        className={status === "syncing" ? "animate-pulse" : ""}
        style={{ fontSize: "10px" }}
      >
        {c.icon}
      </span>
      <span>{c.label}</span>
    </div>
  );
}
