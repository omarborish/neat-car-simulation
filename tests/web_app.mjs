// Narrow DOM/transport harness: test application restore/ack behavior, not layout.
import assert from 'node:assert/strict';
import {defaults} from '../web/preferences.js';
let stored=JSON.stringify({...defaults,color:'purple',sensors:false,cameraMode:'follow',cameraZoom:2.25});
globalThis.localStorage={getItem:()=>stored,setItem:(_,value)=>{stored=value;}};
const nodes=new Map();
function node(id=''){
  if(nodes.has(id))return nodes.get(id);
  const n={id,value:'',checked:false,hidden:false,textContent:'',style:{setProperty(){}},
    classList:{toggle(){},contains(){return false;}},attributes:{},events:{},
    setAttribute(k,v){this.attributes[k]=v;},append(){},replaceChildren(){},querySelector(){return null;},
    addEventListener(k,f){this.events[k]=f;},getContext(){return {};},
    elements:Object.fromEntries(['max_speed','steering_step','sensor_range','population','seed','episode_steps','road_width'].map(k=>[k,{value:0}]))};
  if(id)nodes.set(id,n);return n;
}
globalThis.document={getElementById:node,querySelectorAll:()=>[],createElement:()=>node(),documentElement:node(),addEventListener(){},body:node()};
globalThis.matchMedia=()=>({matches:false});globalThis.requestAnimationFrame=()=>{};
globalThis.location={protocol:'http:',host:'127.0.0.1:1234'};
let socket,commands=[];
globalThis.WebSocket=class {static OPEN=1;constructor(){socket=this;this.readyState=1;}};
let state={schema_version:1,session_id:'session',episode_id:'episode',track_id:'classic',generation:3,
  settings:{max_speed:18,steering_step:5,sensor_range:300,population:30,seed:7,episode_steps:1200,road_width:120},
  appearance:{color:'mixed',sensors:true},fitness:{current:2,saved:3},replay:null,cars:[{id:1,position:[1,2]}],leader:null};
globalThis.fetch=async(url,options)=>{
  if(url==='/api/catalog')return {ok:true,json:async()=>({tracks:[],road_width:120})};
  if(url==='/api/state')return {ok:true,json:async()=>structuredClone(state)};
  assert.equal(url,'/api/command');const command=JSON.parse(options.body);commands.push(command);
  assert.equal(command.command,'appearance');const {command:_,...fields}=command;
  state={...state,appearance:{...state.appearance,...fields}};
  return {ok:true,json:async()=>({ok:true,snapshot:structuredClone(state)})};
};
const settle=()=>new Promise(resolve=>setImmediate(resolve));
await import('../web/app.js');await settle();
assert.equal(node('follow').attributes['aria-pressed'],true);assert.equal(node('zoom-value').textContent,'2.3×');
socket.onopen();await settle();
assert.deepEqual(commands,[{command:'appearance',color:'purple',sensors:false}]);
for(let i=0;i<10;i++)socket.onmessage({data:JSON.stringify(state)});
await settle();assert.equal(commands.length,1);
assert.equal(state.session_id,'session');assert.equal(state.episode_id,'episode');assert.equal(state.generation,3);assert.deepEqual(state.cars,[{id:1,position:[1,2]}]);
node('sensors').checked=true;await node('sensors').onchange();
assert.equal(JSON.parse(stored).sensors,true);assert.equal(commands.length,2);
node('fit').onclick();assert.equal(JSON.parse(stored).cameraMode,'fit');assert.equal(JSON.parse(stored).cameraZoom,1);
node('follow').onclick();node('zoom-in').onclick();assert.equal(JSON.parse(stored).cameraZoom,2.25);
socket.onopen();await settle();assert.equal(commands.length,2,'reconnect must not reassert once-restored preferences');
console.log('PASS one initial appearance restore, no snapshot/ack/reconnect command loop, acknowledged palette/sensor persistence, camera controls, unchanged session/episode/generation/cars.');
