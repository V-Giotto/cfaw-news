// Managed development server; all API traffic targets the isolated QA service.
import { createServer } from '../../../frontend/node_modules/vite/dist/node/index.js';
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
const root = path.resolve(process.argv[2]);
const configFile = path.join(root, 'vite.config.ts');
const port = Number(process.argv[3]);
const target = process.argv[4];
const output = process.argv[5];
if (port !== 5175 || target !== 'http://127.0.0.1:8135') throw new Error('QA targets required');
const server = await createServer({ root, configFile, mode: 'development', server: {
  host: '127.0.0.1', port, strictPort: true, open: false, proxy: { '/api': target },
} });
fs.writeFileSync(output, JSON.stringify({ root, configFile, mode: server.config.mode,
  host: server.config.server.host, port: server.config.server.port, strictPort: true,
  proxy_target: target, open: false, strict_mode_entry: 'src/main.tsx' }, null, 2), { flag: 'wx' });
await server.listen();
readline.createInterface({ input: process.stdin }).on('line', async line => {
  if (line === 'STOP') { await server.close(); process.exit(0); }
});
