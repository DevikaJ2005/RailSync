import React, { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { initApi, api, setToken, connectLiveSocket, onUnauthorized } from './src/api';
import { loadSession, saveSession, clearSession } from './src/auth';
import { saveApiUrl } from './src/config';
import LoginScreen from './src/screens/LoginScreen';
import HomeScreen from './src/screens/HomeScreen';
import { colors } from './src/theme';

export default function App() {
  const [booting, setBooting] = useState(true);
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [loginError, setLoginError] = useState('');
  const [serverUrl, setServerUrl] = useState('');
  const [liveState, setLiveState] = useState(null);
  const [network, setNetwork] = useState(null);
  const [networkError, setNetworkError] = useState('');
  const [connected, setConnected] = useState(false);
  const [modelInfo, setModelInfo] = useState(null);

  useEffect(() => {
    const boot = async () => {
      const url = await initApi();
      setServerUrl(url);
      const session = await loadSession();
      if (session) {
        setToken(session.token);
        try {
          const payload = await api.getMe();
          setUser({ ...session.user, ...payload });
        } catch {
          await clearSession();
        }
      }
      setAuthLoading(false);
      setBooting(false);
    };
    boot();
  }, []);

  useEffect(() => {
    const off = onUnauthorized(() => setUser(null));
    return off;
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const loadNetwork = () => {
      api
        .getNetwork()
        .then((data) => {
          if (!cancelled) {
            setNetwork(data);
            setNetworkError('');
          }
        })
        .catch((error) => {
          if (!cancelled) setNetworkError(error.message);
        });
    };
    loadNetwork();
    api.getModelInfo().then(setModelInfo).catch(() => {});
    const retryTimer = setInterval(loadNetwork, 3000);
    const ws = connectLiveSocket(setLiveState, setConnected);
    return () => {
      cancelled = true;
      clearInterval(retryTimer);
      ws.close();
    };
  }, [user]);

  const handleLogin = async (username, password) => {
    setLoginError('');
    try {
      const url = await saveApiUrl(serverUrl);
      await initApi();
      setServerUrl(url);
      const { token, user: loggedInUser } = await api.login(username, password);
      await setToken(token);
      await saveSession(token, loggedInUser);
      setUser(loggedInUser);
    } catch (error) {
      setLoginError(error.message);
    }
  };

  const handleLogout = async () => {
    await clearSession();
    setToken(null);
    setUser(null);
    setLiveState(null);
    setNetwork(null);
  };

  if (booting || authLoading) {
    return (
      <SafeAreaProvider>
        <View style={styles.loading}>
          <ActivityIndicator color={colors.railBlue} />
          <Text style={styles.loadingText}>Restoring session…</Text>
        </View>
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <SafeAreaView style={styles.safe} edges={['top', 'left', 'right']}>
        {!user ? (
          <LoginScreen
            onLogin={handleLogin}
            error={loginError}
            serverUrl={serverUrl}
            onServerChange={setServerUrl}
          />
        ) : (
          <HomeScreen
            user={user}
            liveState={liveState}
            network={network}
            networkError={networkError}
            connected={connected}
            modelInfo={modelInfo}
            onLogout={handleLogout}
            serverUrl={serverUrl}
          />
        )}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.bgVoid,
  },
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bgVoid,
    gap: 12,
  },
  loadingText: {
    color: colors.textMuted,
    fontSize: 13,
  },
});