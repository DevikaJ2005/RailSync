import React, { useState, useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { colors } from '../theme';
import TabStrip from '../components/TabStrip';
import StationView from './StationView';
import ConflictsView from './ConflictsView';
import DecisionLogView from './DecisionLogView';
import AnalyticsView from './AnalyticsView';

const TABS = [
  { key: 'station', label: 'Station' },
  { key: 'conflicts', label: 'Conflicts' },
  { key: 'log', label: 'Log' },
  { key: 'analytics', label: 'Analytics' },
];

export default function ControllerTabs({ liveState, network, modelInfo, selectedStation, onSelectStation }) {
  const [activeTab, setActiveTab] = useState('conflicts');

  useEffect(() => {
    if (selectedStation) setActiveTab('station');
  }, [selectedStation]);

  const activeConflictCount = liveState?.resolutions?.length || 0;

  const badgeFor = (key) => (key === 'conflicts' ? activeConflictCount : null);

  const handleSelect = (key) => {
    setActiveTab(key);
    if (key === 'station') onSelectStation(null);
  };

  return (
    <View style={styles.container}>
      <TabStrip tabs={TABS} active={activeTab} onSelect={handleSelect} badgeFor={badgeFor} />
      <View style={styles.content}>
        {activeTab === 'station' && (
          <StationView station={selectedStation} liveState={liveState} network={network} />
        )}
        {activeTab === 'conflicts' && <ConflictsView liveState={liveState} />}
        {activeTab === 'log' && <DecisionLogView />}
        {activeTab === 'analytics' && <AnalyticsView modelInfo={modelInfo} liveState={liveState} />}
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