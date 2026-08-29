import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '../theme';
import { Panel, SectionTitle, Stat, EmptyState, Note } from '../components/ui';
import WhatIfView from './WhatIfView';
import { api } from '../api';

export default function AnalyticsView({ modelInfo, liveState }) {
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => {
    const load = () => api.getAnalytics().then(setAnalytics).catch(() => {});
    load();
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
  }, []);

  if (!analytics) return <EmptyState>Loading analytics…</EmptyState>;

  const testBaseline = modelInfo?.metrics?.test_baseline_metrics;

  return (
    <View>
      <Panel style={styles.panel}>
        <SectionTitle>Delay Model Evaluation</SectionTitle>
        <Text style={styles.scopeText}>
          {modelInfo?.scope?.prediction || 'Synthetic per-section delay prediction.'}
        </Text>
        {modelInfo?.metrics?.mae_min != null ? (
          <View style={styles.statRow}>
            <View style={styles.stat}>
              <Stat label="Test MAE" value={`${modelInfo.metrics.mae_min} min`} color={colors.signalGreen} />
            </View>
            <View style={styles.stat}>
              <Stat label="Test RMSE" value={`${modelInfo.metrics.rmse_min} min`} color={colors.signalAmber} />
            </View>
            <View style={styles.stat}>
              <Stat label="Test R²" value={modelInfo.metrics.r2} color={colors.railBlue} />
            </View>
          </View>
        ) : (
          <EmptyState>Evaluation metrics unavailable</EmptyState>
        )}
        {modelInfo?.metrics?.splits?.test && (
          <Text style={styles.mutedText}>
            Chronological holdout: {Number(modelInfo.metrics.splits.test.rows).toLocaleString()} unseen
            synthetic section records
            {testBaseline?.mae_min != null && ` | Mean baseline MAE: ${testBaseline.mae_min} min`}
          </Text>
        )}
      </Panel>

      <Panel style={styles.panel}>
        <SectionTitle>Simulation Operations</SectionTitle>
        <View style={styles.statRow}>
          <View style={styles.stat}>
            <Stat label="Conflict Onsets" value={analytics.conflicts_detected} />
          </View>
          <View style={styles.stat}>
            <Stat label="Active Conflicts" value={analytics.active_conflicts} color={colors.signalAmber} />
          </View>
        </View>
        <View style={styles.statRow}>
          <View style={styles.stat}>
            <Stat label="Controller Holds" value={analytics.controller_resolutions_applied} color={colors.signalGreen} />
          </View>
          <View style={styles.stat}>
            <Stat
              label="Safety Interventions"
              value={analytics.forced_releases + analytics.deadlocks_broken}
              color={colors.signalRed}
            />
          </View>
        </View>
        <Stat label="Active Predicted Delay" value={`${analytics.active_predicted_delay_min} min`} color={colors.railBlue} />
      </Panel>

      <Note style={styles.scopeNote}>
        <Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Scope note: </Text>
        delay is the model output. Section and platform conflicts are detected and resolved by
        explainable simulation rules; these operational counters are not an “AI versus no-AI”
        experiment.
      </Note>

      <WhatIfView liveState={liveState} />
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { marginBottom: 14 },
  scopeText: { fontSize: 11.5, color: colors.textSecondary, lineHeight: 16, marginBottom: 10 },
  mutedText: { fontSize: 11, color: colors.textMuted, marginTop: 10, lineHeight: 15 },
  statRow: { flexDirection: 'row', gap: 10, marginBottom: 10 },
  stat: { flex: 1 },
  scopeNote: { marginBottom: 14 },
});