import { Question, QuizMode } from "./types";
import { getMistakes, getLastPosition } from "./store";

// Fisher-Yates shuffle
function shuffle<T>(array: T[]): T[] {
  const arr = [...array];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

export function buildQuizQueue(
  questions: Question[],
  mode: QuizMode,
  source: string
): Question[] {
  switch (mode) {
    case "sequential":
      return [...questions];

    case "random":
      return shuffle(questions);

    case "mistakes": {
      const mistakes = getMistakes(source);
      const mistakeIds = new Set(mistakes.map((m) => m.questionId));
      const filtered = questions.filter((q) => mistakeIds.has(q.id));
      return shuffle(filtered);
    }

    default:
      return [...questions];
  }
}

export function getStartIndex(
  mode: QuizMode,
  source: string
): number {
  if (mode === "sequential") {
    return getLastPosition(source);
  }
  return 0;
}

export async function loadQuestionSet(file: string): Promise<Question[]> {
  const res = await fetch(`/data/${file}`);
  if (!res.ok) throw new Error(`Failed to load question set: ${file}`);
  return res.json();
}

export async function loadManifest() {
  const res = await fetch("/data/manifest.json");
  if (!res.ok) throw new Error("Failed to load manifest");
  return res.json();
}
