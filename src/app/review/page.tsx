"use client";

import { useEffect, useState } from "react";
import { Question, Manifest, AnswerRecord } from "@/lib/types";
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
        <div className="text-5xl mb-4">🎉</div>
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>No Mistakes!</h1>
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
            <ExplanationPanel question={question} wasCorrect={selectedAnswer === question.correctAnswer} />
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
  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            Review Mistakes
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            {mistakes.length} question{mistakes.length !== 1 ? "s" : ""} to review
          </p>
        </div>
        <button
          onClick={() => {
            setCurrentIndex(0);
            setSelectedAnswer(null);
            setShowResult(false);
            setReviewMode("quiz");
          }}
          className="px-5 py-2.5 rounded-lg text-sm font-medium text-white hover:opacity-90"
          style={{ backgroundColor: "var(--accent)" }}
        >
          Re-attempt All
        </button>
      </div>

      <div className="space-y-3">
        {mistakes.map((m, i) => {
          const q = allQuestions.get(`${m.source}:${m.questionId}`);
          if (!q) return null;
          const setInfo = manifest?.questionSets.find((s) => s.id === m.source);
          return (
            <div
              key={`${m.source}:${m.questionId}`}
              className="rounded-lg p-4 cursor-pointer hover:shadow-sm transition-shadow"
              style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
              onClick={() => {
                setCurrentIndex(i);
                setSelectedAnswer(null);
                setShowResult(false);
                setReviewMode("quiz");
              }}
            >
              <div className="flex items-start gap-3">
                <span
                  className="shrink-0 text-xs font-bold px-2 py-1 rounded"
                  style={{ backgroundColor: "var(--error-bg)", color: "var(--error)" }}
                >
                  Q{q.id}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium line-clamp-2" style={{ color: "var(--text-primary)" }}>
                    {q.question}
                  </p>
                  <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                    {setInfo?.name || m.source} · You answered: {m.selectedAnswer}. {q.options[m.selectedAnswer]} · Correct: {q.correctAnswer}. {q.options[q.correctAnswer]}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
