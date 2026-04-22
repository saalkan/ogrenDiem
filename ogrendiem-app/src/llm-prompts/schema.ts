/**
 * Zod validator for LLM-emitted Question batches.
 *
 * RemoteEngine calls:
 *
 *   const raw = await llmClient.completeJson({ system, user });
 *   const parsed = questionBatchSchema.parse(raw);   // throws on bad shape
 *   await cache.upsertQuestions(parsed);
 *
 * If the caller wants to be forgiving, use `.safeParse()` and drop
 * individual items that fail. The server, not the client, talks to the LLM —
 * this file lives under `src/` only so the shape stays co-located with
 * `shared/types.ts` and stays in lockstep with `worked-example.md`.
 */
import { z } from 'zod';

export const roleSchema = z.enum(['recognize', 'apply', 'vary', 'trap', 'integrate']);
export const tierSchema = z.enum(['easy', 'medium', 'hard']);

export const questionSchema = z.object({
  question_id: z.string().min(3),
  topic_id: z.string().min(3),
  role: roleSchema,
  tier: tierSchema,
  prompt: z.string().min(1),
  solution_steps: z.array(z.string().min(1)).min(2),
  answer: z.string().min(1),
  checks: z.array(z.string()).default([]),
  origin: z.literal('llm-generated'),
  created_at: z.string().optional(),
});

export const questionBatchSchema = z.array(questionSchema).min(1).max(8);

export type LlmQuestion = z.infer<typeof questionSchema>;
export type LlmQuestionBatch = z.infer<typeof questionBatchSchema>;

/**
 * Fill the user-prompt template with caller-provided variables.
 * Kept dumb on purpose — no escaping, no sandboxing. The caller controls all
 * inputs (they come from our own topics.json / DAG).
 */
export function fillTemplate(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_, k) => {
    const v = vars[k];
    return v === undefined ? '' : String(v);
  });
}
