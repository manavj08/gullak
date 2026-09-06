const KEY = 'gullak_settings';

function readAll() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}');
  } catch {
    return {};
  }
}

export function getSetting(key, fallback) {
  const all = readAll();
  return key in all ? all[key] : fallback;
}

export function setSetting(key, value) {
  const all = readAll();
  all[key] = value;
  localStorage.setItem(KEY, JSON.stringify(all));
}
