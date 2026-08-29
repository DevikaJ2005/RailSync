import AsyncStorage from '@react-native-async-storage/async-storage';

const TOKEN_KEY = 'railsync_auth_token';
const USER_KEY = 'railsync_auth_user';

export async function loadSession() {
  try {
    const token = await AsyncStorage.getItem(TOKEN_KEY);
    const rawUser = await AsyncStorage.getItem(USER_KEY);
    if (!token || !rawUser) return null;
    return { token, user: JSON.parse(rawUser) };
  } catch {
    await clearSession();
    return null;
  }
}

export async function saveSession(token, user) {
  await AsyncStorage.setItem(TOKEN_KEY, token);
  await AsyncStorage.setItem(USER_KEY, JSON.stringify(user));
}

export async function clearSession() {
  await AsyncStorage.multiRemove([TOKEN_KEY, USER_KEY]);
}

export const SAMPLE_CREDENTIALS = [
  {
    role: 'controller',
    username: 'controller',
    password: 'admin@123',
    label: 'Station Controller',
    hint: 'Full control: map, conflicts, approvals, overrides, what-if, analytics',
  },
  {
    role: 'passenger',
    username: 'passenger',
    password: 'pass@123',
    label: 'Passenger',
    hint: 'Read-only: live map, platform board, train search',
  },
];