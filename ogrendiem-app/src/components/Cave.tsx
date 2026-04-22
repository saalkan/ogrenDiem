/**
 * Cave — one cluster's cave-chamber view.
 *
 * Topics in a cluster are positioned by pre-baked `cave_slot = { x, y }`
 * (x,y ∈ [0,1]) from a Python-side spring layout. Edges between same-cluster
 * topics are drawn as dim curves (the "cave tunnels"). Each topic is an
 * animal/crystal emoji node that behaves identically to tree nodes.
 */
import React, { useMemo } from 'react';
import { View, Text, StyleSheet, useWindowDimensions } from 'react-native';
import Svg, { Path, Rect, Defs, RadialGradient, Stop } from 'react-native-svg';
import { EmojiNode } from './EmojiNode';
import { topics as allTopics, graph, clusterById } from '@/data/bundled';
import { useTutor } from '@/store/tutor';
import type { TopicId } from '@/shared/types';

interface Props {
  clusterId: number;
  onOpenTopic: (tid: TopicId) => void;
}

export const Cave: React.FC<Props> = ({ clusterId, onOpenTopic }) => {
  const { width } = useWindowDimensions();
  const H = 520;
  const W = width - 24;
  const padX = 28;
  const padY = 36;

  const cluster = clusterById[clusterId];
  const color = cluster?.color ?? '#74b9ff';

  const clusterTopics = useMemo(
    () => allTopics.filter((t) => t.cluster_id === clusterId),
    [clusterId],
  );

  const idSet = useMemo(() => new Set(clusterTopics.map((t) => t.topic_id)), [clusterTopics]);

  // Map topic_id → pixel pos.
  const pos = useMemo(() => {
    const m: Record<string, { x: number; y: number }> = {};
    for (const t of clusterTopics) {
      m[t.topic_id] = {
        x: padX + t.cave_slot.x * (W - 2 * padX),
        y: padY + t.cave_slot.y * (H - 2 * padY),
      };
    }
    return m;
  }, [clusterTopics, W]);

  // In-cluster edges as faint tunnels.
  const tunnels = useMemo(
    () => graph.edges.filter((e) => idSet.has(e.from) && idSet.has(e.to)),
    [idSet],
  );

  const derived = useTutor((s) => s.derived);
  const recordPick = useTutor((s) => s.recordPick);

  return (
    <View style={{ width: W, height: H, alignSelf: 'center' }}>
      <Svg width={W} height={H}>
        <Defs>
          <RadialGradient id="caveBg" cx="50%" cy="50%" rx="70%" ry="70%">
            <Stop offset="0%" stopColor="#1a2230" stopOpacity="1" />
            <Stop offset="100%" stopColor="#0a0d12" stopOpacity="1" />
          </RadialGradient>
        </Defs>
        <Rect x={0} y={0} width={W} height={H} rx={16} fill="url(#caveBg)" />
        {tunnels.map((e, i) => {
          const a = pos[e.from];
          const b = pos[e.to];
          if (!a || !b) return null;
          const mx = (a.x + b.x) / 2;
          const my = (a.y + b.y) / 2 - 18;
          const d = `M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`;
          return (
            <Path
              key={i}
              d={d}
              stroke={color}
              strokeOpacity={0.22}
              strokeWidth={2}
              fill="none"
            />
          );
        })}
      </Svg>

      {clusterTopics.map((t) => {
        const p = pos[t.topic_id];
        if (!p) return null;
        const stash = derived.stash[t.topic_id] ?? 0;
        const picked = derived.picked[t.topic_id] ?? 0;
        return (
          <View
            key={t.topic_id}
            style={{
              position: 'absolute',
              left: p.x - 22,
              top: p.y - 22,
              width: 44,
              height: 44,
            }}
          >
            <EmojiNode
              topicId={t.topic_id}
              emoji={t.cave_emoji}
              stash={stash}
              picked={picked}
              size={34}
              onPick={() => recordPick(t.topic_id, t.cave_emoji, 'cave')}
              onOpen={() => onOpenTopic(t.topic_id)}
            />
          </View>
        );
      })}

      <Text style={[styles.caption, { color }]} numberOfLines={1}>
        {cluster?.title ?? `Cluster ${clusterId}`}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  caption: {
    position: 'absolute',
    bottom: 8,
    alignSelf: 'center',
    fontWeight: '700',
    letterSpacing: 0.5,
    maxWidth: '92%',
    textAlign: 'center',
  },
});
