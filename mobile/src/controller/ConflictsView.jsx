import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { colors, fonts } from '../theme';
import { EmptyState, ActionMessage, Note, Badge, SplitFlapCell } from '../components/ui';
import { api } from '../api';

export default function ConflictsView({ liveState }) {
  const [updating, setUpdating] = useState(null);
  const [message, setMessage] = useState('');

  if (!liveState) return <EmptyState>Loading…</EmptyState>;

  const resolutions = liveState.resolutions || [];
  const trainsByNo = Object.fromEntries((liveState.trains || []).map((train) => [train.train_no, train]));
  const controllerHolds = liveState.controller_holds || {};

  const handleApproval = async (decisionId, approved) => {
    setUpdating(`decision:${decisionId}`);
    setMessage('');
    try {
      await api.approveDecision(
        decisionId,
        approved,
        approved
          ? 'Controller approved the simulated rule-based recommendation and applied a hold.'
          : 'Controller rejected or released the simulated rule-based recommendation.',
      );
      setMessage(approved ? 'Controller hold applied.' : 'Recommendation released.');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setUpdating(null);
    }
  };

  const handleOverride = async (trainNo, action) => {
    setUpdating(`override:${trainNo}:${action}`);
    setMessage('');
    try {
      const result = await api.override(trainNo, action, `Controller override: ${action}`);
      setMessage(result.success ? `Override applied to ${trainNo}.` : result.error || 'Override could not be applied.');
    } catch (error) {
      setMessage(error.message);
    } finally {
      setUpdating(null);
    }
  };

  const manualHolds = Object.entries(controllerHolds)
    .filter(([_, hold]) => hold.manual)
    .map(([trainNo]) => trainNo);

  if (resolutions.length === 0 && manualHolds.length === 0) {
    return <EmptyState>No active simulated section conflicts right now.</EmptyState>;
  }

  return (
    <View>
      <Note>
        Delay values are model predictions. Conflict detection and recommendations use simulated
        operational rules; the controller remains in control.
      </Note>
      {message && <ActionMessage>{message}</ActionMessage>}
      {resolutions.map((resolution, index) => {
        const severity = resolution.severity === 'major' ? colors.signalRed : colors.signalAmber;
        return (
          <View key={resolution.decision_id || index} style={[styles.card, { borderLeftColor: severity }]}>
            <View style={styles.head}>
              <View style={styles.titleBlock}>
                <Text style={[styles.severity, resolution.severity === 'minor' && styles.severityMinor]}>
                  <Text style={styles.severityDot}>●</Text> {String(resolution.severity).toUpperCase()} CONFLICT
                </Text>
                <Text style={styles.section} numberOfLines={2}>{resolution.section}</Text>
              </View>
              <Badge
                tone={
                  resolution.approval_status === 'approved'
                    ? 'admin'
                    : resolution.approval_status === 'rejected'
                      ? 'danger'
                      : 'simulation'
                }
              >
                {resolution.approval_status === 'approved'
                  ? 'hold applied'
                  : resolution.approval_status === 'rejected'
                    ? 'released'
                    : 'simulation rule'}
              </Badge>
            </View>

            <View style={styles.winnerLine}>
              <Text style={{ color: colors.signalGreen }}>{resolution.winner_train} proceeds</Text>
              <Text style={{ color: colors.textMuted }}> / </Text>
              <Text style={{ color: colors.signalAmber }}>{resolution.held_trains.join(', ')} held</Text>
            </View>

            <View style={styles.impactGrid}>
              <View style={styles.impactCell}>
                <Text style={styles.impactLabel}>Risk</Text>
                <Text style={styles.impactValue}>{resolution.severity}</Text>
              </View>
              <View style={styles.impactCell}>
                <Text style={styles.impactLabel}>Trains</Text>
                <Text style={styles.impactValue}>{resolution.affected_trains}</Text>
              </View>
              <View style={styles.impactCell}>
                <Text style={styles.impactLabel}>Model delay</Text>
                <Text style={styles.impactValue}>{resolution.max_predicted_delay} min</Text>
              </View>
              <View style={styles.impactCell}>
                <Text style={styles.impactLabel}>Hold est.</Text>
                <Text style={styles.impactValue}>{resolution.estimated_hold_minutes} min</Text>
              </View>
            </View>

            <Text style={styles.reason}>{resolution.reason}</Text>
            <View style={styles.priorityNote}>
              <Text style={styles.priorityNoteText}>
                <Text style={styles.priorityNoteStrong}>Why this choice:</Text> express trains and
                more-delayed trains go first. Approving applies a simulated hold — the waiting train
                stops until the chosen train has passed.
              </Text>
            </View>

            <View style={styles.actions}>
              {resolution.approval_status === 'pending' && (
                <TouchableOpacity
                  style={[styles.btn, styles.btnSuccess]}
                  disabled={updating !== null}
                  onPress={() => handleApproval(resolution.decision_id, true)}
                >
                  {updating === `decision:${resolution.decision_id}` ? (
                    <ActivityIndicator color="#fff" size="small" />
                  ) : (
                    <Text style={styles.btnSuccessText}>Approve &amp; Apply Hold</Text>
                  )}
                </TouchableOpacity>
              )}
              {resolution.approval_status !== 'rejected' && (
                <TouchableOpacity
                  style={[styles.btn, styles.btnDanger]}
                  disabled={updating !== null}
                  onPress={() => handleApproval(resolution.decision_id, false)}
                >
                  {updating === `decision:${resolution.decision_id}` ? (
                    <ActivityIndicator color={colors.signalRed} size="small" />
                  ) : (
                    <Text style={styles.btnDangerText}>
                      {resolution.approval_status === 'approved' ? 'Release hold' : 'Reject'}
                    </Text>
                  )}
                </TouchableOpacity>
              )}

              {resolution.held_trains.map((trainNo) => {
                const train = trainsByNo[trainNo];
                const isManualHold = Boolean(controllerHolds[trainNo]?.manual);
                const canApplyManualHold = ['moving', 'checking'].includes(train?.status);
                if (!isManualHold && !canApplyManualHold) return null;
                const action = isManualHold ? 'release_manual_hold' : 'hold_train';
                return (
                  <TouchableOpacity
                    key={`${trainNo}:${action}`}
                    style={styles.btn}
                    disabled={updating !== null}
                    onPress={() => handleOverride(trainNo, action)}
                  >
                    {updating === `override:${trainNo}:${action}` ? (
                      <ActivityIndicator color={colors.textPrimary} size="small" />
                    ) : (
                      <Text style={styles.btnText}>
                        {isManualHold ? `Release manual hold: ${trainNo}` : `Manual hold: ${trainNo}`}
                      </Text>
                    )}
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        );
      })}

      {manualHolds.length > 0 && (
        <View style={{ marginTop: 16 }}>
          <Text style={styles.manualTitle}>Active Manual Holds</Text>
          {manualHolds.map((trainNo) => (
            <View key={trainNo} style={[styles.card, styles.manualCard]}>
              <Text style={styles.manualTrain}><Text style={{ color: colors.textPrimary, fontWeight: '700' }}>{trainNo}</Text> is manually held</Text>
              <TouchableOpacity
                style={styles.btn}
                disabled={updating !== null}
                onPress={() => handleOverride(trainNo, 'release_manual_hold')}
              >
                {updating === `override:${trainNo}:release_manual_hold` ? (
                  <ActivityIndicator color={colors.textPrimary} size="small" />
                ) : (
                  <Text style={styles.btnText}>Release manual hold</Text>
                )}
              </TouchableOpacity>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderLeftWidth: 3,
    borderRadius: 8,
    padding: 12,
    marginBottom: 10,
  },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 },
  titleBlock: { flex: 1 },
  severity: {
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    color: colors.signalRed,
    marginBottom: 3,
  },
  severityMinor: { color: colors.signalAmber },
  severityDot: { fontSize: 6 },
  section: { fontSize: 13, color: colors.textPrimary, lineHeight: 18 },
  winnerLine: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 6, fontSize: 12.5 },
  impactGrid: { flexDirection: 'row', gap: 6, marginTop: 10 },
  impactCell: {
    flex: 1,
    backgroundColor: colors.bgBoard,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 6,
    padding: 7,
  },
  impactLabel: { fontSize: 9.5, color: colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.4 },
  impactValue: { marginTop: 3, fontFamily: fonts.mono, fontSize: 11, color: colors.textPrimary },
  reason: { marginTop: 8, color: colors.textSecondary, fontSize: 12.5, lineHeight: 18 },
  priorityNote: {
    marginTop: 9,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.lineSteel,
  },
  priorityNoteText: { color: colors.textMuted, fontSize: 11, lineHeight: 16 },
  priorityNoteStrong: { color: colors.textSecondary },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 7, marginTop: 10 },
  btn: {
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 7,
    backgroundColor: colors.bgPanel,
    paddingHorizontal: 12,
    paddingVertical: 7,
    minHeight: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnSuccess: { backgroundColor: colors.signalGreen, borderColor: colors.signalGreen },
  btnDanger: { borderColor: colors.signalRed },
  btnText: { fontSize: 11.5, fontWeight: '600', color: colors.textPrimary },
  btnSuccessText: { fontSize: 11.5, fontWeight: '600', color: '#fff' },
  btnDangerText: { fontSize: 11.5, fontWeight: '600', color: colors.signalRed },
  manualTitle: { fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 10 },
  manualCard: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  manualTrain: { fontSize: 12, color: colors.textSecondary, flex: 1 },
});