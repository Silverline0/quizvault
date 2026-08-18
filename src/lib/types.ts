export interface Question {
  id: number;
  source: string;
  question: string;
  options: Record<string, string>;
  correctAnswer: string;
  explanation: string;
  respondentStats?: Record<string, number> | null;
  imageUrl?: string | null;
  imageUrls?: string[];
  highYield?: boolean | null;
  /** Promotion Exam recalls carry their exam year and section. */
  year?: string;
  subspecialty?: string;
  /** Page in the source PDF, kept so a recall can be traced back. */
  pdfPage?: number;
  /**
   * How sure we are the attached figure belongs to THIS question. Absent means
   * high — the stem names its own picture, which was correct in every audited
   * case. "medium"/"low" mark figures bound by position alone; a sampled audit
   * put misplacement at ~13% overall, concentrated in these.
   */
  figureConfidence?: "medium" | "low";
  /**
   * Scan of the source PDF page, for questions whose figure is uncertain.
   * Lets the reader see which picture actually sat beside which stem.
   */
  pageScanUrl?: string;
  /** Question was transcribed from a screenshot rather than the text layer. */
  ocr?: boolean;
  /** What the question's figure ought to show, in one phrase. */
  figureFinding?: string;
  /**
   * Links to openly-licensed pages showing that finding, for questions whose
   * own figure is doubtful or missing. Links only — nothing is rehosted.
   */
  referenceLinks?: ReferenceLink[];
  /** Second opinion from an independent reviewer. */
  review?: QuestionReview;
  /** This question's key came from a reviewer, not from the exam recall. */
  reviewerAnswered?: boolean;
  reviewConfidence?: "high" | "medium" | "low";
  reviewConcern?: string;
  /** What the source compiler wrote where an answer should have been. */
  sourceHint?: string;
}

/**
 * An independent reviewer's second opinion. Never overwrites `correctAnswer`:
 * the exam's key is what the exam marks, and a reviewer is not the exam.
 */
export interface QuestionReview {
  answer: string;
  agrees: boolean;
  /**
   * The reviewer's answer is a letter this recall does not offer — evidence the
   * option holding the right answer was lost, so the question is unanswerable
   * as it stands.
   */
  answerMissing?: boolean;
  confidence: "high" | "medium" | "low";
  explanation: string;
  concern?: string;
}

export interface ReferenceLink {
  title: string;
  url: string;
  source?: string;
  shows?: string;
}

export interface QuestionSet {
  id: string;
  name: string;
  description: string;
  file: string;
  questionCount: number;
  category?: string;
  source?: QuestionSource;
}

export type QuestionSource = "BCSC" | "OphthoQ" | "Promotion";

/**
 * Badge class per source. Kept beside the union so adding a source without a
 * badge is a compile error rather than a silently mislabelled chip.
 */
export const SOURCE_BADGE: Record<QuestionSource, string> = {
  BCSC: "badge-bcsc",
  OphthoQ: "badge-ophthoq",
  Promotion: "badge-promotion",
};

export const badgeClass = (source?: string): string =>
  SOURCE_BADGE[source as QuestionSource] ?? "badge-neutral";

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
