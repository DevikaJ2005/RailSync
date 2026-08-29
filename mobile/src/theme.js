export const colors = {
  bgVoid: '#0A0E14',
  bgPanel: '#10151D',
  bgPanelRaised: '#161C26',
  bgBoard: '#0D1117',
  lineSteel: '#232B38',
  lineSteelBright: '#2F3A4A',

  signalGreen: '#3FA66B',
  signalGreenGlow: 'rgba(63, 166, 107, 0.35)',
  signalAmber: '#E8A23D',
  signalAmberGlow: 'rgba(232, 162, 61, 0.35)',
  signalRed: '#D64545',
  signalRedGlow: 'rgba(214, 69, 69, 0.35)',
  railBlue: '#4F8FE8',
  railBlueGlow: 'rgba(79, 143, 232, 0.3)',

  textPrimary: '#E7EBF0',
  textSecondary: '#A7B0BE',
  textMuted: '#6B7787',
  textBoard: '#F0A94E',
};

export const fonts = {
  display: 'System',
  body: 'System',
  mono: 'monospace',
};

export const STATUS_COLOR = {
  moving: colors.railBlue,
  waiting: colors.signalAmber,
  held: colors.signalRed,
  checking: colors.signalAmber,
  at_platform: colors.signalGreen,
  completed: colors.textMuted,
};

export const STATUS_LABEL = {
  moving: 'Moving',
  waiting: 'Waiting',
  held: 'Held',
  checking: 'Checking',
  at_platform: 'At platform',
  completed: 'Completed',
};

export function statusColor(status) {
  return STATUS_COLOR[status] || colors.railBlue;
}

export function statusLabel(status) {
  return STATUS_LABEL[status] || String(status || '').replace('_', ' ');
}