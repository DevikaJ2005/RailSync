import React, { useEffect, useMemo, useRef } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import MapView, { Marker, Polyline } from 'react-native-maps';
import { colors, statusColor, statusLabel } from '../theme';
import { buildStationsByName, buildSectionsByKey, trainPositionOnNetwork } from '../util';

const DARK_MAP_STYLE = [
  { elementType: 'geometry', stylers: [{ color: '#10161f' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#10161f' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#7c8798' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1b2430' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0a1420' }] },
  { featureType: 'poi', elementType: 'geometry', stylers: [{ color: '#141c26' }] },
  { featureType: 'transit', elementType: 'geometry', stylers: [{ color: '#16202c' }] },
  { featureType: 'landscape.natural', elementType: 'geometry', stylers: [{ color: '#121a24' }] },
];

export default function LiveMap({
  network,
  networkError,
  liveState,
  onStationClick,
  interactive = true,
  height = 360,
}) {
  const mapRef = useRef(null);
  const stationsByName = useMemo(() => buildStationsByName(network), [network]);
  const sectionsByKey = useMemo(() => buildSectionsByKey(network), [network]);

  const initialRegion = useMemo(() => {
    const stations = network?.stations || [];
    if (stations.length === 0) return null;
    const lats = stations.map((s) => s.lat);
    const lngs = stations.map((s) => s.lng);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    return {
      latitude: (minLat + maxLat) / 2,
      longitude: (minLng + maxLng) / 2,
      latitudeDelta: (maxLat - minLat) * 1.35,
      longitudeDelta: (maxLng - minLng) * 1.35,
    };
  }, [network]);

  useEffect(() => {
    if (network?.stations?.length && mapRef.current) {
      mapRef.current.fitToCoordinates(
        network.stations.map((s) => ({ latitude: s.lat, longitude: s.lng })),
        { edgePadding: { top: 70, right: 50, bottom: 70, left: 50 }, animated: false },
      );
    }
  }, [network]);

  const trains = useMemo(
    () =>
      (liveState?.trains || [])
        .filter((t) => t.status !== 'completed')
        .map((t) => {
          const pos = trainPositionOnNetwork(t, stationsByName, sectionsByKey);
          if (!pos) return null;
          return { ...t, pos };
        })
        .filter(Boolean),
    [liveState, stationsByName, sectionsByKey],
  );

  if (!network || !initialRegion) {
    return (
      <View style={[styles.status, { height }]}>
        <Text style={styles.statusTitle}>
          {networkError ? 'Unable to load railway network.' : 'Loading railway network…'}
        </Text>
        {!networkError && <Text style={styles.statusSub}>Make sure the backend is running.</Text>}
      </View>
    );
  }

  return (
    <View style={[styles.container, { height }]}>
      <MapView
        ref={mapRef}
        style={StyleSheet.absoluteFill}
        initialRegion={initialRegion}
        customMapStyle={DARK_MAP_STYLE}
        toolbarEnabled={false}
        showsCompass={false}
        rotateEnabled={false}
        pitchEnabled={false}
        zoomEnabled={interactive}
        scrollEnabled={interactive}
      >
        {network.sections.map((sec) => {
          const from = stationsByName[sec.from];
          const to = stationsByName[sec.to];
          if (!from || !to) return null;
          const coordinates = (sec.path || [
            [from.lat, from.lng],
            [to.lat, to.lng],
          ]).map(([lat, lng]) => ({ latitude: lat, longitude: lng }));
          return (
            <Polyline key={sec.id} coordinates={coordinates} strokeColor="#3E4C63" strokeWidth={3} />
          );
        })}

        {network.stations.map((s) => (
          <Marker
            key={s.name}
            coordinate={{ latitude: s.lat, longitude: s.lng }}
            title={s.name}
            description={`${s.platforms} platform${s.platforms > 1 ? 's' : ''}`}
            onPress={() => onStationClick?.(s.name)}
            tracksViewChanges={false}
            anchor={{ x: 0.5, y: 0.5 }}
          >
            <View style={styles.stationDot} />
          </Marker>
        ))}

        {trains.map((t) => {
          const color = statusColor(t.status);
          const alert = t.status === 'waiting' || t.status === 'held';
          return (
            <Marker
              key={t.train_no}
              coordinate={{ latitude: t.pos[0], longitude: t.pos[1] }}
              title={`${t.train_no} — ${t.name}`}
              description={`${t.type} · ${statusLabel(t.status)} · predicted delay ${t.predicted_delay_min} min${t.assigned_platform ? ` · platform ${t.assigned_platform}` : ''}`}
              anchor={{ x: 0.5, y: 0.5 }}
              flat
            >
              <View style={alert ? styles.trainDotAlertRing : null}>
                <View style={[styles.trainDot, { backgroundColor: color }]} />
              </View>
            </Marker>
          );
        })}
      </MapView>
      <Text style={styles.hint}>
        {trains.length} active train{trains.length === 1 ? '' : 's'} · tap a station for details
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgVoid,
    borderRadius: 10,
    overflow: 'hidden',
    position: 'relative',
  },
  status: {
    backgroundColor: '#18212a',
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
  },
  statusTitle: {
    fontWeight: '600',
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  statusSub: {
    marginTop: 6,
    fontSize: 11,
    color: colors.textMuted,
  },
  stationDot: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: '#10151D',
    borderWidth: 3,
    borderColor: '#F0A94E',
  },
  trainDotAlertRing: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  trainDot: {
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 2,
    borderColor: '#0A0E14',
  },
  hint: {
    position: 'absolute',
    bottom: 8,
    right: 12,
    fontSize: 10,
    color: colors.textSecondary,
    backgroundColor: 'rgba(10,14,20,0.75)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    overflow: 'hidden',
  },
});