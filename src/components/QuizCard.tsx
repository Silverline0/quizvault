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
    <div>
      {/* Question header */}
      <div className="flex items-start justify-between gap-3 mb-5">
        <div className="flex-1">
          <h2 className="text-lg md:text-xl font-semibold leading-relaxed" style={{ color: "var(--text-primary)" }}>
            {question.question}
          </h2>
        </div>
        <button
          onClick={handleBookmark}
          className="shrink-0 mt-1 w-9 h-9 rounded-full flex items-center justify-center hover:scale-110 transition-transform"
          style={{ backgroundColor: bookmarked ? "var(--warning-bg)" : "transparent" }}
          title={bookmarked ? "Remove bookmark" : "Bookmark this question"}
        >
          <svg
            width="20"
            height="20"
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

      {/* Question image */}
      {question.imageUrl && (
        <div className="mb-5 rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={question.imageUrl}
            alt={`Image for question ${question.id}`}
            className="w-full max-h-72 object-contain"
            style={{ backgroundColor: "var(--bg-secondary)" }}
            loading="lazy"
          />
        </div>
      )}

      {/* Options — bordered cards with radio circle on right */}
      <div className="space-y-3">
        {optionKeys.map((key) => {
          const isSelected = selectedAnswer === key;
          const isCorrect = key === question.correctAnswer;

          let borderColor = "var(--border)";
          let bgColor = "transparent";
          let radioContent: React.ReactNode = (
            <span
              className="w-6 h-6 rounded-full shrink-0"
              style={{ border: "2px solid var(--border)" }}
            />
          );

          if (showResult) {
            if (isCorrect) {
              borderColor = "var(--success)";
              bgColor = "var(--success-bg)";
              radioContent = (
                <span
                  className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center"
                  style={{ backgroundColor: "var(--success)" }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </span>
              );
            } else if (isSelected && !isCorrect) {
              borderColor = "var(--error)";
              bgColor = "var(--error-bg)";
              radioContent = (
                <span
                  className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center"
                  style={{ backgroundColor: "var(--error)" }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </span>
              );
            }
          } else if (isSelected) {
            borderColor = "var(--accent)";
            bgColor = "var(--accent-light)";
            radioContent = (
              <span
                className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center"
                style={{ backgroundColor: "var(--accent)" }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </span>
            );
          }

          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              disabled={showResult}
              className="w-full text-left px-4 py-3.5 rounded-xl flex items-center justify-between gap-3 transition-all duration-150"
              style={{
                border: `2px solid ${borderColor}`,
                backgroundColor: bgColor,
                cursor: showResult ? "default" : "pointer",
              }}
            >
              <span className="text-sm md:text-base leading-relaxed" style={{ color: "var(--text-primary)" }}>
                <span className="font-semibold" style={{ color: "var(--text-secondary)" }}>{key}.</span>{" "}
                {question.options[key]}
              </span>
              {radioContent}
            </button>
          );
        })}
      </div>

      {/* Keyboard hint */}
      {!showResult && (
        <p className="text-xs mt-3 text-center" style={{ color: "var(--text-muted)" }}>
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
