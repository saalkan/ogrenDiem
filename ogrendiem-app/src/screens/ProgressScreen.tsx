/**
 * ProgressScreen — the group-level mastery + collection summary.
 *
 * Sections:
 *   1. Totals header: mastered / in-progress / not-started counts,
 *      total stash + picked, and a group-wide mastery average.
 *   2. Per-chapter rollup rows (one bar per chapter).
 *   3. Per-topic list grouped by chapter — each row shows title, mastery
 *      bar, and stash/picked emoji counters.
 *
 * This screen is read-only: tapping a row navigates to Learn for that topic.
 */
import React, { useMemo } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View, Pressable } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { topics as allTopics } from '@/data/bundled';
import { useTutor } from '@/store/tutor';
import { MASTERY_THRESHOLD } from '@/shared/api';
import type { RootTabParamList } from '@/navigation/RootTabs';
import type { TopicId } from '@/shared/types';

export const ProgressScreen: React.FC = () => {
  const derived = useTutor((s) => s.derived);
  const resetProgress = useTutor((s) => s.resetProgress);
  const nav = useNavigation<BottomTabNavigationProp<RootTabParamList, 'Progress'>>();

  const onResetPressed = () => {
    Alert.alert(
      'Reset all progress?',
      'This wipes every Bayes mastery value, every stash, and every picked emoji. The event log is cleared. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset everything',
          style: 'destructive',
          onPress: () => {
            resetProgress();
          },
        },
      ],
    );
  };

  const totals = useMemo(() => {
    let mastered = 0;
    let inProgress = 0;
    let notStarted = 0;
    let sumMastery = 0;
    let stash = 0;
    let picked = 0;
    for (const t of allTopics) {
      const m = derived.mastery[t.topic_id] ?? 0;
      sumMastery += m;
      if (m >= MASTERY_THRESHOLD) mastered++;
      else if (m > 0.01) inProgress++;
      else notStarted++;
      stash += derived.stash[t.topic_id] ?? 0;
      picked += derived.picked[t.topic_id] ?? 0;
    }
    return {
      mastered,
      inProgress,
      notStarted,
      avg: allTopics.length ? sumMastery / allTopics.length : 0,
      stash,
      picked,
    };
  }, [derived]);

  const byChapter = useMemo(() => {
    const groups: Record<string, typeof allTopics> = {};
    for (const t of allTopics) {
      (groups[t.parent_chapter_num] ??= []).push(t);
    }
    // Sort topics inside each chapter by depth then position.
    for (const ch of Object.keys(groups)) {
      groups[ch].sort(
        (a, b) => a.depth - b.depth || a.position_in_section - b.position_in_section,
      );
    }
    return groups;
  }, []);

  const chapterRollup = useMemo(() => {
    return Object.entries(byChapter).map(([ch, ts]) => {
      const sum = ts.reduce((s, t) => s + (derived.mastery[t.topic_id] ?? 0), 0);
      return { ch, avg: ts.length ? sum / ts.length : 0, count: ts.length };
    });
  }, [byChapter, derived.mastery]);

  const openTopic = (tid: TopicId) => nav.navigate('Learn', { topicId: tid });

  return (
    <ScrollView style={styles.root} contentContainerStyle={{ padding: 12 }}>
      {/* Totals card */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Group g1-3-8-9 · Overall</Text>
        <View style={styles.statRow}>
          <Stat label="Mastered" value={totals.mastered} color="#2ecc71" />
          <Stat label="Learning" value={totals.inProgress} color="#74b9ff" />
          <Stat label="Untouched" value={totals.notStarted} color="#8892a6" />
        </View>
        <Bar value={totals.avg} label={`Avg mastery · ${Math.round(totals.avg * 100)}%`} />
        <View style={styles.statRow}>
          <Stat label="🌼 Stash" value={totals.stash} color="#2ecc71" />
          <Stat label="✨ Picked" value={totals.picked} color="#e6edf3" />
        </View>
      </View>

      {/* Per-chapter rollup */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>By chapter</Text>
        {chapterRollup.map(({ ch, avg, count }) => (
          <View key={ch} style={styles.chRow}>
            <Text style={styles.chLabel}>Ch {ch} · {count} topics</Text>
            <Bar value={avg} label={`${Math.round(avg * 100)}%`} compact />
          </View>
        ))}
      </View>

      {/* Per-topic list grouped by chapter */}
      {Object.entries(byChapter).map(([ch, ts]) => (
        <View key={ch} style={styles.card}>
          <Text style={styles.cardTitle}>Chapter {ch}</Text>
          {ts.map((t) => {
            const m = derived.mastery[t.topic_id] ?? 0;
            const s = derived.stash[t.topic_id] ?? 0;
            const p = derived.picked[t.topic_id] ?? 0;
            return (
              <Pressable key={t.topic_id} style={styles.topicRow} onPress={() => openTopic(t.topic_id)}>
                <Text style={styles.topicEmoji}>{t.garden_emoji}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.topicTitle} numberOfLines={1}>{t.title}</Text>
                  <Bar value={m} label={`${Math.round(m * 100)}%`} compact />
                </View>
                <View style={styles.countCol}>
                  {s > 0 && <Text style={styles.stashCt}>+{s}</Text>}
                  {p > 0 && <Text style={styles.pickedCt}>{p}</Text>}
                </View>
              </Pressable>
            );
          })}
        </View>
      ))}

      {/* Danger zone — wipe every event for this student. */}
      <View style={[styles.card, styles.dangerCard]}>
        <Text style={styles.cardTitle}>Danger zone</Text>
        <Text style={styles.dangerHint}>
          Wipe all Bayes progress, stash, and picked emojis for this device.
          Useful for re-running the demo from scratch.
        </Text>
        <Pressable style={styles.dangerBtn} onPress={onResetPressed}>
          <Text style={styles.dangerBtnText}>Reset all progress</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
};

const Stat: React.FC<{ label: string; value: number; color: string }> = ({ label, value, color }) => (
  <View style={styles.stat}>
    <Text style={[styles.statValue, { color }]}>{value}</Text>
    <Text style={styles.statLabel}>{label}</Text>
  </View>
);

const Bar: React.FC<{ value: number; label: string; compact?: boolean }> = ({ value, label, compact }) => {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const color = value >= MASTERY_THRESHOLD ? '#2ecc71' : value >= 0.5 ? '#74b9ff' : value > 0.01 ? '#e67e22' : '#2b3442';
  return (
    <View style={[styles.barWrap, compact && { height: 14, marginTop: 4 }]}>
      <View style={[styles.barFill, { width: `${pct}%`, backgroundColor: color }]} />
      <Text style={[styles.barLabel, compact && { fontSize: 10 }]}>{label}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0e1116' },
  card: {
    backgroundColor: '#12161d',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1f2630',
    padding: 14,
    marginBottom: 12,
  },
  cardTitle: { color: '#e6edf3', fontWeight: '700', fontSize: 15, marginBottom: 10 },
  statRow: { flexDirection: 'row', gap: 12, marginBottom: 10 },
  stat: { flex: 1, alignItems: 'center', padding: 8, backgroundColor: '#1f2630', borderRadius: 8 },
  statValue: { fontSize: 22, fontWeight: '800' },
  statLabel: { color: '#8892a6', fontSize: 11, marginTop: 2 },
  barWrap: {
    height: 20,
    backgroundColor: '#1f2630',
    borderRadius: 10,
    overflow: 'hidden',
    justifyContent: 'center',
    marginTop: 6,
  },
  barFill: { position: 'absolute', left: 0, top: 0, bottom: 0 },
  barLabel: { color: '#e6edf3', fontSize: 11, fontWeight: '700', alignSelf: 'center', zIndex: 1 },
  chRow: { marginBottom: 8 },
  chLabel: { color: '#8892a6', fontSize: 12 },
  topicRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: '#1b2129',
  },
  topicEmoji: { fontSize: 22 },
  topicTitle: { color: '#e6edf3', fontSize: 13, fontWeight: '600' },
  countCol: { alignItems: 'flex-end', minWidth: 40 },
  stashCt: { color: '#2ecc71', fontWeight: '800', fontSize: 12 },
  pickedCt: { color: '#8892a6', fontSize: 11, fontWeight: '700' },
  dangerCard: { borderColor: '#5a2a2a' },
  dangerHint: { color: '#8892a6', fontSize: 12, marginBottom: 10, lineHeight: 17 },
  dangerBtn: {
    backgroundColor: '#3a1a1a',
    borderWidth: 1,
    borderColor: '#e74c3c',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  dangerBtnText: { color: '#e74c3c', fontWeight: '700', letterSpacing: 0.5 },
});
