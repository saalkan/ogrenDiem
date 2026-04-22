/**
 * Shared domain types. Mirrored later on the backend (pydantic).
 * Changing a field here means changing the server's response shape too.
 */

export type TopicId = string;            // e.g. "ch1_s1_t1"
export type QuestionId = string;         // e.g. "ch1_s1_t1__recognize__1"
export type StudentId = string;          // uuid
export type Role = 'recognize' | 'apply' | 'vary' | 'trap' | 'integrate';
export type Tier = 'easy' | 'medium' | 'hard';
export type Mode = 'chapter' | 'group' | 'cluster';
export type Scope = { kind: Mode; key: string };  // key: "1", "g1-3-8-9", or "0"

export interface Topic {
  topic_id: TopicId;
  title: string;
  parent_chapter_num: string;
  parent_section_num: string;
  parent_section: string;
  position_in_section: number;
  difficulty_level: number;
  difficulty_tier: Tier;
  depth: number;
  description: string;
  garden_emoji: string;
  cave_emoji: string;
  garden_slot: { branch: number; u: number };
  cave_slot: { cluster: number; x: number; y: number };
  cluster_id: number;
}

export interface Edge {
  from: TopicId;
  to: TopicId;
  source: string;
  strength: number;
}

export interface Cluster {
  cluster_id: number;
  title: string;
  color: string;
  topic_ids: TopicId[];
}

export interface Question {
  question_id: QuestionId;
  topic_id: TopicId;
  role: Role;
  tier: Tier;
  prompt: string;                 // may contain LaTeX inside $...$ / $$...$$
  solution_steps: string[];
  answer: string;
  checks: string[];
  origin: 'bundled' | 'llm-generated';
  created_at?: string;
}

// ----- events (append-only log; replay source of truth) -----

export interface AnswerEvent {
  t: 'answer';
  ts: number;                     // unix ms
  student_id: StudentId;
  question_id: QuestionId;
  topic_id: TopicId;
  correct: boolean;
  time_ms: number;
}

export interface PickEvent {
  t: 'pick';
  ts: number;
  student_id: StudentId;
  topic_id: TopicId;
  emoji: string;
  area: 'garden' | 'cave';
}

export type LogEvent = AnswerEvent | PickEvent;

// ----- derived state (rebuildable from the log) -----

export interface DerivedState {
  mastery: Record<TopicId, number>;    // Bayes posterior ∈ [0,1]
  stash: Record<TopicId, number>;      // unpicked emojis available
  picked: Record<TopicId, number>;     // lifetime picks
}

export interface MasteryDelta {
  topic_id: TopicId;
  before: number;
  after: number;
  propagated: Record<TopicId, number>; // downstream topics touched
}
