// Display dimensions and sprite anchor are independent from the fixed physics footprint.
export const carVisual = Object.freeze({displayLength: 60, displayWidth: 30,
  anchor: [0.5, 0.5], headingOffset: 0, collisionLength: 60, collisionWidth: 30});
const images = new Map();
const sprites = new Map();
function imageFor(url) {
  if (!images.has(url)) { const image = new Image(); image.src = url; images.set(url, image); }
  return images.get(url);
}
function sprite(color, custom) {
  const key = custom || color;
  if (sprites.has(key)) return sprites.get(key);
  const image = imageFor(`/assets/cars/car${custom ? 'red' : color}.png`);
  if (!image.complete || !image.naturalWidth) return null;
  const canvas = document.createElement('canvas'); canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
  const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, 0);
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const rgb = custom && [1, 3, 5].map(i => parseInt(custom.slice(i, i + 2), 16));
  for (let i = 0; i < pixels.data.length; i += 4) {
    const [r,g,b] = pixels.data.slice(i,i+3);
    if (r === 0 && g === 0 && b === 0) pixels.data[i + 3] = 0;
    else if (rgb && r > g * 1.5 && r > b * 1.5) {
      for (let j = 0; j < 3; j++) pixels.data[i+j] = rgb[j] * r / 255;
    }
  }
  ctx.putImageData(pixels, 0, 0);
  // Bound the optional custom-color cache while the native color picker is dragged.
  if (sprites.size > 16) sprites.clear();
  sprites.set(key, canvas); return canvas;
}
function path(ctx, points) {
  ctx.beginPath(); points.forEach(([x,y], i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
}
function road(ctx, track, appearance, preview = false) {
  if (track.kind === 'bitmap') {
    const image = imageFor(track.image);
    if (image.complete && image.naturalWidth) ctx.drawImage(image, 0, 0, 1920, 1080);
    return;
  }
  const geometry = track.geometry;
  ctx.fillStyle = appearance.surroundings; ctx.fillRect(0,0,1920,1080);
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  path(ctx, geometry.centerline);
  if (appearance.kerbs) {
    ctx.strokeStyle = '#dddcd2'; ctx.lineWidth = geometry.road_width + 16; ctx.stroke();
    ctx.setLineDash([26,26]); ctx.strokeStyle = '#aa5157'; ctx.stroke(); ctx.setLineDash([]);
  }
  ctx.strokeStyle = appearance.road; ctx.lineWidth = geometry.road_width; ctx.stroke();
  const gate = geometry.gates[0];
  path(ctx, [gate.a,gate.b]); ctx.lineCap = 'butt'; ctx.strokeStyle = '#eef2f5'; ctx.lineWidth = 8; ctx.stroke();
  ctx.setLineDash([8,8]); ctx.strokeStyle = '#202a35'; ctx.stroke(); ctx.setLineDash([]);
  if (!preview && appearance.sectorColors) {
    // Boundaries reference the exact sampled centerline; narrow colored lines
    // decorate its center without changing the asphalt width or collision mask.
    const points=geometry.centerline;
    const boundaries=geometry.sectors.map(sector=>points.reduce((best,p,i)=>
      Math.hypot(p[0]-sector.position[0],p[1]-sector.position[1]) < Math.hypot(points[best][0]-sector.position[0],points[best][1]-sector.position[1]) ? i : best,0));
    geometry.sectors.forEach((sector,i)=>{
      const start=boundaries[i], end=boundaries[(i+1)%boundaries.length];
      const segment=end>start ? points.slice(start,end+1) : [...points.slice(start),...points.slice(1,end+1)];
      ctx.strokeStyle=['#db888e','#dccb7d','#83bce0'][i%3];ctx.lineWidth=5;path(ctx,segment);ctx.stroke();
      ctx.fillStyle=ctx.strokeStyle;ctx.font='bold 19px "Segoe UI", sans-serif';ctx.textAlign='center';
      ctx.fillText(`S${sector.number}`,sector.position[0],sector.position[1]-geometry.road_width/2-28);
    });
  }
  if (!preview && appearance.checkpoints) {
    ctx.strokeStyle=appearance.accent;ctx.lineWidth=2;ctx.setLineDash([7,7]);
    geometry.gates.forEach((gate,i)=>{
      path(ctx,[gate.a,gate.b]);ctx.stroke();
      ctx.fillStyle=appearance.accent;ctx.font='13px "Segoe UI", sans-serif';ctx.textAlign='center';
      ctx.fillText(`G${i+1}`,gate.a[0],gate.a[1]-8);
    });
    ctx.setLineDash([]);
  }
  if (!preview && appearance.turnNumbers) {
    ctx.font = '17px "Segoe UI", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (const turn of geometry.turns) {
      const [x,y] = turn.position; ctx.fillStyle = '#202a35'; ctx.beginPath(); ctx.arc(x,y,13,0,Math.PI*2); ctx.fill();
      ctx.fillStyle = '#eef2f5'; ctx.fillText(turn.number,x,y);
    }
  }
}
export function preview(canvas, track, appearance) {
  canvas.width = 240; canvas.height = 135;
  const ctx = canvas.getContext('2d'); ctx.scale(1/8,1/8); road(ctx,track,appearance,true);
  if (track.kind === 'bitmap') {
    const image = imageFor(track.image);
    if (!image.complete) image.addEventListener('load', () => preview(canvas,track,appearance), {once:true});
  }
}
export function createRenderer(canvas) {
  const ctx = canvas.getContext('2d');
  let tracks = new Map(), trail = [], episode = null, trailSnapshot = null, trailLeader = null;
  return {
    setCatalog(catalog) { tracks = new Map(catalog.tracks.map(t => [t.id,t])); },
    draw(snapshot, previousSnapshot, appearance, camera) {
      const bounds = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
      const width = Math.round(bounds.width*dpr), height = Math.round(bounds.height*dpr);
      if (canvas.width !== width || canvas.height !== height) { canvas.width=width; canvas.height=height; }
      ctx.setTransform(dpr,0,0,dpr,0,0); ctx.fillStyle='#18211d'; ctx.fillRect(0,0,bounds.width,bounds.height);
      if (!snapshot || !tracks.has(snapshot.track_id)) return;
      const track=tracks.get(snapshot.track_id);
      if (track.kind === 'vector' && track.geometry.road_width !== snapshot.settings.road_width) return;
      const sameEpisode = previousSnapshot && previousSnapshot.session_id===snapshot.session_id && previousSnapshot.episode_id===snapshot.episode_id;
      const alpha = appearance.reducedMotion || snapshot.paused || !sameEpisode ? 1 : Math.min(1,(performance.now()-camera.receivedAt)/Math.max(16,camera.interval));
      const oldCars = new Map((sameEpisode ? previousSnapshot.cars : []).map(c=>[c.id,c]));
      const matchingLeader=sameEpisode && previousSnapshot.leader?.id===snapshot.leader?.id;
      const cars=snapshot.cars.map(car=>{
        // A handoff has no earlier rays for the new leader: use its complete
        // current pose and endpoints together (also valid paused/reduced-motion).
        const old=oldCars.get(car.id); if (!old || alpha===1 || (car.id===snapshot.leader?.id && !matchingLeader)) return car;
        const angle=((car.angle-old.angle+540)%360)-180;
        return {...car,position:car.position.map((p,i)=>old.position[i]+(p-old.position[i])*alpha),angle:old.angle+angle*alpha};
      });
      const leader=cars.find(c=>c.id===snapshot.leader?.id);
      const scale=Math.min(bounds.width/1920,bounds.height/1080)*camera.zoom;
      const center=camera.follow && leader ? leader.position : [960,540];
      ctx.translate(bounds.width/2,bounds.height/2); ctx.scale(scale,scale); ctx.translate(-center[0],-center[1]);
      road(ctx,track,appearance);
      const key=`${snapshot.session_id}/${snapshot.episode_id}`;
      if (episode!==key || trailLeader!==snapshot.leader?.id || appearance.reducedMotion || !appearance.trails) { trail=[];episode=key;trailSnapshot=null; }
      trailLeader=snapshot.leader?.id;
      if (appearance.trails && !appearance.reducedMotion && leader && trailSnapshot!==snapshot) {
        trail.push(leader.position); trail=trail.slice(-80); trailSnapshot=snapshot;
      }
      if (trail.length>1) { ctx.save();ctx.globalAlpha=appearance.trailOpacity;path(ctx,trail);ctx.lineWidth=3/scale;ctx.strokeStyle=appearance.accent;ctx.stroke();ctx.restore(); }
      if (snapshot.appearance.sensors && leader) {
        ctx.save();ctx.globalAlpha=appearance.sensorOpacity;
        const oldLeader=sameEpisode && previousSnapshot.leader?.id===snapshot.leader.id ? previousSnapshot.leader : null;
        snapshot.leader.sensors.forEach((sensor,i)=>{
          const previous=oldLeader?.sensors[i]?.end;
          const end=previous ? sensor.end.map((p,j)=>previous[j]+(p-previous[j])*alpha) : sensor.end;
          path(ctx,[leader.position,end]);ctx.lineWidth=1.3/scale;ctx.strokeStyle='#a4ebce';ctx.stroke();
          ctx.fillStyle='#eef2f5';ctx.beginPath();ctx.arc(end[0],end[1],2.5/scale,0,Math.PI*2);ctx.fill();
        });
        ctx.restore();
      }
      for (const car of cars) {
        const image=sprite(car.color,appearance.useCustomColor ? appearance.customColor : null);
        ctx.save();ctx.translate(...car.position);ctx.rotate(-(car.angle+carVisual.headingOffset)*Math.PI/180);ctx.globalAlpha=car.alive ? 1 : .25;
        if (image) ctx.drawImage(image,-carVisual.displayLength*carVisual.anchor[0],-carVisual.displayWidth*carVisual.anchor[1],carVisual.displayLength,carVisual.displayWidth);
        ctx.restore();
      }
    }
  };
}
