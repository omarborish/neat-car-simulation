import * as preferences from './preferences.js';
import {createRenderer, preview} from './renderer.js';
const $ = id => document.getElementById(id);
const renderer=createRenderer($('track'));
const appearance=preferences.load();
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
const camera={zoom:appearance.cameraZoom,follow:appearance.cameraMode==='follow',receivedAt:0,interval:50};
let restoreAppearance=true;
const defaults={max_speed:18,steering_step:5,sensor_range:300,population:30,seed:7,episode_steps:1200,road_width:120};
let current=null,previous=null,catalog=null,socket=null,retry=null,stopped=false,busy=false,dirty=false,catalogPromise=null;
const form=$('settings-form');
const number=value=>value==null ? '—' : Number(value).toLocaleString(undefined,{maximumFractionDigits:1});
function message(text,error=false) { $('message').textContent=text; $('message').hidden=!text; $('message').setAttribute('role',error?'alert':'status'); }
function connection(text,connected=false) { $('connection').textContent=text; $('connection').classList.toggle('connected',connected); }
function controlAvailability() {
  document.querySelectorAll('[data-command-control],.track-choice').forEach(el=>el.disabled=busy||!current||socket?.readyState!==WebSocket.OPEN);
}
function fillDraft(settings) { for (const [name,value] of Object.entries(settings)) form.elements[name].value=value; dirty=false; draftStatus(); }
function draftStatus() { $('draft-status').textContent=dirty ? 'Draft changes. Apply to start a fresh training session.' : 'Values match the active session.'; }
function updateNotes(track) {
  const box=$('track-notes');box.replaceChildren();
  const add=text=>{const p=document.createElement('p');p.textContent=text;box.append(p);};
  if (track.kind==='vector') {
    add(track.description);add(track.schematic_adjustments);
    add(`Reference: ${track.reference.layout}, ${track.reference.year}; ${track.reference.length_km} km, ${track.reference.turns} turns, ${track.direction}. Simulation world: 1920 × 1080 units.`);
    add('Circuit studies start with live training when no compatible driver is saved. No GP lap champion is bundled. Fitness rewards ordered checkpoint progress in simulation units; compare scores only on the same track and preset.');
    const a=document.createElement('a');a.href=track.reference.source_url;a.target='_blank';a.rel='noreferrer';a.textContent='Circuit reference (opens online)';box.append(a);
  } else add('Original bitmap circuit. Fitness measures distance travelled. Road width and road styling apply only to the circuit studies.');
}
function accept(snapshot) {
  if (!snapshot || snapshot.schema_version!==1) return;
  const old=current;
  previous=old;current=snapshot;
  camera.interval=Math.min(200,Math.max(16,performance.now()-camera.receivedAt));camera.receivedAt=performance.now();
  if (!dirty) fillDraft(current.settings);
  const track=catalog?.tracks.find(t=>t.id===current.track_id);
  $('track-title').textContent=track?.name||current.track_id;
  $('session-status').textContent=`${current.paused?'Paused · ':''}${current.mode==='train'?'Training':'Replay'}`;
  $('provenance').textContent=current.replay ? `${current.replay.transfer?'Transfer test from':'Driver trained on'} ${current.replay.training_track_id} · ${current.replay.source} driver · generation ${current.replay.generation}` : 'Live evolution · a new population learns this track';
  $('pause').textContent=current.paused?'Resume':'Pause';
  $('replay').setAttribute('aria-pressed',current.mode==='replay');$('train').setAttribute('aria-pressed',current.mode==='train');
  $('speed').value=current.speed_multiplier;$('car-color').value=current.appearance.color;$('sensors').checked=current.appearance.sensors;
  $('generation').textContent=current.generation;$('alive').textContent=`${current.alive} / ${current.population}`;
  $('fitness').textContent=number(current.fitness.current);$('saved').textContent=number(current.fitness.saved);$('laps').textContent=current.laps;
  $('saved-label').textContent=current.replay?.transfer ? 'Source driver fitness' : 'Saved fitness';
  $('saved').title=current.replay?.transfer ? `Measured on ${current.replay.training_track_id}; not comparable with this track’s fitness.` : 'Saved fitness for the active driver or compatible experiment.';
  $('rate').textContent=number(current.effective_step_rate);$('rate').title=`Requested: ${current.step_rate} steps/s. Measured throughput depends on this computer.`;
  $('applied-settings').textContent=`Applied: speed ${current.settings.max_speed}, steering ${current.settings.steering_step}°, sensors ${current.settings.sensor_range}, width ${current.settings.road_width}; ${current.settings.population} cars, seed ${current.settings.seed}, ${current.settings.episode_steps} steps.`;
  document.querySelectorAll('.track-choice').forEach(el=>el.setAttribute('aria-pressed',el.dataset.track===current.track_id));
  if (track && (!old || old.track_id!==current.track_id)) updateNotes(track);
  const sensors=$('sensor-readings');sensors.replaceChildren();
  (current.leader?.inputs||[]).forEach((value,i)=>{const label=document.createElement('label');label.textContent=`${[-90,-45,0,45,90][i]}°  ${value.toFixed(2)}`;const meter=document.createElement('meter');meter.min=0;meter.max=1;meter.value=value;label.append(meter);sensors.append(label);});
  $('action').textContent=current.leader ? `Chosen action: ${['turn left','turn right','slow down','speed up'][current.leader.action]}. Leader car ${current.leader.id+1}.` : 'Waiting for a car.';
  if (catalog && catalog.road_width!==current.settings.road_width) refreshCatalog().catch(error=>message(error.message,true));
  controlAvailability();
}
function buildTracks() {
  const box=$('tracks');const wasOpen=box.querySelector('details')?.open;box.replaceChildren();
  for (const kind of ['vector','bitmap']) {
    const group=document.createElement(kind==='bitmap'?'details':'div');
    const title=document.createElement(kind==='bitmap'?'summary':'h3');title.textContent=kind==='vector'?'Circuit studies':'Original tracks';group.append(title);
    if (kind==='bitmap') group.open=wasOpen??true;
    const grid=document.createElement('div');grid.className='track-grid';
    for (const track of catalog.tracks.filter(t=>t.kind===kind)) {
      const button=document.createElement('button');button.className='track-choice';button.dataset.track=track.id;
      button.setAttribute('aria-pressed',track.id===current?.track_id);button.title=track.kind==='vector'?'Original schematic · train unless a compatible driver is saved':track.name;
      const canvas=document.createElement('canvas');canvas.setAttribute('aria-hidden','true');const name=document.createElement('span');name.textContent=track.name.replace(' GP circuit study','');
      button.append(canvas,name);button.addEventListener('click',()=>command('start',{track_id:track.id}));grid.append(button);preview(canvas,track,appearance);
    }
    group.append(grid);box.append(group);
  }
  controlAvailability();
}
async function refreshCatalog() {
  if (catalogPromise) return catalogPromise;
  catalogPromise=(async()=>{const response=await fetch('/api/catalog');if(!response.ok)throw new Error('Track catalog is not ready. Reconnecting…');catalog=await response.json();renderer.setCatalog(catalog);buildTracks();const track=catalog.tracks.find(t=>t.id===current?.track_id);if(track){$('track-title').textContent=track.name;updateNotes(track);}})();
  try {await catalogPromise;} finally {catalogPromise=null;}
}
async function command(name,fields={}) {
  if (busy || !current || socket?.readyState!==WebSocket.OPEN) return false;
  busy=true;controlAvailability();message('');$('restore').hidden=true;
  try {
    const response=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:name,...fields})});
    const result=await response.json();
    if(result.snapshot) accept(result.snapshot);
    if(!response.ok||!result.ok){message(result.error||'The command could not be applied.',true);$('restore').hidden=!result.compatible_settings;return false;}
    if(name==='apply_settings'||name==='restore_compatible'){fillDraft(result.snapshot.settings);await refreshCatalog();message(name==='apply_settings'?'Settings applied. A new training session has started.':'Compatible preset restored. Replay has started.');}
    return true;
  } catch(error) {message(`Connection interrupted. The server may have received the command. Reconnect to check the active session. ${error.message}`,true);return false;}
  finally {busy=false;controlAvailability();if(current){$('speed').value=current.speed_multiplier;$('car-color').value=current.appearance.color;$('sensors').checked=current.appearance.sensors;}}
}
async function connect() {
  if(stopped)return;clearTimeout(retry);connection('Connecting…');
  try {
    await refreshCatalog();
    const response=await fetch('/api/state');if(!response.ok)throw new Error('Session is starting');accept(await response.json());
    socket=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`);
    socket.onopen=()=>{
      connection('Connected',true);message('');controlAvailability();
      // Restore once per page, never from accept(): snapshots and command acks
      // must not reassert preferences or create a command/ack feedback loop.
      if(restoreAppearance){restoreAppearance=false;
        if(current.appearance.color!==appearance.color || current.appearance.sensors!==appearance.sensors)
          command('appearance',{color:appearance.color,sensors:appearance.sensors});
      }
    };
    socket.onmessage=event=>{try{accept(JSON.parse(event.data));}catch{message('A session update could not be read.',true);}};
    socket.onclose=()=>{controlAvailability();if(!stopped){connection('Reconnecting…');retry=setTimeout(connect,1500);}};
    socket.onerror=()=>socket.close();
  } catch {connection('Waiting for local server…');retry=setTimeout(connect,1500);}
}
const visualFields={'custom-color':'customColor','custom-enabled':'useCustomColor',accent:'accent',surroundings:'surroundings',road:'road',kerbs:'kerbs',checkpoints:'checkpoints','turn-numbers':'turnNumbers','sector-colors':'sectorColors',trails:'trails','sensor-opacity':'sensorOpacity','trail-opacity':'trailOpacity'};
function updateCamera(){
  $('zoom-value').textContent=`${camera.zoom.toFixed(1)}×`;$('follow').setAttribute('aria-pressed',camera.follow);
  appearance.cameraMode=camera.follow?'follow':'fit';appearance.cameraZoom=camera.zoom;preferences.save(appearance);
}
function visualControls(){for(const [id,key] of Object.entries(visualFields)){if(typeof appearance[key]==='boolean')$(id).checked=appearance[key];else $(id).value=appearance[key];}updateVisualStyle();}
function updateVisualStyle(){document.documentElement.style.setProperty('--accent',appearance.accent);for(const name of ['sensor','trail'])$(`${name}-opacity-value`).textContent=`${Math.round(appearance[`${name}Opacity`]*100)}%`;}
function saveVisuals(){preferences.save(appearance);updateVisualStyle();if(catalog)buildTracks();}
for(const [id,key] of Object.entries(visualFields)){$(id).addEventListener('input',()=>{appearance[key]=$(id).type==='checkbox'?$(id).checked:$(id).type==='range'?Number($(id).value):$(id).value;saveVisuals();});}
async function serverAppearance(fields){if(await command('appearance',fields)){Object.assign(appearance,fields);preferences.save(appearance);}}
$('reset-appearance').onclick=async()=>{Object.assign(appearance,preferences.defaults);camera.zoom=appearance.cameraZoom;camera.follow=false;updateCamera();visualControls();saveVisuals();await serverAppearance({color:appearance.color,sensors:appearance.sensors});};
$('car-color').onchange=()=>serverAppearance({color:$('car-color').value});$('sensors').onchange=()=>serverAppearance({sensors:$('sensors').checked});
$('replay').onclick=()=>command('start',{mode:'replay'});$('train').onclick=()=>command('start',{mode:'train'});
$('pause').onclick=()=>command(current?.paused?'resume':'pause');$('restart').onclick=()=>command('restart');$('speed').onchange=()=>command('speed',{multiplier:Number($('speed').value)});
$('transfer').onclick=()=>command('transfer_test');$('restore').onclick=()=>command('restore_compatible');
form.addEventListener('input',()=>{dirty=true;draftStatus();});
form.addEventListener('submit',event=>{event.preventDefault();const settings=Object.fromEntries(Object.keys(defaults).map(name=>[name,Number(form.elements[name].value)]));command('apply_settings',{settings});});
$('reset-settings').onclick=()=>{fillDraft(defaults);dirty=true;draftStatus();};
$('fit').onclick=()=>{camera.zoom=1;camera.follow=false;updateCamera();};$('zoom-in').onclick=()=>{camera.zoom=Math.min(4,camera.zoom+.25);updateCamera();};$('zoom-out').onclick=()=>{camera.zoom=Math.max(1,camera.zoom-.25);updateCamera();};$('follow').onclick=()=>{camera.follow=!camera.follow;if(camera.follow)camera.zoom=Math.max(2,camera.zoom);updateCamera();};
$('presentation').onclick=()=>{document.body.classList.toggle('presentation');$('presentation').setAttribute('aria-pressed',document.body.classList.contains('presentation'));};
$('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{message('Fullscreen is unavailable in this browser. Presentation mode is still available.');}};
document.addEventListener('fullscreenchange',()=>{$('fullscreen').textContent=document.fullscreenElement?'Exit fullscreen':'Fullscreen';});
$('stop').onclick=async()=>{if(busy||stopped)return;busy=true;controlAvailability();try{const response=await fetch('/api/shutdown',{method:'POST'});if(!response.ok)throw new Error('Stop request failed');stopped=true;clearTimeout(retry);socket?.close();connection('Server stopped');message('Server stopped. You can close this tab.');$('stop').disabled=true;}catch(error){message(error.message,true);}finally{busy=false;controlAvailability();}};
document.addEventListener('keydown',event=>{if(event.repeat||event.ctrlKey||event.metaKey||event.altKey||event.target.closest('input,select,textarea,button,summary,a,[contenteditable]'))return;const key=event.key.toLowerCase();const id={' ':'pause',r:'restart',f:'fit',p:'presentation'}[key];if(id){event.preventDefault();$(id).click();}});
function frame(){renderer.draw(current,previous,{...appearance,reducedMotion:reducedMotion.matches},camera);requestAnimationFrame(frame);}
visualControls();updateCamera();controlAvailability();connect();requestAnimationFrame(frame);
