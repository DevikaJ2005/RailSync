import React, { useState } from 'react';
import { View, Text, TextInput, StyleSheet } from 'react-native';
import { colors, fonts } from '../theme';
import { Panel, SectionTitle, EmptyState, StatusChip } from '../components/ui';

export default function TrainSearchView({ liveState }) {
  const [query, setQuery] = useState('');

  const trains = (liveState?.trains || []).filter((t) => t.status !== 'completed');
  const filtered = query
    ? trains.filter(
        (t) =>
          t.train_no.toLowerCase().includes(query.toLowerCase()) ||
          t.name.toLowerCase().includes(query.toLowerCase()),
      )
    : trains;

  return (
    <Panel>
      <SectionTitle>Find Your Train</SectionTitle>
      <TextInput
        style={styles.input}
        placeholder="Search by train number or name…"
        placeholderTextColor={colors.textMuted}
        value={query}
        onChangeText={setQuery}
      />
      {filtered.length === 0 && <EmptyState>No matching trains.</EmptyState>}
      {filtered.map((t) => (
        <View style={styles.row} key={t.train_no}>
          <View style={styles.trainInfo}>
            <Text style={styles.trainName} numberOfLines={1}>{t.train_no} — {t.name}</Text>
            <Text style={styles.route}>{t.from} → {t.to}</Text>
          </View>
          <StatusChip status={t.status} />
        </View>
      ))}
    </Panel>
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
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: colors.lineSteel,
  },
  trainInfo: { flex: 1 },
  trainName: { fontFamily: fonts.mono, fontSize: 13, color: colors.textPrimary },
  route: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
});