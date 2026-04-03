"use client";

import { useState, useEffect } from "react";
import { getProgress, saveProgress } from "@/lib/store";
import {
  getSyncCode,
  setSyncCode as storeSyncCode,
  clearSyncCode,
  getLastSyncTime,
  loadFromCloud,
} from "@/lib/cloud-sync";

export default function CloudSync({ onSyncComplete }: { onSyncComplete?: () => void }) {
  const [syncCode, setSyncCode] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const saved = getSyncCode();
    if (saved) {
      setSyncCode(saved);
      setIsConnected(true);
    }
    setLastSync(getLastSyncTime());
  }, []);

  // Auto-load from cloud on first visit if sync code exists
  useEffect(() => {
    const saved = getSyncCode();
    if (!saved) return;

    const localProgress = getProgress();
    // Only auto-load if local is empty (new device)
    if (localProgress.answers.length === 0) {
      loadFromCloud().then((cloudData) => {
        if (cloudData && cloudData.answers.length > 0) {
          saveProgress(cloudData);
          setMessage(`Auto-loaded ${cloudData.answers.length} answers from cloud`);
          setStatus("success");
          setLastSync(getLastSyncTime());
          onSyncComplete?.();
        }
      });
    }
  }, []);

  const handleConnect = async () => {
    const code = syncCode.trim().toLowerCase();
    if (!code || code.length < 3) {
      setMessage("Code must be at least 3 characters");
      setStatus("error");
      return;
    }

    storeSyncCode(code);
    setIsConnected(true);
    setStatus("loading");
    setMessage("");

    // Try to load existing cloud data
    const cloudData = await loadFromCloud();
    const localProgress = getProgress();

    if (cloudData && cloudData.answers.length > 0) {
      if (localProgress.answers.length === 0) {
        // Local is empty, use cloud data
        saveProgress(cloudData);
        setMessage(`Loaded ${cloudData.answers.length} answers from cloud`);
        onSyncComplete?.();
      } else if (cloudData.answers.length > localProgress.answers.length) {
        // Cloud has more data, ask... but for simplicity, merge by using cloud
        saveProgress(cloudData);
        setMessage(`Updated from cloud (${cloudData.answers.length} answers)`);
        onSyncComplete?.();
      } else {
        // Local has equal or more data, push to cloud
        const res = await fetch("/api/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, data: localProgress }),
        });
        if (res.ok) {
          setMessage("Local progress synced to cloud");
        }
      }
    } else {
      // No cloud data yet, push local
      if (localProgress.answers.length > 0) {
        await fetch("/api/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, data: localProgress }),
        });
        setMessage("Progress saved to cloud");
      } else {
        setMessage("Connected! Progress will auto-sync after each answer.");
      }
    }

    setLastSync(getLastSyncTime());
    setStatus("success");
  };

  const handleDisconnect = () => {
    clearSyncCode();
    setIsConnected(false);
    setSyncCode("");
    setMessage("");
    setStatus("idle");
    setLastSync(null);
  };

  const handleForceSync = async () => {
    const code = getSyncCode();
    if (!code) return;

    setStatus("saving");
    try {
      const progress = getProgress();
      const res = await fetch("/api/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, data: progress }),
      });
      if (!res.ok) throw new Error("Failed");
      setMessage("Synced now");
      setLastSync(new Date().toLocaleString());
      setStatus("success");
    } catch {
      setMessage("Sync failed");
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
        {isConnected && (
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{ backgroundColor: "var(--success-bg)", color: "var(--success)" }}
          >
            Connected
          </span>
        )}
      </div>

      {!isConnected ? (
        <>
          <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
            Enter a sync code to save progress across devices. Auto-syncs after every answer.
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="e.g. myquiz2024"
              value={syncCode}
              onChange={(e) => setSyncCode(e.target.value)}
              className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
              style={{
                backgroundColor: "var(--bg-card)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
              onKeyDown={(e) => e.key === "Enter" && handleConnect()}
            />
            <button
              onClick={handleConnect}
              disabled={status === "loading"}
              className="px-4 py-2 rounded-lg text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ backgroundColor: "var(--accent)" }}
            >
              {status === "loading" ? "Connecting..." : "Connect"}
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>
            Code: <strong>{syncCode}</strong> — auto-syncs 2s after each answer
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleForceSync}
              disabled={status === "saving"}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            >
              {status === "saving" ? "Syncing..." : "Sync Now"}
            </button>
            <button
              onClick={handleDisconnect}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity hover:opacity-90"
              style={{ color: "var(--error)", border: "1px solid var(--error)" }}
            >
              Disconnect
            </button>
          </div>
        </>
      )}

      {message && (
        <p
          className="text-xs mt-2"
          style={{ color: status === "success" ? "var(--success)" : status === "error" ? "var(--error)" : "var(--text-muted)" }}
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
