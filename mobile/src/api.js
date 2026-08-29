import AsyncStorage from '@react-native-async-storage/async-storage';
import { loadApiUrl } from './config';

const TOKEN_KEY = 'railsync_auth_token';

let apiUrl = null;
let currentToken = null;
const unauthorizedListeners = new Set();

export async function initApi() {
  apiUrl = await loadApiUrl();
  try {
    currentToken = await AsyncStorage.getItem(TOKEN_KEY);
  } catch {
    currentToken = null;
  }
  return apiUrl;
}

export async function setToken(token) {
  currentToken = token;
  await AsyncStorage.setItem(TOKEN_KEY, token || '');
}

export function getToken() {
  return currentToken;
}

export function onUnauthorized(callback) {
  unauthorizedListeners.add(callback);
  return () => unauthorizedListeners.delete(callback);
}

function notifyUnauthorized() {
  unauthorizedListeners.forEach((callback) => callback());
}

function authHeaders() {
  return currentToken ? { Authorization: `Bearer ${currentToken}` } : {};
}

function wsBase() {
  if (!apiUrl) throw new Error('API client not initialized');
  return apiUrl.replace(/^http/, 'ws');
}

export function connectLiveSocket(onMessage, onStatusChange) {
  let socket;
  let reconnectTimer;
  let closed = false;

  const connect = () => {
    if (closed) return;
    socket = new WebSocket(`${wsBase()}/ws/live`);
    socket.onopen = () => onStatusChange?.(true);
    socket.onclose = () => {
      onStatusChange?.(false);
      if (!closed) reconnectTimer = setTimeout(connect, 2000);
    };
    socket.onerror = () => socket.close();
    socket.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch {
        // ignore malformed frame
      }
    };
  };

  connect();
  return {
    close: () => {
      closed = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    },
  };
}

export async function pingBackend() {
  if (!apiUrl) throw new Error('API client not initialized');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6000);
  try {
    const res = await fetch(apiUrl, { signal: controller.signal });
    const body = await res.json().catch(() => null);
    if (!res.ok) throw new Error(`backend replied with HTTP ${res.status}`);
    return { ok: true, detail: `status ${body?.status || 'ok'} · model ${body?.model_loaded ? 'loaded' : 'not loaded'}` };
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('no response within 6s — is the backend running?');
    }
    throw new Error('cannot reach backend (network request failed)');
  } finally {
    clearTimeout(timer);
  }
}

async function req(path, options = {}) {  if (!apiUrl) throw new Error('API client not initialized');
  const res = await fetch(`${apiUrl}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(options.headers || {}) },
    ...options,
  });
  if (res.status === 401) {
    await AsyncStorage.multiRemove([TOKEN_KEY, 'railsync_auth_user']);
    currentToken = null;
    notifyUnauthorized();
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status}) for ${path}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // non-JSON error body
    }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }
  return res.json();
}

export const api = {
  login: (username, password) =>
    req('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  getMe: () => req('/api/auth/me'),
  getNetwork: () => req('/api/network'),
  getState: () => req('/api/state'),
  getAnalytics: () => req('/api/analytics'),
  getLogs: (trainNo) => req(`/api/logs${trainNo ? `?train_no=${encodeURIComponent(trainNo)}` : ''}`),
  getModelInfo: () => req('/api/model-info'),
  whatIf: (trainNo, extraMinutes) =>
    req('/api/whatif', {
      method: 'POST',
      body: JSON.stringify({ train_no: trainNo, extra_delay_minutes: extraMinutes }),
    }),
  override: (trainNo, action, adminNote = '') =>
    req('/api/override', {
      method: 'POST',
      body: JSON.stringify({ train_no: trainNo, action, admin_note: adminNote }),
    }),
  approveDecision: (decisionId, approved = true, controllerNote = '') =>
    req('/api/decisions/approve', {
      method: 'POST',
      body: JSON.stringify({ decision_id: decisionId, approved, controller_note: controllerNote }),
    }),
  pauseSimulation: () => req('/api/simulation/pause', { method: 'POST' }),
  resumeSimulation: () => req('/api/simulation/resume', { method: 'POST' }),
  resetSimulation: () => req('/api/simulation/reset', { method: 'POST' }),
  setSpeed: (multiplier) =>
    req('/api/simulation/speed', {
      method: 'POST',
      body: JSON.stringify({ multiplier }),
    }),
};