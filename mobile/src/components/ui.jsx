import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, fonts, statusColor, statusLabel } from '../theme';

export function Panel({ children, style }) {
  return <View style={[styles.panel, style]}>{children}</View>;
}

export function SectionTitle({ children, style }) {
  return <Text style={[styles.sectionTitle, style]}>{children}</Text>;
}

export function EmptyState({ children, style }) {
  return <Text style={[styles.emptyState, style]}>{children}</Text>;
}

export function Badge({ tone, children, style }) {
  const map = {
    simulation: styles.badgeSimulation,
    ai: styles.badgeSimulation,
    admin: styles.badgeAdmin,
    danger: styles.badgeDanger,
  };
  return <View style={[styles.badge, map[tone] || styles.badgeSimulation, style]}>{children}</View>;
}

export function Stat({ label, value, color }) {
  return (
    <View style={styles.stat}>
      <Text style={[styles.statValue, color ? { color } : null]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

export function SplitFlapCell({ children, style }) {
  return <Text style={[styles.splitFlapCell, style]}>{children}</Text>;
}

export function SplitFlapText({ children, style }) {
  return <Text style={[styles.splitFlapText, style]}>{children}</Text>;
}

export function StatusChip({ status }) {
  const color = statusColor(status);
  return (
    <View style={[styles.chip, { backgroundColor: color + '26' }]}>
      <View style={[styles.chipDot, { backgroundColor: color }]} />
      <Text style={[styles.chipText, { color }]}>{statusLabel(status).toUpperCase()}</Text>
    </View>
  );
}

export function ActionMessage({ children, tone = 'info' }) {
  const palette =
    tone === 'error'
      ? { background: colors.signalRedGlow, border: 'rgba(214, 69, 69, 0.5)', color: colors.signalRed }
      : tone === 'success'
        ? { background: 'rgba(63,166,107,0.10)', border: 'rgba(63,166,107,0.30)', color: colors.textSecondary }
        : { background: 'rgba(79,143,232,0.08)', border: 'rgba(79,143,232,0.28)', color: colors.textSecondary };
  return (
    <View style={[styles.actionMessage, { backgroundColor: palette.background, borderColor: palette.border }]}>
      <Text style={{ color: palette.color, fontSize: 11.5, lineHeight: 16 }}>{children}</Text>
    </View>
  );
}

export function Note({ children, style }) {
  return (
    <View style={[styles.note, style]}>
      <Text style={styles.noteText}>{children}</Text>
    </View>
  );
}

export function LegendDot({ color }) {
  return <View style={[styles.legendDot, { backgroundColor: color }]} />;
}

export function Legend({ items, style }) {
  return (
    <View style={[styles.legend, style]}>
      {items.map((item) => (
        <View key={item.label} style={styles.legendItem}>
          <LegendDot color={item.color} />
          <Text style={styles.legendText}>{item.label}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: colors.bgPanelRaised,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 10,
    padding: 14,
  },
  sectionTitle: {
    fontFamily: fonts.display,
    fontWeight: '600',
    fontSize: 13,
    textTransform: 'uppercase',
    letterSpacing: 0.06 * 14,
    color: colors.textSecondary,
    marginBottom: 10,
  },
  emptyState: {
    color: colors.textMuted,
    fontSize: 13,
    textAlign: 'center',
    padding: 20,
  },
  badge: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.04 * 10,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 4,
    overflow: 'hidden',
    alignSelf: 'flex-start',
  },
  badgeSimulation: { backgroundColor: 'rgba(79,143,232,0.15)', color: colors.railBlue },
  badgeAdmin: { backgroundColor: 'rgba(232,162,61,0.15)', color: colors.signalAmber },
  badgeDanger: { backgroundColor: 'rgba(214,69,69,0.15)', color: colors.signalRed },
  stat: {
    backgroundColor: colors.bgPanelRaised,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
  },
  statValue: {
    fontFamily: fonts.mono,
    fontSize: 21,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  statLabel: {
    fontSize: 10.5,
    color: colors.textMuted,
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  splitFlapCell: {
    fontFamily: fonts.mono,
    backgroundColor: colors.bgBoard,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    color: colors.textBoard,
    overflow: 'hidden',
  },
  splitFlapText: {
    fontFamily: fonts.mono,
    backgroundColor: colors.bgBoard,
    color: colors.textBoard,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
    letterSpacing: 0.5,
    textShadowColor: 'rgba(240, 169, 78, 0.4)',
    textShadowRadius: 4,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 9,
    paddingVertical: 3,
    borderRadius: 6,
    alignSelf: 'flex-start',
  },
  chipDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  chipText: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  actionMessage: {
    padding: 10,
    borderRadius: 7,
    borderWidth: 1,
    marginBottom: 10,
  },
  note: {
    backgroundColor: 'rgba(79,143,232,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(79,143,232,0.28)',
    borderRadius: 7,
    padding: 10,
    marginBottom: 10,
  },
  noteText: {
    fontSize: 11.5,
    lineHeight: 16,
    color: colors.textSecondary,
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 14,
    backgroundColor: 'rgba(22, 28, 38, 0.92)',
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 8,
    padding: 10,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendText: {
    fontSize: 11.5,
    color: colors.textSecondary,
  },
});