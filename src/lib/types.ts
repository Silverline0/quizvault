export interface Question {
  id: number;
  source: string;
  question: string;
  options: Record<string, string>;
  correctAnswer: string;
  explanation: string;
  respondentStats?: Record<string, number>;
  imageUrl?: string | null;
}

export interface QuestionSet {
  id: string;
  name: string;
  description: string;
  file: string;
  questionCount: number;
}

export interface Manifest {
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
  lastPosition: Record<string, number>; // setId -> question index
}

export type QuizMode = "sequential" | "random" | "mistakes";
