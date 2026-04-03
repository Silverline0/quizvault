"use client";

import { useEffect, useState } from "react";
import { Manifest } from "@/lib/types";
import { getStats, getAnswersForSet, getMistakes, getProgress } from "@/lib/store";
import Link from "next/link";

export default function StatsPage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [overall, setOverall] = useState({ total: 0, correct: 0, accuracy: 0, uniqueQuestions: 0, streak: 0 });
  const [setStats, setSetStats] = useState<Record<string, { total: number; correct: number; accuracy: number; mistakes: number; unique: number }>>({});
  const [recentAccuracy, setRecentAccuracy] = useState<number[]>([]);
  const [topMistakes, setTopMistakes] = useState<{ id: number; source: string; count: number; question: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const mRes = await fetch("/data/manifest.json");
        const m: Manifest = await mRes.json();
        setManifest(m);

        setOverall(getStats());

        // Per-set stats
        const ss: typeof setStats = {};
        for (const s of m.questionSets) {
          const answers = getAnswersForSet(s.id);
          const correct = answers.filter((a) => a.correct).length;
          const unique = new Set(answers.map((a) => a.questionId)).size;
          ss[s.id] = {
            total: answers.length,
            correct,
            accuracy: answers.length > 0 ? Math.round((correct / answers.length) * 100) : 0,
            mistakes: getMistakes(s.id).length,
            unique,
          };
        }
        setSetStats(ss);

        // Recent accuracy: last 10 batches of 10
        const allAnswers = getProgress().answers;
        const batches: number[] = [];
        for (let i = 0; i < Math.min(allAnswers.length, 100); i += 10) {
          const batch = allAnswers.slice(Math.max(0, allAnswers.length - 100 + i), Math.max(0, allAnswers.length - 100 + i) + 10);
          if (batch.length > 0) {
            const c = batch.filter((a) => a.correct).length;
            batches.push(Math.round((c / batch.length) * 100));
          }
        }
        setRecentAccuracy(batches);

        // Top mistakes: questions with most wrong answers
        const mistakeMap = new Map<string, number>();
        for (const a of allAnswers) {
          if (!a.correct) {
            const key = `${a.source}:${a.questionId}`;
            mistakeMap.set(key, (mistakeMap.get(key) || 0) + 1);
          }
        }
        const sorted = Array.from(mistakeMap.entries())
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5);

        // Load question text for top mistakes
        const topM: typeof topMistakes = [];
        for (const [key, count] of sorted) {
          const [source, idStr] = key.split(":");
          const set = m.questionSets.find((s) => s.id === source);
          if (set) {
            try {
              const res = await fetch(`/data/${set.file}`);
              const questions = await res.json();
              const q = questions.find((q: { id: number }) => q.id === Number(idStr));
              if (q) {
                topM.push({ id: q.id, source, count, question: q.question });
              }
            } catch { /* skip */ }
          }
        }
        setTopMistakes(topM);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div
          className="w-10 h-10 border-4 rounded-full animate-spin"
          style={{ borderColor: "var(--border)", borderTopColor: "var(--accent)" }}
        />
      </div>
    );
  }

  if (overall.total === 0) {
    return (
      <div className="max-w-2xl mx-auto text-center py-20">
        <div className="text-5xl mb-4">📊</div>
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>No Stats Yet</h1>
        <p className="mb-6" style={{ color: "var(--text-secondary)" }}>
          Complete some questions to see your statistics.
        </p>
        <Link
          href="/"
          className="inline-flex px-5 py-2.5 rounded-lg text-sm font-medium text-white"
          style={{ backgroundColor: "var(--accent)" }}
        >
          Start a Quiz
        </Link>
      </div>
    );
  }

  const maxBar = Math.max(...recentAccuracy, 1);

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6" style={{ color: "var(--text-primary)" }}>Statistics</h1>

      {/* Overall stats grid */}
      <div
        className="grid grid-cols-2 sm:grid-cols-4 gap-4 rounded-xl p-5 mb-8"
        style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border)" }}
      >
        <div className="text-center">
          <div className="text-3xl font-bold" style={{ color: "var(--accent)" }}>{overall.total}</div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>Total Answers</div>
        </div>
        <div className="text-center">
          <div className="text-3xl font-bold" style={{ color: "var(--success)" }}>{overall.accuracy}%</div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>Accuracy</div>
        </div>
        <div className="text-center">
          <div className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>{overall.uniqueQuestions}</div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>Unique Q&apos;s</div>
        </div>
        <div className="text-center">
          <div className="text-3xl font-bold" style={{ color: "var(--warning)" }}>{overall.streak}</div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>Streak</div>
        </div>
      </div>

      {/* Accuracy trend */}
      {recentAccuracy.length > 1 && (
        <div
          className="rounded-xl p-5 mb-8"
          style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
        >
          <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>
            Accuracy Trend (recent batches of 10)
          </h2>
          <div className="flex items-end gap-2 h-32">
            {recentAccuracy.map((pct, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>{pct}%</span>
                <div
                  className="w-full rounded-t-sm transition-all"
                  style={{
                    height: `${(pct / maxBar) * 100}%`,
                    backgroundColor: pct >= 80 ? "var(--success)" : pct >= 50 ? "var(--warning)" : "var(--error)",
                    minHeight: "4px",
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-set breakdown */}
      {manifest && manifest.questionSets.length > 0 && (
        <div
          className="rounded-xl p-5 mb-8"
          style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
        >
          <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>
            Per Set Breakdown
          </h2>
          <div className="space-y-4">
            {manifest.questionSets.map((s) => {
              const st = setStats[s.id];
              if (!st || st.total === 0) return null;
              return (
                <div key={s.id}>
                  <div className="flex justify-between mb-1">
                    <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{s.name}</span>
                    <span className="text-sm" style={{ color: "var(--text-muted)" }}>
                      {st.unique}/{s.questionCount} · {st.accuracy}%
                    </span>
                  </div>
                  <div className="w-full h-2.5 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-secondary)" }}>
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${(st.unique / s.questionCount) * 100}%`,
                        backgroundColor: st.accuracy >= 80 ? "var(--success)" : st.accuracy >= 50 ? "var(--warning)" : "var(--error)",
                      }}
                    />
                  </div>
                  {st.mistakes > 0 && (
                    <span className="text-xs" style={{ color: "var(--error)" }}>{st.mistakes} active mistakes</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Most missed questions */}
      {topMistakes.length > 0 && (
        <div
          className="rounded-xl p-5"
          style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
        >
          <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>
            Most Missed Questions
          </h2>
          <div className="space-y-3">
            {topMistakes.map((m) => (
              <div key={`${m.source}:${m.id}`} className="flex items-start gap-3">
                <span
                  className="shrink-0 text-xs font-bold px-2 py-1 rounded"
                  style={{ backgroundColor: "var(--error-bg)", color: "var(--error)" }}
                >
                  {m.count}x
                </span>
                <p className="text-sm line-clamp-2" style={{ color: "var(--text-primary)" }}>
                  Q{m.id}: {m.question}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
