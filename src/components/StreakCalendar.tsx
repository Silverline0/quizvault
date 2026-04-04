"use client";

import { useEffect, useState } from "react";
import { getStudyDays } from "@/lib/store";

export default function StreakCalendar() {
  const [days, setDays] = useState<Map<string, number>>(new Map());

  useEffect(() => {
    setDays(getStudyDays());
  }, []);

  // Build a proper heatmap grid: 7 rows (Sun-Sat) x N columns (weeks)
  const WEEKS_TO_SHOW = 16;
  const today = new Date();

  // Find the Saturday that ends the current week (or today if it's Saturday)
  const endDate = new Date(today);
  const dayOfWeek = endDate.getDay(); // 0=Sun ... 6=Sat
  endDate.setDate(endDate.getDate() + (6 - dayOfWeek)); // advance to Saturday

  // Start date is (WEEKS_TO_SHOW - 1) weeks before that Saturday's Sunday
  const startDate = new Date(endDate);
  startDate.setDate(startDate.getDate() - (WEEKS_TO_SHOW * 7 - 1)); // back to Sunday of first week

  // Build grid: array of weeks, each week is array of 7 days (Sun=0 ... Sat=6)
  type Cell = { date: string; count: number; isAfterToday: boolean };
  const weeks: (Cell | null)[][] = [];

  const cursor = new Date(startDate);
  for (let w = 0; w < WEEKS_TO_SHOW; w++) {
    const week: (Cell | null)[] = [];
    for (let d = 0; d < 7; d++) {
      if (cursor > today) {
        week.push(null); // future dates: empty
      } else {
        // Use local date format to match getStudyDays()
        const dateStr = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-${String(cursor.getDate()).padStart(2, "0")}`;
        week.push({
          date: dateStr,
          count: days.get(dateStr) || 0,
          isAfterToday: false,
        });
      }
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
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

  const totalDays = Array.from(days.values()).filter((v) => v > 0).length;
  const totalQuestions = Array.from(days.values()).reduce((s, v) => s + v, 0);

  // Day labels: show every other for space (Sun, Tue, Thu, Sat)
  const allDayLabels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const dayLabels = allDayLabels.map((label, i) =>
    i % 2 === 0 ? label : ""
  );

  return (
    <div
      className="rounded-xl p-4"
      style={{
        backgroundColor: "var(--bg-card)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3
          className="text-xs font-semibold uppercase tracking-wider"
          style={{ color: "var(--text-muted)" }}
        >
          Study Activity
        </h3>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {totalDays} days &middot; {totalQuestions.toLocaleString()} Qs
        </span>
      </div>

      <div className="flex gap-[3px] overflow-hidden">
        {/* Day labels column */}
        <div className="flex flex-col gap-[3px] shrink-0 mr-0.5">
          {dayLabels.map((label, i) => (
            <div key={i} className="h-[11px] flex items-center justify-end">
              <span
                className="text-[9px] leading-none"
                style={{ color: "var(--text-muted)" }}
              >
                {label}
              </span>
            </div>
          ))}
        </div>

        {/* Heatmap grid: each week is a column, each row is a day of week */}
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-[3px]">
            {week.map((cell, di) => (
              <div
                key={`${wi}-${di}`}
                className="w-[11px] h-[11px] rounded-sm transition-colors"
                style={{
                  backgroundColor: cell
                    ? getColor(cell.count)
                    : "transparent",
                }}
                title={cell ? `${cell.date}: ${cell.count} questions` : ""}
              />
            ))}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-1 mt-2 justify-end">
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          Less
        </span>
        {[0, 0.25, 0.5, 0.75, 1].map((level) => (
          <div
            key={level}
            className="w-[11px] h-[11px] rounded-sm"
            style={{
              backgroundColor: getColor(
                level === 0 ? 0 : Math.ceil(level * maxCount)
              ),
            }}
          />
        ))}
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          More
        </span>
      </div>
    </div>
  );
}
