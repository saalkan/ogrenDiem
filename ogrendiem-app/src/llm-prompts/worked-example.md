# User prompt — request N worked examples for one topic

Variables filled by the caller (`requestMoreQuestions` in RemoteEngine):

- `{{topic_id}}` — the target topic (e.g. `ch3_s1_t2`)
- `{{topic_title}}` — human-readable title
- `{{topic_description}}` — one-paragraph summary from `topics.json`
- `{{parent_chapter_num}}`, `{{parent_section}}` — context
- `{{prereq_titles}}` — comma-separated titles of direct DAG parents
- `{{role}}` — one of recognize | apply | vary | trap | integrate
- `{{tier}}` — easy | medium | hard
- `{{n}}` — how many items to return

---

Generate **{{n}}** worked-example items for the topic below. Every item must
have role=`{{role}}` and tier=`{{tier}}`.

**Topic:** `{{topic_id}}` — {{topic_title}} (Ch {{parent_chapter_num}}, {{parent_section}})

**Topic description:** {{topic_description}}

**Direct prerequisites the student already knows:** {{prereq_titles}}

## Output contract

Return a **JSON array** of length exactly {{n}}. Each element matches:

```ts
{
  "question_id": string,    // "{{topic_id}}__{{role}}__<short-slug>"
  "topic_id":    "{{topic_id}}",
  "role":        "{{role}}",
  "tier":        "{{tier}}",
  "prompt":      string,    // LaTeX in $...$ / $$...$$
  "solution_steps": string[],  // >= 2 strings, one teachable move each
  "answer":      string,    // short canonical form, in $...$
  "checks":      string[],  // plausible correct student tokens
  "origin":      "llm-generated"
}
```

No commentary, no Markdown fences, no trailing prose. The first character
of your reply is `[` and the last character is `]`.

## Guardrails specific to the role

- `recognize` → prompt asks "which of these is …" or "identify …"; one step.
- `apply` → straight computation with the rule just introduced.
- `vary` → same method, surface variation (different variable name,
  permuted givens, or a numerical re-skin).
- `trap` → the prompt lures the student into a named misconception; the
  first solution step must name that misconception.
- `integrate` → combines this topic with one explicitly-listed prereq.
