import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, fonts } from '../theme';
import { formatEta } from '../util';

export default function NextTrainCard({ liveState, network }) {
  const service = liveState?.next_departure_service;

  let trainType = null;
  if (service && network?.trains) {
    const base = network.trains.find((t) => service.train_no.startsWith(`${t.train_no}-`));
    trainType = base?.type ? base.type.toUpperCase() : null;
  }

  return (
    <View style={styles.card}>
      <Text style={styles.label}><Text style={styles.dot}>●</Text> NEXT TRAIN</Text>
      {service ? (
        <>
          <View style={styles.trainRow}>
            <Text style={styles.trainNo}>{service.train_no}</Text>
            {trainType && <View style={styles.typeBadge}><Text style={styles.typeBadgeText}>{trainType}</Text></View>}
          </View>
          <View style={styles.route}>
            <Text style={styles.station}>{service.origin}</Text>
            <Text style={styles.arrow}>↓</Text>
            <Text style={styles.station}>{service.destination}</Text>
          </View>
          <View style={styles.meta}>
            <View style={styles.metaCell}>
              <Text style={styles.metaLabel}>ETA</Text>
              <Text style={styles.metaValue}>{formatEta(liveState?.next_departure_time)}</Text>
            </View>
            <View style={styles.metaCell}>
              <Text style={styles.metaLabel}>STATUS</Text>
              <Text style={[styles.metaValue, styles.onTime]}>● ON TIME</Text>
            </View>
          </View>
        </>
      ) : (
        <Text style={styles.empty}>No upcoming trains</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: 220,
    backgroundColor: 'rgba(13, 20, 32, 0.92)',
    borderWidth: 1,
    borderColor: 'rgba(79,143,232,0.4)',
    borderRadius: 8,
    padding: 12,
  },
  label: {
    fontSize: 9.5,
    fontWeight: '700',
    letterSpacing: 1.4,
    color: colors.railBlue,
    marginBottom: 8,
  },
  dot: { fontSize: 6, color: colors.railBlue },
  trainRow: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  trainNo: { fontFamily: fonts.mono, fontSize: 17, fontWeight: '700', color: colors.textPrimary },
  typeBadge: {
    backgroundColor: 'rgba(79,143,232,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(79,143,232,0.35)',
    borderRadius: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginLeft: 'auto',
  },
  typeBadgeText: { fontSize: 8.5, fontWeight: '700', letterSpacing: 0.8, color: colors.railBlue },
  route: {
    marginTop: 9,
    padding: 9,
    backgroundColor: 'rgba(16,21,29,0.7)',
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 6,
  },
  station: { fontSize: 11.5, fontWeight: '600', color: colors.textSecondary, lineHeight: 16 },
  arrow: { color: colors.railBlue, fontSize: 11, lineHeight: 13 },
  meta: {
    marginTop: 10,
    paddingTop: 9,
    borderTopWidth: 1,
    borderTopColor: colors.lineSteel,
    flexDirection: 'row',
    gap: 14,
  },
  metaCell: { flex: 1 },
  metaLabel: { fontSize: 8.5, fontWeight: '700', letterSpacing: 1.2, color: colors.textMuted },
  metaValue: {
    marginTop: 3,
    fontFamily: fonts.mono,
    fontSize: 13.5,
    fontWeight: '700',
    color: colors.textBoard,
  },
  onTime: { color: colors.signalGreen, fontSize: 11, letterSpacing: 0.6 },
  empty: { fontSize: 12, color: colors.textMuted },
});