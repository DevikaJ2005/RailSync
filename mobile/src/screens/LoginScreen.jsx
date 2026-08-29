import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { colors, fonts } from '../theme';
import { SAMPLE_CREDENTIALS } from '../auth';

export default function LoginScreen({ onLogin, error: serverError, serverUrl, onServerChange, onTestConnection }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [editingServer, setEditingServer] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const detail = await onTestConnection(serverUrl);
      setTestResult({ ok: true, text: detail });
    } catch (e) {
      setTestResult({ ok: false, text: e.message });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await onLogin(username.trim(), password);
    } finally {
      setSubmitting(false);
    }
  };

  const fill = (cred) => {
    setUsername(cred.username);
    setPassword(cred.password);
  };

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.card}>
          <Text style={styles.title}>RailSync Sign-In</Text>
          <Text style={styles.subtitle}>
            Role-based access to the simulated control room and passenger views.
          </Text>

          <View style={styles.form}>
            <Text style={styles.label}>Username</Text>
            <TextInput
              style={styles.input}
              value={username}
              onChangeText={setUsername}
              placeholder="controller or passenger"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
            />

            <View style={styles.serverRow}>
              <TouchableOpacity onPress={() => setEditingServer((v) => !v)}>
                <Text style={styles.serverToggle}>
                  {editingServer ? 'Hide server settings' : `Backend: ${serverUrl || 'auto'}`}
                </Text>
              </TouchableOpacity>
            </View>

            {editingServer && (
              <View style={styles.serverBox}>
                <Text style={styles.serverHint}>
                  Your phone must reach the backend on the same Wi-Fi. The default uses the Expo
                  development host on port 8000.
                </Text>
                <TextInput
                  style={styles.input}
                  value={serverUrl}
                  onChangeText={onServerChange}
                  placeholder="http://192.168.1.10:8000"
                  placeholderTextColor={colors.textMuted}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                />
                <View style={styles.testRow}>
                  <TouchableOpacity style={styles.testBtn} onPress={handleTest} disabled={testing}>
                    <Text style={styles.testBtnText}>{testing ? 'Testing…' : 'Test connection'}</Text>
                  </TouchableOpacity>
                  {testResult ? (
                    <Text style={[styles.testResult, testResult.ok ? styles.testOk : styles.testFail]}>
                      {testResult.ok ? '✓ ' : '✕ '}
                      {testResult.text}
                    </Text>
                  ) : null}
                </View>
              </View>
            )}

            {serverError ? <View style={styles.errorBox}><Text style={styles.errorText}>{serverError}</Text></View> : null}

            <TouchableOpacity
              style={[styles.submit, (!username || !password) && styles.submitDisabled]}
              onPress={handleSubmit}
              disabled={!username || !password || submitting}
            >
              <Text style={styles.submitText}>{submitting ? 'Signing in…' : 'Sign In'}</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.creds}>
            <Text style={styles.credsTitle}>Sample accounts</Text>
            {SAMPLE_CREDENTIALS.map((cred) => (
              <TouchableOpacity key={cred.role} style={styles.credCard} onPress={() => fill(cred)}>
                <View style={styles.credHeader}>
                  <View style={[styles.rolePill, cred.role === 'controller' ? styles.roleController : styles.rolePassenger]}>
                    <Text style={[styles.rolePillText, cred.role === 'controller' ? styles.roleControllerText : styles.rolePassengerText]}>
                      {cred.role}
                    </Text>
                  </View>
                  <Text style={styles.credLabel}>{cred.label}</Text>
                </View>
                <View style={styles.credLine}>
                  <Text style={styles.credMono}>{cred.username}</Text>
                  <Text style={styles.credSep}>/</Text>
                  <Text style={styles.credMono}>{cred.password}</Text>
                </View>
                <Text style={styles.credHint}>{cred.hint}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bgVoid,
  },
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 14,
    padding: 24,
  },
  title: {
    fontFamily: fonts.display,
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: 6,
    marginBottom: 18,
    lineHeight: 17,
  },
  form: { gap: 10 },
  label: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    color: colors.textSecondary,
  },
  input: {
    backgroundColor: colors.bgBoard,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 6,
    color: colors.textPrimary,
    fontSize: 13,
    paddingHorizontal: 11,
    paddingVertical: 9,
  },
  serverRow: { marginTop: 4 },
  serverToggle: {
    fontSize: 11,
    color: colors.railBlue,
    fontWeight: '600',
  },
  serverBox: {
    backgroundColor: colors.bgPanelRaised,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    padding: 10,
    gap: 8,
  },
  serverHint: {
    fontSize: 11,
    color: colors.textMuted,
    lineHeight: 15,
  },
  errorBox: {
    backgroundColor: colors.signalRedGlow,
    borderWidth: 1,
    borderColor: 'rgba(214, 69, 69, 0.5)',
    borderRadius: 7,
    padding: 9,
  },
  errorText: {
    fontSize: 12,
    color: colors.signalRed,
  },
  testRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flexWrap: 'wrap',
  },
  testBtn: {
    borderWidth: 1,
    borderColor: colors.railBlue,
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  testBtnText: { fontSize: 11.5, fontWeight: '600', color: colors.railBlue },
  testResult: { fontSize: 11, flexShrink: 1, flex: 1 },
  testOk: { color: colors.signalGreen },
  testFail: { color: colors.signalRed },
  submit: {
    marginTop: 4,
    backgroundColor: colors.railBlue,
    borderRadius: 7,
    paddingVertical: 11,
    alignItems: 'center',
  },
  submitDisabled: { opacity: 0.55 },
  submitText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#fff',
  },
  creds: {
    borderTopWidth: 1,
    borderTopColor: colors.lineSteel,
    marginTop: 18,
    paddingTop: 14,
  },
  credsTitle: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: colors.textMuted,
    marginBottom: 10,
  },
  credCard: {
    backgroundColor: colors.bgPanelRaised,
    borderWidth: 1,
    borderColor: colors.lineSteel,
    borderRadius: 9,
    padding: 12,
    marginBottom: 8,
  },
  credHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 7,
  },
  rolePill: {
    borderRadius: 5,
    paddingHorizontal: 9,
    paddingVertical: 3,
    borderWidth: 1,
  },
  roleController: {
    backgroundColor: 'rgba(232,162,61,0.15)',
    borderColor: 'rgba(232,162,61,0.4)',
  },
  rolePassenger: {
    backgroundColor: 'rgba(79,143,232,0.15)',
    borderColor: 'rgba(79,143,232,0.4)',
  },
  rolePillText: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  roleControllerText: { color: colors.signalAmber },
  rolePassengerText: { color: colors.railBlue },
  credLabel: {
    fontFamily: fonts.display,
    fontSize: 12.5,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  credLine: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  credMono: { fontFamily: fonts.mono, fontSize: 12, color: colors.textBoard },
  credSep: { color: colors.textMuted },
  credHint: { fontSize: 11, color: colors.textMuted, lineHeight: 15 },
});