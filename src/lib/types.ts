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
  timeSpent?: number; // seconds spent on this question
}

export interface SpacedRepItem {
  questionId: number;
  source: string;
  interval: number;    // days until next review (1, 3, 7, 14, 30)
  nextReview: number;  // timestamp of next review
  streak: number;      // consecutive correct answers
}

export interface StudySession {
  startTime: number;
  endTime?: number;
  source: string;
  questionsAnswered: number;
  correctCount: number;
}

export interface UserProgress {
  answers: AnswerRecord[];
  bookmarks: { questionId: number; source: string }[];
  flagged: { questionId: number; source: string; note?: string }[];
  lastPosition: Record<string, number>;
  lastActiveSet?: string;        // for "Continue where you left off"
  lastActiveMode?: string;
  spacedRep: SpacedRepItem[];
  studyTime: {
    totalSeconds: number;
    sessions: StudySession[];
  };
}

export type QuizMode = "sequential" | "random" | "mistakes" | "spaced" | "exam";
