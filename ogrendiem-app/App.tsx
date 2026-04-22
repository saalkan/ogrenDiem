import 'react-native-gesture-handler';
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { RootTabs } from '@/navigation/RootTabs';
import { useBootstrap } from '@/store/bootstrap';

const NavTheme = {
  ...DefaultTheme,
  dark: true,
  colors: {
    ...DefaultTheme.colors,
    background: '#0e1116',
    card: '#12161d',
    text: '#e6edf3',
    border: '#1f2630',
    primary: '#74b9ff',
    notification: '#e74c3c',
  },
};

export default function App() {
  const ready = useBootstrap();
  if (!ready) return null;
  return (
    <SafeAreaProvider>
      <NavigationContainer theme={NavTheme}>
        <StatusBar style="light" />
        <RootTabs />
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
