// Scope all Next writes to the fresh isolated artifact; retain deletion denial.
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {syncBuiltinESMExports} from "node:module";
const root = process.env.C247_M1_FRONTEND;
const realpath = fs.realpathSync.native;
const stat = fs.lstatSync;
if (!root || realpath(root) !== root || !["frontend11"].includes(path.basename(root))) throw Error("invalid frontend scope");
const contains = (a,b) => b === a || b.startsWith(a+path.sep);
const denied = () => {throw Error("M1 frontend mutation denied");};
function check(value, writing) {
  if (typeof value === "number") return writing ? denied() : value;
  const target = path.resolve(value instanceof URL ? fileURLToPath(value) : String(value));
  if ([".env", ".fixture-state.json", ".npmrc"].includes(path.basename(target)) || path.basename(target).startsWith(".env.")) return denied();
  if (writing) {
    if (!contains(root,target)) return denied();
    let parent = target;
    while (!fs.existsSync(parent)) parent = path.dirname(parent);
    if (!contains(root,realpath(parent)) || stat(parent).isSymbolicLink()) return denied();
  }
  return target;
}
for (const api of [fs,fsp]) {
  for (const name of ["writeFile","writeFileSync","appendFile","appendFileSync","mkdir","mkdirSync","createWriteStream"]) {
    if (typeof api[name] !== "function") continue;
    const original = api[name]; api[name] = function(target,...args){return original.call(this,check(target,true),...args);};
  }
  for (const name of ["readFile","readFileSync","createReadStream"]) {
    if (typeof api[name] !== "function") continue;
    const original = api[name]; api[name] = function(target,...args){return original.call(this,check(target,false),...args);};
  }
  for (const name of ["open","openSync"]) {
    if (typeof api[name] !== "function") continue;
    const original = api[name]; api[name] = function(target,flags,...args){return original.call(this,check(target,typeof flags === "number" ? (flags & 0x243)!==0 : /[wax+]/.test(flags)),flags,...args);};
  }
  for (const name of ["unlink","unlinkSync","rm","rmSync","rmdir","rmdirSync","rename","renameSync","truncate","truncateSync","chmod","chmodSync","chown","chownSync","symlink","symlinkSync","link","linkSync"]) if (typeof api[name] === "function") api[name] = denied;
}
// Preserve every generated artifact when Next requests build cleanup. This
// fresh directory has no previous build. No delete or destructive move occurs.
const retained = path.join(root,"retained-build-cleanup.jsonl");
const append = fs.appendFileSync.bind(fs);
const copy = fs.copyFileSync.bind(fs);
function generated(value) {
  const target = check(value,true);
  if (!contains(path.join(root,".next"),target)) return denied();
  return target;
}
function retain(value) {
  const target = generated(value);
  append(retained,JSON.stringify({operation:"cleanup-retained",target,exists:fs.existsSync(target)})+"\n");
}
for (const name of ["unlinkSync","rmSync","rmdirSync"]) fs[name] = retain;
for (const name of ["unlink","rm","rmdir"]) {
  fs[name] = (value,...args) => {try {retain(value);args.at(-1)(null);} catch(error) {args.at(-1)(error);}};
  fsp[name] = async(value) => {retain(value);};
}
function preserveRename(from,to) {
  const source = generated(from), destination = generated(to);
  if (fs.existsSync(destination)) return denied();
  copy(source,destination,fs.constants.COPYFILE_EXCL);
  append(retained,JSON.stringify({operation:"non-destructive-copy-instead-of-rename",source,destination})+"\n");
}
fs.renameSync = preserveRename;
fs.rename = (from,to,callback) => {try {preserveRename(from,to);callback(null);} catch(error) {callback(error);}};
fsp.rename = async(from,to) => {preserveRename(from,to);};
syncBuiltinESMExports();
