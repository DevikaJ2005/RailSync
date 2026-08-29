import React, { useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Polyline, Circle, Text as SvgText, G } from 'react-native-svg';
import { colors, statusColor } from '../theme';
import { buildStationsByName, buildSectionsByKey, trainPositionOnNetwork } from '../util';

const VB_WIDTH = 1000;

function project(lat, lng, bounds) {
  const { minLat, maxLat, minLng, maxLng, spanLat, spanLng, pad, width, height } = bounds;
  const innerW = width - 2 * pad * width;
  const innerH = height - 2 * pad * height;
  const x = ((lng - minLng) / spanLng) * innerW + pad * width;
  const y = ((maxLat - lat) / spanLat) * innerH + pad * height;
  return { x, y };
}

export default function LiveMap({
  network,
  networkError,
  liveState,
  onStationClick,
  interactive = true,
  height = 360,
}) {
  const stationsByName = useMemo(() => buildStationsByName(network), [network]);
  const sectionsByKey = useMemo(() => buildSectionsByKey(network), [network]);

  const bounds = useMemo(() => {
    const stations = network?.stations || [];
    if (stations.length === 0) return null;
    const lats = stations.map((s) => s.lat);
    const lngs = stations.map((s) => s.lng);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    const spanLat = Math.max(maxLat - minLat, 1e-6);
    const spanLng = Math.max(maxLng - minLng, 1e-6);
    const height = VB_WIDTH * (spanLat / spanLng);
    return { minLat, maxLat, minLng, maxLng, spanLat, spanLng, pad: 0.14, width: VB_WIDTH, height };
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

  if (!network) {
    return (
      <View style={[styles.status, { height }]}>
        <Text style={styles.statusTitle}>
          {networkError ? 'Unable to load railway network.' : 'Loading railway network…'}
        </Text>
        {!networkError && <Text style={styles.statusSub}>Make sure the backend is running.</Text>}
      </View>
    );
  }

  const viewHeight = (bounds.height * 100) / VB_WIDTH;

  return (
    <View style={[styles.container, { height }]}>
      <Svg width="100%" height="100%" viewBox={`0 0 ${VB_WIDTH} ${bounds.height}`}>
        {network.sections.map((sec) => {
          const from = stationsByName[sec.from];
          const to = stationsByName[sec.to];
          if (!from || !to) return null;
          const points = (sec.path || [
            [from.lat, from.lng],
            [to.lat, to.lng],
          ])
            .map(([lat, lng]) => {
              const p = project(lat, lng, bounds);
              return `${p.x},${p.y}`;
            })
            .join(' ');
          return (
            <Polyline key={sec.id} points={points} fill="none" stroke={colors.lineSteelBright} strokeWidth={5} />
          );
        })}

        {network.stations.map((s) => {
          const p = project(s.lat, s.lng, bounds);
          return (
            <G
              key={s.name}
              onPress={interactive ? () => onStationClick?.(s.name) : undefined}
              opacity={interactive ? 1 : 0.85}
            >
              <Circle cx={p.x} cy={p.y} r={16} fill="#10151D" stroke="#F0A94E" strokeWidth={5} />
              <SvgText
                x={p.x + 24}
                y={p.y + 6}
                fontSize={30}
                fontWeight="600"
                fill={colors.textSecondary}
              >
                {s.name}
              </SvgText>
            </G>
          );
        })}

        {trains.map((t) => {
          const p = project(t.pos[0], t.pos[1], bounds);
          const color = statusColor(t.status);
          return (
            <G key={t.train_no}>
              <Circle cx={p.x} cy={p.y} r={13} fill={color} stroke="#0A0E14" strokeWidth={3} />
              {t.status === 'waiting' || t.status === 'held' ? (
                <Circle cx={p.x} cy={p.y} r={20} fill="none" stroke={color} strokeWidth={2.5} opacity={0.55} />
              ) : null}
            </G>
          );
        })}
      </Svg>
      <Text style={styles.hint}>
        {trains.length} active train{trains.length === 1 ? '' : 's'} · {network.stations.length} stations
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
    fontFamily: 'System',
    fontWeight: '600',
    fontSize: 15,
    color: colors.textSecondary,
  },
  statusSub: {
    marginTop: 6,
    fontSize: 11,
    color: colors.textMuted,
  },
  hint: {
    position: 'absolute',
    bottom: 8,
    right: 12,
    fontSize: 10,
    color: colors.textMuted,
    backgroundColor: 'rgba(10,14,20,0.7)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    overflow: 'hidden',
  },
});