import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { colors, fonts } from '../theme';
import { Panel, SectionTitle, ActionMessage } from '../components/ui';
import { api } from '../api';

const SPEEDS = [0.5, 1, 2, 4];

export default function SimControls({ liveState }) {
  const [busy, setBusy] = useState(null);
  const [message, setMessage] = useState('');

  const paused = liveState?.paused ?? false;

  const run = async (key, task) => {
    setBusy(key);
    setMessage('');
    try {
      const res = await task();
      setMessage(
        key === 'speed'
          ? `Speed set to ${res.speed_multiplier}x.`
          : key === 'pause'
            ? 'Simulation paused.'
            : key === 'resume'
              ? 'Simulation resumed.'
              : 'Simulation state reset.',
      );
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Panel>
      <SectionTitle>Simulation Control</SectionTitle>
      <View style={styles.row}>
        {paused ? (
          <TouchableOpacity
            style={[styles.btn, styles.btnSuccess]}
            disabled={busy !== null}
            onPress={() => run('resume', api.resumeSimulation)}
          >
            <Text style={styles.btnText}>Resume</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={styles.btn}
            disabled={busy !== null}
            onPress={() => run('pause', api.pauseSimulation)}
          >
            <Text style={styles.btnText}>Pause</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity
          style={[styles.btn, styles.btnDanger]}
          disabled={busy !== null}
          onPress={() => run('reset', api.resetSimulation)}
        >
          <Text style={styles.btnDangerText}>Reset</Text>
        </TouchableOpacity>
        <View style={styles.speedGroup}>
          <Text style={styles.speedLabel}>SPEED</Text>
          {SPEEDS.map((speed) => {
            const active = Math.abs((liveState?.speed_multiplier || 1) - speed) < 0.001;
            return (
              <TouchableOpacity
                key={speed}
                style={[styles.speedBtn, active && styles.speedActive]}
                disabled={busy !== null}
                onPress={() => run('speed', () => api.setSpeed(speed))}
              >
                <Text style={[styles.speedText, active && styles.speedActiveText]}>{speed}x</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>
      <Text style={styles.simTime}>
        Simulation time: <Text style={styles.simTimeValue}>{liveState?.sim_time || '—'}</Text>
        {paused ? '  ·  PAUSED' : ''}
      </Text>
      {busy !== null && <ActivityIndicator style={{ marginTop: 8 }} color={colors.railBlue} size="small" />}
      {message ? <View style={{ marginTop: 8 }}><ActionMessage>{message}</ActionMessage></View> : null}
    </Panel>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  btn: {
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 7,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  btnSuccess: { backgroundColor: colors.signalGreen, borderColor: colors.signalGreen },
  btnDanger: { borderColor: colors.signalRed },
  btnText: { fontSize: 12.5, fontWeight: '600', color: colors.textPrimary },
  btnDangerText: { fontSize: 12.5, fontWeight: '600', color: colors.signalRed },
  speedGroup: { flexDirection: 'row', alignItems: 'center', gap: 6, marginLeft: 'auto' },
  speedLabel: { fontSize: 9, fontWeight: '700', letterSpacing: 1, color: colors.textMuted, marginRight: 2 },
  speedBtn: {
    backgroundColor: colors.bgBoard,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  speedActive: { borderColor: colors.railBlue, backgroundColor: 'rgba(79,143,232,0.15)' },
  speedText: { fontSize: 11.5, fontWeight: '600', color: colors.textSecondary },
  speedActiveText: { color: colors.railBlue },
  simTime: {
    marginTop: 10,
    fontSize: 11,
    color: colors.textMuted,
    fontFamily: fonts.mono,
  },
  simTimeValue: { color: colors.textBoard },
});