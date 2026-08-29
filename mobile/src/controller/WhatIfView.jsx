import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { colors } from '../theme';
import { Panel, SectionTitle, SplitFlapCell, EmptyState, Note, ActionMessage } from '../components/ui';
import { api } from '../api';

export default function WhatIfView({ liveState }) {
  const [trainNo, setTrainNo] = useState('');
  const [minutes, setMinutes] = useState('15');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const trains = liveState?.trains?.filter((t) => t.status !== 'completed') || [];

  const run = async () => {
    if (!trainNo) return;
    setLoading(true);
    setMessage('');
    try {
      const res = await api.whatIf(trainNo, Number(minutes));
      setResult(res);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel>
      <SectionTitle>What-If Simulator</SectionTitle>
      <View style={styles.picker}>
        {trains.map((t) => (
          <TouchableOpacity
            key={t.train_no}
            style={[styles.pill, trainNo === t.train_no && styles.pillActive]}
            onPress={() => setTrainNo(t.train_no)}
          >
            <Text style={[styles.pillText, trainNo === t.train_no && styles.pillTextActive]} numberOfLines={1}>
              {t.train_no}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.controls}>
        <Text style={styles.label}>Extra delay (min)</Text>
        <View style={styles.minutesRow}>
          {[5, 15, 30, 60].map((value) => (
            <TouchableOpacity
              key={value}
              style={[styles.minuteBtn, Number(minutes) === value && styles.minuteActive]}
              onPress={() => setMinutes(String(value))}
            >
              <Text style={[styles.minuteText, Number(minutes) === value && styles.minuteTextActive]}>{value}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <TouchableOpacity style={[styles.runBtn, (!trainNo || loading) && styles.runDisabled]} onPress={run} disabled={!trainNo || loading}>
          {loading ? (
            <ActivityIndicator color="#fff" size="small" />
          ) : (
            <Text style={styles.runText}>Simulate</Text>
          )}
        </TouchableOpacity>
      </View>
      {message ? <View style={{ marginTop: 8 }}><ActionMessage tone="error">{message}</ActionMessage></View> : null}
      {result && (
        <View style={styles.result}>
          <View style={styles.resultRow}>
            <Text style={styles.resultLabel}>Projected total network delay</Text>
            <SplitFlapCell>{result.total_projected_network_delay} min</SplitFlapCell>
          </View>
          <Text style={styles.resultSub}>Projected conflicts: {result.projected_conflicts.length}</Text>
          {result.projected_resolutions.map((r, index) => (
            <Text key={index} style={styles.reason}>• {r.reason}</Text>
          ))}
        </View>
      )}
    </Panel>
  );
}

const styles = StyleSheet.create({
  picker: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 },
  pill: {
    backgroundColor: colors.bgBoard,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    maxWidth: '48%',
  },
  pillActive: { borderColor: colors.railBlue, backgroundColor: 'rgba(79,143,232,0.15)' },
  pillText: { fontSize: 12, fontFamily: 'monospace', color: colors.textSecondary },
  pillTextActive: { color: colors.railBlue },
  controls: { gap: 10 },
  label: { fontSize: 11, fontWeight: '600', letterSpacing: 0.6, color: colors.textSecondary },
  minutesRow: { flexDirection: 'row', gap: 6 },
  minuteBtn: {
    backgroundColor: colors.bgBoard,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 6,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  minuteActive: { borderColor: colors.signalAmber, backgroundColor: 'rgba(232,162,61,0.15)' },
  minuteText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  minuteTextActive: { color: colors.signalAmber },
  runBtn: {
    backgroundColor: colors.railBlue,
    borderRadius: 7,
    paddingVertical: 10,
    alignItems: 'center',
  },
  runDisabled: { opacity: 0.55 },
  runText: { fontSize: 13, fontWeight: '600', color: '#fff' },
  result: { marginTop: 14 },
  resultRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  resultLabel: { fontSize: 12.5, color: colors.textSecondary },
  resultSub: { color: colors.textSecondary, fontSize: 12 },
  reason: { marginTop: 6, color: colors.textSecondary, fontSize: 12.5, lineHeight: 17 },
});