// Browser persistence contains appearance only; experiment values belong to the server.
export const defaults = Object.freeze({customColor: '#70b3d7', useCustomColor: false,
  accent: '#70b3d7', surroundings: '#526d5b', road: '#3b3e42', kerbs: true,
  checkpoints: false, turnNumbers: true, sectorColors: true, trails: false,
  sensorOpacity: 1, trailOpacity: .5, color: 'mixed', sensors: true,
  cameraMode: 'fit', cameraZoom: 1});
const key = 'neat-car-appearance-v1';
const colors = ['mixed','red','green','blue','yellow','orange','pink','purple'];
export function sanitize(value) {
  const result = {...defaults};
  if (!value || typeof value !== 'object' || Array.isArray(value)) return result;
  for (const name of Object.keys(defaults)) {
    if (typeof defaults[name] === 'boolean' && typeof value[name] === 'boolean') result[name] = value[name];
    if (typeof defaults[name] === 'string' && defaults[name].startsWith('#') && typeof value[name] === 'string' && /^#[0-9a-f]{6}$/i.test(value[name])) result[name] = value[name];
  }
  // Migrate the former combined label toggle only where a new choice is absent.
  for (const name of ['turnNumbers','sectorColors']) {
    if (!(name in value) && typeof value.labels === 'boolean') result[name] = value.labels;
  }
  if (colors.includes(value.color)) result.color = value.color;
  if (['fit','follow'].includes(value.cameraMode)) result.cameraMode = value.cameraMode;
  for (const [name,min,max] of [['sensorOpacity',0,1],['trailOpacity',0,1],['cameraZoom',1,4]]) {
    if (Number.isFinite(value[name]) && value[name]>=min && value[name]<=max) result[name]=value[name];
  }
  return result;
}
export function load() {
  try { return sanitize(JSON.parse(localStorage.getItem(key))); } catch { return {...defaults}; }
}
export function save(appearance) {
  try { localStorage.setItem(key, JSON.stringify(sanitize(appearance))); } catch { /* Session still works without storage. */ }
}
