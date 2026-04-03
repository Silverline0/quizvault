"use client";

import { Question } from "@/lib/types";
import { useCallback, useEffect, useState } from "react";
import { isBookmarked, toggleBookmark } from "@/lib/store";

interface QuizCardProps {
  question: Question;
  onAnswer: (selected: string, correct: boolean) => void;
  showResult: boolean;
  selectedAnswer: string | null;
}

export default function QuizCard({ question, onAnswer, showResult, selectedAnswer }: QuizCardProps) {
  const [bookmarked, setBookmarked] = useState(false);

  useEffect(() => {
    setBookmarked(isBookmarked(question.id, question.source));
  }, [question.id, question.source]);

  const handleSelect = useCallback(
    (key: string) => {
      if (showResult) return;
      onAnswer(key, key === question.correctAnswer);
    },
    [showResult, onAnswer, question.correctAnswer]
  );

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (showResult) return;
      const key = e.key.toUpperCase();
      if (["A", "B", "C", "D", "E"].includes(key) && question.options[key]) {
        handleSelect(key);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showResult, handleSelect, question.options]);

  const handleBookmark = () => {
    toggleBookmark(question.id, question.source);
    setBookmarked(!bookmarked);
  };

  const optionKeys = Object.keys(question.options).sort();

  return (
    <div
      className="rounded-xl p-6 md:p-8 shadow-sm"
      style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      {/* Question header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex-1">
          <span
            className="text-xs font-medium px-2 py-1 rounded-full"
            style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-muted)" }}
          >
            Q{question.id}
          </span>
          <h2 className="text-lg md:text-xl font-semibold mt-3 leading-relaxed" style={{ color: "var(--text-primary)" }}>
            {question.question}
          </h2>
        </div>
        <button
          onClick={handleBookmark}
          className="shrink-0 mt-1 hover:scale-110 transition-transform"
          title={bookmarked ? "Remove bookmark" : "Bookmark this question"}
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill={bookmarked ? "var(--warning)" : "none"}
            stroke={bookmarked ? "var(--warning)" : "var(--text-muted)"}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      </div>

      {/* Options */}
      <div className="space-y-3">
        {optionKeys.map((key) => {
          const isSelected = selectedAnswer === key;
          const isCorrect = key === question.correctAnswer;
          let borderColor = "var(--border)";
          let bgColor = "transparent";

          if (showResult) {
            if (isCorrect) {
              borderColor = "var(--success)";
              bgColor = "var(--success-bg)";
            } else if (isSelected && !isCorrect) {
              borderColor = "var(--error)";
              bgColor = "var(--error-bg)";
            }
          } else if (isSelected) {
            borderColor = "var(--accent)";
            bgColor = "var(--bg-secondary)";
          }

          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              disabled={showResult}
              className="w-full text-left px-4 py-3 rounded-lg flex items-start gap-3 transition-all duration-150"
              style={{
                border: `2px solid ${borderColor}`,
                backgroundColor: bgColor,
                cursor: showResult ? "default" : "pointer",
              }}
            >
              <span
                className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                style={{
                  backgroundColor: isSelected && !showResult ? "var(--accent)" : "var(--bg-secondary)",
                  color: isSelected && !showResult ? "#fff" : "var(--text-secondary)",
                }}
              >
                {key}
              </span>
              <span className="pt-1 text-sm md:text-base" style={{ color: "var(--text-primary)" }}>
                {question.options[key]}
              </span>
              {showResult && isCorrect && (
                <svg className="shrink-0 ml-auto mt-1" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              )}
              {showResult && isSelected && !isCorrect && (
                <svg className="shrink-0 ml-auto mt-1" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--error)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              )}
            </button>
          );
        })}
      </div>

      {/* Keyboard hint */}
      {!showResult && (
        <p className="text-xs mt-4" style={{ color: "var(--text-muted)" }}>
          Press <kbd className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ backgroundColor: "var(--bg-secondary)" }}>A</kbd>
          {" "}<kbd className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ backgroundColor: "var(--bg-secondary)" }}>B</kbd>
          {" "}<kbd className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ backgroundColor: "var(--bg-secondary)" }}>C</kbd>
          {" "}<kbd className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ backgroundColor: "var(--bg-secondary)" }}>D</kbd>
          {" "}to select
        </p>
      )}
    </div>
  );
}
