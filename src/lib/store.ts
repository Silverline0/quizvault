import { AnswerRecord, UserProgress } from "./types";
import { triggerAutoSync } from "./cloud-sync";

const STORAGE_KEY = "quizzes_progress";

const defaultProgress: UserProgress = {
  answers: [],
  bookmarks: [],
  lastPosition: {},
};

export function getProgress(): UserProgress {
  if (typeof window === "undefined") return defaultProgress;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultProgress;
    return JSON.parse(raw) as UserProgress;
  } catch {
    return defaultProgress;
  }
}

export function saveProgress(progress: UserProgress): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
  // Auto-sync to cloud (debounced, non-blocking)
  triggerAutoSync(progress);
}

export function recordAnswer(record: AnswerRecord): void {
  const progress = getProgress();
  progress.answers.push(record);
  saveProgress(progress);
}

export function getAnswersForSet(source: string): AnswerRecord[] {
  return getProgress().answers.filter((a) => a.source === source);
}

export function getMistakes(source: string): AnswerRecord[] {
  const answers = getAnswersForSet(source);
  // Get the latest answer per question, keep only wrong ones
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

export function getLastPosition(setId: string): number {
  return getProgress().lastPosition[setId] || 0;
}

export function saveLastPosition(setId: string, index: number): void {
  const progress = getProgress();
  progress.lastPosition[setId] = index;
  saveProgress(progress);
}

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

export function getStats(source?: string) {
  const answers = source ? getAnswersForSet(source) : getProgress().answers;
  const total = answers.length;
  const correct = answers.filter((a) => a.correct).length;
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;

  // Unique questions answered
  const uniqueQuestions = new Set(
    answers.map((a) => `${a.source}:${a.questionId}`)
  ).size;

  // Current streak
  let streak = 0;
  for (let i = answers.length - 1; i >= 0; i--) {
    if (answers[i].correct) streak++;
    else break;
  }

  return { total, correct, accuracy, uniqueQuestions, streak };
}

// Export progress as downloadable JSON
export function exportProgress(): string {
  return JSON.stringify(getProgress(), null, 2);
}

// Import progress from JSON string
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
