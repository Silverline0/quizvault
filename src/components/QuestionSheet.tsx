"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Question } from "@/lib/types";
import { getAllFlagged } from "@/lib/store";

type Filter = "all" | "todo" | "wrong" | "flagged";

interface QuestionSheetProps {
  open: boolean;
  onClose: () => void;
  questions: Question[];
  currentIndex: number;
  answeredMap: Map<number, boolean>;
  onJump: (index: number) => void;
  onMarkPreviousAnswered?: () => void;
}

/**
 * Jump-to-question sheet for phones and tablets.
 *
 * `QuestionNavigator` is the same idea for desktop, but it is `hidden xl:block`
 * — below 1280px there was no way to reach a question except Prev/Next, which
 * is unusable in a bank of several hundred recalls.
 */
export default function QuestionSheet({
  open,
  onClose,
  questions,
  currentIndex,
  answeredMap,
  onJump,
  onMarkPreviousAnswered,
}: QuestionSheetProps) {
  const [filter, setFilter] = useState<Filter>("all");
  const [flagged, setFlagged] = useState<Set<number>>(new Set());
  const currentRef = useRef<HTMLButtonElement | null>(null);

  // Read the flag list once per opening. `isFlagged()` re-parses localStorage on
  // every call, so asking it per question would mean hundreds of parses each
  // render.
  useEffect(() => {
    if (!open) return;
    const keys = new Set(getAllFlagged().map((f) => `${f.source}:${f.questionId}`));
    const indices = new Set<number>();
    questions.forEach((q, i) => {
      if (keys.has(`${q.source}:${q.id}`)) indices.add(i);
    });
    setFlagged(indices);
  }, [open, questions]);

  // Escape to close, and hold the page still behind the sheet.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  // Bring the question you are on into view — in a 900-question bank the
  // current cell is otherwise far below the fold.
  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => {
      currentRef.current?.scrollIntoView({ block: "center" });
    });
    return () => cancelAnimationFrame(id);
  }, [open, filter]);

  const counts = useMemo(() => {
    let todo = 0;
    let wrong = 0;
    for (let i = 0; i < questions.length; i++) {
      if (!answeredMap.has(i)) todo++;
      else if (!answeredMap.get(i)) wrong++;
    }
    return { all: questions.length, todo, wrong, flagged: flagged.size };
  }, [questions.length, answeredMap, flagged]);

  const visible = useMemo(() => {
    const out: number[] = [];
    for (let i = 0; i < questions.length; i++) {
      if (filter === "todo" && answeredMap.has(i)) continue;
      if (filter === "wrong" && answeredMap.get(i) !== false) continue;
      if (filter === "flagged" && !flagged.has(i)) continue;
      out.push(i);
    }
    return out;
  }, [questions.length, answeredMap, flagged, filter]);

  if (!open) return null;

  const FILTERS: { id: Filter; label: string; count: number }[] = [
    { id: "all", label: "All", count: counts.all },
    { id: "todo", label: "Unanswered", count: counts.todo },
    { id: "wrong", label: "Wrong", count: counts.wrong },
    { id: "flagged", label: "Flagged", count: counts.flagged },
  ];

  return (
    <>
      <div
        className="fixed inset-0 z-[80] animate-fade-in xl:hidden"
        style={{ backgroundColor: "rgba(0,0,0,0.45)" }}
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Jump to question"
        className="fixed left-0 right-0 bottom-0 z-[81] flex flex-col animate-sheet-in xl:hidden"
        style={{
          height: "min(66vh, 560px)",
          backgroundColor: "var(--bg-card)",
          borderTop: "1px solid var(--border)",
          boxShadow: "var(--shadow-lg)",
          paddingBottom: "env(safe-area-inset-bottom)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-3.5 pb-2.5 shrink-0">
          <span
            className="text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--text-muted)" }}
          >
            Jump to question
          </span>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-11 h-11 -mr-2.5 flex items-center justify-center hover:opacity-70"
            style={{ color: "var(--text-muted)" }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-1.5 px-4 pb-3 overflow-x-auto shrink-0" style={{ scrollbarWidth: "none" }}>
          {FILTERS.map((f) => {
            const on = filter === f.id;
            return (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className="h-8 px-2.5 flex items-center gap-1.5 text-xs font-semibold shrink-0 transition-colors"
                style={{
                  border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`,
                  backgroundColor: on ? "var(--accent-light)" : "var(--bg-primary)",
                  color: on ? "var(--accent)" : "var(--text-secondary)",
                }}
              >
                {f.label}
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

        {/* Grid */}
        <div className="flex-1 overflow-y-auto px-4 pb-4 min-h-0">
          {visible.length === 0 ? (
            <p className="text-sm text-center mt-8" style={{ color: "var(--text-muted)" }}>
              {filter === "wrong"
                ? "Nothing wrong so far."
                : filter === "flagged"
                  ? "You haven't flagged anything in this bank."
                  : "Every question here is answered."}
            </p>
          ) : (
            <div className="grid grid-cols-6 sm:grid-cols-8 gap-1.5">
              {visible.map((i) => {
                const isCurrent = i === currentIndex;
                const answered = answeredMap.has(i);
                const correct = answeredMap.get(i);

                let bgColor = "transparent";
                let borderColor = "var(--border)";
                let textColor = "var(--text-muted)";

                if (isCurrent) {
                  bgColor = "var(--accent-light)";
                  borderColor = "var(--accent)";
                  textColor = "var(--accent)";
                } else if (answered && correct) {
                  bgColor = "var(--success-bg)";
                  borderColor = "var(--success)";
                  textColor = "var(--success)";
                } else if (answered && !correct) {
                  bgColor = "var(--error-bg)";
                  borderColor = "var(--error)";
                  textColor = "var(--error)";
                }

                return (
                  <button
                    key={i}
                    ref={isCurrent ? currentRef : undefined}
                    onClick={() => {
                      onJump(i);
                      onClose();
                    }}
                    aria-current={isCurrent ? "true" : undefined}
                    className="w-full aspect-square text-xs font-semibold flex items-center justify-center transition-transform active:scale-95"
                    style={{
                      backgroundColor: bgColor,
                      border: `1px solid ${borderColor}`,
                      color: textColor,
                    }}
                  >
                    {i + 1}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Recover lost progress — the action the desktop sidebar already offers */}
        {onMarkPreviousAnswered && currentIndex > 0 && (
          <div className="px-4 py-3 shrink-0" style={{ borderTop: "1px solid var(--border)" }}>
            <button
              onClick={() => {
                onMarkPreviousAnswered();
                onClose();
              }}
              className="w-full h-11 text-xs font-semibold hover:opacity-80"
              style={{
                border: "1px solid var(--border)",
                backgroundColor: "var(--bg-primary)",
                color: "var(--text-secondary)",
              }}
            >
              Mark Q1&ndash;{currentIndex} as done
            </button>
          </div>
        )}
      </div>
    </>
  );
}
