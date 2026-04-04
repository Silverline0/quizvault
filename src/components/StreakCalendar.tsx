"use client";

import { useEffect, useState } from "react";
import { getStudyDays } from "@/lib/store";

export default function StreakCalendar() {
  const [days, setDays] = useState<Map<string, number>>(new Map());

  useEffect(() => {
    setDays(getStudyDays());
  }, []);

  // Generate last 12 weeks (84 days)
  const today = new Date();
  const cells: { date: string; count: number; day: number }[] = [];

  for (let i = 83; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    cells.push({ date: dateStr, count: days.get(dateStr) || 0, day: d.getDay() });
  }

  const maxCount = Math.max(1, ...Array.from(days.values()));

  const getColor = (count: number) => {
    if (count === 0) return "var(--bg-secondary)";
    const intensity = Math.min(count / maxCount, 1);
    if (intensity < 0.25) return "var(--accent-light)";
    if (intensity < 0.5) return "color-mix(in srgb, var(--accent) 40%, var(--accent-light))";
    if (intensity < 0.75) return "color-mix(in srgb, var(--accent) 65%, var(--accent-light))";
    return "var(--accent)";
  };

  // Group by weeks (columns)
  const weeks: typeof cells[] = [];
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7));
  }

  const totalDays = Array.from(days.values()).filter(v => v > 0).length;
  const totalQuestions = Array.from(days.values()).reduce((s, v) => s + v, 0);

  return (
    <div
      className="rounded-xl p-4"
      style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
          Study Activity
        </h3>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {totalDays} days · {totalQuestions.toLocaleString()} Qs
        </span>
      </div>

      <div className="flex gap-0.5">
        {/* Day labels */}
        <div className="flex flex-col gap-0.5 mr-1 justify-between py-0.5">
          {["Sun", "", "Tue", "", "", "", "Sat"].map((label, i) => (
            <div key={i} className="h-3 flex items-center">
              <span className="text-[9px] leading-none" style={{ color: "var(--text-muted)" }}>{label}</span>
            </div>
          ))}
        </div>
        {/* Grid */}
        <div className="flex gap-0.5 flex-1 justify-end">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-0.5">
              {week.map((cell) => (
                <div
                  key={cell.date}
                  className="w-3 h-3 transition-colors"
                  style={{ backgroundColor: getColor(cell.count) }}
                  title={`${cell.date}: ${cell.count} questions`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-1 mt-2 justify-end">
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>Less</span>
        {[0, 0.25, 0.5, 0.75, 1].map((level) => (
          <div
            key={level}
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: getColor(level === 0 ? 0 : Math.ceil(level * maxCount)) }}
          />
        ))}
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>More</span>
      </div>
    </div>
  );
}
