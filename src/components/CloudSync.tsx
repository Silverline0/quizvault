"use client";

import { useState, useEffect } from "react";
import { getProgress, saveProgress } from "@/lib/store";
import { UserProgress } from "@/lib/types";

export default function CloudSync({ onSyncComplete }: { onSyncComplete?: () => void }) {
  const [syncCode, setSyncCode] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [lastSync, setLastSync] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("quizvault_sync_code");
    if (saved) setSyncCode(saved);
    const ls = localStorage.getItem("quizvault_last_sync");
    if (ls) setLastSync(ls);
  }, []);

  const handleSave = async () => {
    if (!syncCode.trim() || syncCode.trim().length < 3) {
      setMessage("Code must be at least 3 characters");
      setStatus("error");
      return;
    }

    setStatus("saving");
    setMessage("");

    try {
      const progress = getProgress();
      const res = await fetch("/api/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: syncCode.trim(), data: progress }),
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.error || "Failed to save");
      }

      const sizeKB = Math.round((result.size || 0) / 1024);
      const now = new Date().toLocaleString();
      localStorage.setItem("quizvault_sync_code", syncCode.trim());
      localStorage.setItem("quizvault_last_sync", now);
      setLastSync(now);
      setMessage(`Saved to cloud (${sizeKB}KB)`);
      setStatus("success");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save failed");
      setStatus("error");
    }
  };

  const handleLoad = async () => {
    if (!syncCode.trim() || syncCode.trim().length < 3) {
      setMessage("Code must be at least 3 characters");
      setStatus("error");
      return;
    }

    setStatus("loading");
    setMessage("");

    try {
      const res = await fetch(`/api/sync?code=${encodeURIComponent(syncCode.trim())}`);
      const result = await res.json();

      if (!res.ok) {
        throw new Error(result.error || "Failed to load");
      }

      if (!result.exists) {
        setMessage("No data found for this code. Save first!");
        setStatus("error");
        return;
      }

      const data = result.data as UserProgress;
      if (!data.answers || !Array.isArray(data.answers)) {
        throw new Error("Invalid data format");
      }

      saveProgress(data);
      localStorage.setItem("quizvault_sync_code", syncCode.trim());
      const now = new Date().toLocaleString();
      localStorage.setItem("quizvault_last_sync", now);
      setLastSync(now);
      setMessage(`Loaded ${data.answers.length} answers from cloud`);
      setStatus("success");
      onSyncComplete?.();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Load failed");
      setStatus("error");
    }
  };

  return (
    <div
      className="rounded-xl p-5"
      style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}
    >
      <div className="flex items-center gap-2 mb-3">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
        </svg>
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
          Cloud Sync
        </h3>
      </div>

      <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
        Use a sync code to save/load your progress across devices.
      </p>

      <div className="flex gap-2 mb-3">
        <input
          type="text"
          placeholder="Enter sync code (e.g. myquiz2024)"
          value={syncCode}
          onChange={(e) => setSyncCode(e.target.value)}
          className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
          style={{
            backgroundColor: "var(--bg-card)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSave();
          }}
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={status === "saving" || status === "loading"}
          className="px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          style={{ backgroundColor: "var(--accent)" }}
        >
          {status === "saving" ? "Saving..." : "Save to Cloud"}
        </button>
        <button
          onClick={handleLoad}
          disabled={status === "saving" || status === "loading"}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity hover:opacity-90 disabled:opacity-50"
          style={{
            backgroundColor: "var(--bg-card)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
          }}
        >
          {status === "loading" ? "Loading..." : "Load from Cloud"}
        </button>
      </div>

      {/* Status message */}
      {message && (
        <p
          className="text-xs mt-2"
          style={{
            color: status === "success" ? "var(--success)" : status === "error" ? "var(--error)" : "var(--text-muted)",
          }}
        >
          {message}
        </p>
      )}

      {lastSync && (
        <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
          Last synced: {lastSync}
        </p>
      )}
    </div>
  );
}
