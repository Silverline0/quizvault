export interface Question {
  id: number;
  source: string;
  question: string;
  options: Record<string, string>;
  correctAnswer: string;
  explanation: string;
  respondentStats?: Record<string, number> | null;
  imageUrl?: string | null;
  highYield?: boolean | null;
}

export interface QuestionSet {
  id: string;
  name: string;
  description: string;
  file: string;
  questionCount: number;
  category?: string;
  source?: "BCSC" | "OphthoQ";
}

export interface Category {
  id: string;
  name: string;
  icon: string;
}

export interface Manifest {
  categories?: Category[];
  questionSets: QuestionSet[];
}

export interface AnswerRecord {
  questionId: number;
  source: string;
  selectedAnswer: string;
  correct: boolean;
  timestamp: number;
  confidence?: number;
}

export interface UserProgress {
  answers: AnswerRecord[];
  bookmarks: { questionId: number; source: string }[];
  lastPosition: Record<string, number>;
}

export type QuizMode = "sequential" | "random" | "mistakes";
