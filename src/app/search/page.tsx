"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { Question, Manifest, QuestionSet, badgeClass } from "@/lib/types";

interface SearchResult {
  question: Question;
  setInfo: QuestionSet;
  score: number;
  matchField: "question" | "options" | "explanation";
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [allQuestions, setAllQuestions] = useState<{ q: Question; set: QuestionSet }[]>([]);
  const [loading, setLoading] = useState(true);
  const [searched, setSearched] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load all questions on mount
  useEffect(() => {
    async function loadAll() {
      try {
        const mRes = await fetch("/data/manifest.json");
        const manifest: Manifest = await mRes.json();
        const allQs: { q: Question; set: QuestionSet }[] = [];
        const fetches = manifest.questionSets
          .filter(s => s.questionCount > 0)
          .map(async (qSet) => {
            try {
              const res = await fetch(`/data/${qSet.file}`);
              const questions: Question[] = await res.json();
              for (const q of questions) allQs.push({ q, set: qSet });
            } catch { /* skip */ }
          });
        await Promise.all(fetches);
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
      setSearched(false);
      return;
    }

    setSearched(true);
    const terms = searchQuery.toLowerCase().split(/\s+/).filter(t => t.length >= 2);
    if (terms.length === 0) { setResults([]); return; }

    const found: SearchResult[] = [];

    for (const { q, set } of allQuestions) {
      const qLower = q.question.toLowerCase();
      const optText = Object.values(q.options).join(" ").toLowerCase();
      const explLower = (q.explanation || "").toLowerCase();

      // Score: how many search terms match, weighted by field
      let score = 0;
      let matchField: "question" | "options" | "explanation" = "question";

      for (const term of terms) {
        // Question match = 10 points per term
        if (qLower.includes(term)) score += 10;
        // Option match = 5 points
        if (optText.includes(term)) score += 5;
        // Explanation match = 2 points
        if (explLower.includes(term)) score += 2;
      }

      if (score === 0) continue;

      // Determine primary match field
      const qMatch = terms.some(t => qLower.includes(t));
      const optMatch = terms.some(t => optText.includes(t));
      if (qMatch) matchField = "question";
      else if (optMatch) matchField = "options";
      else matchField = "explanation";

      // Bonus: all terms match = much higher score
      const allTermsMatch = terms.every(t => qLower.includes(t) || optText.includes(t) || explLower.includes(t));
      if (allTermsMatch) score += 20;

      // Bonus: exact phrase match in question
      if (qLower.includes(searchQuery.toLowerCase())) score += 30;

      found.push({ question: q, setInfo: set, score, matchField });
    }

    // Sort by relevance score (highest first)
    found.sort((a, b) => b.score - a.score);

    setResults(found.slice(0, 100));
  }, [allQuestions]);

  const handleSubmit = () => {
    setSubmittedQuery(query);
    doSearch(query);
  };

  const highlightMatch = (text: string, q: string) => {
    if (!q || q.length < 2) return text;
    const terms = q.split(/\s+/).filter(t => t.length >= 2);
    if (terms.length === 0) return text;
    const pattern = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join("|");
    const regex = new RegExp(`(${pattern})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? <mark key={i}>{part}</mark> : part
    );
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--text-primary)" }}>
          <span className="font-display italic">Search</span> Questions
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {allQuestions.length.toLocaleString()} questions loaded. Press Enter to search.
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
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
          placeholder="Type keywords and press Enter..."
          className="w-full pl-12 pr-24 py-3.5 text-base outline-none transition-shadow focus:ring-2"
          style={{
            backgroundColor: "var(--bg-card)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
            boxShadow: "var(--shadow-sm)",
          }}
          autoFocus={typeof window !== "undefined" && !("ontouchstart" in window)}
        />
        <button
          onClick={handleSubmit}
          className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 text-xs font-semibold"
          style={{ backgroundColor: "var(--accent)", color: "white" }}
        >
          Search
        </button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="text-center py-12">
          <div
            className="w-10 h-10 border-4 rounded-full animate-spin mx-auto mb-3"
            style={{ borderColor: "var(--border)", borderTopColor: "var(--accent)" }}
          />
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading question database...</p>
        </div>
      )}

      {/* Results */}
      {!loading && searched && (
        <div>
          <p className="text-xs font-medium mb-3" style={{ color: "var(--text-muted)" }}>
            {results.length === 0 ? "No results found" : `${results.length} result${results.length !== 1 ? "s" : ""}`}
            {results.length >= 100 && " (showing top 100 by relevance)"}
          </p>

          <div className="space-y-2">
            {results.map((r) => {
              const key = `${r.question.source}:${r.question.id}`;
              const isExpanded = expandedId === key;

              return (
                <div
                  key={key}
                  className="overflow-hidden transition-shadow hover:shadow-md cursor-pointer"
                  style={{
                    backgroundColor: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    boxShadow: "var(--shadow-sm)",
                  }}
                  onClick={() => setExpandedId(isExpanded ? null : key)}
                >
                  <div className="px-4 py-3">
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium leading-relaxed" style={{ color: "var(--text-primary)" }}>
                          {highlightMatch(r.question.question, submittedQuery)}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span
                            className={`text-xs px-2 py-0.5 font-medium ${badgeClass(r.setInfo.source)}`}
                          >
                            {r.setInfo.name}
                          </span>
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                            Q{r.question.id}
                          </span>
                        </div>
                      </div>
                      <svg
                        width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)"
                        strokeWidth="2" className="shrink-0 mt-1 transition-transform"
                        style={{ transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)" }}
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="px-4 pb-3 animate-slide-up" style={{ borderTop: "1px solid var(--border)" }}>
                      <div className="pt-3 space-y-1.5">
                        {Object.entries(r.question.options).sort().map(([k, v]) => (
                          <div key={k} className="flex items-start gap-2 text-sm">
                            <span className="font-bold shrink-0"
                              style={{ color: k === r.question.correctAnswer ? "var(--success)" : "var(--text-muted)" }}>
                              {k}.
                            </span>
                            <span style={{ color: "var(--text-secondary)" }}>
                              {highlightMatch(v, submittedQuery)}
                              {k === r.question.correctAnswer && " *"}
                            </span>
                          </div>
                        ))}
                      </div>
                      {r.question.explanation && (
                        <p className="text-xs mt-2 leading-relaxed" style={{ color: "var(--text-muted)" }}>
                          {r.question.explanation.slice(0, 300)}
                          {r.question.explanation.length > 300 && "..."}
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
      {!loading && !searched && (
        <div className="text-center py-16">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--border)" strokeWidth="1.5" className="mx-auto mb-4">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <p style={{ color: "var(--text-muted)" }}>Type keywords and press Enter to search</p>
          <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
            Try: "glaucoma surgery", "retinal detachment", "amblyopia treatment"
          </p>
        </div>
      )}
    </div>
  );
}
