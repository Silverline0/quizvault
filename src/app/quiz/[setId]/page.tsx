"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Question, QuizMode } from "@/lib/types";
import { loadQuestionSet } from "@/lib/quiz-engine";
import { buildQuizQueue, getStartIndex } from "@/lib/quiz-engine";
import { recordAnswer, saveLastPosition, saveLastActive, updateSpacedRep, startStudySession, endStudySession, getAnswersForSet } from "@/lib/store";
import { getSetting } from "@/lib/settings";
import { StudySession } from "@/lib/types";
import QuizCard from "@/components/QuizCard";
import ExplanationPanel from "@/components/ExplanationPanel";
import QuestionCounter from "@/components/QuestionCounter";
import QuizHeader from "@/components/QuizHeader";
import QuestionNavigator from "@/components/QuestionNavigator";
import SessionSummary from "@/components/SessionSummary";
import Link from "next/link";
import { useRouter } from "next/navigation";

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
  const [setName, setSetName] = useState("");
  const [answeredMap, setAnsweredMap] = useState<Map<number, boolean>>(new Map());
  const [answerRecord, setAnswerRecord] = useState<Map<number, string>>(new Map());
  const [studySession, setStudySession] = useState<StudySession | null>(null);
  const [questionStartTime, setQuestionStartTime] = useState(Date.now());
  const [showSessionSummary, setShowSessionSummary] = useState(false);
  const sessionEndedRef = useRef(false);
  const router = useRouter();

  // Safe session end — prevents double-counting
  const safeEndSession = useCallback(() => {
    if (studySession && !sessionEndedRef.current) {
      sessionEndedRef.current = true;
      endStudySession(studySession);
    }
  }, [studySession]);

  // Track last active set for "Continue where you left off"
  useEffect(() => {
    if (setId && mode) saveLastActive(setId, mode);
  }, [setId, mode]);

  // Start study session timer
  useEffect(() => {
    if (setId) {
      const session = startStudySession(setId);
      setStudySession(session);
      return () => {
        if (session.questionsAnswered > 0 && !sessionEndedRef.current) {
          sessionEndedRef.current = true;
          endStudySession(session);
        }
      };
    }
  }, [setId]);

  // Reset question timer on each new question
  useEffect(() => {
    setQuestionStartTime(Date.now());
  }, [currentIndex]);

  // Load questions
  useEffect(() => {
    async function load() {
      try {
        const manifestRes = await fetch("/data/manifest.json");
        const manifest = await manifestRes.json();
        const qSet = manifest.questionSets.find((s: { id: string }) => s.id === setId);
        if (!qSet) return;
        setSetName(qSet.name);

        const raw = await loadQuestionSet(qSet.file);
        const queue = buildQuizQueue(raw, mode, setId);
        const start = getStartIndex(mode, setId);
        setQuestions(queue);
        setCurrentIndex(Math.min(start, queue.length - 1));

        // Hydrate sidebar dots from historical answers stored in localStorage
        const historicalAnswers = getAnswersForSet(setId);
        if (historicalAnswers.length > 0) {
          // Build a map of questionId -> latest answer
          const latestByQuestion = new Map<number, { correct: boolean; selectedAnswer: string; timestamp: number }>();
          for (const a of historicalAnswers) {
            const existing = latestByQuestion.get(a.questionId);
            if (!existing || a.timestamp > existing.timestamp) {
              latestByQuestion.set(a.questionId, { correct: a.correct, selectedAnswer: a.selectedAnswer, timestamp: a.timestamp });
            }
          }

          // Map queue indices to historical answers
          const restoredAnsweredMap = new Map<number, boolean>();
          const restoredAnswerRecord = new Map<number, string>();
          let restoredCorrect = 0;

          for (let i = 0; i < queue.length; i++) {
            const entry = latestByQuestion.get(queue[i].id);
            if (entry) {
              restoredAnsweredMap.set(i, entry.correct);
              restoredAnswerRecord.set(i, entry.selectedAnswer);
              if (entry.correct) restoredCorrect++;
            }
          }

          if (restoredAnsweredMap.size > 0) {
            setAnsweredMap(restoredAnsweredMap);
            setAnswerRecord(restoredAnswerRecord);
            setAnsweredCount(restoredAnsweredMap.size);
            setCorrectCount(restoredCorrect);
          }
        }
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

      setAnsweredMap((prev) => {
        const next = new Map(prev);
        next.set(currentIndex, correct);
        return next;
      });

      setAnswerRecord((prev) => {
        const next = new Map(prev);
        next.set(currentIndex, selected);
        return next;
      });

      const timeSpent = Math.round((Date.now() - questionStartTime) / 1000);

      recordAnswer({
        questionId: currentQuestion.id,
        source: currentQuestion.source,
        selectedAnswer: selected,
        correct,
        timestamp: Date.now(),
        timeSpent,
      });

      // Update spaced repetition (if enabled in settings)
      if (getSetting("spacedRepEnabled")) {
        updateSpacedRep(currentQuestion.id, currentQuestion.source, correct);
      }

      // Update study session
      if (studySession) {
        studySession.questionsAnswered++;
        if (correct) studySession.correctCount++;
      }

      if (mode === "sequential") {
        saveLastPosition(setId, currentIndex + 1);
      }
    },
    [currentQuestion, currentIndex, mode, setId, questionStartTime, studySession]
  );

  const handleNext = useCallback(() => {
    if (currentIndex + 1 >= questions.length) {
      safeEndSession();
      setFinished(true);
      return;
    }
    const nextIdx = currentIndex + 1;
    setCurrentIndex(nextIdx);
    // Restore previous answer if already answered
    if (answeredMap.has(nextIdx)) {
      setSelectedAnswer(answerRecord.get(nextIdx) || null);
      setShowResult(true);
    } else {
      setSelectedAnswer(null);
      setShowResult(false);
    }
  }, [currentIndex, questions.length, answeredMap, answerRecord, safeEndSession]);

  const handlePrev = useCallback(() => {
    if (currentIndex <= 0) return;
    const prevIdx = currentIndex - 1;
    setCurrentIndex(prevIdx);
    // Restore previous answer state if question was already answered
    if (answeredMap.has(prevIdx)) {
      setSelectedAnswer(answerRecord.get(prevIdx) || null);
      setShowResult(true);
    } else {
      setSelectedAnswer(null);
      setShowResult(false);
    }
  }, [currentIndex, answeredMap, answerRecord]);

  const handleJump = useCallback((index: number) => {
    setCurrentIndex(index);
    // Restore previous answer state if already answered
    if (answeredMap.has(index)) {
      setSelectedAnswer(answerRecord.get(index) || null);
      setShowResult(true);
    } else {
      setSelectedAnswer(null);
      setShowResult(false);
    }
  }, [answeredMap, answerRecord]);

  // Mark all questions before current as "correctly answered" (to recover lost progress)
  const handleMarkPreviousAnswered = useCallback(() => {
    if (currentIndex <= 0) return;
    const count = currentIndex;
    if (!confirm(`Mark questions 1–${count} as correctly answered? This records them as correct in your progress.`)) return;

    const newAnsweredMap = new Map(answeredMap);
    const newAnswerRecord = new Map(answerRecord);
    let newCorrectCount = correctCount;
    let newlyAdded = 0;

    for (let i = 0; i < currentIndex; i++) {
      if (!newAnsweredMap.has(i)) {
        const q = questions[i];
        if (!q) continue;

        newAnsweredMap.set(i, true);
        newAnswerRecord.set(i, q.correctAnswer || "A");
        newCorrectCount++;
        newlyAdded++;

        recordAnswer({
          questionId: q.id,
          source: q.source,
          selectedAnswer: q.correctAnswer || "A",
          correct: true,
          timestamp: Date.now(),
        });
      }
    }

    setAnsweredMap(newAnsweredMap);
    setAnswerRecord(newAnswerRecord);
    setCorrectCount(newCorrectCount);
    setAnsweredCount((prev) => prev + newlyAdded);

    if (mode === "sequential") {
      saveLastPosition(setId, currentIndex);
    }
  }, [currentIndex, questions, answeredMap, answerRecord, correctCount, mode, setId]);

  // Keyboard: Next/Prev using remapped keys from settings
  useEffect(() => {
    const keyMap = getSetting("keyMap");
    const handler = (e: KeyboardEvent) => {
      if (e.key === keyMap.prev || e.key === "ArrowLeft") {
        handlePrev();
      } else if (e.key === "Enter" || e.key === keyMap.next || e.key === "ArrowRight") {
        handleNext();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showResult, handleNext, handlePrev]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
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
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white"
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
      <div className="max-w-lg mx-auto text-center py-16 px-4">
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
          Session Complete
        </h1>
        <p className="text-lg mb-1" style={{ color: "var(--text-secondary)" }}>
          {correctCount} / {answeredCount} correct
        </p>
        <p
          className="text-4xl font-bold mb-8"
          style={{ color: accuracy >= 80 ? "var(--success)" : accuracy >= 50 ? "var(--warning)" : "var(--error)" }}
        >
          {accuracy}%
        </p>
        <div className="flex gap-3 justify-center">
          <Link
            href="/"
            className="px-6 py-3 rounded-xl text-sm font-semibold"
            style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
          >
            Home
          </Link>
          <Link
            href="/review"
            className="px-6 py-3 rounded-xl text-sm font-semibold text-white"
            style={{ backgroundColor: "var(--text-primary)" }}
          >
            Review Mistakes
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
      <QuizHeader
        title={setName}
        onBack={() => answeredCount > 0 ? setShowSessionSummary(true) : router.push("/")}
      />

      <div className="flex gap-6 max-w-7xl mx-auto px-4 lg:px-8 py-4">
        {/* Main quiz column */}
        <div className="flex-1 min-w-0 pb-4">
          <QuestionCounter current={currentIndex} total={questions.length} correct={correctCount} onMarkPreviousAnswered={handleMarkPreviousAnswered} />

          {/* Question with slide animation */}
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

        {/* Desktop sidebar — question navigator */}
        <QuestionNavigator
          total={questions.length}
          currentIndex={currentIndex}
          answeredMap={answeredMap}
          onJump={handleJump}
          onMarkPreviousAnswered={handleMarkPreviousAnswered}
        />
      </div>

      {/* Sticky bottom navigation bar — always visible */}
      <div
        className="fixed bottom-0 left-0 right-0 p-4 z-30"
        style={{ backgroundColor: "var(--bg-primary)", borderTop: "1px solid var(--border)", paddingBottom: "max(16px, env(safe-area-inset-bottom))" }}
      >
        <div className="max-w-2xl mx-auto flex gap-3">
          {/* Previous button */}
          <button
            onClick={handlePrev}
            disabled={currentIndex <= 0}
            className="py-3.5 px-5 text-sm font-bold flex items-center justify-center gap-1.5 transition-opacity hover:opacity-90 disabled:opacity-30"
            style={{
              backgroundColor: "var(--bg-secondary)",
              color: "var(--text-primary)",
              border: "1px solid var(--border)",
            }}
          >
            Prev
          </button>

          {/* Next button — always enabled */}
          <button
            onClick={handleNext}
            disabled={currentIndex + 1 >= questions.length && !showResult}
            className="flex-1 py-3.5 text-base font-bold flex items-center justify-center gap-2 transition-opacity hover:opacity-90 disabled:opacity-40 relative overflow-hidden"
            style={{
              backgroundColor: "var(--text-primary)",
              color: "var(--bg-primary)",
            }}
          >
            {/* Progress fill bar */}
            {showResult && (
              <span
                className="absolute left-0 top-0 bottom-0 opacity-10 transition-all duration-500"
                style={{
                  width: `${questions.length > 0 ? ((currentIndex + 1) / questions.length * 100) : 0}%`,
                  backgroundColor: "var(--bg-primary)",
                }}
              />
            )}
            <span className="relative z-10 flex items-center gap-2">
              {currentIndex + 1 >= questions.length ? "Finish" : "Next"}
            </span>
          </button>
        </div>
      </div>

      {/* Session summary modal */}
      {showSessionSummary && studySession && (
        <SessionSummary
          questionsAnswered={answeredCount}
          correctCount={correctCount}
          startTime={studySession.startTime}
          onClose={() => {
            safeEndSession();
            router.push("/");
          }}
          onContinue={() => setShowSessionSummary(false)}
        />
      )}
    </>
  );
}
