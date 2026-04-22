/**
 * TutorEngine — the one swap point between local (bundled+JS Bayes) and
 * remote (HTTP API) implementations. UI screens depend only on this interface.
 *
 * When the Python FastAPI backend is built, RemoteEngine implements the same
 * signatures with fetch(). No UI changes required.
 */
import type {
  AnswerEvent,
  Cluster,
  DerivedState,
  Edge,
  LogEvent,
  MasteryDelta,
  Mode,
  PickEvent,
  Question,
  Role,
  Scope,
  StudentId,
  Topic,
  TopicId,
} from './types';

export interface TutorEngine {
  // --- static content ---
  getTopics(): Promise<Topic[]>;
  getGraph(): Promise<{ nodes: TopicId[]; edges: Edge[] }>;
  getClusters(): Promise<Cluster[]>;

  // --- per-student derived state ---
  getDerived(studentId: StudentId): Promise<DerivedState>;

  // --- frontier & recommendations ---
  getFrontier(studentId: StudentId, scope: Scope): Promise<TopicId[]>;
  getNextTopic(studentId: StudentId, scope: Scope): Promise<TopicId | null>;

  // --- questions ---
  getQuestions(topicId: TopicId, n?: number): Promise<Question[]>;
  /** LocalEngine: returns cached-only (never generates).
   *  RemoteEngine: calls backend which may call an LLM. */
  requestMoreQuestions(topicId: TopicId, role: Role, n: number): Promise<Question[]>;

  // --- writes ---
  recordAnswer(e: Omit<AnswerEvent, 't' | 'ts'>): Promise<MasteryDelta & { stash: number }>;
  recordPick(e: Omit<PickEvent, 't' | 'ts'>): Promise<{ stash: number; picked: number }>;

  // --- event-log maintenance (for future sync) ---
  exportEventLog(studentId: StudentId): Promise<LogEvent[]>;
  importEventLog(events: LogEvent[]): Promise<void>;
}

export const MASTERY_THRESHOLD = 0.8;
