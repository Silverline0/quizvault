import { AnswerRecord, UserProgress, SpacedRepItem, StudySession } from "./types";
import { triggerAutoSync } from "./cloud-sync";

const STORAGE_KEY = "quizzes_progress";

const defaultProgress: UserProgress = {
  answers: [],
  bookmarks: [],
  flagged: [],
  lastPosition: {},
  spacedRep: [],
  studyTime: { totalSeconds: 0, sessions: [] },
};

export function getProgress(): UserProgress {
  if (typeof window === "undefined") return defaultProgress;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultProgress;
    const data = JSON.parse(raw) as UserProgress;
    // Ensure new fields exist (backward compat)
    if (!data.flagged) data.flagged = [];
    if (!data.spacedRep) data.spacedRep = [];
    if (!data.studyTime) data.studyTime = { totalSeconds: 0, sessions: [] };
    return data;
  } catch {
    return defaultProgress;
  }
}

export function saveProgress(progress: UserProgress): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
  triggerAutoSync(progress);
}

// ── Answers ──────────────────────────────────────────────

export function recordAnswer(record: AnswerRecord): void {
  const progress = getProgress();
  progress.answers.push(record);
  saveProgress(progress);
}

/**
 * Take back one recorded answer, identified by its exact timestamp.
 *
 * `recordAnswer` appends rather than replaces, so a question can carry many
 * records across attempts. An undo must remove the one it just wrote and leave
 * every earlier attempt alone.
 */
export function removeAnswer(questionId: number, source: string, timestamp: number): boolean {
  const progress = getProgress();
  const idx = progress.answers.findIndex(
    (a) => a.questionId === questionId && a.source === source && a.timestamp === timestamp
  );
  if (idx < 0) return false;
  progress.answers.splice(idx, 1);
  saveProgress(progress);
  return true;
}

export function getAnswersForSet(source: string): AnswerRecord[] {
  return getProgress().answers.filter((a) => a.source === source);
}

export function getMistakes(source: string): AnswerRecord[] {
  const answers = getAnswersForSet(source);
  const latestByQuestion = new Map<number, AnswerRecord>();
  for (const a of answers) {
    const existing = latestByQuestion.get(a.questionId);
    if (!existing || a.timestamp > existing.timestamp) {
      latestByQuestion.set(a.questionId, a);
    }
  }
  return Array.from(latestByQuestion.values()).filter((a) => !a.correct);
}

export function getAllMistakes(): AnswerRecord[] {
  const answers = getProgress().answers;
  const latestByKey = new Map<string, AnswerRecord>();
  for (const a of answers) {
    const key = `${a.source}:${a.questionId}`;
    const existing = latestByKey.get(key);
    if (!existing || a.timestamp > existing.timestamp) {
      latestByKey.set(key, a);
    }
  }
  return Array.from(latestByKey.values()).filter((a) => !a.correct);
}

// ── Position ─────────────────────────────────────────────

export function getLastPosition(setId: string): number {
  return getProgress().lastPosition[setId] || 0;
}

export function saveLastPosition(setId: string, index: number): void {
  const progress = getProgress();
  progress.lastPosition[setId] = index;
  saveProgress(progress);
}

export function saveLastActive(setId: string, mode: string): void {
  const progress = getProgress();
  progress.lastActiveSet = setId;
  progress.lastActiveMode = mode;
  saveProgress(progress);
}

export function getLastActive(): { setId?: string; mode?: string; position?: number } {
  const p = getProgress();
  return {
    setId: p.lastActiveSet,
    mode: p.lastActiveMode,
    position: p.lastActiveSet ? p.lastPosition[p.lastActiveSet] : undefined,
  };
}

// ── Bookmarks ────────────────────────────────────────────

export function toggleBookmark(questionId: number, source: string): void {
  const progress = getProgress();
  const idx = progress.bookmarks.findIndex(
    (b) => b.questionId === questionId && b.source === source
  );
  if (idx >= 0) {
    progress.bookmarks.splice(idx, 1);
  } else {
    progress.bookmarks.push({ questionId, source });
  }
  saveProgress(progress);
}

export function isBookmarked(questionId: number, source: string): boolean {
  return getProgress().bookmarks.some(
    (b) => b.questionId === questionId && b.source === source
  );
}

// ── Flagged ──────────────────────────────────────────────

export function toggleFlagged(questionId: number, source: string, note?: string): void {
  const progress = getProgress();
  const idx = progress.flagged.findIndex(
    (f) => f.questionId === questionId && f.source === source
  );
  if (idx >= 0) {
    progress.flagged.splice(idx, 1);
  } else {
    progress.flagged.push({ questionId, source, note });
  }
  saveProgress(progress);
}

export function isFlagged(questionId: number, source: string): boolean {
  return getProgress().flagged.some(
    (f) => f.questionId === questionId && f.source === source
  );
}

export function getAllFlagged() {
  return getProgress().flagged;
}

// ── Spaced Repetition ────────────────────────────────────

const SR_INTERVALS = [1, 3, 7, 14, 30, 60]; // days

export function updateSpacedRep(questionId: number, source: string, correct: boolean): void {
  const progress = getProgress();
  const key = `${source}:${questionId}`;
  let item = progress.spacedRep.find(
    (s) => s.questionId === questionId && s.source === source
  );

  if (!item) {
    item = { questionId, source, interval: 0, nextReview: 0, streak: 0 };
    progress.spacedRep.push(item);
  }

  if (correct) {
    item.streak++;
    const intervalIdx = Math.min(item.streak - 1, SR_INTERVALS.length - 1);
    item.interval = SR_INTERVALS[intervalIdx];
  } else {
    item.streak = 0;
    item.interval = SR_INTERVALS[0]; // reset to 1 day
  }

  item.nextReview = Date.now() + item.interval * 24 * 60 * 60 * 1000;
  saveProgress(progress);
}

/**
 * A copy of a question's review schedule, for taking a snapshot before
 * `updateSpacedRep` overwrites it. `null` means the question has no schedule.
 */
export function getSpacedRepItem(questionId: number, source: string): SpacedRepItem | null {
  const item = getProgress().spacedRep.find(
    (s) => s.questionId === questionId && s.source === source
  );
  return item ? { ...item } : null;
}

/**
 * Put a review schedule back the way it was. Passing `null` means the question
 * had no schedule before the answer, so the entry `updateSpacedRep` created is
 * dropped rather than left behind with a streak the reader never earned.
 */
export function restoreSpacedRep(
  questionId: number,
  source: string,
  previous: SpacedRepItem | null
): void {
  const progress = getProgress();
  const idx = progress.spacedRep.findIndex(
    (s) => s.questionId === questionId && s.source === source
  );
  if (previous) {
    if (idx >= 0) progress.spacedRep[idx] = { ...previous };
    else progress.spacedRep.push({ ...previous });
  } else if (idx >= 0) {
    progress.spacedRep.splice(idx, 1);
  } else {
    return; // no schedule before, none now — nothing to write
  }
  saveProgress(progress);
}

export function getDueForReview(source?: string): SpacedRepItem[] {
  const now = Date.now();
  return getProgress().spacedRep.filter(
    (s) => s.nextReview <= now && (!source || s.source === source)
  );
}

export function getSpacedRepStats() {
  const items = getProgress().spacedRep;
  const now = Date.now();
  return {
    total: items.length,
    due: items.filter((s) => s.nextReview <= now).length,
    mastered: items.filter((s) => s.streak >= 4).length,
    learning: items.filter((s) => s.streak > 0 && s.streak < 4).length,
  };
}

// ── Study Time ───────────────────────────────────────────

export function startStudySession(source: string): StudySession {
  const session: StudySession = {
    startTime: Date.now(),
    source,
    questionsAnswered: 0,
    correctCount: 0,
  };
  return session;
}

export function endStudySession(session: StudySession): void {
  const progress = getProgress();
  session.endTime = Date.now();
  const duration = Math.round((session.endTime - session.startTime) / 1000);
  progress.studyTime.totalSeconds += duration;
  progress.studyTime.sessions.push(session);
  // Keep last 100 sessions
  if (progress.studyTime.sessions.length > 100) {
    progress.studyTime.sessions = progress.studyTime.sessions.slice(-100);
  }
  saveProgress(progress);
}

export function getStudyTimeStats() {
  const st = getProgress().studyTime;
  const totalMinutes = Math.round(st.totalSeconds / 60);
  const totalHours = Math.round(totalMinutes / 60 * 10) / 10;
  const recentSessions = st.sessions.slice(-10);
  const avgSessionMin = recentSessions.length > 0
    ? Math.round(recentSessions.reduce((sum, s) => sum + ((s.endTime || s.startTime) - s.startTime) / 1000, 0) / recentSessions.length / 60)
    : 0;
  return { totalSeconds: st.totalSeconds, totalMinutes, totalHours, avgSessionMin, sessionCount: st.sessions.length };
}

// ── Stats ────────────────────────────────────────────────

export function getStats(source?: string) {
  const answers = source ? getAnswersForSet(source) : getProgress().answers;
  const total = answers.length;
  const correct = answers.filter((a) => a.correct).length;
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;
  const uniqueQuestions = new Set(
    answers.map((a) => `${a.source}:${a.questionId}`)
  ).size;
  let streak = 0;
  for (let i = answers.length - 1; i >= 0; i--) {
    if (answers[i].correct) streak++;
    else break;
  }
  return { total, correct, accuracy, uniqueQuestions, streak };
}

// ── Weak Areas ───────────────────────────────────────────

export function getWeakAreas(): { source: string; accuracy: number; totalAnswered: number }[] {
  const progress = getProgress();
  const bySource = new Map<string, { correct: number; total: number }>();

  for (const a of progress.answers) {
    const entry = bySource.get(a.source) || { correct: 0, total: 0 };
    entry.total++;
    if (a.correct) entry.correct++;
    bySource.set(a.source, entry);
  }

  return Array.from(bySource.entries())
    .map(([source, { correct, total }]) => ({
      source,
      accuracy: Math.round((correct / total) * 100),
      totalAnswered: total,
    }))
    .filter((a) => a.totalAnswered >= 5) // need at least 5 answers
    .sort((a, b) => a.accuracy - b.accuracy);
}

// ── Knowledge Decay ──────────────────────────────────

export function getDecayWarnings(manifest?: { questionSets: { id: string; name: string }[] }): { source: string; name: string; daysSince: number }[] {
  const progress = getProgress();
  const now = Date.now();
  const thirtyDays = 30 * 24 * 60 * 60 * 1000;

  // Group answers by source, find latest timestamp per source
  const lastActivity = new Map<string, number>();
  for (const a of progress.answers) {
    const existing = lastActivity.get(a.source) || 0;
    if (a.timestamp > existing) lastActivity.set(a.source, a.timestamp);
  }

  const warnings: { source: string; name: string; daysSince: number }[] = [];
  for (const [source, lastTs] of lastActivity) {
    const elapsed = now - lastTs;
    if (elapsed > thirtyDays) {
      const daysSince = Math.floor(elapsed / (24 * 60 * 60 * 1000));
      const setInfo = manifest?.questionSets.find(s => s.id === source);
      warnings.push({ source, name: setInfo?.name || source, daysSince });
    }
  }

  return warnings.sort((a, b) => b.daysSince - a.daysSince);
}

// ── Streak Calendar ──────────────────────────────────

export function getStudyDays(): Map<string, number> {
  const progress = getProgress();
  const dayMap = new Map<string, number>(); // "YYYY-MM-DD" -> question count

  for (const a of progress.answers) {
    const d = new Date(a.timestamp);
    // Use local date so studying at 11pm doesn't show as next day
    const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    dayMap.set(date, (dayMap.get(date) || 0) + 1);
  }

  return dayMap;
}

// ── Export / Import ──────────────────────────────────────

export function exportProgress(): string {
  return JSON.stringify(getProgress(), null, 2);
}

export function importProgress(json: string): boolean {
  try {
    const data = JSON.parse(json) as UserProgress;
    if (!data.answers || !Array.isArray(data.answers)) return false;
    saveProgress(data);
    return true;
  } catch {
    return false;
  }
}

export function clearProgress(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}
