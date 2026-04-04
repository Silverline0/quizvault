"use client";

import { useState, useEffect } from "react";
import { AppSettings, getSettings, saveSettings } from "@/lib/settings";
import Link from "next/link";

const FONT_SIZES = [
  { id: "small" as const, label: "Small", preview: "Aa" },
  { id: "medium" as const, label: "Medium", preview: "Aa" },
  { id: "large" as const, label: "Large", preview: "Aa" },
];

const KEY_LABELS: Record<string, string> = {
  optionA: "Option A",
  optionB: "Option B",
  optionC: "Option C",
  optionD: "Option D",
  next: "Next Question",
  prev: "Previous Question",
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(getSettings());
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSettings(getSettings());
  }, []);

  const update = (partial: Partial<AppSettings>) => {
    const updated = saveSettings(partial);
    setSettings(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);

    // Apply theme immediately
    if (partial.theme) {
      document.documentElement.setAttribute("data-theme", partial.theme);
      localStorage.setItem("theme", partial.theme);
    }

    // Apply font size immediately
    if (partial.fontSize) {
      document.documentElement.setAttribute("data-fontsize", partial.fontSize);
    }
  };

  const handleKeyCapture = (settingKey: string) => {
    setEditingKey(settingKey);
    const handler = (e: KeyboardEvent) => {
      e.preventDefault();
      const newKeyMap = { ...settings.keyMap, [settingKey]: e.key };
      update({ keyMap: newKeyMap });
      setEditingKey(null);
      window.removeEventListener("keydown", handler);
    };
    window.addEventListener("keydown", handler);
  };

  return (
    <div className="max-w-xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            <span className="font-display italic">Settings</span>
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            Customize your study experience
          </p>
        </div>
        {saved && (
          <span className="text-xs font-medium px-3 py-1 rounded-full animate-fade-in"
            style={{ backgroundColor: "var(--success-bg)", color: "var(--success)" }}>
            Saved
          </span>
        )}
      </div>

      {/* ── Display ───────────────────────── */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
          Display
        </h2>

        {/* Theme */}
        <div className="rounded-xl p-4 mb-3" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <p className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>Theme</p>
          <div className="flex gap-2">
            {(["light", "dark", "sepia"] as const).map((t) => (
              <button
                key={t}
                onClick={() => update({ theme: t })}
                className="flex-1 py-2.5 rounded-lg text-xs font-semibold capitalize transition-all"
                style={{
                  backgroundColor: settings.theme === t ? "var(--accent-light)" : "var(--bg-secondary)",
                  border: `2px solid ${settings.theme === t ? "var(--accent)" : "var(--border)"}`,
                  color: settings.theme === t ? "var(--accent)" : "var(--text-secondary)",
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Font Size */}
        <div className="rounded-xl p-4" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <p className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>Font Size</p>
          <div className="flex gap-2">
            {FONT_SIZES.map((fs) => (
              <button
                key={fs.id}
                onClick={() => update({ fontSize: fs.id })}
                className="flex-1 py-3 rounded-lg transition-all flex flex-col items-center gap-1"
                style={{
                  backgroundColor: settings.fontSize === fs.id ? "var(--accent-light)" : "var(--bg-secondary)",
                  border: `2px solid ${settings.fontSize === fs.id ? "var(--accent)" : "var(--border)"}`,
                  color: settings.fontSize === fs.id ? "var(--accent)" : "var(--text-secondary)",
                }}
              >
                <span style={{ fontSize: fs.id === "small" ? "14px" : fs.id === "large" ? "22px" : "18px", fontWeight: 700 }}>
                  {fs.preview}
                </span>
                <span className="text-xs">{fs.label}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ── Quiz Behavior ─────────────────── */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
          Quiz Behavior
        </h2>
        <div className="rounded-xl overflow-hidden" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          {[
            { key: "spacedRepEnabled" as const, label: "Spaced Repetition", desc: "Resurface wrong answers at increasing intervals (1, 3, 7, 14, 30 days)" },
            { key: "hapticFeedback" as const, label: "Haptic Feedback", desc: "Vibrate on correct/incorrect answers (mobile only)" },
            { key: "showKeyboardHints" as const, label: "Keyboard Hints", desc: "Show A/B/C/D key hints below options" },
          ].map((item, i) => (
            <div
              key={item.key}
              className="flex items-center justify-between px-4 py-3.5"
              style={{ borderTop: i > 0 ? "1px solid var(--border)" : "none" }}
            >
              <div className="flex-1 mr-4">
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{item.label}</p>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{item.desc}</p>
              </div>
              <button
                onClick={() => update({ [item.key]: !settings[item.key] })}
                className="w-11 h-6 rounded-full relative transition-colors shrink-0"
                style={{
                  backgroundColor: settings[item.key] ? "var(--accent)" : "var(--border)",
                }}
              >
                <span
                  className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform"
                  style={{
                    left: settings[item.key] ? "calc(100% - 22px)" : "2px",
                  }}
                />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* ── Keyboard Shortcuts ────────────── */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
          Keyboard Shortcuts
        </h2>
        <div className="rounded-xl overflow-hidden" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          {Object.entries(settings.keyMap).map(([key, value], i) => (
            <div
              key={key}
              className="flex items-center justify-between px-4 py-3"
              style={{ borderTop: i > 0 ? "1px solid var(--border)" : "none" }}
            >
              <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                {KEY_LABELS[key] || key}
              </span>
              <button
                onClick={() => handleKeyCapture(key)}
                className="px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all"
                style={{
                  backgroundColor: editingKey === key ? "var(--accent-light)" : "var(--bg-secondary)",
                  border: `2px solid ${editingKey === key ? "var(--accent)" : "var(--border)"}`,
                  color: editingKey === key ? "var(--accent)" : "var(--text-primary)",
                  minWidth: "60px",
                  textAlign: "center",
                }}
              >
                {editingKey === key ? "Press key..." : value}
              </button>
            </div>
          ))}
        </div>
        <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
          Click a key binding, then press the new key to remap it.
        </p>
      </section>

      {/* ── Study Plan ────────────────────── */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
          Study Plan
        </h2>
        <div className="rounded-xl p-4" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="mb-4">
            <label className="text-sm font-medium block mb-1.5" style={{ color: "var(--text-primary)" }}>
              Exam Date
            </label>
            <input
              type="date"
              value={settings.examDate || ""}
              onChange={(e) => update({ examDate: e.target.value })}
              className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
              style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1.5" style={{ color: "var(--text-primary)" }}>
              Daily Goal (questions)
            </label>
            <div className="flex gap-2">
              {[25, 50, 100, 200].map((n) => (
                <button
                  key={n}
                  onClick={() => update({ dailyGoal: n })}
                  className="flex-1 py-2 rounded-lg text-xs font-semibold transition-all"
                  style={{
                    backgroundColor: settings.dailyGoal === n ? "var(--accent-light)" : "var(--bg-secondary)",
                    border: `2px solid ${settings.dailyGoal === n ? "var(--accent)" : "var(--border)"}`,
                    color: settings.dailyGoal === n ? "var(--accent)" : "var(--text-secondary)",
                  }}
                >
                  {n}/day
                </button>
              ))}
            </div>
          </div>
          {settings.examDate && (
            <div className="mt-4 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {(() => {
                  const days = Math.ceil((new Date(settings.examDate).getTime() - Date.now()) / 86400000);
                  const goal = settings.dailyGoal || 50;
                  return days > 0
                    ? `${days} days until exam · ${goal} Qs/day = ${days * goal} total · You have 4,026 questions available`
                    : "Exam date has passed";
                })()}
              </p>
            </div>
          )}
        </div>
      </section>

      <Link href="/" className="block text-center text-sm hover:opacity-70 mb-8" style={{ color: "var(--accent)" }}>
        ← Back to Home
      </Link>
    </div>
  );
}
