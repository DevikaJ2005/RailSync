import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, TextInput, ScrollView, ActivityIndicator } from 'react-native';
import { colors, fonts } from '../theme';
import { Panel, SectionTitle, EmptyState, SplitFlapCell, StatusChip, ActionMessage } from '../components/ui';
import { api } from '../api';

export default function StationView({ station, liveState, network }) {
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(null);

  if (!station) return <EmptyState>Tap a station on the map to see platform status.</EmptyState>;
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

  const handleForceProceed = async (trainNo) => {
    setBusy(trainNo);
    setMessage('');
    try {
      const result = await api.override(trainNo, 'force_proceed', 'Mobile controller override: force proceed');
      setMessage(result.success ? `Force proceed applied to ${trainNo}.` : result.error || 'Override could not be applied.');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <View>
      {message ? <ActionMessage>{message}</ActionMessage> : null}
      <SectionTitle>{station}</SectionTitle>
      <View style={styles.headerRow}>
        <Text style={styles.header}>PLAT</Text>
        <Text style={styles.header}>TRAIN</Text>
        <Text style={styles.header}>STATUS</Text>
      </View>
      {Object.entries(platformData.platforms).map(([plat, trainNo]) => {
        const t = trainNo ? trainsByNo[trainNo] : null;
        return (
          <View style={styles.row} key={plat}>
            <SplitFlapCell>{plat}</SplitFlapCell>
            <Text style={styles.rowTrain} numberOfLines={1}>{trainNo || '—'}</Text>
            <View style={styles.rowStatus}>
              {t ? <StatusChip status={t.status} /> : <Text style={styles.muted}>—</Text>}
            </View>
          </View>
        );
      })}

      {platformData.waiting_queue.length > 0 && (
        <>
          <SectionTitle style={{ marginTop: 14 }}>Waiting Queue</SectionTitle>
          {platformData.waiting_queue.map((trainNo) => {
            const t = trainsByNo[trainNo];
            return (
              <View style={styles.row} key={trainNo}>
                <Text style={styles.rowTrain}>{trainNo}</Text>
                <Text style={styles.muted}>{t?.type}</Text>
                <TouchableOpacity
                  style={styles.btn}
                  disabled={busy === trainNo}
                  onPress={() => handleForceProceed(trainNo)}
                >
                  {busy === trainNo ? (
                    <ActivityIndicator color={colors.railBlue} size="small" />
                  ) : (
                    <Text style={styles.btnText}>Force proceed</Text>
                  )}
                </TouchableOpacity>
              </View>
            );
          })}
        </>
      )}

      <SectionTitle style={{ marginTop: 14 }}>Arrivals &amp; Departures</SectionTitle>
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
              <Text style={styles.rowTrain} numberOfLines={1}>{train.name}</Text>
              <Text style={{ color: isAtStation ? colors.signalGreen : colors.textMuted, fontSize: 11 }}>
                {isAtStation ? 'At station' : `In ${eta} min`}
              </Text>
              <StatusChip status={train.status} />
            </View>
          );
        })
      )}
    </View>
  );
}

function distanceKm(a, b) {
  const earthRadius = 6371;
  const lat = ((b.lat - a.lat) * Math.PI) / 180;
  const lng = ((b.lng - a.lng) * Math.PI) / 180;
  const value =
    Math.sin(lat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(lng / 2) ** 2;
  return earthRadius * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
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
  headerRow: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 2,
    paddingBottom: 4,
  },
  header: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textMuted,
    letterSpacing: 0.8,
    flex: 1,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: colors.lineSteel,
  },
  rowTrain: { fontFamily: fonts.mono, fontSize: 13, flex: 1, color: colors.textPrimary },
  rowStatus: { flex: 1, alignItems: 'flex-start' },
  muted: { fontSize: 11, color: colors.textMuted, flex: 1 },
  btn: {
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  btnText: { fontSize: 11.5, fontWeight: '600', color: colors.textPrimary },
});