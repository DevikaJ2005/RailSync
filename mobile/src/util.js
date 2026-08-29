export function distanceKm(a, b) {
  const earthRadius = 6371;
  const lat = ((b.lat - a.lat) * Math.PI) / 180;
  const lng = ((b.lng - a.lng) * Math.PI) / 180;
  const value =
    Math.sin(lat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(lng / 2) ** 2;
  return earthRadius * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

export function getArrivalMinutes(train, station, stationsByName) {
  const stationIndex = train.route.indexOf(station);
  let minutes = 0;
  for (let index = train.route_index; index < stationIndex; index += 1) {
    const from = stationsByName[train.route[index]];
    const to = stationsByName[train.route[index + 1]];
    if (from && to) minutes += (distanceKm(from, to) / train.speed_kmph) * 60;
  }
  if (stationIndex === train.route_index + 1) minutes *= Math.max(0, 1 - train.progress);
  return Math.max(0, Math.round(minutes));
}

export function formatEta(value) {
  if (!value) return '—';
  const parsed = new Date(String(value).replace(' ', 'T'));
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

export function interpolate(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

export function interpolatePath(path, progress) {
  if (!path || path.length < 2) return null;
  const segmentLength = 1 / (path.length - 1);
  const segment = Math.min(path.length - 2, Math.floor(progress / segmentLength));
  const localProgress = (progress - segment * segmentLength) / segmentLength;
  return interpolate(path[segment], path[segment + 1], Math.max(0, Math.min(1, localProgress)));
}

export function buildStationsByName(network) {
  return Object.fromEntries((network?.stations || []).map((item) => [item.name, item]));
}

export function buildSectionsByKey(network) {
  return Object.fromEntries(
    (network?.sections || []).map((section) => [
      [section.from, section.to].sort().join('|'),
      section,
    ]),
  );
}

export function trainPositionOnNetwork(train, stationsByName, sectionsByKey) {
  const from = stationsByName[train.from];
  const to = stationsByName[train.to];
  if (!from || !to) return null;
  const section = sectionsByKey[[train.from, train.to].sort().join('|')];
  const sectionPath = section?.path || [
    [from.lat, from.lng],
    [to.lat, to.lng],
  ];
  const path = section?.from === train.from ? sectionPath : [...sectionPath].reverse();
  return interpolatePath(path, train.progress);
}