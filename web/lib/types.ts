// Mirrors the backend learning_session blob (services/learning_service.new_learning_session).
// Kept loose where the backend stores open dicts; only the fields the UI reads are typed.

export type NodeStatus =
  | "available"
  | "in_progress"
  | "mastered"
  | "needs_review"
  | "blocked";

export interface SkillNode {
  id: string;
  label: string;
  description: string;
  level?: "foundational" | "intermediate" | "advanced" | null;
}

export interface SkillEdge {
  source: string;
  target: string;
  relation?: string | null;
}

export interface SkillGraph {
  summary?: string;
  nodes: SkillNode[];
  edges: SkillEdge[];
}

export interface NodeState {
  status: NodeStatus;
  best_score: number;
  attempts: number;
  weaknesses: string[];
  last_feedback: GradeResult | null;
  // Deterministic-lock signal set by a sub-40 grade (mirrors services/mastery.py). Optional for
  // backward-compat with sessions persisted before the field existed.
  remediation_pending?: boolean;
}

export interface GradingArtifact {
  format?: string;
  unit_tests?: string[];
  rubric?: { criterion?: string; weight?: number }[];
  instructions?: string;
}

export interface Exercise {
  format?: "coding_challenge" | "case_study" | null;
  statement?: string | null;
  grading_artifact?: GradingArtifact | null;
}

export interface Lesson {
  content?: string | null;
  exercise?: Exercise;
}

export interface GradeResult {
  score?: number;
  passed?: number;
  total?: number;
  failures?: string[];
  stdout?: string;
  timed_out?: boolean;
  per_criterion?: string[];
  feedback?: string;
}

export interface LearningSession {
  skill_graph: SkillGraph;
  summary?: string | null;
  review_passed?: boolean | null;
  review_notes?: string | null;
  format_type?: string;
  node_state: Record<string, NodeState>;
  lessons: Record<string, Lesson>;
  selected_node?: string | null;
}

export interface SessionMeta {
  session_id: string;
  title: string;
  updated_at: string | null;
}

export interface StartSessionResponse {
  route: string;
  session_id?: string | null;
  learning_session?: LearningSession | null;
  final_content?: string | null;
  exercise?: Exercise | null;
}

export interface SessionResponse {
  session_id: string;
  learning_session: LearningSession;
}

export interface IngestResponse {
  filename: string;
  chunks: number;
}
