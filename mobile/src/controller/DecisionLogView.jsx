import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TextInput } from 'react-native';
import { colors, fonts } from '../theme';
import { EmptyState, Badge, SplitFlapText } from '../components/ui';
import { api } from '../api';

export default function DecisionLogView() {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    const load = () => api.getLogs(filter || undefined).then(setLogs).catch(() => {});
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [filter]);

  return (
    <View>
      <TextInput
        style={styles.input}
        placeholder="Search by train number…"
        placeholderTextColor={colors.textMuted}
        value={filter}
        onChangeText={setFilter}
      />
      {logs.length === 0 && <EmptyState>No decisions logged yet.</EmptyState>}
      {logs.map((log, index) => (
        <View key={index} style={styles.card}>
          <View style={styles.cardHead}>
            <SplitFlapText style={{ fontSize: 11 }}>{log.sim_timestamp}</SplitFlapText>
            <Badge tone={log.resolved_by === 'controller' ? 'admin' : 'simulation'}>{log.resolved_by}</Badge>
          </View>
          <Text style={styles.meta}>
            {log.trains_involved?.join(', ') || '—'} · {log.conflict_type}
          </Text>
          <Text style={styles.reason}>{log.reason}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  input: {
    backgroundColor: colors.bgBoard,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 6,
    color: colors.textPrimary,
    fontSize: 12.5,
    paddingHorizontal: 11,
    paddingVertical: 8,
    marginBottom: 12,
  },
  card: {
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderLeftWidth: 3,
    borderLeftColor: colors.lineSteelBright,
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  cardHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  meta: { marginTop: 6, fontSize: 12, color: colors.textSecondary },
  reason: { marginTop: 6, color: colors.textSecondary, fontSize: 12.5, lineHeight: 18 },
});