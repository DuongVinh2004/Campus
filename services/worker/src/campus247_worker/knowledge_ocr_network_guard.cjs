'use strict';
// Local OCR has no reason to open a socket or spawn another executable.
// Worker threads inherit this preload; the installed WASM engine stays local.
const deny = () => { throw new Error('LOCAL_OCR_NETWORK_OR_PROCESS_DENIED'); };
const net = require('node:net');
net.Socket.prototype.connect = deny;
require('node:tls').connect = deny;
for (const name of ['node:http', 'node:https']) {
  const protocol = require(name);
  protocol.request = deny;
  protocol.get = deny;
}
const child = require('node:child_process');
for (const name of ['exec', 'execFile', 'spawn', 'fork', 'execSync', 'execFileSync', 'spawnSync']) child[name] = deny;
globalThis.fetch = deny;
require('node:module').syncBuiltinESMExports();
