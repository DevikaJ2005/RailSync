import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, fonts } from '../theme';
import { EmptyState, SplitFlapCell, StatusChip } from '../components/ui';
import { distanceKm } from '../util';

export default function PlatformView({ station, liveState, network }) {
  if (!station) return <EmptyState>Tap a station on the map to see arrivals.</EmptyState>;
  if (!liveState) return <EmptyState>Loading…</EmptyState>;

  const platformData = liveState.platforms?.[station];
  if (!platformData) return <EmptyState>No data for {station}.</EmptyState>;

  const trainsByNo = {};
  liveState.trains.forEach((t) => { trainsByNo[t.train_no] = t; });
  const stationsByName = Object.fromEntries((network?.stations || []).map((item) => [item.name, item]));

  const arrivals = liveState.trains.filter((train) => {
    const stationIndex = train.route?.indexOf(station) ?? -1;
    return train.status !== 'completed' && stationIndex > train.route_index;
  });

  return (
    <View style={styles.card}>
      <View style={styles.cardHead}>
        <Text style={styles.stationTitle}>{station}</Text>
      </View>
      <View style={styles.board}>
        {Object.entries(platformData.platforms).map(([plat, trainNo]) => {
          const t = trainNo ? trainsByNo[trainNo] : null;
          return (
            <View style={styles.row} key={plat}>
              <SplitFlapCell>PL{plat}</SplitFlapCell>
              <Text style={styles.trainCell} numberOfLines={1}>
                {t ? `${t.train_no} ${t.name}` : '— no train —'}
              </Text>
              <Text style={styles.typeCell}>{t ? t.type.slice(0, 3).toUpperCase() : ''}</Text>
              <View style={styles.statusCell}>
                {t?.status === 'waiting' && <Text style={styles.waiting}>● WAITING</Text>}
                {t?.status === 'at_platform' && <Text style={styles.boarding}>● BOARDING</Text>}
                {!t && <Text style={styles.muted}>—</Text>}
              </View>
            </View>
          );
        })}
        {platformData.waiting_queue.length > 0 &&
          platformData.waiting_queue.map((tn) => {
            const t = trainsByNo[tn];
            return (
              <View style={[styles.row, { opacity: 0.75 }]} key={tn}>
                <SplitFlapCell>—</SplitFlapCell>
                <Text style={styles.trainCell} numberOfLines={1}>{tn} {t?.name}</Text>
                <Text style={styles.typeCell}>{t?.type.slice(0, 3).toUpperCase()}</Text>
                <Text style={styles.waiting}>● HOLDING</Text>
              </View>
            );
          })}
      </View>

      <Text style={styles.upcomingTitle}>Upcoming Trains</Text>
      {arrivals.length === 0 ? (
        <EmptyState>No active trains scheduled for this station.</EmptyState>
      ) : (
        arrivals.map((train) => {
          const stationIndex = train.route.indexOf(station);
          const isAtStation = train.to === station && train.status !== 'moving';
          const eta = getArrivalMinutes(train, station, stationsByName);
          return (
            <View style={styles.row} key={train.train_no}>
              <SplitFlapCell>{train.train_no}</SplitFlapCell>
              <Text style={styles.trainCell} numberOfLines={1}>{train.name}</Text>
              <Text style={{ color: isAtStation ? colors.signalGreen : colors.textMuted, fontSize: 11 }}>
                {isAtStation ? 'At station' : `${eta} min`}
              </Text>
              <StatusChip status={train.status} />
            </View>
          );
        })
      )}
    </View>
  );
}

function getArrivalMinutes(train, station, stationsByName) {
  const stationIndex = train.route.indexOf(station);
  let minutes = 0;
  for (let index = train.route_index; index < stationIndex; index += 1) {
    const from = stationsByName[train.route[index]];
    const to = stationsByName[train.route[index + 1]];
    if (from && to) minutes += (distanceKm(from, to) / train.speed_kmph) * 60;
  }
  if (stationIndex === train.route_index + 1) minutes *= Math.max(0, 1 - train.progress);
  return Math.max(0, Math.round(minutes));
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgPanelRaised,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 10,
    overflow: 'hidden',
  },
  cardHead: {
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.lineSteel,
  },
  stationTitle: {
    fontFamily: fonts.display,
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  board: { paddingVertical: 4 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 9,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.lineSteel,
  },
  trainCell: { fontFamily: fonts.mono, fontSize: 12.5, flex: 1, color: colors.textPrimary },
  typeCell: { fontSize: 10, color: colors.textMuted, width: 30 },
  statusCell: { flex: 1, alignItems: 'flex-end' },
  waiting: { fontSize: 10, fontWeight: '700', color: colors.signalAmber },
  boarding: { fontSize: 10, fontWeight: '700', color: colors.signalGreen },
  muted: { fontSize: 10, color: colors.textMuted },
  upcomingTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 2,
  },
});