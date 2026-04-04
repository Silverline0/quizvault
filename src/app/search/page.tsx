"use client";

import { useEffect, useState, useCallback } from "react";
import { Question, Manifest, QuestionSet } from "@/lib/types";
import Link from "next/link";

interface SearchResult {
  question: Question;
  setInfo: QuestionSet;
  matchField: "question" | "options" | "explanation";
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [allQuestions, setAllQuestions] = useState<{ q: Question; set: QuestionSet }[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Load all questions on mount
  useEffect(() => {
    async function loadAll() {
      try {
        const mRes = await fetch("/data/manifest.json");
        const manifest: Manifest = await mRes.json();
        const allQs: { q: Question; set: QuestionSet }[] = [];

        for (const qSet of manifest.questionSets) {
          if (qSet.questionCount === 0) continue;
          try {
            const res = await fetch(`/data/${qSet.file}`);
            const questions: Question[] = await res.json();
            for (const q of questions) {
              allQs.push({ q, set: qSet });
            }
          } catch { /* skip */ }
        }
        setAllQuestions(allQs);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadAll();
  }, []);

  const doSearch = useCallback((searchQuery: string) => {
    if (searchQuery.length < 2) {
      setResults([]);
      return;
    }

    setSearching(true);
    const lower = searchQuery.toLowerCase();
    const found: SearchResult[] = [];

    for (const { q, set } of allQuestions) {
      if (found.length >= 50) break; // cap at 50 results

      if (q.question.toLowerCase().includes(lower)) {
        found.push({ question: q, setInfo: set, matchField: "question" });
      } else if (Object.values(q.options).some(v => v.toLowerCase().includes(lower))) {
        found.push({ question: q, setInfo: set, matchField: "options" });
      } else if (q.explanation?.toLowerCase().includes(lower)) {
        found.push({ question: q, setInfo: set, matchField: "explanation" });
      }
    }

    setResults(found);
    setSearching(false);
  }, [allQuestions]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => doSearch(query), 250);
    return () => clearTimeout(timer);
  }, [query, doSearch]);

  const highlightMatch = (text: string, q: string) => {
    if (!q || q.length < 2) return text;
    const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? <mark key={i}>{part}</mark> : part
    );
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--text-primary)" }}>
          <span className="font-display italic">Search</span> Questions
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Search across all {allQuestions.length.toLocaleString()} questions
        </p>
      </div>

      {/* Search input */}
      <div className="relative mb-6">
        <svg
          className="absolute left-4 top-1/2 -translate-y-1/2"
          width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search questions, options, explanations..."
          className="w-full pl-12 pr-4 py-3.5 rounded-xl text-base outline-none transition-shadow focus:ring-2"
          style={{
            backgroundColor: "var(--bg-card)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
            boxShadow: "var(--shadow-sm)",
            // @ts-expect-error ring color
            "--tw-ring-color": "var(--accent-glow)",
          }}
          autoFocus
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            className="absolute right-4 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70"
            style={{ color: "var(--text-muted)" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>

      {/* Loading state */}
      {loading && (
        <div className="text-center py-12">
          <div
            className="w-8 h-8 border-3 rounded-full animate-spin mx-auto mb-3"
            style={{ borderColor: "var(--border)", borderTopColor: "var(--accent)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading question database...</p>
        </div>
      )}

      {/* Results */}
      {!loading && query.length >= 2 && (
        <div>
          <p className="text-xs font-medium mb-3" style={{ color: "var(--text-muted)" }}>
            {results.length === 0 ? "No results found" : `${results.length} result${results.length !== 1 ? "s" : ""} found`}
            {results.length >= 50 && " (showing first 50)"}
          </p>

          <div className="space-y-3">
            {results.map((r) => {
              const key = `${r.question.source}:${r.question.id}`;
              const isExpanded = expandedId === key;

              return (
                <div
                  key={key}
                  className="rounded-xl overflow-hidden transition-shadow hover:shadow-md cursor-pointer"
                  style={{
                    backgroundColor: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    boxShadow: "var(--shadow-sm)",
                  }}
                  onClick={() => setExpandedId(isExpanded ? null : key)}
                >
                  <div className="px-4 py-3.5">
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium leading-relaxed" style={{ color: "var(--text-primary)" }}>
                          {highlightMatch(r.question.question, query)}
                        </p>
                        <div className="flex items-center gap-2 mt-1.5">
                          <span
                            className="text-xs px-2 py-0.5 rounded-full font-medium"
                            style={{
                              backgroundColor: r.setInfo.source === "BCSC" ? "#dbeafe" : "#ede9fe",
                              color: r.setInfo.source === "BCSC" ? "#1d4ed8" : "#6d28d9",
                            }}
                          >
                            {r.setInfo.name}
                          </span>
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                            Q{r.question.id} · matched in {r.matchField}
                          </span>
                        </div>
                      </div>
                      <svg
                        width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)"
                        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                        className="shrink-0 mt-1 transition-transform"
                        style={{ transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)" }}
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="px-4 pb-4 animate-slide-up" style={{ borderTop: "1px solid var(--border)" }}>
                      <div className="pt-3 space-y-2">
                        {Object.entries(r.question.options).sort().map(([k, v]) => (
                          <div key={k} className="flex items-start gap-2 text-sm">
                            <span
                              className="font-bold shrink-0"
                              style={{ color: k === r.question.correctAnswer ? "var(--success)" : "var(--text-muted)" }}
                            >
                              {k}.
                            </span>
                            <span style={{ color: "var(--text-secondary)" }}>
                              {highlightMatch(v, query)}
                              {k === r.question.correctAnswer && " ✓"}
                            </span>
                          </div>
                        ))}
                      </div>
                      {r.question.explanation && (
                        <p className="text-xs mt-3 leading-relaxed" style={{ color: "var(--text-muted)" }}>
                          {r.question.explanation.slice(0, 200)}
                          {r.question.explanation.length > 200 && "..."}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && query.length < 2 && (
        <div className="text-center py-16">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--border)" strokeWidth="1.5" className="mx-auto mb-4">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <p style={{ color: "var(--text-muted)" }}>Type at least 2 characters to search</p>
        </div>
      )}
    </div>
  );
}
