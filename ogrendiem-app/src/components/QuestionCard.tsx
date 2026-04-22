/**
 * QuestionCard — renders a single worked example.
 *
 * Flow:
 *   1. Prompt shown immediately.
 *   2. "Reveal steps" shows solution_steps (one at a time or all at once).
 *   3. "Reveal answer" shows the answer.
 *   4. Student self-reports "I got it" / "Not yet" → recordAnswer.
 *
 * A self-report UI is intentional for a demo tutor: auto-grading free-form
 * math answers is out of scope. Future role: optional "check" expressions
 * matched against `question.checks` tokens.
 */
import React, { useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { MathView } from './MathView';
import type { Question } from '@/shared/types';
import { useTutor } from '@/store/tutor';

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

interface Props {
  question: Question;
  onResolved?: (correct: boolean) => void;
}

export const QuestionCard: React.FC<Props> = ({ question, onResolved }) => {
  const [revealedSteps, setRevealedSteps] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [resolved, setResolved] = useState<null | boolean>(null);
  const startedAt = useRef(Date.now());

  const recordAnswer = useTutor((s) => s.recordAnswer);

  const promptHtml = useMemo(() => `<p>${escapeHtml(question.prompt)}</p>`, [question.prompt]);
  const stepsHtml = useMemo(() => {
    if (revealedSteps === 0) return null;
    const items = question.solution_steps
      .slice(0, revealedSteps)
      .map((s) => `<li>${escapeHtml(s)}</li>`)
      .join('');
    return `<p><strong>Steps</strong></p><ol>${items}</ol>`;
  }, [revealedSteps, question.solution_steps]);
  const answerHtml = useMemo(
    () =>
      showAnswer
        ? `<div class="answer"><strong>Answer:</strong> ${escapeHtml(question.answer)}</div>`
        : null,
    [showAnswer, question.answer],
  );

  const totalSteps = question.solution_steps.length;

  async function resolve(correct: boolean) {
    if (resolved !== null) return;
    setResolved(correct);
    const elapsed = Date.now() - startedAt.current;
    await recordAnswer(question.topic_id, question.question_id, correct, elapsed);
    onResolved?.(correct);
  }

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.role}>{question.role.toUpperCase()}</Text>
        <Text style={styles.tier}>{question.tier}</Text>
      </View>

      <MathView content={promptHtml} />

      {stepsHtml && <MathView content={stepsHtml} />}
      {answerHtml && <MathView content={answerHtml} />}

      <View style={styles.actions}>
        {revealedSteps < totalSteps && (
          <Pressable style={styles.btn} onPress={() => setRevealedSteps((n) => n + 1)}>
            <Text style={styles.btnText}>Show next step ({revealedSteps}/{totalSteps})</Text>
          </Pressable>
        )}
        {revealedSteps === totalSteps && !showAnswer && (
          <Pressable style={styles.btn} onPress={() => setShowAnswer(true)}>
            <Text style={styles.btnText}>Reveal answer</Text>
          </Pressable>
        )}
        {showAnswer && resolved === null && (
          <View style={styles.row}>
            <Pressable style={[styles.btn, styles.btnGood]} onPress={() => resolve(true)}>
              <Text style={styles.btnText}>I got it ✓</Text>
            </Pressable>
            <Pressable style={[styles.btn, styles.btnBad]} onPress={() => resolve(false)}>
              <Text style={styles.btnText}>Not yet</Text>
            </Pressable>
          </View>
        )}
        {resolved !== null && (
          <Text style={[styles.resolved, resolved ? styles.good : styles.bad]}>
            {resolved ? 'Nice — collected!' : 'Noted — we will revisit.'}
          </Text>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#12161d',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1f2630',
    padding: 14,
    marginBottom: 16,
  },
  header: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  role: { color: '#74b9ff', fontWeight: '700', letterSpacing: 1 },
  tier: { color: '#8892a6', fontStyle: 'italic' },
  actions: { marginTop: 10, gap: 8 },
  row: { flexDirection: 'row', gap: 10 },
  btn: {
    backgroundColor: '#1f2630',
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 8,
    alignItems: 'center',
    flex: 1,
  },
  btnGood: { backgroundColor: '#2ecc7133', borderWidth: 1, borderColor: '#2ecc71' },
  btnBad: { backgroundColor: '#e74c3c22', borderWidth: 1, borderColor: '#e74c3c' },
  btnText: { color: '#e6edf3', fontWeight: '600' },
  resolved: { textAlign: 'center', marginTop: 6, fontWeight: '700' },
  good: { color: '#2ecc71' },
  bad: { color: '#e74c3c' },
});
