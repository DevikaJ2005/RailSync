import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const OVERRIDE_KEY = 'railsync_server_url';
const DEFAULT_PORT = 8000;

function hostFromExpo() {
  const hostUri =
    Constants.expoConfig?.hostUri ||
    Constants.expoGoConfig?.debuggerHost ||
    Constants.manifest2?.extra?.expoGo?.debuggerHost ||
    '';
  const host = hostUri.split(':')[0];
  return host || '';
}

export function defaultApiUrl() {
  const host = hostFromExpo();
  if (host) return `http://${host}:${DEFAULT_PORT}`;
  return Platform.OS === 'android' ? `http://10.0.2.2:${DEFAULT_PORT}` : `http://127.0.0.1:${DEFAULT_PORT}`;
}

export async function loadApiUrl() {
  try {
    const saved = await AsyncStorage.getItem(OVERRIDE_KEY);
    if (saved && saved.trim()) return saved.trim().replace(/\/+$/, '');
  } catch {
    // fall through to default
  }
  return defaultApiUrl();
}

export async function saveApiUrl(url) {
  const normalized = (url || '').trim().replace(/\/+$/, '');
  await AsyncStorage.setItem(OVERRIDE_KEY, normalized);
  return normalized;
}