/**
 * LearnScreen — the question loop for the currently active topic.
 *
 * Topic selection priority:
 *   1. route.params.topicId (when navigated from Garden/Cave)
 *   2. engine.getNextTopic(scope='group/g1-3-8-9') → frontier-best topic
 *   3. first topic in scope (cold start)
 *
 * For a given topic we show all bundled questions sequentially (recognize →
 * apply → vary/trap/integrate), letting the student self-grade each one.
 * A correct answer credits a stash emoji on the topic's Garden + Cave node.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, View, Pressable } from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { QuestionCard } from '@/components/QuestionCard';
import { topicById, questionsByTopic } from '@/data/bundled';
import { engine } from '@/engine';
import { useTutor } from '@/store/tutor';
import type { RootTabParamList } from '@/navigation/RootTabs';
import type { TopicId } from '@/shared/types';

const SCOPE = { kind: 'group' as const, key: 'g1-3-8-9' };

export const LearnScreen: React.FC = () => {
  const route = useRoute<RouteProp<RootTabParamList, 'Learn'>>();
  const nav = useNavigation();
  const studentId = useTutor((s) => s.studentId);
  const mastery = useTutor((s) => s.derived.mastery);

  const [topicId, setTopicId] = useState<TopicId | null>(
    (route.params && route.params.topicId) || null,
  );

  // Load a recommended topic if none was passed in.
  useEffect(() => {
    if (topicId || !studentId) return;
    let cancelled = false;
    (async () => {
      const next = await engine.getNextTopic(studentId, SCOPE);
      if (!cancelled) setTopicId(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [studentId, topicId]);

  // If a new topic came in via route params, pick it up.
  useEffect(() => {
    const pid = route.params?.topicId;
    if (pid && pid !== topicId) setTopicId(pid);
  }, [route.params?.topicId]);

  const topic = topicId ? topicById[topicId] : null;
  const qs = useMemo(() => (topicId ? questionsByTopic[topicId] ?? [] : []), [topicId]);
  const m = topicId ? mastery[topicId] ?? 0 : 0;

  const pickNext = async () => {
    if (!studentId) return;
    const next = await engine.getNextTopic(studentId, SCOPE);
    setTopicId(next);
  };

  if (!topic) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyEmoji}>🌱</Text>
        <Text style={styles.emptyTitle}>Nothing queued yet</Text>
        <Text style={styles.emptyText}>
          Head to Garden or Cave and tap an emoji to start a topic.
        </Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={{ padding: 12 }}>
      <View style={styles.header}>
        <Text style={styles.topicEmoji}>
          {topic.garden_emoji} · {topic.cave_emoji}
        </Text>
        <Text style={styles.topicTitle}>{topic.title}</Text>
        <Text style={styles.topicMeta}>
          Ch {topic.parent_chapter_num} · depth {topic.depth} · {topic.difficulty_tier}
        </Text>
        <MasteryBar value={m} />
      </View>

      {qs.length === 0 ? (
        <Text style={styles.noQs}>
          No bundled questions for this topic yet. (RemoteEngine will request
          more from the backend here.)
        </Text>
      ) : (
        qs.map((q) => <QuestionCard key={q.question_id} question={q} />)
      )}

      <Pressable style={styles.nextBtn} onPress={pickNext}>
        <Text style={styles.nextBtnText}>Next recommended topic →</Text>
      </Pressable>
    </ScrollView>
  );
};

const MasteryBar: React.FC<{ value: number }> = ({ value }) => {
  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? '#2ecc71' : value >= 0.5 ? '#74b9ff' : '#e67e22';
  return (
    <View style={styles.barWrap}>
      <View style={[styles.barFill, { width: `${pct}%`, backgroundColor: color }]} />
      <Text style={styles.barLabel}>Mastery · {pct}%</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0e1116' },
  header: {
    backgroundColor: '#12161d',
    borderRadius: 10,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1f2630',
  },
  topicEmoji: { fontSize: 26 },
  topicTitle: { color: '#e6edf3', fontSize: 18, fontWeight: '700', marginTop: 4 },
  topicMeta: { color: '#8892a6', fontSize: 12, marginTop: 2 },
  barWrap: {
    marginTop: 10,
    height: 18,
    backgroundColor: '#1f2630',
    borderRadius: 9,
    overflow: 'hidden',
    justifyContent: 'center',
  },
  barFill: { position: 'absolute', left: 0, top: 0, bottom: 0 },
  barLabel: {
    color: '#e6edf3',
    fontSize: 11,
    fontWeight: '700',
    alignSelf: 'center',
    zIndex: 1,
  },
  noQs: { color: '#8892a6', textAlign: 'center', padding: 16 },
  nextBtn: {
    backgroundColor: '#1f2630',
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginVertical: 10,
    borderWidth: 1,
    borderColor: '#2b3442',
  },
  nextBtnText: { color: '#74b9ff', fontWeight: '700' },
  empty: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, backgroundColor: '#0e1116' },
  emptyEmoji: { fontSize: 52, marginBottom: 10 },
  emptyTitle: { color: '#e6edf3', fontSize: 18, fontWeight: '700' },
  emptyText: { color: '#8892a6', textAlign: 'center', marginTop: 6 },
});
