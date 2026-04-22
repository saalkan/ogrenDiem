/**
 * Noisy-AND propagation across the prerequisite DAG.
 *
 * A student's "effective ability" on topic T is modeled as:
 *   ability(T) = localMastery(T) * Π over parents p of ability(p)
 *
 * This is the noisy-AND: to really have T, you need T *and* all prerequisites.
 * When a student improves on topic T (via BKT), downstream descendants see a
 * proportional lift in their ability floor because a parent just got stronger.
 *
 * This mirrors what pgm/cpts.py (Python) does with pgmpy noisy-AND CPTs.
 */
import { childrenOf, parentsOf, topicById } from '@/data/bundled';
import type { TopicId } from '@/shared/types';

/** Compute ability(T) = local * ∏ ability(parents).
 *  Cached within a single invocation via memo. */
export function abilityMap(
  localMastery: Record<TopicId, number>,
): Record<TopicId, number> {
  const memo: Record<TopicId, number> = {};

  function ab(t: TopicId): number {
    if (memo[t] !== undefined) return memo[t];
    const local = localMastery[t] ?? 0.05;
    const parents = parentsOf[t] ?? [];
    if (parents.length === 0) {
      memo[t] = local;
      return local;
    }
    let prod = 1;
    for (const p of parents) prod *= ab(p);
    memo[t] = local * prod;
    return memo[t];
  }

  for (const tid of Object.keys(topicById)) ab(tid);
  return memo;
}

/** Given a mastery change at `root`, return all downstream descendants
 *  whose ability would be affected. Used to report propagation deltas. */
export function descendantsOf(root: TopicId): TopicId[] {
  const out: TopicId[] = [];
  const seen = new Set<TopicId>();
  const stack = [...(childrenOf[root] ?? [])];
  while (stack.length) {
    const n = stack.pop()!;
    if (seen.has(n)) continue;
    seen.add(n);
    out.push(n);
    for (const c of childrenOf[n] ?? []) stack.push(c);
  }
  return out;
}
