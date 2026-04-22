/**
 * CaveScreen — cluster picker + a Cave per selected cluster.
 *
 * Horizontal cluster chips (color-coded) let the student flip between the
 * five g1-3-8-9 clusters. Each cave is a force-directed layout of that
 * cluster's topics, with in-cluster prereq edges as faint tunnels.
 */
import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, View, Pressable } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { Cave } from '@/components/Cave';
import { clusters } from '@/data/bundled';
import type { RootTabParamList } from '@/navigation/RootTabs';
import type { TopicId } from '@/shared/types';

export const CaveScreen: React.FC = () => {
  const [cid, setCid] = useState<number>(clusters[0]?.cluster_id ?? 0);
  const nav = useNavigation<BottomTabNavigationProp<RootTabParamList, 'Cave'>>();

  const openTopic = (tid: TopicId) => nav.navigate('Learn', { topicId: tid });

  return (
    <View style={styles.root}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipRow}
      >
        {clusters.map((c) => {
          const active = c.cluster_id === cid;
          return (
            <Pressable
              key={c.cluster_id}
              onPress={() => setCid(c.cluster_id)}
              style={[
                styles.chip,
                { borderColor: active ? c.color : '#1f2630' },
                active && { backgroundColor: '#2b3442' },
              ]}
            >
              <Text
                numberOfLines={1}
                style={[
                  styles.chipText,
                  { color: active ? '#e6edf3' : '#8892a6' },
                ]}
              >
                <Text style={{ color: c.color }}>● </Text>
                {c.title.length > 28 ? c.title.slice(0, 27) + '…' : c.title}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <Text style={styles.hint}>
        Tap a glowing creature to collect · long-press to open the topic.
      </Text>

      <ScrollView contentContainerStyle={{ paddingBottom: 16 }}>
        <Cave clusterId={cid} onOpenTopic={openTopic} />
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
    maxWidth: 240,
  },
  chipText: { fontWeight: '600' },
  hint: {
    color: '#8892a6',
    fontSize: 12,
    paddingHorizontal: 12,
    paddingBottom: 6,
  },
});
