"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Question, QuizMode } from "@/lib/types";
import { loadQuestionSet } from "@/lib/quiz-engine";
import { buildQuizQueue, getStartIndex } from "@/lib/quiz-engine";
import { recordAnswer, saveLastPosition } from "@/lib/store";
import QuizCard from "@/components/QuizCard";
import ExplanationPanel from "@/components/ExplanationPanel";
import ProgressBar from "@/components/ProgressBar";
import Link from "next/link";

export default function QuizPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const setId = params.setId as string;
  const mode = (searchParams.get("mode") || "sequential") as QuizMode;

  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [correctCount, setCorrectCount] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [finished, setFinished] = useState(false);

  // Load questions
  useEffect(() => {
    async function load() {
      try {
        // Find the file name from manifest
        const manifestRes = await fetch("/data/manifest.json");
        const manifest = await manifestRes.json();
        const qSet = manifest.questionSets.find((s: { id: string }) => s.id === setId);
        if (!qSet) return;

        const raw = await loadQuestionSet(qSet.file);
        const queue = buildQuizQueue(raw, mode, setId);
        const start = getStartIndex(mode, setId);
        setQuestions(queue);
        setCurrentIndex(Math.min(start, queue.length - 1));
      } catch (err) {
        console.error("Failed to load questions:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [setId, mode]);

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

      if (mode === "sequential") {
        saveLastPosition(setId, currentIndex + 1);
      }
    },
    [currentQuestion, currentIndex, mode, setId]
  );

  const handleNext = useCallback(() => {
    if (currentIndex + 1 >= questions.length) {
      setFinished(true);
      return;
    }
    setCurrentIndex((i) => i + 1);
    setSelectedAnswer(null);
    setShowResult(false);
  }, [currentIndex, questions.length]);

  // Keyboard: Enter/ArrowRight for next
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.key === "Enter" || e.key === "ArrowRight") && showResult) {
        handleNext();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showResult, handleNext]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <div
            className="w-10 h-10 border-4 rounded-full animate-spin mx-auto mb-4"
            style={{ borderColor: "var(--border)", borderTopColor: "var(--accent)" }}
          />
          <p style={{ color: "var(--text-muted)" }}>Loading questions...</p>
        </div>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="text-center py-20">
        <p className="text-lg mb-4" style={{ color: "var(--text-secondary)" }}>
          {mode === "mistakes" ? "No mistakes to review! Great job." : "No questions found."}
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white"
          style={{ backgroundColor: "var(--accent)" }}
        >
          Back to Home
        </Link>
      </div>
    );
  }

  if (finished) {
    const accuracy = answeredCount > 0 ? Math.round((correctCount / answeredCount) * 100) : 0;
    return (
      <div className="max-w-lg mx-auto text-center py-16">
        <div className="text-6xl mb-6">{accuracy >= 80 ? "🎉" : accuracy >= 50 ? "👍" : "📚"}</div>
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
          Session Complete!
        </h1>
        <p className="text-lg mb-1" style={{ color: "var(--text-secondary)" }}>
          {correctCount} / {answeredCount} correct
        </p>
        <p className="text-3xl font-bold mb-8" style={{ color: accuracy >= 80 ? "var(--success)" : accuracy >= 50 ? "var(--warning)" : "var(--error)" }}>
          {accuracy}%
        </p>
        <div className="flex gap-3 justify-center">
          <Link
            href="/"
            className="px-5 py-2.5 rounded-lg text-sm font-medium"
            style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
          >
            Home
          </Link>
          <Link
            href="/review"
            className="px-5 py-2.5 rounded-lg text-sm font-medium text-white"
            style={{ backgroundColor: "var(--accent)" }}
          >
            Review Mistakes
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <ProgressBar current={answeredCount} total={questions.length} correct={correctCount} />
      <QuizCard
        question={currentQuestion}
        onAnswer={handleAnswer}
        showResult={showResult}
        selectedAnswer={selectedAnswer}
      />
      {showResult && (
        <>
          <ExplanationPanel question={currentQuestion} wasCorrect={selectedAnswer === currentQuestion.correctAnswer} />
          <div className="flex justify-end mt-4">
            <button
              onClick={handleNext}
              className="px-6 py-2.5 rounded-lg text-sm font-medium text-white flex items-center gap-2 hover:opacity-90 transition-opacity"
              style={{ backgroundColor: "var(--accent)" }}
            >
              {currentIndex + 1 >= questions.length ? "Finish" : "Next"}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
              </svg>
              <span className="text-xs opacity-60 ml-1">Enter</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
