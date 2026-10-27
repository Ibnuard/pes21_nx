// Offline geometric-border and UV preserving stadium reduction.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const [modulePath,input,output]=process.argv.slice(2);
const {MeshoptSimplifier:m}=await import(pathToFileURL(modulePath));
await m.ready;
const d=JSON.parse(fs.readFileSync(input,'utf8'));
const rows=[];
for(const r of d.materials){
  if(!r.indices.length || r.indices.length%3 || r.positions.length%3 ||
     r.uv.length/2!==r.positions.length/3 || !Number.isFinite(d.ratio) ||
     d.ratio<=0 || d.ratio>1 || !Number.isFinite(d.error) || d.error<0)
    throw new Error('Invalid stadium surface contract');
  const fixed=r.lock_border!==false;
  const source=new Uint32Array(r.indices),positions=new Float32Array(r.positions);
  const keep=r.preserve_triangles||[];
  if(new Set(keep).size!==keep.length || keep.some(i=>!Number.isInteger(i)||i<0||i>=source.length/3))
    throw new Error('Invalid preserved source panels');
  const kept=[],work=[],keepSet=new Set(keep);
  for(let i=0;i<source.length;i+=3)
    (keepSet.has(i/3)?kept:work).push(source[i],source[i+1],source[i+2]);
  const inputIndices=keep.length?new Uint32Array(work):source;
  let indices,error,method='fixed_border';
  if(!inputIndices.length){
    indices=new Uint32Array();error=0;method='original_source';
  }else if(d.cluster_relative_error && inputIndices.length>12000){
    if(![.005,.008].includes(d.cluster_relative_error))
      throw new Error('Unreviewed stair clustering allowance');
    [indices,error]=m.simplifySloppy(inputIndices,positions,3,null,
      Math.max(3,Math.floor(inputIndices.length*.13/3)*3),d.cluster_relative_error);
    error*=m.getScale(positions,3);method='spatial_cluster';
  }else{
    [indices,error]=m.simplifyWithAttributes(inputIndices,positions,3,new Float32Array(r.uv),2,[.1,.1],null,
      Math.min(inputIndices.length,Math.max(3,Math.floor(inputIndices.length*d.ratio/3)*3)),d.error,
      ['ErrorAbsolute','Permissive',...(fixed?['LockBorder']:[])]);
  }
  rows.push({name:r.name,indices:[...indices,...kept],error,method,preserved_source_triangles:keep.length});
}
fs.writeFileSync(output,JSON.stringify(rows));
