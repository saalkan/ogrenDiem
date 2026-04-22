/**
 * EmojiNode — one tappable collectable on the tree/cave.
 *
 * States (from stash/picked counts, not Bayes mastery):
 *   bare     stash 0, picked 0 → greyscale silhouette
 *   ripe     stash > 0         → full-color emoji with count badge
 *   harvested stash 0, picked > 0 → muted emoji + lifetime counter
 *
 * Tapping a ripe node picks one emoji (stash -= 1, picked += 1).
 * Long-press navigates to Learn for that topic.
 */
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { TopicId } from '@/shared/types';

interface Props {
  topicId: TopicId;
  emoji: string;
  stash: number;
  picked: number;
  size?: number;
  onPick: () => void;
  onOpen: () => void;     // long-press → open learn screen for this topic
}

export const EmojiNode: React.FC<Props> = ({
  emoji, stash, picked, size = 40, onPick, onOpen,
}) => {
  const hasStash = stash > 0;
  const isHarvested = stash === 0 && picked > 0;
  const isBare = stash === 0 && picked === 0;

  return (
    <Pressable
      onPress={hasStash ? onPick : onOpen}
      onLongPress={onOpen}
      hitSlop={8}
      style={styles.wrap}
    >
      <Text
        style={[
          styles.emoji,
          { fontSize: size, opacity: isBare ? 0.28 : isHarvested ? 0.55 : 1 },
        ]}
      >
        {emoji}
      </Text>
      {hasStash && (
        <View style={styles.stashBadge}>
          <Text style={styles.stashText}>{stash}</Text>
        </View>
      )}
      {isHarvested && (
        <View style={styles.pickedBadge}>
          <Text style={styles.pickedText}>{picked}</Text>
        </View>
      )}
    </Pressable>
  );
};

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', justifyContent: 'center', padding: 4 },
  emoji: { textAlign: 'center' },
  stashBadge: {
    position: 'absolute',
    top: -2,
    right: -2,
    backgroundColor: '#2ecc71',
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stashText: { color: '#0e1116', fontSize: 11, fontWeight: '800' },
  pickedBadge: {
    position: 'absolute',
    bottom: -2,
    right: -2,
    backgroundColor: '#1f2630',
    minWidth: 18,
    height: 16,
    borderRadius: 8,
    paddingHorizontal: 4,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#2b3442',
  },
  pickedText: { color: '#8892a6', fontSize: 10, fontWeight: '700' },
});
