/**
 * GardenScreen — chapter picker + a Tree per selected chapter.
 *
 * Horizontal chapter chips at the top let the student flip between chapters
 * in scope (1, 3, 8, 9). Tapping an emoji long-press on the tree navigates
 * to Learn with that topic pre-selected.
 */
import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, View, Pressable } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { Tree } from '@/components/Tree';
import { chaptersInScope } from '@/data/bundled';
import type { RootTabParamList } from '@/navigation/RootTabs';
import type { TopicId } from '@/shared/types';

const CHAPTER_LABELS: Record<string, string> = {
  '1': 'Ch 1 · Functions',
  '3': 'Ch 3 · Polynomial',
  '8': 'Ch 8 · Trig Ext',
  '9': 'Ch 9 · Conics',
};

export const GardenScreen: React.FC = () => {
  const chapters = chaptersInScope();
  const [ch, setCh] = useState<string>(chapters[0] ?? '1');
  const nav = useNavigation<BottomTabNavigationProp<RootTabParamList, 'Garden'>>();

  const openTopic = (tid: TopicId) => nav.navigate('Learn', { topicId: tid });

  return (
    <View style={styles.root}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipRow}
      >
        {chapters.map((c) => {
          const active = c === ch;
          return (
            <Pressable
              key={c}
              onPress={() => setCh(c)}
              style={[styles.chip, active && styles.chipActive]}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>
                {CHAPTER_LABELS[c] ?? `Ch ${c}`}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <Text style={styles.hint}>
        Tap a ripe emoji to collect 🌼 · long-press to open that topic.
      </Text>

      <ScrollView contentContainerStyle={{ paddingBottom: 16 }}>
        <Tree chapterNum={ch} onOpenTopic={openTopic} />
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0e1116' },
  chipRow: { padding: 10, gap: 8 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 16,
    backgroundColor: '#1f2630',
    borderWidth: 1,
    borderColor: '#1f2630',
  },
  chipActive: {
    backgroundColor: '#2b3442',
    borderColor: '#74b9ff',
  },
  chipText: { color: '#8892a6', fontWeight: '600' },
  chipTextActive: { color: '#e6edf3' },
  hint: {
    color: '#8892a6',
    fontSize: 12,
    paddingHorizontal: 12,
    paddingBottom: 6,
  },
});
