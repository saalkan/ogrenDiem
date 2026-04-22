/**
 * Tree — one chapter's tree-in-nature view.
 *
 * The trunk and branches are organic cubic Bezier curves drawn in SVG.
 * Emoji positions come from pre-baked `garden_slot = { branch, u }`:
 *   - `branch` picks which branch path
 *   - `u ∈ [0,1]` is the parameter along that branch path
 *
 * The React Native SVG Path element supports `getPointAtLength`-style math
 * indirectly — we sample the Bezier curve analytically in JS to place nodes.
 */
import React, { useMemo } from 'react';
import { View, Text, StyleSheet, useWindowDimensions } from 'react-native';
import Svg, { Path, G } from 'react-native-svg';
import { EmojiNode } from './EmojiNode';
import { topics as allTopics } from '@/data/bundled';
import { useTutor } from '@/store/tutor';
import type { TopicId } from '@/shared/types';

/** Cubic Bezier interpolation. */
function bezier(
  p0: [number, number], p1: [number, number], p2: [number, number], p3: [number, number], t: number,
): [number, number] {
  const u = 1 - t;
  const x = u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0];
  const y = u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1];
  return [x, y];
}

interface Branch {
  p0: [number, number];
  p1: [number, number];
  p2: [number, number];
  p3: [number, number];
  d: string;
}

function makeBranches(n: number, W: number, H: number): Branch[] {
  const branches: Branch[] = [];
  const trunkX = W / 2;
  const bottomY = H - 40;
  const topY = 60;
  // Branches emerge alternating from a curving trunk at spaced heights.
  for (let i = 0; i < n; i++) {
    const frac = (i + 1) / (n + 1);
    const y0 = bottomY - (bottomY - topY) * frac;
    const side = i % 2 === 0 ? -1 : 1;
    const p0: [number, number] = [trunkX, y0];
    const p1: [number, number] = [trunkX + side * W * 0.15, y0 - 20];
    const p2: [number, number] = [trunkX + side * W * 0.35, y0 - 60];
    const p3: [number, number] = [trunkX + side * W * 0.42, y0 - 90];
    const d = `M ${p0[0]} ${p0[1]} C ${p1[0]} ${p1[1]} ${p2[0]} ${p2[1]} ${p3[0]} ${p3[1]}`;
    branches.push({ p0, p1, p2, p3, d });
  }
  return branches;
}

function trunkPath(W: number, H: number): string {
  const x = W / 2;
  const bottom = H - 10;
  const top = 40;
  // slight S-curve trunk
  return `M ${x} ${bottom} C ${x - 10} ${bottom - (bottom - top) * 0.4}, ${x + 12} ${bottom - (bottom - top) * 0.7}, ${x} ${top}`;
}

interface Props {
  chapterNum: string;
  onOpenTopic: (tid: TopicId) => void;
}

export const Tree: React.FC<Props> = ({ chapterNum, onOpenTopic }) => {
  const { width } = useWindowDimensions();
  const H = 560;
  const W = width - 24;

  const chapterTopics = useMemo(
    () => allTopics.filter((t) => t.parent_chapter_num === chapterNum),
    [chapterNum],
  );

  // How many branches? Use the max branch index actually used.
  const branchCount = useMemo(() => {
    const maxB = chapterTopics.reduce((m, t) => Math.max(m, t.garden_slot.branch), 0);
    return maxB + 1;
  }, [chapterTopics]);

  const branches = useMemo(() => makeBranches(Math.max(branchCount, 1), W, H), [branchCount, W]);

  const derived = useTutor((s) => s.derived);
  const recordPick = useTutor((s) => s.recordPick);

  return (
    <View style={{ width: W, height: H, alignSelf: 'center' }}>
      <Svg width={W} height={H}>
        {/* Trunk */}
        <Path d={trunkPath(W, H)} stroke="#6a4a2a" strokeWidth={10} strokeLinecap="round" fill="none" />
        {/* Branches */}
        <G>
          {branches.map((b, i) => (
            <Path key={i} d={b.d} stroke="#6a4a2a" strokeWidth={5} strokeLinecap="round" fill="none" />
          ))}
        </G>
      </Svg>

      {/* Emoji nodes absolutely positioned on top of the SVG */}
      {chapterTopics.map((t) => {
        const br = branches[t.garden_slot.branch] ?? branches[0];
        const [x, y] = bezier(br.p0, br.p1, br.p2, br.p3, t.garden_slot.u);
        const stash = derived.stash[t.topic_id] ?? 0;
        const picked = derived.picked[t.topic_id] ?? 0;
        return (
          <View
            key={t.topic_id}
            style={{
              position: 'absolute',
              left: x - 22,
              top: y - 22,
              width: 44,
              height: 44,
            }}
          >
            <EmojiNode
              topicId={t.topic_id}
              emoji={t.garden_emoji}
              stash={stash}
              picked={picked}
              size={36}
              onPick={() => recordPick(t.topic_id, t.garden_emoji, 'garden')}
              onOpen={() => onOpenTopic(t.topic_id)}
            />
          </View>
        );
      })}

      <Text style={styles.caption}>Chapter {chapterNum}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  caption: {
    position: 'absolute',
    bottom: 6,
    alignSelf: 'center',
    color: '#8892a6',
    fontWeight: '600',
  },
});
