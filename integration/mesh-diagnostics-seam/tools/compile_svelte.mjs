import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { createRequire } from "node:module";
const root=resolve(import.meta.dirname,"../frontend");
const require=createRequire(join(root,"package.json"));
const { compile, VERSION }=require("svelte/compiler");
function walk(dir) {
  return readdirSync(dir,{withFileTypes:true}).flatMap((item) => {
    if (["node_modules","dist"].includes(item.name)) return [];
    return item.isDirectory()?walk(join(dir,item.name)):[join(dir,item.name)];
  });
}
let errors=0;
for(const file of walk(root).filter((p)=>p.endsWith(".svelte"))) {
  try {
    for(const generate of ["client","server"]) {
      const result=compile(readFileSync(file,"utf8"),{filename:file,generate});
      for(const warning of result.warnings) { console.warn(file,warning.code,warning.message); errors++; }
    }
    console.log("Compiled",file);
  } catch(error) { errors++; console.error(file,error); }
}
console.log("Svelte compiler",VERSION);
process.exitCode=errors?1:0;
