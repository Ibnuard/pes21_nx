// Offline adapter for the pinned, user-installed meshoptimizer 1.1.1 module.
// Emits only indices into the original vertices: UVs/weights never interpolate.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const [modulePath, input, output] = process.argv.slice(2);
const {MeshoptSimplifier: m} = await import(pathToFileURL(modulePath));
await m.ready;
const d = JSON.parse(fs.readFileSync(input, 'utf8'));
if (!d.indices.length || d.indices.length % 3 || d.positions.length % 3 ||
    d.uv.length / 2 !== d.positions.length / 3 || d.locks.length !== d.positions.length / 3 ||
    !Number.isFinite(d.error) || d.error < 0 || !Number.isInteger(d.target) || d.target < 1)
  throw new Error('Invalid reduction contract');
let attributes=d.uv,weights=[d.uvWeight,d.uvWeight],stride=2;
if(d.normals){
  if(d.normals.length!==d.positions.length || !d.normals.every(Number.isFinite) ||
     !Number.isFinite(d.normalWeight) || d.normalWeight<0) throw new Error('Invalid normal attribute contract');
  attributes=[];stride=5;weights.push(d.normalWeight,d.normalWeight,d.normalWeight);
  for(let i=0;i<d.locks.length;i++)attributes.push(...d.uv.slice(i*2,i*2+2),...d.normals.slice(i*3,i*3+3));
}
const [indices, error] = m.simplifyWithAttributes(new Uint32Array(d.indices),
  new Float32Array(d.positions), 3, new Float32Array(attributes), stride,
  weights, new Uint8Array(d.locks), Math.min(d.target * 3,d.indices.length), d.error, d.flags);
fs.writeFileSync(output, JSON.stringify({indices: Array.from(indices), error,
  verticesMoved: false, implementation: 'meshoptimizer 1.1.1'}));
