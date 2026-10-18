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
  let indices,error,method='fixed_border';
  if(d.cluster_relative_error && r.indices.length>12000){
    if(![.005,.008].includes(d.cluster_relative_error))
      throw new Error('Unreviewed stair clustering allowance');
    [indices,error]=m.simplifySloppy(source,positions,3,null,
      Math.max(3,Math.floor(r.indices.length*.13/3)*3),d.cluster_relative_error);
    error*=m.getScale(positions,3);method='spatial_cluster';
  }else{
    [indices,error]=m.simplifyWithAttributes(source,positions,3,new Float32Array(r.uv),2,[.1,.1],null,
      Math.min(r.indices.length,Math.max(3,Math.floor(r.indices.length*d.ratio/3)*3)),d.error,
      ['ErrorAbsolute','Permissive',...(fixed?['LockBorder']:[])]);
  }
  rows.push({name:r.name,indices:Array.from(indices),error,method});
}
fs.writeFileSync(output,JSON.stringify(rows));
