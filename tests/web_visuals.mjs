// Run with Node; no packages or browser mutation needed for deterministic checks.
import assert from 'node:assert/strict';
import {defaults, sanitize, load, save} from '../web/preferences.js';
import {createRenderer} from '../web/renderer.js';

for (const value of [null, [], 'bad', 3]) assert.deepEqual(sanitize(value), defaults);
for (const value of [NaN, Infinity, -1, 2, '0.5', true]) {
  assert.equal(sanitize({sensorOpacity:value}).sensorOpacity, defaults.sensorOpacity);
  assert.equal(sanitize({trailOpacity:value}).trailOpacity, defaults.trailOpacity);
}
assert.deepEqual(sanitize({labels:false,turnNumbers:true}), {...defaults,turnNumbers:true,sectorColors:false});
assert.deepEqual(sanitize({color:'#ff0000',cameraMode:'unknown',cameraZoom:Infinity,accent:'red'}), defaults);
const custom={...defaults,color:'purple',sensors:false,accent:'#aBcDeF',sensorOpacity:0,trailOpacity:1,cameraMode:'follow',cameraZoom:2.25,checkpoints:true};
let stored;
globalThis.localStorage={getItem:()=>stored,setItem:(key,value)=>{stored=value;}};
save({...custom,population:100});assert.deepEqual(load(),custom);assert(!stored.includes('population'));
for (stored of ['{','null','[]','42']) assert.deepEqual(load(), defaults);
globalThis.localStorage={getItem(){throw Error('denied');},setItem(){throw Error('denied');}};
assert.deepEqual(load(),defaults);save(custom);

globalThis.window={devicePixelRatio:1};
globalThis.Image=class {complete=false;};
let strokes=[],texts=[],line=[],poses=[];
const state=[];
const ctx={globalAlpha:1,strokeStyle:'',lineWidth:1,
  beginPath(){line=[];},moveTo(x,y){line.push([x,y]);},lineTo(x,y){line.push([x,y]);},
  stroke(){strokes.push({points:line,style:this.strokeStyle,alpha:this.globalAlpha,width:this.lineWidth});},
  fillText(t){texts.push(String(t));},save(){state.push(this.globalAlpha);},restore(){this.globalAlpha=state.pop();},
  translate(x,y){poses.push([x,y]);},setTransform(){},fillRect(){},setLineDash(){},arc(){},fill(){},scale(){},rotate(){}
};
const canvas={getContext:()=>ctx,getBoundingClientRect:()=>({width:1920,height:1080})};
const renderer=createRenderer(canvas);
const geometry={centerline:[[0,0],[100,0],[100,100],[0,0]],road_width:90,
  gates:[{a:[0,-45],b:[0,45]},{a:[100,55],b:[100,145]}],
  turns:[{number:1,position:[100,0]}],sectors:[{number:1,position:[0,0]},{number:2,position:[100,0]},{number:3,position:[100,100]}]};
renderer.setCatalog({tracks:[{id:'test',kind:'vector',geometry}]});
const car=(id,x)=>({id,position:[x,50],angle:0,color:'red',alive:true});
const snap=(leader,x,episode='one')=>({session_id:'s',episode_id:episode,track_id:'test',settings:{road_width:90},paused:false,cars:[car(1,x),car(2,x+100)],leader:{id:leader,sensors:[{end:[x+200,50]}]},appearance:{sensors:true}});
const camera={zoom:1,follow:false,receivedAt:performance.now(),interval:10000};
const draw=(now,old,prefs)=>{strokes=[];texts=[];poses=[];renderer.draw(now,old,{...defaults,...prefs},camera);};
const before=snap(1,10), after=snap(2,30);
for(const enabled of ['checkpoints','turnNumbers','sectorColors']){
  draw(before,null,{checkpoints:false,turnNumbers:false,sectorColors:false,[enabled]:true});
  assert.equal(texts.some(t=>t.startsWith('G')),enabled==='checkpoints');
  assert.equal(texts.includes('1'),enabled==='turnNumbers');
  assert.equal(texts.some(t=>t.startsWith('S')),enabled==='sectorColors');
  const asphalt=strokes.find(s=>s.style===defaults.road);
  assert.equal(asphalt.width,geometry.road_width);assert.deepEqual(asphalt.points,geometry.centerline);
}
draw(before,null,{trails:true});draw(snap(1,20),before,{trails:true,trailOpacity:.25});
assert(strokes.some(s=>s.style===defaults.accent && s.alpha===.25));
for (const options of [{},{reducedMotion:true},{paused:true}]){
  draw({...after,paused:options.paused||false},before,{trails:true,sensorOpacity:.35,...options});
  const ray=strokes.find(s=>s.style==='#a4ebce');
  assert.deepEqual(ray.points,[[130,50],[230,50]]);assert.equal(ray.alpha,.35);
  assert(!strokes.some(s=>s.style===defaults.accent));
  assert(poses.some(p=>p[0]===130&&p[1]===50));
}
draw(snap(2,45,'two'),after,{trails:true});
assert(!strokes.some(s=>s.style===defaults.accent));
console.log('PASS preferences validation/migration/storage denial; independent overlays/exact asphalt; opacity; leader handoff and episode trail reset (normal, paused, reduced motion).');
