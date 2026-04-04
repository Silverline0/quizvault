"use client";

import { useEffect, useState, useCallback } from "react";
import { Question, Manifest } from "@/lib/types";
import { recordAnswer, updateSpacedRep } from "@/lib/store";
import { getSetting } from "@/lib/settings";
import QuizCard from "@/components/QuizCard";
import ExplanationPanel from "@/components/ExplanationPanel";
import QuizHeader from "@/components/QuizHeader";
import Link from "next/link";

const EXAM_SIZES = [25, 50, 100, 200];
const TIME_LIMITS: Record<number, number> = { 25: 30, 50: 60, 100: 120, 200: 240 }; // minutes

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

type ExamState = "setup" | "active" | "finished";

export default function ExamPage() {
  const [state, setState] = useState<ExamState>("setup");
  const [examSize, setExamSize] = useState(50);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [correctCount, setCorrectCount] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [timeLeft, setTimeLeft] = useState(0);
  const [loading, setLoading] = useState(false);
  const [allQuestions, setAllQuestions] = useState<Question[]>([]);

  // Load all questions
  useEffect(() => {
    async function loadAll() {
      const mRes = await fetch("/data/manifest.json");
      const manifest: Manifest = await mRes.json();
      const all: Question[] = [];
      for (const qSet of manifest.questionSets) {
        if (qSet.questionCount === 0) continue;
        try {
          const res = await fetch(`/data/${qSet.file}`);
          const qs: Question[] = await res.json();
          // Only include questions with correct answers
          all.push(...qs.filter(q => q.correctAnswer));
        } catch { /* skip */ }
      }
      setAllQuestions(all);
    }
    loadAll();
  }, []);

  // Timer countdown
  useEffect(() => {
    if (state !== "active" || timeLeft <= 0) return;
    const timer = setInterval(() => {
      setTimeLeft((t) => {
        if (t <= 1) {
          setState("finished");
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [state, timeLeft]);

  const startExam = useCallback(() => {
    setLoading(true);
    const selected = shuffle(allQuestions).slice(0, examSize);
    setQuestions(selected);
    setTimeLeft(TIME_LIMITS[examSize] * 60);
    setCurrentIndex(0);
    setCorrectCount(0);
    setAnsweredCount(0);
    setSelectedAnswer(null);
    setShowResult(false);
    setState("active");
    setLoading(false);
  }, [allQuestions, examSize]);

  const currentQuestion = questions[currentIndex];

  const handleAnswer = useCallback(
    (selected: string, correct: boolean) => {
      if (!currentQuestion) return;
      setSelectedAnswer(selected);
      setShowResult(true);
      setAnsweredCount((c) => c + 1);
      if (correct) setCorrectCount((c) => c + 1);

      recordAnswer({
        questionId: currentQuestion.id,
        source: currentQuestion.source,
        selectedAnswer: selected,
        correct,
        timestamp: Date.now(),
      });
      if (getSetting("spacedRepEnabled")) {
        updateSpacedRep(currentQuestion.id, currentQuestion.source, correct);
      }
    },
    [currentQuestion]
  );

  const handleNext = useCallback(() => {
    if (currentIndex + 1 >= questions.length) {
      setState("finished");
      return;
    }
    setCurrentIndex((i) => i + 1);
    setSelectedAnswer(null);
    setShowResult(false);
  }, [currentIndex, questions.length]);

  // Keyboard
  useEffect(() => {
    if (state !== "active") return;
    const handler = (e: KeyboardEvent) => {
      if ((e.key === "Enter" || e.key === "ArrowRight") && showResult) handleNext();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [state, showResult, handleNext]);

  // ── Setup screen ───────────────────────────────────
  if (state === "setup") {
    return (
      <div className="max-w-lg mx-auto text-center py-12">
        <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
          <span className="font-display italic">Mock</span> Exam
        </h1>
        <p className="mb-8" style={{ color: "var(--text-secondary)" }}>
          Random questions from all banks. Timed. No going back.
        </p>

        <div className="space-y-3 mb-8">
          {EXAM_SIZES.map((size) => (
            <button
              key={size}
              onClick={() => setExamSize(size)}
              disabled={allQuestions.length < size}
              className="w-full px-5 py-4 rounded-xl text-left flex items-center justify-between transition-all"
              style={{
                backgroundColor: examSize === size ? "var(--accent-light)" : "var(--bg-card)",
                border: `2px solid ${examSize === size ? "var(--accent)" : "var(--border)"}`,
                opacity: allQuestions.length < size ? 0.4 : 1,
              }}
            >
              <div>
                <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
                  {size} Questions
                </span>
                <span className="text-sm ml-2" style={{ color: "var(--text-muted)" }}>
                  {TIME_LIMITS[size]} min
                </span>
              </div>
              {examSize === size && (
                <span className="w-6 h-6 rounded-full flex items-center justify-center" style={{ backgroundColor: "var(--accent)" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </span>
              )}
            </button>
          ))}
        </div>

        <button
          onClick={startExam}
          disabled={allQuestions.length === 0}
          className="w-full py-4 rounded-xl text-base font-bold transition-opacity hover:opacity-90 disabled:opacity-50"
          style={{ backgroundColor: "var(--text-primary)", color: "var(--bg-primary)" }}
        >
          {allQuestions.length === 0 ? "Loading questions..." : `Start ${examSize}-Question Exam`}
        </button>

        <Link href="/" className="block mt-4 text-sm hover:opacity-70" style={{ color: "var(--text-muted)" }}>
          ← Back to Home
        </Link>
      </div>
    );
  }

  // ── Finished screen ────────────────────────────────
  if (state === "finished") {
    const accuracy = answeredCount > 0 ? Math.round((correctCount / answeredCount) * 100) : 0;
    const unanswered = questions.length - answeredCount;
    const passed = accuracy >= 70;

    return (
      <div className="max-w-lg mx-auto text-center py-12 px-4">
        <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--text-primary)" }}>
          {passed ? "Exam Passed" : "Keep Studying"}
        </h1>
        <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
          {answeredCount} of {questions.length} answered
          {unanswered > 0 && ` · ${unanswered} skipped (time ran out)`}
        </p>

        <div
          className="rounded-xl p-6 mb-8 text-center"
          style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "var(--shadow-md)" }}
        >
          <p className="text-5xl font-bold font-display" style={{ color: passed ? "var(--success)" : "var(--error)" }}>
            {accuracy}%
          </p>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            {correctCount} correct · {answeredCount - correctCount} wrong
          </p>
        </div>

        <div className="flex gap-3 justify-center">
          <Link
            href="/"
            className="px-6 py-3 rounded-xl text-sm font-semibold"
            style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
          >
            Home
          </Link>
          <button
            onClick={() => { setState("setup"); setQuestions([]); }}
            className="px-6 py-3 rounded-xl text-sm font-semibold text-white"
            style={{ backgroundColor: "var(--text-primary)" }}
          >
            New Exam
          </button>
        </div>
      </div>
    );
  }

  // ── Active exam ────────────────────────────────────
  const timerColor = timeLeft < 60 ? "var(--error)" : timeLeft < 300 ? "var(--warning)" : "var(--text-muted)";

  return (
    <>
      <QuizHeader title={`Mock Exam · ${formatTime(timeLeft)}`} backHref="/exam" />

      <div className="max-w-3xl mx-auto px-4 py-4 pb-28">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm font-semibold" style={{ color: "var(--accent)" }}>
            Question {currentIndex + 1} of {questions.length}
          </span>
          <span className="text-sm font-mono font-bold" style={{ color: timerColor }}>
            {formatTime(timeLeft)}
          </span>
        </div>

        <div key={currentIndex} className="animate-slide-in">
          <QuizCard
            question={currentQuestion}
            onAnswer={handleAnswer}
            showResult={showResult}
            selectedAnswer={selectedAnswer}
          />
        </div>

        {showResult && (
          <ExplanationPanel
            question={currentQuestion}
            wasCorrect={selectedAnswer === currentQuestion.correctAnswer}
          />
        )}
      </div>

      {showResult && (
        <div
          className="fixed bottom-0 left-0 right-0 p-4 z-30"
          style={{ backgroundColor: "var(--bg-primary)", borderTop: "1px solid var(--border)", paddingBottom: "max(16px, env(safe-area-inset-bottom))" }}
        >
          <div className="max-w-2xl mx-auto">
            <button
              onClick={handleNext}
              className="w-full py-3.5 rounded-xl text-base font-bold flex items-center justify-center gap-2 transition-opacity hover:opacity-90"
              style={{ backgroundColor: "var(--text-primary)", color: "var(--bg-primary)" }}
            >
              {currentIndex + 1 >= questions.length ? "Finish Exam" : "Next"}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}
