/**
 * App-wide state: student id + cached derived state (re-fetched after writes).
 * UI imports selectors; writes go through engine methods and then refresh.
 */
import { create } from 'zustand';
import { engine } from '@/engine';
import { resetLog } from '@/store/persist';
import type { DerivedState, StudentId, TopicId } from '@/shared/types';

interface TutorStore {
  studentId: StudentId | null;
  derived: DerivedState;
  setStudentId: (id: StudentId) => void;
  refresh: () => Promise<void>;
  recordAnswer: (topicId: TopicId, questionId: string, correct: boolean, timeMs: number) => Promise<void>;
  recordPick: (topicId: TopicId, emoji: string, area: 'garden' | 'cave') => Promise<void>;
  /** Wipe the entire event log for the current student. All Bayes mastery,
   *  stash, and picked counters reset. The student_id itself is kept. */
  resetProgress: () => Promise<void>;
}

const emptyDerived: DerivedState = { mastery: {}, stash: {}, picked: {} };

export const useTutor = create<TutorStore>((set, get) => ({
  studentId: null,
  derived: emptyDerived,

  setStudentId: (id) => set({ studentId: id }),

  refresh: async () => {
    const sid = get().studentId;
    if (!sid) return;
    const derived = await engine.getDerived(sid);
    set({ derived });
  },

  recordAnswer: async (topicId, questionId, correct, timeMs) => {
    const sid = get().studentId;
    if (!sid) return;
    await engine.recordAnswer({
      student_id: sid,
      question_id: questionId,
      topic_id: topicId,
      correct,
      time_ms: timeMs,
    });
    await get().refresh();
  },

  recordPick: async (topicId, emoji, area) => {
    const sid = get().studentId;
    if (!sid) return;
    await engine.recordPick({ student_id: sid, topic_id: topicId, emoji, area });
    await get().refresh();
  },

  resetProgress: async () => {
    const sid = get().studentId;
    if (!sid) return;
    await resetLog(sid);
    await get().refresh();
  },
}));
