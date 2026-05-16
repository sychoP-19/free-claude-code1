import { createServer } from 'node:http';
import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import initSqlJs from 'sql.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PUBLIC = resolve(__dirname, 'public');
const DATA_DIR = resolve(__dirname, 'data');
const DB_PATH = join(DATA_DIR, 'jobs.db');
const PORT = 3456;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

// ── Database ─────────────────────────────────────────────────────────────────

let db;

function initDb(database) {
  database.run(`
    CREATE TABLE IF NOT EXISTS searches (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      keyword TEXT NOT NULL,
      results_count INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    )
  `);
  database.run(`
    CREATE TABLE IF NOT EXISTS saved_jobs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      company TEXT NOT NULL,
      location TEXT,
      url TEXT NOT NULL UNIQUE,
      source TEXT,
      salary TEXT,
      job_type TEXT,
      date TEXT,
      notes TEXT DEFAULT '',
      saved_at TEXT DEFAULT (datetime('now'))
    )
  `);
  database.run(`
    CREATE TABLE IF NOT EXISTS search_results (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      search_id INTEGER REFERENCES searches(id),
      title TEXT NOT NULL,
      company TEXT NOT NULL,
      location TEXT,
      url TEXT NOT NULL,
      source TEXT,
      salary TEXT,
      job_type TEXT,
      date TEXT
    )
  `);
}

function saveDb() {
  if (!db) return;
  try {
    const data = db.export();
    const buffer = Buffer.from(data);
    writeFileSync(DB_PATH, buffer);
  } catch {}
}

// ── Job Sources ──────────────────────────────────────────────────────────────

const SOURCES = [
  {
    name: 'Remotive',
    async fetch(keyword, opts = {}) {
      let url = `https://remotive.com/api/remote-jobs?search=${encodeURIComponent(keyword)}&limit=${opts.limit || 50}`;
      if (opts.category) url += `&category=${encodeURIComponent(opts.category)}`;
      if (opts.company) url += `&company_name=${encodeURIComponent(opts.company)}`;
      const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
      if (!res.ok) return [];
      const data = await res.json();
      return (data.jobs || []).map(j => ({
        title: j.title,
        company: j.company_name,
        location: Array.isArray(j.candidate_required_location) ? j.candidate_required_location.join(', ') : (j.candidate_required_location || 'Remote'),
        url: j.url,
        source: 'Remotive',
        salary: j.salary || '',
        job_type: j.job_type || '',
        date: j.publication_date,
      }));
    },
  },
  {
    name: 'Arbeitnow',
    async fetch(keyword, opts = {}) {
      const url = `https://arbeitnow.com/api/job-board-api?search=${encodeURIComponent(keyword)}`;
      const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
      if (!res.ok) return [];
      const data = await res.json();
      return (data.data || []).map(j => ({
        title: j.title,
        company: j.company_name,
        location: [j.location, ...(j.remote ? ['Remote'] : [])].filter(Boolean).join(', ') || 'N/A',
        url: `https://arbeitnow.com/jobs/${j.slug}`,
        source: 'Arbeitnow',
        salary: j.salary || '',
        job_type: j.job_type || '',
        date: j.created_at,
      }));
    },
  },
  {
    name: 'Jobicy',
    async fetch(keyword) {
      const url = `https://jobicy.com/api/v2/jobs?search=${encodeURIComponent(keyword)}&count=50`;
      const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
      if (!res.ok) return [];
      const data = await res.json();
      return (data.jobs || []).map(j => ({
        title: j.title,
        company: j.companyName || j.company || '',
        location: j.location || 'Remote',
        url: j.url || j.applyUrl || '',
        source: 'Jobicy',
        salary: j.salary || '',
        job_type: j.jobType || '',
        date: j.pubDate || j.date,
      })).filter(j => j.url);
    },
  },
  {
    name: 'HackerNews',
    async fetch(keyword) {
      const url = `https://hacker-news.firebaseio.com/v0/item/41795637.json`;
      try {
        const monthAgo = new Date();
        monthAgo.setMonth(monthAgo.getMonth() - 1);
        const searchUrl = `https://hn.algolia.com/api/v1/search?query=${encodeURIComponent(keyword)}&tags=story&numericFilters=created_at_i>${Math.floor(monthAgo.getTime() / 1000)}&hitsPerPage=30`;
        const res = await fetch(searchUrl, { signal: AbortSignal.timeout(8000) });
        if (!res.ok) return [];
        const data = await res.json();
        return (data.hits || [])
          .filter(h => h.title && (h.title.toLowerCase().includes('hiring') || h.title.toLowerCase().includes('job') || h.title.toLowerCase().includes(keyword.toLowerCase())))
          .map(h => ({
            title: h.title,
            company: h.author || '',
            location: 'See post',
            url: h.url || `https://news.ycombinator.com/item?id=${h.objectID}`,
            source: 'HackerNews',
            salary: '',
            job_type: '',
            date: h.created_at,
          }));
      } catch {
        return [];
      }
    },
  },
];

// ── API Handlers ─────────────────────────────────────────────────────────────

function json(res, data, status = 200) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
  });
  res.end(JSON.stringify(data));
}

function readBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', c => (body += c));
    req.on('end', () => resolve(body));
  });
}

async function handleSearch(req, res) {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const keyword = url.searchParams.get('q')?.trim();
  const sources = url.searchParams.get('sources')?.split(',').filter(Boolean) || [];
  const remoteOnly = url.searchParams.get('remote') === 'true';

  if (!keyword) return json(res, { error: 'Provide a ?q= keyword' }, 400);

  const activeSources = sources.length
    ? SOURCES.filter(s => sources.includes(s.name.toLowerCase()))
    : SOURCES;

  const results = await Promise.allSettled(activeSources.map(s => s.fetch(keyword)));
  let jobs = results
    .filter(r => r.status === 'fulfilled')
    .flatMap(r => r.value);

  if (remoteOnly) {
    jobs = jobs.filter(j => /remote/i.test(j.location));
  }

  // Deduplicate by URL
  const seen = new Set();
  jobs = jobs.filter(j => {
    if (seen.has(j.url)) return false;
    seen.add(j.url);
    return true;
  });

  jobs.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));

  // Save search to history
  try {
    db.run('INSERT INTO searches (keyword, results_count) VALUES (?, ?)', [keyword, jobs.length]);
    const searchId = db.exec('SELECT last_insert_rowid() as id')[0].values[0][0];
    for (const j of jobs) {
      db.run(
        'INSERT OR IGNORE INTO search_results (search_id, title, company, location, url, source, salary, job_type, date) VALUES (?,?,?,?,?,?,?,?,?)',
        [searchId, j.title, j.company, j.location, j.url, j.source, j.salary || '', j.job_type || '', j.date || '']
      );
    }
    saveDb();
  } catch {}

  json(res, { jobs, total: jobs.length, sources: activeSources.map(s => s.name) });
}

async function handleSaveJob(req, res) {
  const body = JSON.parse(await readBody(req));
  const { title, company, location, url: jobUrl, source, salary, job_type, notes } = body;
  if (!title || !jobUrl) return json(res, { error: 'title and url required' }, 400);

  try {
    db.run(
      'INSERT OR IGNORE INTO saved_jobs (title, company, location, url, source, salary, job_type, notes) VALUES (?,?,?,?,?,?,?,?)',
      [title, company, location || '', jobUrl, source || '', salary || '', job_type || '', notes || '']
    );
    saveDb();
    json(res, { ok: true });
  } catch (e) {
    json(res, { error: e.message }, 500);
  }
}

async function handleUnsaveJob(req, res) {
  const body = JSON.parse(await readBody(req));
  const { url: jobUrl } = body;
  if (!jobUrl) return json(res, { error: 'url required' }, 400);
  db.run('DELETE FROM saved_jobs WHERE url = ?', [jobUrl]);
  saveDb();
  json(res, { ok: true });
}

async function handleUpdateNote(req, res) {
  const body = JSON.parse(await readBody(req));
  const { url: jobUrl, notes } = body;
  if (!jobUrl) return json(res, { error: 'url required' }, 400);
  db.run('UPDATE saved_jobs SET notes = ? WHERE url = ?', [notes || '', jobUrl]);
  saveDb();
  json(res, { ok: true });
}

function handleSavedJobs(req, res) {
  const rows = db.exec('SELECT * FROM saved_jobs ORDER BY saved_at DESC');
  if (!rows.length) return json(res, { jobs: [] });
  const cols = rows[0].columns;
  const jobs = rows[0].values.map(v => {
    const obj = {};
    cols.forEach((c, i) => (obj[c] = v[i]));
    return obj;
  });
  json(res, { jobs });
}

function handleHistory(req, res) {
  const rows = db.exec('SELECT * FROM searches ORDER BY created_at DESC LIMIT 100');
  if (!rows.length) return json(res, { searches: [] });
  const cols = rows[0].columns;
  const searches = rows[0].values.map(v => {
    const obj = {};
    cols.forEach((c, i) => (obj[c] = v[i]));
    return obj;
  });
  json(res, { searches });
}

function handleClearHistory(req, res) {
  db.run('DELETE FROM searches');
  db.run('DELETE FROM search_results');
  saveDb();
  json(res, { ok: true });
}

function handleExport(req, res) {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const type = url.searchParams.get('type') || 'saved';

  let jobs;
  if (type === 'saved') {
    const rows = db.exec('SELECT * FROM saved_jobs ORDER BY saved_at DESC');
    if (!rows.length) return json(res, { csv: '' });
    const cols = rows[0].columns;
    jobs = rows[0].values.map(v => {
      const obj = {};
      cols.forEach((c, i) => (obj[c] = v[i]));
      return obj;
    });
  } else {
    return json(res, { error: 'type must be "saved"' }, 400);
  }

  const header = 'Title,Company,Location,URL,Source,Salary,Type,Notes\n';
  const csv = header + jobs.map(j =>
    `"${(j.title || '').replace(/"/g, '""')}","${(j.company || '').replace(/"/g, '""')}","${(j.location || '').replace(/"/g, '""')}","${j.url}","${j.source || ''}","${j.salary || ''}","${j.job_type || ''}","${(j.notes || '').replace(/"/g, '""')}"`
  ).join('\n');

  res.writeHead(200, {
    'Content-Type': 'text/csv; charset=utf-8',
    'Content-Disposition': 'attachment; filename=jobs.csv',
  });
  res.end(csv);
}

// ── Router ───────────────────────────────────────────────────────────────────

// ── Anthropic-compatible Proxy ──────────────────────────────────────────────

const PROXY_TARGET = process.env.PROXY_TARGET || 'http://localhost:8082';

async function handleMessagesProxy(req, res) {
  const body = await readBody(req);
  try {
    const upstream = await fetch(PROXY_TARGET + '/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': req.headers['x-api-key'] || 'sk-local-proxy',
        'anthropic-version': req.headers['anthropic-version'] || '2023-06-01',
      },
      body,
    });
    res.writeHead(upstream.status, {
      'Content-Type': upstream.headers.get('content-type') || 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    const buf = Buffer.from(await upstream.arrayBuffer());
    res.end(buf);
  } catch (e) {
    json(res, { error: 'Proxy failed: ' + e.message }, 502);
  }
}

const ROUTES = {
  'POST /v1/messages': handleMessagesProxy,
  'GET /api/jobs': handleSearch,
  'POST /api/jobs/save': handleSaveJob,
  'POST /api/jobs/unsave': handleUnsaveJob,
  'POST /api/jobs/notes': handleUpdateNote,
  'GET /api/jobs/saved': handleSavedJobs,
  'GET /api/history': handleHistory,
  'DELETE /api/history': handleClearHistory,
  'GET /api/export': handleExport,
};

// ── Static file server ───────────────────────────────────────────────────────

function serveStatic(req, res) {
  const urlPath = req.url === '/' ? '/index.html' : req.url.split('?')[0];
  const resolved = resolve(PUBLIC, urlPath.replace(/^\/+/, ''));

  if (!resolved.startsWith(PUBLIC + sep) && resolved !== PUBLIC) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  if (!existsSync(resolved)) {
    res.writeHead(404);
    res.end('Not found');
    return;
  }

  const ext = extname(resolved);
  const mime = MIME[ext] || 'application/octet-stream';
  res.writeHead(200, { 'Content-Type': mime });
  res.end(readFileSync(resolved));
}

// ── Server ───────────────────────────────────────────────────────────────────

async function main() {
  const SQL = await initSqlJs();

  if (!existsSync(DATA_DIR)) mkdirSync(DATA_DIR, { recursive: true });

  if (existsSync(DB_PATH)) {
    const buffer = readFileSync(DB_PATH);
    db = new SQL.Database(buffer);
  } else {
    db = new SQL.Database();
  }

  initDb(db);
  saveDb();

  const server = createServer(async (req, res) => {
    const method = req.method;
    const path = req.url.split('?')[0];
    const key = `${method} ${path}`;
    const handler = ROUTES[key];
    if (handler) return handler(req, res);
    serveStatic(req, res);
  });

      server.listen(PORT, () => {
    console.log('\n  Job Scout Agent - Signal Drift - http://localhost:' + PORT + '\n  API proxy -> ' + PROXY_TARGET + '/v1/messages\n');
  });
}

main();
