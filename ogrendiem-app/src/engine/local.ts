/**
 * LocalEngine — implements TutorEngine with bundled data + JS Bayes + AsyncStorage.
 *
 * Contract stability: the signatures match the future RemoteEngine exactly.
 * When the backend is ready, replacing this with a fetch-based implementation
 * is a single-line change in src/engine/index.ts.
 */
import {
  topics,
  topicById,
  parentsOf,
  clusters,
  graph,
  questionsByTopic,
  clusterById,
} from '@/data/bundled';
import { bktUpdate } from './bkt';
import { abilityMap, descendantsOf } from './propagate';
import { loadLog, appendEvent } from '@/store/persist';
import { MASTERY_THRESHOLD } from '@/shared/api';
import type { TutorEngine } from '@/shared/api';
import type {
  AnswerEvent,
  Cluster,
  DerivedState,
  Edge,
  LogEvent,
  MasteryDelta,
  PickEvent,
  Question,
  Role,
  Scope,
  StudentId,
  Topic,
  TopicId,
} from '@/shared/types';

// ---------- derived state replay ----------

function replay(events: LogEvent[]): DerivedState {
  const mastery: Record<TopicId, number> = {};
  const stash: Record<TopicId, number> = {};
  const picked: Record<TopicId, number> = {};
  for (const t of topics) {
    mastery[t.topic_id] = 0.05;
    stash[t.topic_id] = 0;
    picked[t.topic_id] = 0;
  }
  for (const e of events) {
    if (e.t === 'answer') {
      const prev = mastery[e.topic_id] ?? 0.05;
      mastery[e.topic_id] = bktUpdate(prev, e.correct);
      if (e.correct) stash[e.topic_id] = (stash[e.topic_id] ?? 0) + 1;
    } else if (e.t === 'pick') {
      if ((stash[e.topic_id] ?? 0) > 0) {
        stash[e.topic_id] = (stash[e.topic_id] ?? 0) - 1;
        picked[e.topic_id] = (picked[e.topic_id] ?? 0) + 1;
      }
    }
  }
  return { mastery, stash, picked };
}

// ---------- frontier ----------

/** A topic is "available" when every parent's ability ≥ MASTERY_THRESHOLD
 *  (and the topic itself is not yet mastered). */
function frontierWithinScope(
  derived: DerivedState,
  allowed: Set<TopicId>,
): TopicId[] {
  const ability = abilityMap(derived.mastery);
  const out: TopicId[] = [];
  for (const tid of allowed) {
    if ((derived.mastery[tid] ?? 0) >= MASTERY_THRESHOLD) continue;
    const parents = (parentsOf[tid] ?? []).filter((p) => allowed.has(p));
    const ok = parents.every((p) => (ability[p] ?? 0) >= MASTERY_THRESHOLD);
    if (ok) out.push(tid);
  }
  // Order: lower depth first, then lower difficulty.
  out.sort((a, b) => {
    const ta = topicById[a];
    const tb = topicById[b];
    if (ta.depth !== tb.depth) return ta.depth - tb.depth;
    return ta.difficulty_level - tb.difficulty_level;
  });
  return out;
}

function allowedTopicsForScope(scope: Scope): Set<TopicId> {
  if (scope.kind === 'chapter') {
    return new Set(
      topics.filter((t) => t.parent_chapter_num === scope.key).map((t) => t.topic_id),
    );
  }
  if (scope.kind === 'cluster') {
    const cid = Number(scope.key);
    const c = clusterById[cid];
    return new Set(c ? c.topic_ids : []);
  }
  // group: everything bundled (g1-3-8-9 is the whole set)
  return new Set(topics.map((t) => t.topic_id));
}

// ---------- the engine ----------

export class LocalEngine implements TutorEngine {
  async getTopics(): Promise<Topic[]> {
    return topics;
  }
  async getGraph(): Promise<{ nodes: TopicId[]; edges: Edge[] }> {
    return graph;
  }
  async getClusters(): Promise<Cluster[]> {
    return clusters;
  }

  async getDerived(studentId: StudentId): Promise<DerivedState> {
    const log = await loadLog(studentId);
    return replay(log);
  }

  async getFrontier(studentId: StudentId, scope: Scope): Promise<TopicId[]> {
    const d = await this.getDerived(studentId);
    return frontierWithinScope(d, allowedTopicsForScope(scope));
  }

  async getNextTopic(studentId: StudentId, scope: Scope): Promise<TopicId | null> {
    const f = await this.getFrontier(studentId, scope);
    return f[0] ?? null;
  }

  async getQuestions(topicId: TopicId, n?: number): Promise<Question[]> {
    const all = questionsByTopic[topicId] ?? [];
    return typeof n === 'number' ? all.slice(0, n) : all;
  }

  async requestMoreQuestions(
    _topicId: TopicId,
    _role: Role,
    _n: number,
  ): Promise<Question[]> {
    // LocalEngine has no LLM; return what's already bundled.
    return [];
  }

  async recordAnswer(
    e: Omit<AnswerEvent, 't' | 'ts'>,
  ): Promise<MasteryDelta & { stash: number }> {
    const before = (await this.getDerived(e.student_id)).mastery[e.topic_id] ?? 0.05;
    const full: AnswerEvent = { t: 'answer', ts: Date.now(), ...e };
    await appendEvent(e.student_id, full);
    const derivedAfter = await this.getDerived(e.student_id);
    const after = derivedAfter.mastery[e.topic_id];
    const descendants = descendantsOf(e.topic_id);
    const propagated: Record<TopicId, number> = {};
    for (const d of descendants) propagated[d] = derivedAfter.mastery[d];
    return {
      topic_id: e.topic_id,
      before,
      after,
      propagated,
      stash: derivedAfter.stash[e.topic_id] ?? 0,
    };
  }

  async recordPick(
    e: Omit<PickEvent, 't' | 'ts'>,
  ): Promise<{ stash: number; picked: number }> {
    const full: PickEvent = { t: 'pick', ts: Date.now(), ...e };
    await appendEvent(e.student_id, full);
    const d = await this.getDerived(e.student_id);
    return { stash: d.stash[e.topic_id] ?? 0, picked: d.picked[e.topic_id] ?? 0 };
  }

  async exportEventLog(studentId: StudentId): Promise<LogEvent[]> {
    return loadLog(studentId);
  }
  async importEventLog(_events: LogEvent[]): Promise<void> {
    // No-op in LocalEngine for demo; a future sync would append-dedupe into
    // AsyncStorage. Intentionally left unimplemented here.
  }
}
