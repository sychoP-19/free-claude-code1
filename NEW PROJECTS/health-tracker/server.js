import { createServer } from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import { join, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const DIST = resolve(__dirname, 'dist');
const PORT = 5174;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

const server = createServer((req, res) => {
  const urlPath = req.url === '/' ? '/index.html' : req.url.split('?')[0];
  const resolved = resolve(DIST, urlPath.replace(/^\/+/, ''));

  if (!resolved.startsWith(DIST + sep) && resolved !== DIST) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  if (!existsSync(resolved)) {
    // SPA fallback — serve index.html for any unmatched route
    const fallback = join(DIST, 'index.html');
    res.writeHead(200, { 'Content-Type': MIME['.html'] });
    res.end(readFileSync(fallback));
    return;
  }

  const ext = extname(resolved);
  const mime = MIME[ext] || 'application/octet-stream';
  res.writeHead(200, { 'Content-Type': mime });
  res.end(readFileSync(resolved));
});

server.listen(PORT, () => {
  console.log(`\n  HealthTracker — http://localhost:${PORT}\n  All data stored locally in your browser.\n`);
});
