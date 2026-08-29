import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { colors, fonts } from '../theme';
import LiveMap from '../components/LiveMap';
import { Legend } from '../components/ui';
import NextTrainCard from '../components/NextTrainCard';
import SimControls from '../controller/SimControls';
import ControllerTabs from '../controller/ControllerTabs';
import PassengerTabs from '../passenger/PassengerTabs';

const WEEKDAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

export default function HomeScreen({ user, liveState, network, networkError, connected, modelInfo, onLogout }) {
  const [systemTime, setSystemTime] = useState(() => new Date());
  const [selectedStation, setSelectedStation] = useState(null);

  useEffect(() => {
    const timer = setInterval(() => setSystemTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const isController = user.role === 'controller';
  const clockTime = systemTime.toLocaleTimeString([], { hour12: false });
  const clockDate = `${WEEKDAYS[systemTime.getDay()]}, ${String(systemTime.getDate()).padStart(2, '0')} ${MONTHS[systemTime.getMonth()]} ${systemTime.getFullYear()}`;

  const legendItems = isController
    ? [
        { label: 'Moving', color: '#4F8FE8' },
        { label: 'Waiting', color: '#E8A23D' },
        { label: 'Held', color: '#D64545' },
        { label: 'At platform', color: '#3FA66B' },
        { label: 'Completed', color: '#6B7787' },
      ]
    : [
        { label: 'Moving', color: '#4F8FE8' },
        { label: 'Waiting', color: '#E8A23D' },
        { label: 'Boarding', color: '#3FA66B' },
      ];

  return (
    <View style={styles.container}>
      <View style={styles.topbar}>
        <View style={styles.brandRow}>
          <Text style={styles.brand}>RailSync</Text>
          <View style={[styles.rolePill, isController ? styles.roleController : styles.rolePassenger]}>
            <Text style={[styles.roleText, isController ? styles.roleControllerText : styles.rolePassengerText]}>
              {user.role}
            </Text>
          </View>
        </View>
        <View style={styles.sessionRow}>
          <Text style={styles.sessionName} numberOfLines={1}>
            {user.display_name || user.username}
          </Text>
          <TouchableOpacity onPress={onLogout} style={styles.logoutBtn}>
            <Text style={styles.logoutText}>Sign out</Text>
          </TouchableOpacity>
          <View style={styles.clockBlock}>
            <View style={styles.clockHead}>
              <Text style={connected ? styles.online : styles.offline}>
                {connected ? '● SYSTEM ONLINE' : '● OFFLINE'}
              </Text>
              <Text style={styles.clockTime}>{clockTime}</Text>
            </View>
            <Text style={styles.clockDate}>{clockDate}</Text>
          </View>
        </View>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        <View style={styles.mapWrap}>
          <LiveMap
            network={network}
            networkError={networkError}
            liveState={liveState}
            onStationClick={setSelectedStation}
            height={330}
          />
          {isController && <View style={styles.nextTrainOverlay}><NextTrainCard liveState={liveState} network={network} /></View>}
        </View>

        <Legend items={legendItems} style={styles.legend} />

        {isController && (
          <SimControls liveState={liveState} />
        )}

        {isController ? (
          <ControllerTabs
            liveState={liveState}
            network={network}
            networkError={networkError}
            modelInfo={modelInfo}
            selectedStation={selectedStation}
            onSelectStation={setSelectedStation}
          />
        ) : (
          <PassengerTabs
            liveState={liveState}
            network={network}
            selectedStation={selectedStation}
            onSelectStation={setSelectedStation}
          />
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bgVoid },
  topbar: {
    backgroundColor: colors.bgPanel,
    borderBottomWidth: 1,
    borderBottomColor: colors.lineSteel,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 8,
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  brand: {
    fontFamily: fonts.display,
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
    letterSpacing: 0.5,
  },
  rolePill: { borderRadius: 5, paddingHorizontal: 9, paddingVertical: 3, borderWidth: 1 },
  roleController: { backgroundColor: 'rgba(232,162,61,0.15)', borderColor: 'rgba(232,162,61,0.4)' },
  rolePassenger: { backgroundColor: 'rgba(79,143,232,0.15)', borderColor: 'rgba(79,143,232,0.4)' },
  roleText: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8 },
  roleControllerText: { color: colors.signalAmber },
  rolePassengerText: { color: colors.railBlue },
  sessionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  sessionName: { fontSize: 13, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
  logoutBtn: {
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 7,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  logoutText: { fontSize: 11, color: colors.textMuted, fontWeight: '600' },
  clockBlock: { marginLeft: 'auto', alignItems: 'flex-end' },
  clockHead: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  online: { fontSize: 9, fontWeight: '700', letterSpacing: 1.2, color: colors.signalGreen },
  offline: { fontSize: 9, fontWeight: '700', letterSpacing: 1, color: colors.signalRed },
  clockTime: {
    fontFamily: fonts.mono,
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 1.2,
    color: colors.textBoard,
    textShadowColor: 'rgba(240,169,78,0.35)',
    textShadowRadius: 4,
  },
  clockDate: { fontSize: 10, fontWeight: '600', letterSpacing: 1, color: colors.textMuted },
  scroll: { flex: 1 },
  scrollContent: { padding: 14, gap: 12 },
  mapWrap: { position: 'relative' },
  nextTrainOverlay: { position: 'absolute', top: 10, left: 10 },
  legend: { alignSelf: 'flex-start' },
});