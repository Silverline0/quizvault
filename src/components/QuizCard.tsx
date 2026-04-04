"use client";

import { Question } from "@/lib/types";
import { useCallback, useEffect, useState } from "react";
import { isBookmarked, toggleBookmark, isFlagged, toggleFlagged } from "@/lib/store";
import { triggerHaptic, getSetting } from "@/lib/settings";
import ImageZoom from "@/components/ImageZoom";

interface QuizCardProps {
  question: Question;
  onAnswer: (selected: string, correct: boolean) => void;
  showResult: boolean;
  selectedAnswer: string | null;
}

export default function QuizCard({ question, onAnswer, showResult, selectedAnswer }: QuizCardProps) {
  const [bookmarked, setBookmarked] = useState(false);
  const [flagged, setFlagged] = useState(false);
  const [glowKey, setGlowKey] = useState<string | null>(null);

  useEffect(() => {
    setBookmarked(isBookmarked(question.id, question.source));
    setFlagged(isFlagged(question.id, question.source));
    setGlowKey(null);
  }, [question.id, question.source]);

  const handleSelect = useCallback(
    (key: string) => {
      if (showResult) return;
      const correct = key === question.correctAnswer;
      onAnswer(key, correct);
      triggerHaptic(correct ? "success" : "error");

      // Trigger glow animation on correct answer
      if (correct) {
        setGlowKey(key);
      }
    },
    [showResult, onAnswer, question.correctAnswer]
  );

  // Keyboard shortcuts
  useEffect(() => {
    if (showResult) return;
    const settings = typeof window !== "undefined" ? getSetting("keyMap") : null;
    const handler = (e: KeyboardEvent) => {
      if (!settings) return;
      const keyUpper = e.key.toUpperCase();
      if (keyUpper === settings.optionA.toUpperCase() && question.options["A"]) handleSelect("A");
      else if (keyUpper === settings.optionB.toUpperCase() && question.options["B"]) handleSelect("B");
      else if (keyUpper === settings.optionC.toUpperCase() && question.options["C"]) handleSelect("C");
      else if (keyUpper === settings.optionD.toUpperCase() && question.options["D"]) handleSelect("D");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showResult, handleSelect, question.options]);

  const handleBookmark = () => {
    toggleBookmark(question.id, question.source);
    setBookmarked(!bookmarked);
    triggerHaptic("light");
  };

  const handleFlag = () => {
    toggleFlagged(question.id, question.source);
    setFlagged(!flagged);
    triggerHaptic("light");
  };

  const optionKeys = Object.keys(question.options).sort();
  const showHints = typeof window !== "undefined" ? getSetting("showKeyboardHints") : true;

  return (
    <div>
      {/* Question header */}
      <div className="flex items-start justify-between gap-3 mb-5">
        <h2
          className="quiz-question text-xl md:text-2xl lg:text-3xl font-semibold leading-relaxed flex-1"
          style={{ color: "var(--text-primary)" }}
        >
          {question.question}
        </h2>
        <div className="flex items-center gap-0.5 shrink-0">
          {/* Flag button */}
          <button
            onClick={handleFlag}
            className="w-11 h-11 rounded-full flex items-center justify-center transition-transform"
            style={{
              backgroundColor: flagged ? "var(--error-bg)" : "transparent",
              transform: flagged ? "scale(1.1)" : "scale(1)",
            }}
            title={flagged ? "Unflag" : "Flag for discussion"}
          >
            <svg width="16" height="16" viewBox="0 0 24 24"
              fill={flagged ? "var(--error)" : "none"}
              stroke={flagged ? "var(--error)" : "var(--text-muted)"}
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" /><line x1="4" y1="22" x2="4" y2="15" />
            </svg>
          </button>
          {/* Bookmark button */}
          <button
            onClick={handleBookmark}
            className="w-11 h-11 rounded-full flex items-center justify-center transition-transform"
            style={{
              backgroundColor: bookmarked ? "var(--warning-bg)" : "transparent",
              transform: bookmarked ? "scale(1.1)" : "scale(1)",
            }}
            title={bookmarked ? "Remove bookmark" : "Bookmark"}
          >
            <svg width="16" height="16" viewBox="0 0 24 24"
              fill={bookmarked ? "var(--warning)" : "none"}
              stroke={bookmarked ? "var(--warning)" : "var(--text-muted)"}
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
            </svg>
          </button>
        </div>
      </div>

      {/* Question image with zoom */}
      {question.imageUrl && (
        <div className="mb-5" style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }}>
          <ImageZoom src={question.imageUrl} alt={`Clinical image for question ${question.id}`} />
        </div>
      )}

      {/* Options — 2x2 grid on desktop, single column on mobile */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 lg:gap-4 md:min-h-[200px]">
        {optionKeys.map((key) => {
          const isSelected = selectedAnswer === key;
          const isCorrect = key === question.correctAnswer;
          const isGlowing = glowKey === key;

          let borderColor = "var(--border)";
          let bgColor = "var(--bg-card)";
          let letterBg = "var(--bg-secondary)";
          let letterColor = "var(--text-muted)";
          let shadow = "var(--shadow-sm)";
          let radioContent: React.ReactNode = (
            <span className="w-6 h-6 rounded-full shrink-0" style={{ border: "2px solid var(--border)" }} />
          );

          if (showResult) {
            if (isCorrect) {
              borderColor = "var(--success)";
              bgColor = "var(--success-bg)";
              letterBg = "var(--success)";
              letterColor = "white";
              shadow = isGlowing ? "0 0 20px color-mix(in srgb, var(--success) 30%, transparent)" : "var(--shadow-sm)";
              radioContent = (
                <span className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center" style={{ backgroundColor: "var(--success)" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>
                </span>
              );
            } else if (isSelected && !isCorrect) {
              borderColor = "var(--error)";
              bgColor = "var(--error-bg)";
              letterBg = "var(--error)";
              letterColor = "white";
              radioContent = (
                <span className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center" style={{ backgroundColor: "var(--error)" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                </span>
              );
            }
          } else if (isSelected) {
            borderColor = "var(--accent)";
            bgColor = "var(--accent-light)";
            letterBg = "var(--accent)";
            letterColor = "white";
            shadow = "var(--shadow-glow)";
            radioContent = (
              <span className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center" style={{ backgroundColor: "var(--accent)" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>
              </span>
            );
          }

          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              disabled={showResult}
              className="option-card w-full text-left px-4 py-3.5 flex items-center gap-3"
              style={{
                border: `2px solid ${borderColor}`,
                backgroundColor: bgColor,
                boxShadow: shadow,
                cursor: showResult ? "default" : "pointer",
              }}
            >
              {/* Radio circle on left */}
              {radioContent}
              {/* Letter + text */}
              <span className="quiz-option flex-1 text-sm md:text-base leading-relaxed" style={{ color: "var(--text-primary)" }}>
                <span className="font-semibold" style={{ color: letterColor === "white" ? letterColor : "var(--text-muted)" }}>{key}.</span>{" "}
                {question.options[key]}
              </span>
            </button>
          );
        })}
      </div>

      {/* Keyboard hint */}
      {!showResult && showHints && (
        <p className="text-xs mt-3 text-center hidden md:block" style={{ color: "var(--text-muted)" }}>
          Press{" "}
          {optionKeys.map((k) => (
            <kbd key={k} className="px-1.5 py-0.5 rounded text-xs font-mono mx-0.5" style={{ backgroundColor: "var(--bg-secondary)" }}>
              {k}
            </kbd>
          ))}
          {" "}to select
        </p>
      )}
    </div>
  );
}
