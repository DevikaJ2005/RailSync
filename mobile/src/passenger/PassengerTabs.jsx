import React, { useState, useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { colors } from '../theme';
import TabStrip from '../components/TabStrip';
import PlatformView from './PlatformView';
import TrainSearchView from './TrainSearchView';

const TABS = [
  { key: 'platform', label: 'Platform Board' },
  { key: 'search', label: 'Find Train' },
];

export default function PassengerTabs({ liveState, network, selectedStation, onSelectStation }) {
  const [tab, setTab] = useState('platform');

  useEffect(() => {
    if (selectedStation) setTab('platform');
  }, [selectedStation]);

  return (
    <View style={styles.container}>
      <TabStrip tabs={TABS} active={tab} onSelect={setTab} />
      <View style={styles.content}>
        {tab === 'platform' && (
          <PlatformView station={selectedStation} liveState={liveState} network={network} />
        )}
        {tab === 'search' && <TrainSearchView liveState={liveState} />}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 10,
    overflow: 'hidden',
  },
  content: { padding: 14 },
});