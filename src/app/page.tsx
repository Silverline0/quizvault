"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Manifest, QuizMode, Category, QuestionSet } from "@/lib/types";
import { getStats, getMistakes, getLastPosition, exportProgress, importProgress, clearProgress } from "@/lib/store";
import CloudSync from "@/components/CloudSync";

const MODES: { id: QuizMode; label: string; desc: string; icon: string }[] = [
  { id: "sequential", label: "Sequential", desc: "Go through questions in order", icon: "→" },
  { id: "random", label: "Random", desc: "Shuffled, no repeats", icon: "🔀" },
  { id: "mistakes", label: "Mistakes Only", desc: "Review what you got wrong", icon: "✗" },
];

const SOURCE_COLORS: Record<string, { bg: string; text: string }> = {
  BCSC: { bg: "#dbeafe", text: "#1d4ed8" },
  OphthoQ: { bg: "#ede9fe", text: "#6d28d9" },
};

export default function HomePage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedSet, setSelectedSet] = useState<string | null>(null);
  const [overallStats, setOverallStats] = useState({ total: 0, correct: 0, accuracy: 0, uniqueQuestions: 0, streak: 0 });
  const [mistakeCounts, setMistakeCounts] = useState<Record<string, number>>({});
  const [positions, setPositions] = useState<Record<string, number>>({});

  useEffect(() => {
    fetch("/data/manifest.json")
      .then((r) => r.json())
      .then((m: Manifest) => {
        setManifest(m);
        // Auto-select if only 1 category
        if (m.categories && m.categories.length === 1) {
          setSelectedCategory(m.categories[0].id);
        }
      });
  }, []);

  const refreshStats = () => {
    setOverallStats(getStats());
    if (manifest) {
      const mc: Record<string, number> = {};
      const pos: Record<string, number> = {};
      for (const s of manifest.questionSets) {
        mc[s.id] = getMistakes(s.id).length;
        pos[s.id] = getLastPosition(s.id);
      }
      setMistakeCounts(mc);
      setPositions(pos);
    }
  };

  useEffect(() => {
    refreshStats();
  }, [manifest]);

  const handleExport = () => {
    const data = exportProgress();
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `quizvault-progress-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const text = await file.text();
      if (importProgress(text)) {
        refreshStats();
        alert("Progress imported successfully!");
      } else {
        alert("Invalid progress file.");
      }
    };
    input.click();
  };

  const handleClear = () => {
    if (confirm("Clear all progress? This cannot be undone.")) {
      clearProgress();
      setOverallStats({ total: 0, correct: 0, accuracy: 0, uniqueQuestions: 0, streak: 0 });
      setMistakeCounts({});
      setPositions({});
    }
  };

  if (!manifest) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div
          className="w-10 h-10 border-4 rounded-full animate-spin"
          style={{ borderColor: "var(--border)", borderTopColor: "var(--accent)" }}
        />
      </div>
    );
  }

  const categories = manifest.categories || [];
  const totalQuestions = manifest.questionSets.reduce((sum, s) => sum + s.questionCount, 0);

  // Get sets for selected category
  const categorySets = selectedCategory
    ? manifest.questionSets.filter((s) => s.category === selectedCategory)
    : [];

  // Get the selected category object
  const currentCategory = categories.find((c) => c.id === selectedCategory);

  // Group sets by category for the category grid
  const categoryTotals: Record<string, { count: number; sets: number }> = {};
  for (const s of manifest.questionSets) {
    const cat = s.category || "uncategorized";
    if (!categoryTotals[cat]) categoryTotals[cat] = { count: 0, sets: 0 };
    categoryTotals[cat].count += s.questionCount;
    categoryTotals[cat].sets += 1;
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Hero */}
      <div className="text-center mb-10">
        <h1 className="text-3xl md:text-4xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
          QuizVault
        </h1>
        <p style={{ color: "var(--text-secondary)" }}>
          Medical Self Assessment — {totalQuestions.toLocaleString()} questions across {manifest.questionSets.length} banks
        </p>
      </div>

      {/* Quick stats */}
      {overallStats.total > 0 && (
        <div
          className="grid grid-cols-3 gap-4 rounded-xl p-5 mb-8"
          style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}
        >
          <div className="text-center">
            <div className="text-2xl font-bold" style={{ color: "var(--accent)" }}>{overallStats.uniqueQuestions}</div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Attempted</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold" style={{ color: "var(--success)" }}>{overallStats.accuracy}%</div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Accuracy</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold" style={{ color: "var(--warning)" }}>{overallStats.streak}</div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Streak</div>
          </div>
        </div>
      )}

      {/* Step 1: Choose Subspecialty */}
      {!selectedCategory && categories.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
            Choose Subspecialty
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {categories.map((cat) => {
              const totals = categoryTotals[cat.id];
              return (
                <button
                  key={cat.id}
                  onClick={() => { setSelectedCategory(cat.id); setSelectedSet(null); }}
                  className="text-left px-4 py-4 rounded-xl transition-all hover:shadow-md"
                  style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
                >
                  <div className="text-2xl mb-1">{cat.icon}</div>
                  <div className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
                    {cat.name}
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    {totals ? `${totals.count} Qs · ${totals.sets} bank${totals.sets > 1 ? "s" : ""}` : ""}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Step 2: Choose Question Bank */}
      {selectedCategory && !selectedSet && (
        <div className="mb-8">
          <button
            onClick={() => setSelectedCategory(null)}
            className="flex items-center gap-1 text-sm mb-4 hover:opacity-80 transition-opacity"
            style={{ color: "var(--accent)" }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6" /></svg>
            Back to subspecialties
          </button>
          <h2 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>
            {currentCategory?.icon} {currentCategory?.name}
          </h2>
          <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>
            Choose a question bank
          </p>
          <div className="space-y-3">
            {categorySets.map((s) => {
              const sourceStyle = SOURCE_COLORS[s.source || "BCSC"] || SOURCE_COLORS.BCSC;
              return (
                <button
                  key={s.id}
                  onClick={() => setSelectedSet(s.id)}
                  className="w-full text-left px-4 py-4 rounded-xl transition-all hover:shadow-md"
                  style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
                      {s.name}
                    </span>
                    {s.source && (
                      <span
                        className="text-xs font-medium px-2 py-0.5 rounded-full"
                        style={{ backgroundColor: sourceStyle.bg, color: sourceStyle.text }}
                      >
                        {s.source}
                      </span>
                    )}
                  </div>
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {s.questionCount} questions
                    {positions[s.id] ? ` · Resumed at Q${positions[s.id] + 1}` : ""}
                    {mistakeCounts[s.id] ? ` · ${mistakeCounts[s.id]} mistakes` : ""}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Step 3: Choose Quiz Mode */}
      {selectedSet && (
        <div className="mb-8">
          <button
            onClick={() => setSelectedSet(null)}
            className="flex items-center gap-1 text-sm mb-4 hover:opacity-80 transition-opacity"
            style={{ color: "var(--accent)" }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6" /></svg>
            Back to banks
          </button>
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
            Choose Quiz Mode
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {MODES.map((m) => {
              const disabled = m.id === "mistakes" && (mistakeCounts[selectedSet] || 0) === 0;
              return (
                <Link
                  key={m.id}
                  href={disabled ? "#" : `/quiz/${selectedSet}?mode=${m.id}`}
                  onClick={(e) => disabled && e.preventDefault()}
                  className="block px-4 py-5 rounded-xl text-center transition-all hover:shadow-md"
                  style={{
                    backgroundColor: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    opacity: disabled ? 0.4 : 1,
                    cursor: disabled ? "not-allowed" : "pointer",
                  }}
                >
                  <div className="text-2xl mb-2">{m.icon}</div>
                  <div className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{m.label}</div>
                  <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{m.desc}</div>
                  {m.id === "mistakes" && (mistakeCounts[selectedSet] || 0) > 0 && (
                    <div
                      className="text-xs mt-2 px-2 py-0.5 rounded-full inline-block"
                      style={{ backgroundColor: "var(--error-bg)", color: "var(--error)" }}
                    >
                      {mistakeCounts[selectedSet]} to review
                    </div>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Fallback: if no categories, show flat list (backward compat) */}
      {!categories.length && !selectedSet && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
            Choose Question Set
          </h2>
          <div className="space-y-2">
            {manifest.questionSets.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedSet(s.id)}
                className="w-full text-left px-4 py-3 rounded-lg transition-all"
                style={{
                  backgroundColor: selectedSet === s.id ? "var(--bg-secondary)" : "transparent",
                  border: `2px solid ${selectedSet === s.id ? "var(--accent)" : "var(--border)"}`,
                }}
              >
                <div className="font-medium text-sm" style={{ color: "var(--text-primary)" }}>{s.name}</div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                  {s.questionCount} questions
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Cloud sync */}
      <div className="mt-8">
        <CloudSync onSyncComplete={refreshStats} />
      </div>

      {/* Data management */}
      <div
        className="rounded-xl p-5 mt-4"
        style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}
      >
        <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
          Data Management
        </h3>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleExport}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity hover:opacity-80"
            style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            Export Progress
          </button>
          <button
            onClick={handleImport}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity hover:opacity-80"
            style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          >
            Import Progress
          </button>
          <button
            onClick={handleClear}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity hover:opacity-80"
            style={{ color: "var(--error)", border: "1px solid var(--error)" }}
          >
            Clear All Data
          </button>
        </div>
      </div>
    </div>
  );
}
