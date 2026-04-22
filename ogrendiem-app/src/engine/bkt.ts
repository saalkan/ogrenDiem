/**
 * Bayesian Knowledge Tracing (BKT) — per-topic update on a single observation.
 * Classic 4-parameter model:
 *   p_learn   probability a student learns the skill on this attempt
 *   p_slip    probability they answer wrong even though they know it
 *   p_guess   probability they answer correctly without knowing it
 *   p_forget  probability they forget between attempts (usually 0)
 *
 * Given prior P(known) and observation correct ∈ {true,false}, compute posterior.
 * Same formulas the backend will apply via pgmpy with identical parameters.
 */

export interface BKTParams {
  pLearn: number;
  pSlip: number;
  pGuess: number;
  pForget: number;
}

export const DEFAULT_BKT: BKTParams = {
  pLearn: 0.25,
  pSlip: 0.1,
  pGuess: 0.2,
  pForget: 0.0,
};

/** Posterior P(known | observation) then apply learning transition. */
export function bktUpdate(
  prior: number,
  correct: boolean,
  params: BKTParams = DEFAULT_BKT,
): number {
  const { pLearn, pSlip, pGuess, pForget } = params;

  // P(obs | known)
  const pObsGivenKnown = correct ? 1 - pSlip : pSlip;
  // P(obs | ¬known)
  const pObsGivenNotKnown = correct ? pGuess : 1 - pGuess;

  const numer = prior * pObsGivenKnown;
  const denom = numer + (1 - prior) * pObsGivenNotKnown;
  const posterior = denom > 0 ? numer / denom : prior;

  // Transition: ¬known → known with pLearn, known → ¬known with pForget
  const nextKnown = posterior * (1 - pForget) + (1 - posterior) * pLearn;
  return clamp(nextKnown);
}

export function clamp(p: number, lo = 0.001, hi = 0.999): number {
  return Math.max(lo, Math.min(hi, p));
}
