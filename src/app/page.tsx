"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Manifest, QuizMode, Category, QuestionSet } from "@/lib/types";
import {
  getStats, getMistakes, getLastPosition, exportProgress, importProgress,
  clearProgress, getLastActive, getWeakAreas, getDueForReview,
  getStudyTimeStats, getSpacedRepStats,
} from "@/lib/store";
import CloudSync from "@/components/CloudSync";

const MODES: { id: QuizMode; label: string; desc: string; icon: string }[] = [
  { id: "sequential", label: "Sequential", desc: "In order, resume where you left off", icon: "→" },
  { id: "random", label: "Random", desc: "Shuffled, no repeats", icon: "🔀" },
  { id: "mistakes", label: "Mistakes", desc: "Review what you got wrong", icon: "✗" },
];

export default function HomePage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedSet, setSelectedSet] = useState<string | null>(null);
  const [overallStats, setOverallStats] = useState({ total: 0, correct: 0, accuracy: 0, uniqueQuestions: 0, streak: 0 });
  const [mistakeCounts, setMistakeCounts] = useState<Record<string, number>>({});
  const [positions, setPositions] = useState<Record<string, number>>({});
  const [lastActive, setLastActive] = useState<{ setId?: string; mode?: string; position?: number }>({});
  const [weakAreas, setWeakAreas] = useState<{ source: string; accuracy: number; totalAnswered: number }[]>([]);
  const [studyTime, setStudyTime] = useState({ totalHours: 0, avgSessionMin: 0, sessionCount: 0 });
  const [spacedRepStats, setSpacedRepStats] = useState({ total: 0, due: 0, mastered: 0, learning: 0 });
  const [dueCount, setDueCount] = useState(0);

  useEffect(() => {
    fetch("/data/manifest.json")
      .then((r) => r.json())
      .then((m: Manifest) => {
        setManifest(m);
        if (m.categories && m.categories.length === 1) setSelectedCategory(m.categories[0].id);
      });
  }, []);

  const refreshStats = () => {
    setOverallStats(getStats());
    setLastActive(getLastActive());
    setWeakAreas(getWeakAreas().slice(0, 3));
    setStudyTime(getStudyTimeStats());
    setSpacedRepStats(getSpacedRepStats());
    setDueCount(getDueForReview().length);
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

  useEffect(() => { refreshStats(); }, [manifest]);

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
      if (importProgress(text)) { refreshStats(); alert("Progress imported!"); }
      else alert("Invalid file.");
    };
    input.click();
  };

  if (!manifest) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-10 h-10 border-4 rounded-full animate-spin" style={{ borderColor: "var(--border)", borderTopColor: "var(--accent)" }} />
      </div>
    );
  }

  const categories = manifest.categories || [];
  const totalQuestions = manifest.questionSets.reduce((sum, s) => sum + s.questionCount, 0);
  const categorySets = selectedCategory ? manifest.questionSets.filter((s) => s.category === selectedCategory) : [];
  const currentCategory = categories.find((c) => c.id === selectedCategory);
  const categoryTotals: Record<string, { count: number; sets: number }> = {};
  for (const s of manifest.questionSets) {
    const cat = s.category || "uncategorized";
    if (!categoryTotals[cat]) categoryTotals[cat] = { count: 0, sets: 0 };
    categoryTotals[cat].count += s.questionCount;
    categoryTotals[cat].sets += 1;
  }

  // Find the last active set name
  const lastActiveSet = lastActive.setId ? manifest.questionSets.find(s => s.id === lastActive.setId) : null;

  return (
    <div className="max-w-2xl mx-auto">
      {/* Hero */}
      <div className="text-center mb-8">
        <h1 className="text-4xl md:text-5xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
          <span style={{ color: "var(--accent)" }}>Quiz</span><span className="font-display italic">Vault</span>
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {totalQuestions.toLocaleString()} questions · {manifest.questionSets.length} banks · {categories.length} specialties
        </p>
      </div>

      {/* Continue where you left off */}
      {lastActiveSet && lastActive.position !== undefined && lastActive.position > 0 && !selectedCategory && (
        <Link
          href={`/quiz/${lastActive.setId}?mode=${lastActive.mode || "sequential"}`}
          className="block rounded-xl p-4 mb-6 transition-all hover:shadow-lg animate-fade-in"
          style={{
            backgroundColor: "var(--accent-light)",
            border: "2px solid var(--accent)",
            boxShadow: "var(--shadow-glow)",
          }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--accent)" }}>
                Continue studying
              </p>
              <p className="font-bold" style={{ color: "var(--text-primary)" }}>
                {lastActiveSet.name}
              </p>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                Question {lastActive.position + 1} of {lastActiveSet.questionCount} · {lastActive.mode} mode
              </p>
            </div>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.5">
              <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
            </svg>
          </div>
        </Link>
      )}

      {/* Quick stats */}
      {overallStats.total > 0 && !selectedCategory && (
        <div
          className="grid grid-cols-4 gap-3 rounded-xl p-4 mb-6"
          style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}
        >
          <div className="text-center">
            <div className="text-xl font-bold font-display" style={{ color: "var(--accent)" }}>{overallStats.uniqueQuestions}</div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Answered</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold font-display" style={{ color: "var(--success)" }}>{overallStats.accuracy}%</div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Accuracy</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold font-display" style={{ color: "var(--warning)" }}>{overallStats.streak}</div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Streak</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold font-display" style={{ color: "var(--text-primary)" }}>{studyTime.totalHours}h</div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Study time</div>
          </div>
        </div>
      )}

      {/* Spaced rep due + weak areas row */}
      {(dueCount > 0 || weakAreas.length > 0) && !selectedCategory && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
          {dueCount > 0 && (
            <Link
              href="/review"
              className="rounded-xl p-4 transition-all hover:shadow-md"
              style={{ backgroundColor: "var(--warning-bg)", border: "1px solid var(--warning)" }}
            >
              <p className="text-sm font-bold" style={{ color: "var(--warning)" }}>
                {dueCount} due for review
              </p>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                Spaced repetition · {spacedRepStats.mastered} mastered
              </p>
            </Link>
          )}
          {weakAreas.length > 0 && (
            <div
              className="rounded-xl p-4"
              style={{ backgroundColor: "var(--error-bg)", border: "1px solid var(--error)" }}
            >
              <p className="text-sm font-bold mb-1" style={{ color: "var(--error)" }}>
                Weak areas
              </p>
              {weakAreas.map((w) => {
                const setInfo = manifest.questionSets.find(s => s.id === w.source);
                return (
                  <p key={w.source} className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    {setInfo?.name || w.source}: {w.accuracy}%
                  </p>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Step 1: Choose Subspecialty */}
      {!selectedCategory && categories.length > 0 && (
        <div className="mb-6">
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
                  style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}
                >
                  <div className="text-2xl mb-1">{cat.icon}</div>
                  <div className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{cat.name}</div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    {totals ? `${totals.count} Qs · ${totals.sets} bank${totals.sets > 1 ? "s" : ""}` : ""}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Step 2: Choose Bank */}
      {selectedCategory && !selectedSet && (
        <div className="mb-6 animate-fade-in">
          <button onClick={() => setSelectedCategory(null)} className="flex items-center gap-1 text-sm mb-4 hover:opacity-70" style={{ color: "var(--accent)" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6" /></svg>
            Back
          </button>
          <h2 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>
            {currentCategory?.icon} {currentCategory?.name}
          </h2>
          <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>Choose a question bank</p>
          <div className="space-y-3">
            {categorySets.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedSet(s.id)}
                className="w-full text-left px-4 py-4 rounded-xl transition-all hover:shadow-md"
                style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{s.name}</span>
                  {s.source && (
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: s.source === "BCSC" ? "#dbeafe" : "#ede9fe", color: s.source === "BCSC" ? "#1d4ed8" : "#6d28d9" }}>
                      {s.source}
                    </span>
                  )}
                </div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {s.questionCount} questions
                  {positions[s.id] ? ` · Q${positions[s.id] + 1}` : ""}
                  {mistakeCounts[s.id] ? ` · ${mistakeCounts[s.id]} mistakes` : ""}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: Choose Mode */}
      {selectedSet && (
        <div className="mb-6 animate-fade-in">
          <button onClick={() => setSelectedSet(null)} className="flex items-center gap-1 text-sm mb-4 hover:opacity-70" style={{ color: "var(--accent)" }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6" /></svg>
            Back
          </button>
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>Choose Mode</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {MODES.map((m) => {
              const disabled = m.id === "mistakes" && (mistakeCounts[selectedSet] || 0) === 0;
              return (
                <Link key={m.id} href={disabled ? "#" : `/quiz/${selectedSet}?mode=${m.id}`}
                  onClick={(e) => disabled && e.preventDefault()}
                  className="block px-4 py-5 rounded-xl text-center transition-all hover:shadow-md"
                  style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", opacity: disabled ? 0.4 : 1, cursor: disabled ? "not-allowed" : "pointer", boxShadow: "var(--shadow-sm)" }}>
                  <div className="text-2xl mb-2">{m.icon}</div>
                  <div className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{m.label}</div>
                  <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{m.desc}</div>
                  {m.id === "mistakes" && (mistakeCounts[selectedSet] || 0) > 0 && (
                    <div className="text-xs mt-2 px-2 py-0.5 rounded-full inline-block" style={{ backgroundColor: "var(--error-bg)", color: "var(--error)" }}>
                      {mistakeCounts[selectedSet]} to review
                    </div>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Fallback flat list */}
      {!categories.length && !selectedSet && (
        <div className="mb-6">
          {manifest.questionSets.map((s) => (
            <button key={s.id} onClick={() => setSelectedSet(s.id)}
              className="w-full text-left px-4 py-3 rounded-lg mb-2" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
              <div className="font-medium text-sm" style={{ color: "var(--text-primary)" }}>{s.name}</div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>{s.questionCount} questions</div>
            </button>
          ))}
        </div>
      )}

      {/* Cloud sync + Data management */}
      {!selectedCategory && (
        <>
          <div className="mt-8"><CloudSync onSyncComplete={refreshStats} /></div>
          <div className="rounded-xl p-4 mt-4" style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}>
            <h3 className="text-xs font-semibold mb-3 uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Data</h3>
            <div className="flex flex-wrap gap-2">
              <button onClick={handleExport} className="px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80"
                style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>Export</button>
              <button onClick={handleImport} className="px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80"
                style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>Import</button>
              <button onClick={() => { if (confirm("Clear all progress?")) { clearProgress(); refreshStats(); } }}
                className="px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80"
                style={{ color: "var(--error)", border: "1px solid var(--error)" }}>Clear</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
