"use client";

import { useEffect, useMemo, useState } from "react";
import { Question, Manifest, AnswerRecord, badgeClass } from "@/lib/types";
import { getAllMistakes } from "@/lib/store";
import { loadQuestionSet } from "@/lib/quiz-engine";
import QuizCard from "@/components/QuizCard";
import ExplanationPanel from "@/components/ExplanationPanel";
import { recordAnswer } from "@/lib/store";
import Link from "next/link";

export default function ReviewPage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [mistakes, setMistakes] = useState<AnswerRecord[]>([]);
  const [allQuestions, setAllQuestions] = useState<Map<string, Question>>(new Map());
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [reviewMode, setReviewMode] = useState<"list" | "quiz">("list");
  const [bankFilter, setBankFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const mRes = await fetch("/data/manifest.json");
        const m: Manifest = await mRes.json();
        setManifest(m);

        const allMistakes = getAllMistakes();
        setMistakes(allMistakes);

        // Load all question sets that have mistakes
        const sourcesNeeded = new Set(allMistakes.map((m) => m.source));
        const qMap = new Map<string, Question>();

        for (const s of m.questionSets) {
          if (sourcesNeeded.has(s.id)) {
            const questions = await loadQuestionSet(s.file);
            for (const q of questions) {
              qMap.set(`${q.source}:${q.id}`, q);
            }
          }
        }
        setAllQuestions(qMap);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleAnswer = (selected: string, correct: boolean) => {
    const mistake = mistakes[currentIndex];
    if (!mistake) return;
    setSelectedAnswer(selected);
    setShowResult(true);
    recordAnswer({
      questionId: mistake.questionId,
      source: mistake.source,
      selectedAnswer: selected,
      correct,
      timestamp: Date.now(),
    });
  };

  const handleNext = () => {
    if (currentIndex + 1 >= mistakes.length) {
      setReviewMode("list");
      // Refresh mistakes
      setMistakes(getAllMistakes());
      setCurrentIndex(0);
      return;
    }
    setCurrentIndex((i) => i + 1);
    setSelectedAnswer(null);
    setShowResult(false);
  };

  // Keyboard: Enter/ArrowRight for next
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.key === "Enter" || e.key === "ArrowRight") && showResult && reviewMode === "quiz") {
        handleNext();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showResult, reviewMode]);

  // Which banks these mistakes come from, and how many each owes. Declared with
  // the other hooks, above the early returns, so the hook order never shifts.
  const bankInfo = useMemo(() => {
    const counts = new Map<string, number>();
    for (const m of mistakes) counts.set(m.source, (counts.get(m.source) || 0) + 1);
    return Array.from(counts.entries())
      .map(([id, count]) => {
        const set = manifest?.questionSets.find((q) => q.id === id);
        return { id, count, name: set?.name || id, source: set?.source };
      })
      .sort((a, b) => b.count - a.count);
  }, [mistakes, manifest]);

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

  if (mistakes.length === 0) {
    return (
      <div className="max-w-2xl mx-auto text-center py-20">
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>No Mistakes</h1>
        <p className="mb-6" style={{ color: "var(--text-secondary)" }}>
          You haven&apos;t gotten any questions wrong yet, or you&apos;ve corrected them all.
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

  // Quiz mode — re-attempt mistakes
  if (reviewMode === "quiz") {
    const mistake = mistakes[currentIndex];
    const question = allQuestions.get(`${mistake.source}:${mistake.questionId}`);
    if (!question) return null;

    return (
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            Review Mistakes
          </h1>
          <span className="text-sm" style={{ color: "var(--text-muted)" }}>
            {currentIndex + 1} / {mistakes.length}
          </span>
        </div>
        <QuizCard
          question={question}
          onAnswer={handleAnswer}
          showResult={showResult}
          selectedAnswer={selectedAnswer}
        />
        {showResult && (
          <>
            <ExplanationPanel question={question} wasCorrect={selectedAnswer === question.correctAnswer} selectedAnswer={selectedAnswer} />
            <div className="flex justify-end mt-4">
              <button
                onClick={handleNext}
                className="px-6 py-2.5 rounded-lg text-sm font-medium text-white flex items-center gap-2 hover:opacity-90"
                style={{ backgroundColor: "var(--accent)" }}
              >
                {currentIndex + 1 >= mistakes.length ? "Done" : "Next"}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
              </button>
            </div>
          </>
        )}
      </div>
    );
  }

  // List mode — show all mistakes
  const rows = mistakes
    .map((m, i) => ({ m, i }))
    .filter(({ m }) => bankFilter === "all" || m.source === bankFilter);

  // A bank filter maps straight onto a route that already exists: the whole
  // queue goes to the cross-bank virtual set, one bank to its own mistakes mode.
  const ctaHref =
    bankFilter === "all" ? "/quiz/all-mistakes?mode=mistakes" : `/quiz/${bankFilter}?mode=mistakes`;

  const FILTERS = [{ id: "all", name: "All", count: mistakes.length }, ...bankInfo];

  return (
    <div className="max-w-2xl mx-auto" style={{ paddingBottom: "calc(88px + env(safe-area-inset-bottom))" }}>
      <div className="mb-4">
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
          Review mistakes
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
          {mistakes.length} wrong answer{mistakes.length !== 1 ? "s" : ""} across {bankInfo.length}{" "}
          bank{bankInfo.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Bank filter — the queue mixes every bank, so let it be narrowed */}
      {bankInfo.length > 1 && (
        <div className="flex gap-1.5 overflow-x-auto pb-3 mb-2" style={{ scrollbarWidth: "none" }}>
          {FILTERS.map((f) => {
            const on = bankFilter === f.id;
            return (
              <button
                key={f.id}
                onClick={() => setBankFilter(f.id)}
                className="h-8 px-2.5 flex items-center gap-1.5 text-xs font-semibold shrink-0 transition-colors"
                style={{
                  border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`,
                  backgroundColor: on ? "var(--accent-light)" : "var(--bg-card)",
                  color: on ? "var(--accent)" : "var(--text-secondary)",
                }}
              >
                {f.name}
                <span
                  className="px-1.5 text-[10px] font-bold"
                  style={{
                    backgroundColor: on ? "var(--accent)" : "var(--bg-secondary)",
                    color: on ? "white" : "var(--text-muted)",
                  }}
                >
                  {f.count}
                </span>
              </button>
            );
          })}
        </div>
      )}

      <div className="space-y-2.5">
        {rows.map(({ m, i }) => {
          const q = allQuestions.get(`${m.source}:${m.questionId}`);
          if (!q) return null;
          const setInfo = manifest?.questionSets.find((s) => s.id === m.source);
          return (
            <button
              key={`${m.source}:${m.questionId}`}
              className="w-full text-left p-3.5 transition-colors hover:shadow-sm"
              style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}
              onClick={() => {
                setCurrentIndex(i);
                setSelectedAnswer(null);
                setShowResult(false);
                setReviewMode("quiz");
              }}
            >
              <div className="flex items-center gap-2 mb-1.5">
                {setInfo?.source && (
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 shrink-0 ${badgeClass(setInfo.source)}`}>
                    {setInfo.source}
                  </span>
                )}
                <span className="text-[11.5px] font-semibold truncate" style={{ color: "var(--text-secondary)" }}>
                  {setInfo?.name || m.source}
                </span>
                <span className="ml-auto text-[11px] shrink-0" style={{ color: "var(--text-muted)" }}>
                  Q{q.id}
                </span>
              </div>

              <p className="text-sm font-medium line-clamp-2 leading-snug" style={{ color: "var(--text-primary)" }}>
                {q.question}
              </p>

              {/* Your answer against the key, as two labelled lines rather than
                  one muted run-on that wrapped to three. */}
              <div className="mt-2 flex flex-col gap-1">
                <div className="flex items-start gap-2">
                  <span
                    className="w-[19px] h-[19px] shrink-0 mt-px flex items-center justify-center text-[10.5px] font-bold"
                    style={{ backgroundColor: "var(--error-bg)", color: "var(--error-ink)", border: "1px solid var(--error)", borderRadius: "var(--radius-md)" }}
                  >
                    {m.selectedAnswer}
                  </span>
                  <span className="text-xs leading-snug" style={{ color: "var(--text-muted)" }}>
                    {q.options[m.selectedAnswer]} <span className="opacity-75">— you</span>
                  </span>
                </div>
                <div className="flex items-start gap-2">
                  <span
                    className="w-[19px] h-[19px] shrink-0 mt-px flex items-center justify-center text-[10.5px] font-bold"
                    style={{ backgroundColor: "var(--success-bg)", color: "var(--success-ink)", border: "1px solid var(--success)", borderRadius: "var(--radius-md)" }}
                  >
                    {q.correctAnswer}
                  </span>
                  <span className="text-xs leading-snug" style={{ color: "var(--text-secondary)" }}>
                    {q.options[q.correctAnswer]} <span className="opacity-75">— key</span>
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Primary action follows the filter */}
      <div
        className="fixed bottom-0 left-0 right-0 z-30 px-4 pt-3"
        style={{
          backgroundColor: "var(--bg-primary)",
          borderTop: "1px solid var(--border)",
          paddingBottom: "max(12px, env(safe-area-inset-bottom))",
        }}
      >
        <Link
          href={ctaHref}
          className="max-w-2xl mx-auto h-12 flex items-center justify-center text-sm font-bold text-white"
          style={{ backgroundColor: "var(--accent)" }}
        >
          {rows.length === 1
            ? "Re-attempt this one"
            : bankFilter === "all"
              ? `Re-attempt all ${rows.length}`
              : `Re-attempt these ${rows.length}`}
        </Link>
      </div>
    </div>
  );
}
