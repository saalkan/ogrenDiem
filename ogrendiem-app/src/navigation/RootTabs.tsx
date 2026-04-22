/**
 * Root bottom-tab navigator.
 *
 * Four tabs mirror the four modes of the tutor:
 *   Garden   — per-chapter tree collection (Mode 1: chapter)
 *   Cave     — per-cluster cave collection (Mode 3: cluster)
 *   Learn    — question loop for the current/selected topic
 *   Progress — mastery bars + collection totals (Mode 2: group summary)
 *
 * Tapping an emoji on Garden/Cave navigates to Learn with that topic pre-set
 * via a shared Zustand selection slice on the Learn screen's params.
 */
import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text } from 'react-native';
import { GardenScreen } from '@/screens/GardenScreen';
import { CaveScreen } from '@/screens/CaveScreen';
import { LearnScreen } from '@/screens/LearnScreen';
import { ProgressScreen } from '@/screens/ProgressScreen';
import type { TopicId } from '@/shared/types';

export type RootTabParamList = {
  Garden: undefined;
  Cave: undefined;
  Learn: { topicId?: TopicId } | undefined;
  Progress: undefined;
};

const Tab = createBottomTabNavigator<RootTabParamList>();

function tabIcon(emoji: string) {
  return ({ focused }: { focused: boolean }) => (
    <Text style={{ fontSize: focused ? 22 : 18, opacity: focused ? 1 : 0.6 }}>{emoji}</Text>
  );
}

export const RootTabs: React.FC = () => (
  <Tab.Navigator
    screenOptions={{
      headerStyle: { backgroundColor: '#12161d' },
      headerTitleStyle: { color: '#e6edf3', fontWeight: '700' },
      tabBarStyle: {
        backgroundColor: '#12161d',
        borderTopColor: '#1f2630',
      },
      tabBarActiveTintColor: '#74b9ff',
      tabBarInactiveTintColor: '#8892a6',
    }}
  >
    <Tab.Screen
      name="Garden"
      component={GardenScreen}
      options={{ tabBarIcon: tabIcon('🌳'), title: 'Garden' }}
    />
    <Tab.Screen
      name="Cave"
      component={CaveScreen}
      options={{ tabBarIcon: tabIcon('🦇'), title: 'Cave' }}
    />
    <Tab.Screen
      name="Learn"
      component={LearnScreen}
      options={{ tabBarIcon: tabIcon('📖'), title: 'Learn' }}
    />
    <Tab.Screen
      name="Progress"
      component={ProgressScreen}
      options={{ tabBarIcon: tabIcon('📈'), title: 'Progress' }}
    />
  </Tab.Navigator>
);
