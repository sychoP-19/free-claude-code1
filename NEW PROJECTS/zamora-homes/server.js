import { createServer } from 'node:http';
import { readFileSync, existsSync, writeFileSync, copyFileSync, mkdirSync } from 'node:fs';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { searchInternet } from './scraper.js';
import Database from 'better-sqlite3';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PUBLIC = resolve(__dirname, 'public');
const PORT = 4567;
const DATA_DIR = resolve(__dirname, 'data');
const DB_PATH = resolve(DATA_DIR, 'jobs.db');

// ── Data dir + DB backup ──────────────────────────────────────────────────────
if (!existsSync(DATA_DIR)) mkdirSync(DATA_DIR, { recursive: true });
if (existsSync(DB_PATH)) {
  try { copyFileSync(DB_PATH, resolve(DATA_DIR, 'jobs.backup.db')); } catch {}
}

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

// ── Schema ────────────────────────────────────────────────────────────────────
db.exec(`
  CREATE TABLE IF NOT EXISTS saved_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'venta',
    property TEXT DEFAULT 'casa',
    price INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'MXN',
    bedrooms INTEGER DEFAULT 0,
    bathrooms INTEGER DEFAULT 0,
    area INTEGER DEFAULT 0,
    neighborhood TEXT DEFAULT '',
    address TEXT DEFAULT '',
    description TEXT DEFAULT '',
    features TEXT DEFAULT '[]',
    contact TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    source TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    image TEXT DEFAULT '',
    status TEXT DEFAULT 'saved',
    notes TEXT DEFAULT '',
    applied_at TEXT,
    saved_at TEXT DEFAULT (datetime('now'))
  );
  CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    type TEXT DEFAULT 'all',
    property TEXT DEFAULT 'all',
    source TEXT DEFAULT 'local',
    result_count INTEGER DEFAULT 0,
    searched_at TEXT DEFAULT (datetime('now'))
  );
`);

// Safe migration: add status/applied_at if missing
try { db.exec(`ALTER TABLE saved_jobs ADD COLUMN status TEXT DEFAULT 'saved'`); } catch {}
try { db.exec(`ALTER TABLE saved_jobs ADD COLUMN applied_at TEXT`); } catch {}
try { db.exec(`ALTER TABLE saved_jobs ADD COLUMN notes TEXT DEFAULT ''`); } catch {}

// Prepared statements
const stmts = {
  saveJob: db.prepare(`
    INSERT OR IGNORE INTO saved_jobs
      (listing_id, title, type, property, price, currency, bedrooms, bathrooms,
       area, neighborhood, address, description, features, contact, phone,
       source, source_url, image, status)
    VALUES (@listing_id, @title, @type, @property, @price, @currency, @bedrooms, @bathrooms,
            @area, @neighborhood, @address, @description, @features, @contact, @phone,
            @source, @source_url, @image, @status)
  `),
  removeJob: db.prepare(`DELETE FROM saved_jobs WHERE id = ?`),
  updateStatus: db.prepare(`UPDATE saved_jobs SET status = ?, applied_at = CASE WHEN ? = 'applied' THEN datetime('now') ELSE applied_at END WHERE id = ?`),
  updateNotes: db.prepare(`UPDATE saved_jobs SET notes = ? WHERE id = ?`),
  getSaved: db.prepare(`SELECT * FROM saved_jobs ORDER BY saved_at DESC`),
  getSavedById: db.prepare(`SELECT * FROM saved_jobs WHERE id = ?`),
  isInSaved: db.prepare(`SELECT 1 FROM saved_jobs WHERE listing_id = ?`),
  logSearch: db.prepare(`INSERT INTO searches (keyword, type, property, source, result_count) VALUES (?, ?, ?, ?, ?)`),
  deleteSaved: db.prepare(`DELETE FROM saved_jobs WHERE id = ?`),
  getStats: db.prepare(`
    SELECT
      (SELECT COUNT(*) FROM searches) as totalSearches,
      (SELECT COUNT(*) FROM saved_jobs) as totalSaved,
      (SELECT COUNT(*) FROM searches WHERE searched_at >= datetime('now', '-7 days')) as searchesThisWeek
  `),
  topKeywords: db.prepare(`
    SELECT keyword, COUNT(*) as cnt FROM searches GROUP BY keyword ORDER BY cnt DESC LIMIT 10
  `),
  savedByStatus: db.prepare(`
    SELECT status, COUNT(*) as cnt FROM saved_jobs GROUP BY status
  `),
};

// ── Cache ─────────────────────────────────────────────────────────────────────
const cache = new Map();
function cached(key, ttl, fn) {
  const entry = cache.get(key);
  if (entry && Date.now() - entry.ts < ttl) return Promise.resolve(entry.data);
  return fn().then(data => { cache.set(key, { data, ts: Date.now() }); return data; });
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
};

// ── Zamora Listings Data ─────────────────────────────────────────────────────

const ZAMORA_LISTINGS = [
  // Casas en venta
  { id: 1, title: 'Casa Colonial Centro Histórico', type: 'venta', property: 'casa', price: 2800000, currency: 'MXN', bedrooms: 3, bathrooms: 2, area: 180, neighborhood: 'Centro', address: 'Av. Madero Sur 48, Centro, Zamora de Hidalgo, Mich.', description: 'Casa colonial con patio interior, techos altos y vigas originales. Remodelada cocina y baños. A 2 cuadras de la Catedral de la Inmaculada.', features: ['Patio', 'Estacionamiento', 'Vigas originales', 'Cisterna'], contact: 'Ana Martínez - Inmobiliaria Zamora', phone: '(351) 517-2040', image: 'casa-colonial-centro' },
  { id: 2, title: 'Casa Residencial Camichines', type: 'venta', property: 'casa', price: 3500000, currency: 'MXN', bedrooms: 4, bathrooms: 3, area: 250, neighborhood: 'Fracc. Los Camichines', address: 'Paseo de los Camichines 112, Fracc. Los Camichines, Zamora, Mich.', description: 'Casa nueva en fraccionamiento privado con alberca, jardín amplio y seguridad 24/7. Cocina integral y clósets walker.', features: ['Alberca', 'Jardín', 'Seguridad 24/7', 'Cocina integral', '2 autos estacionamiento'], contact: 'Roberto Herrera - Remax Zamora', phone: '(351) 518-3360', image: 'casa-camichines' },
  { id: 3, title: 'Casa Economía Lázaro Cárdenas', type: 'venta', property: 'casa', price: 1200000, currency: 'MXN', bedrooms: 2, bathrooms: 1, area: 90, neighborhood: 'Col. Lázaro Cárdenas', address: 'Calle Jalisco 27, Col. Lázaro Cárdenas, Zamora, Mich.', description: 'Casa accesible en zona con todos los servicios cerca. Escuela, mercado y transporte público a una cuadra.', features: ['Servicios completos', 'Cerca transporte', 'Patio trasero'], contact: 'María González - Propietaria', phone: '(351) 512-4500', image: 'casa-lazaro' },
  { id: 4, title: 'Casa de Lujo Valle Verde', type: 'venta', property: 'casa', price: 5800000, currency: 'MXN', bedrooms: 5, bathrooms: 4, area: 380, neighborhood: 'Fracc. Valle Verde', address: 'Paseo Valle Verde 8, Fracc. Valle Verde, Zamora, Mich.', description: 'Casa premium con acabados de lujo, alberca climatizada, cuarto de servicio, estudio y terraza con vista.', features: ['Alberca climatizada', 'Cuarto servicio', 'Estudio', 'Terraza', '3 autos estacionamiento', 'Sistema domótico'], contact: 'Carlos Mendoza - Luxury Homes Zamora', phone: '(351) 519-8820', image: 'casa-valle-verde' },
  { id: 5, title: 'Casa Gemelas Colonia Roma', type: 'venta', property: 'casa', price: 2100000, currency: 'MXN', bedrooms: 3, bathrooms: 2, area: 140, neighborhood: 'Col. Roma', address: 'Calle Roma 15-B, Col. Roma, Zamora, Mich.', description: 'Casa en condominio con áreas verdes compartidas. Moderna distribución, cocina abierta al living.', features: ['Áreas verdes', 'Cocina abierta', 'Cisterna comunitaria'], contact: 'Inmobiliaria Zamora Centro', phone: '(351) 517-0090', image: 'casa-roma' },

  // Casas en renta
  { id: 6, title: 'Casa en Renta Centro', type: 'renta', property: 'casa', price: 12000, currency: 'MXN', bedrooms: 3, bathrooms: 2, area: 160, neighborhood: 'Centro', address: 'Calle Morelos 62, Centro, Zamora de Hidalgo, Mich.', description: 'Casa amueblada en el centro, ideal para familia. Incluye refrigerador, estufa y calentador.', features: ['Amueblada', 'Patio de servicio', 'Cerca centro histórico'], contact: 'Familia Ramos', phone: '(351) 515-6740', image: 'renta-casa-centro' },
  { id: 7, title: 'Casa Renta Camichines', type: 'renta', property: 'casa', price: 15000, currency: 'MXN', bedrooms: 3, bathrooms: 2.5, area: 180, neighborhood: 'Fracc. Los Camichines', address: 'Circuito Camichines 45, Fracc. Los Camichines, Zamora, Mich.', description: 'Casa en fraccionamiento con alberca comunitaria y jardín. Sin amueblar, contratos de 1 año.', features: ['Alberca comunitaria', 'Jardín propio', '2 estacionamientos'], contact: 'Administración Camichines', phone: '(351) 518-1120', image: 'renta-camichines' },
  { id: 8, title: 'Casa Económica Renta Ferrocarrilera', type: 'renta', property: 'casa', price: 6500, currency: 'MXN', bedrooms: 2, bathrooms: 1, area: 80, neighborhood: 'Col. Ferrocarrilera', address: 'Calle Naranjo 9, Col. Ferrocarrilera, Zamora, Mich.', description: 'Casa sencilla, bien ubicada cerca de la central camionera. Sin amueblar, servicios incluidos.', features: ['Servicios incluidos', 'Cerca central camionera'], contact: 'Sra. Lupita Mejía', phone: '(351) 512-3300', image: 'renta-ferrocarrilera' },

  // Departamentos en venta
  { id: 9, title: 'Depto Moderno Plaza Zamora', type: 'venta', property: 'departamento', price: 1800000, currency: 'MXN', bedrooms: 2, bathrooms: 1, area: 85, neighborhood: 'Centro', address: 'Av. 5 de Mayo 120, Piso 4, Centro, Zamora, Mich.', description: 'Departamento nuevo con terraza, vista a la Catedral. Edificio con elevador y gimnasio.', features: ['Elevador', 'Gimnasio', 'Terraza', 'Vista panorámica'], contact: 'Desarrolladora ZM', phone: '(351) 517-8850', image: 'depto-plaza' },
  { id: 10, title: 'Loft Industrial Centro', type: 'venta', property: 'departamento', price: 1400000, currency: 'MXN', bedrooms: 1, bathrooms: 1, area: 65, neighborhood: 'Centro', address: 'Calle Hidalgo 30, Piso 2, Centro, Zamora, Mich.', description: 'Loft estilo industrial con kitchenette abierta. Ideal profesionista solo o pareja.', features: ['Kitchenette', 'Doble altura', 'Luz natural'], contact: 'Arq. Daniela Torres', phone: '(351) 516-2270', image: 'loft-industrial' },

  // Departamentos en renta
  { id: 11, title: 'Depto Amueblado Centro', type: 'renta', property: 'departamento', price: 8000, currency: 'MXN', bedrooms: 1, bathrooms: 1, area: 50, neighborhood: 'Centro', address: 'Av. Madero Norte 85, Piso 3, Centro, Zamora, Mich.', description: 'Departamento completamente amueblado con todos los servicios. Ideal estudiante o profesional.', features: ['Amueblado', 'Servicios incluidos', 'WiFi', 'Cerca UAZ'], contact: 'Ing. Pablo Silva', phone: '(351) 514-5590', image: 'renta-depto-centro' },
  { id: 12, title: 'Depto 2 Recámaras Valle Verde', type: 'renta', property: 'departamento', price: 10000, currency: 'MXN', bedrooms: 2, bathrooms: 1, area: 70, neighborhood: 'Fracc. Valle Verde', address: 'Blvd. Valle Verde 200, Piso 2, Fracc. Valle Verde, Zamora, Mich.', description: 'Departamento amplio en zona residencial tranquila. Estacionamiento incluido.', features: ['Estacionamiento', 'Zona tranquila', 'Cerca plazas comerciales'], contact: 'Admin. Torres Valle Verde', phone: '(351) 519-4410', image: 'renta-depto-valle' },
  { id: 13, title: 'Estudio Juventino Rosas', type: 'renta', property: 'departamento', price: 4500, currency: 'MXN', bedrooms: 0, bathrooms: 1, area: 30, neighborhood: 'Col. Juventino Rosas', address: 'Calle P. Miranda 14, Col. Juventino Rosas, Zamora, Mich.', description: 'Estudio económico, funcional y bien iluminado. Servicios aparte.', features: ['Económico', 'Bien iluminado'], contact: 'Sra. Carmen Vda. de Flores', phone: '(351) 513-7760', image: 'renta-estudio' },

  // Terrenos
  { id: 14, title: 'Terreno Camichines Norte', type: 'venta', property: 'terreno', price: 2200000, currency: 'MXN', bedrooms: 0, bathrooms: 0, area: 400, neighborhood: 'Camichines Norte', address: 'Prol. Paseo Camichines s/n, Camichines Norte, Zamora, Mich.', description: 'Terreno plano con escrituras, excelente para construir. Frente a boulevard pavimentado.', features: ['Escrituras', 'Plano', 'Frente a boulevard', 'Servicios en la calle'], contact: 'Lic. Fernando Rangel', phone: '(351) 518-9050', image: 'terreno-camichines' },
  { id: 15, title: 'Terreno Ejidal Santa Paula', type: 'venta', property: 'terreno', price: 800000, currency: 'MXN', bedrooms: 0, bathrooms: 0, area: 500, neighborhood: 'Santa Paula', address: 'Camino a Santa Paula km 2, Zamora, Mich.', description: 'Terreno ejidal con posibilidad de regularización. Ideal para huerto o galpón.', features: ['Amplio', 'Camino de acceso', 'Regularizable'], contact: 'Comunidad Santa Paula', phone: '(351) 511-2240', image: 'terreno-santa-paula' },

  // Locales comerciales
  { id: 16, title: 'Local Comercial Av. Madero', type: 'renta', property: 'local', price: 18000, currency: 'MXN', bedrooms: 0, bathrooms: 1, area: 60, neighborhood: 'Centro', address: 'Av. Madero Sur 120, Centro, Zamora de Hidalgo, Mich.', description: 'Local comercial en zona de alta afluencia. Ideal para restaurante, tienda o consultorio.', features: ['Alta afluencia', 'Estacionamiento cercano', 'Gran vitrina'], contact: 'Familia Arreguín', phone: '(351) 517-3350', image: 'local-madero' },
  { id: 17, title: 'Oficina Renta Centro', type: 'renta', property: 'local', price: 9000, currency: 'MXN', bedrooms: 0, bathrooms: 1, area: 40, neighborhood: 'Centro', address: 'Calle Hidalgo 55, Piso 2, Centro, Zamora, Mich.', description: 'Oficina remodelada con recepción y 2 cubículos. Ideal despacho contable o legal.', features: ['Recepción', '2 cubículos', 'Baño privado', 'Aire acondicionado'], contact: 'Lic. Adriana Villaseñor', phone: '(351) 516-8820', image: 'oficina-centro' },
];

// ── External Portal Links Generator ──────────────────────────────────────────

function generatePortalLinks(filters) {
  const q = filters.keyword || '';
  const opType = filters.type === 'renta' ? 'en-renta' : 'en-venta';
  const opML = filters.type === 'renta' ? 'renta' : 'venta';

  const propI24 = { casa: 'casa', departamento: 'departamento', terreno: 'terreno', local: 'local-comercial' }[filters.property] || 'inmueble';
  const propVA = { casa: 'casa', departamento: 'departamento', terreno: 'terreno', local: 'local-comercial' }[filters.property] || 'inmueble';
  const propML = { casa: 'casas', departamento: 'departamentos', terreno: 'terrenos-lotes', local: 'locales-oficinas' }[filters.property] || 'casas';
  const propLa = { casa: 'casas', departamento: 'departamentos', terreno: 'terrenos', local: 'locales' }[filters.property] || 'casas';

  return [
    { name: 'Inmuebles24', url: `https://www.inmuebles24.com/propiedades/${propI24}-${opType}-en-zamora-de-hidalgo-michoacan${q ? '-' + q.replace(/\s+/g, '-') : ''}.html`, icon: 'I24', color: '#b45309' },
    { name: 'Vivanuncios', url: `https://www.vivanuncios.com.mx/s/${propVA}-${opType.slice(3)}-v/zamora-de-hidalgo-michoacan/${q ? '?q=' + encodeURIComponent(q) : ''}`, icon: 'VA', color: '#1d4ed8' },
    { name: 'MercadoLibre', url: `https://inmuebles.mercadolibre.com.mx/${propML}/${opML}/zamora-michoacan/${q ? '_Keywords_' + encodeURIComponent(q) : ''}`, icon: 'ML', color: '#ffe600' },
    { name: 'Lamudi', url: `https://www.lamudi.com.mx/zamora-de-hidalgo/${opType.slice(3)}/${propLa}/${q ? '?q=' + encodeURIComponent(q) : ''}`, icon: 'LA', color: '#00b4d8' },
    { name: 'Facebook Marketplace', url: `https://www.facebook.com/marketplace/109478749086570/search?query=${encodeURIComponent((q ? q + ' ' : '') + (filters.type === 'renta' ? 'renta' : 'venta') + ' zamora michoacan')}`, icon: 'FB', color: '#1877f2' },
  ];
}

// ── Filter Logic ─────────────────────────────────────────────────────────────

function filterListings(params) {
  let results = [...ZAMORA_LISTINGS];

  if (params.type && params.type !== 'all') {
    results = results.filter(l => l.type === params.type);
  }
  if (params.property && params.property !== 'all') {
    results = results.filter(l => l.property === params.property);
  }
  if (params.neighborhood && params.neighborhood !== 'all') {
    const nb = params.neighborhood.toLowerCase();
    results = results.filter(l =>
      l.neighborhood.toLowerCase().includes(nb) ||
      l.address.toLowerCase().includes(nb)
    );
  }
  if (params.keyword) {
    const kw = params.keyword.toLowerCase();
    results = results.filter(l =>
      l.title.toLowerCase().includes(kw) ||
      l.description.toLowerCase().includes(kw) ||
      l.neighborhood.toLowerCase().includes(kw) ||
      l.address.toLowerCase().includes(kw) ||
      l.features.some(f => f.toLowerCase().includes(kw))
    );
  }
  if (params.minPrice) {
    results = results.filter(l => l.price >= Number(params.minPrice));
  }
  if (params.maxPrice) {
    results = results.filter(l => l.price <= Number(params.maxPrice));
  }
  if (params.bedrooms) {
    results = results.filter(l => l.bedrooms >= Number(params.bedrooms));
  }

  return results;
}

const NEIGHBORHOODS = [...new Set(ZAMORA_LISTINGS.map(l => l.neighborhood))].sort();

// ── API Helpers ───────────────────────────────────────────────────────────────

function json(res, data, status = 200) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
  });
  res.end(JSON.stringify(data));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

// ── API: Listings ─────────────────────────────────────────────────────────────

function handleListings(req, res) {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const params = {
    type: url.searchParams.get('type') || 'all',
    property: url.searchParams.get('property') || 'all',
    neighborhood: url.searchParams.get('neighborhood') || 'all',
    keyword: url.searchParams.get('q')?.trim() || '',
    minPrice: url.searchParams.get('minPrice') || '',
    maxPrice: url.searchParams.get('maxPrice') || '',
    bedrooms: url.searchParams.get('bedrooms') || '',
  };

  const listings = filterListings(params);
  const portals = generatePortalLinks(params);

  stmts.logSearch.run(params.keyword || '*', params.type, params.property, 'local', listings.length);

  json(res, { listings, portals, neighborhoods: NEIGHBORHOODS, total: listings.length });
}

// ── API: Internet Search ──────────────────────────────────────────────────────

async function handleInternetSearch(req, res) {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const filters = {
    type: url.searchParams.get('type') || 'all',
    property: url.searchParams.get('property') || 'all',
    keyword: url.searchParams.get('q')?.trim() || '',
  };

  const cacheKey = `inet:${filters.type}:${filters.property}:${filters.keyword}`;

  try {
    const data = await cached(cacheKey, 600000, () => searchInternet(filters));
    stmts.logSearch.run(filters.keyword || '*', filters.type, filters.property, 'internet', (data.listings || []).length);
    json(res, { ...data, ok: true });
  } catch (err) {
    console.error('[InternetSearch]', err.message);
    json(res, { listings: [], errors: [{ source: 'server', error: err.message }], ok: false }, 502);
  }
}

// ── API: Saved Jobs ───────────────────────────────────────────────────────────

function handleGetSaved(req, res) {
  const rows = stmts.getSaved.all();
  const saved = rows.map(r => ({ ...r, features: JSON.parse(r.features || '[]') }));
  json(res, { saved });
}

async function handleSaveJob(req, res) {
  try {
    const body = JSON.parse(await readBody(req));
    const job = {
      listing_id: body.listing_id || body.id || '',
      title: body.title || '',
      type: body.type || 'venta',
      property: body.property || 'casa',
      price: body.price || 0,
      currency: body.currency || 'MXN',
      bedrooms: body.bedrooms || 0,
      bathrooms: body.bathrooms || 0,
      area: body.area || 0,
      neighborhood: body.neighborhood || '',
      address: body.address || '',
      description: body.description || '',
      features: JSON.stringify(body.features || []),
      contact: body.contact || '',
      phone: body.phone || '',
      source: body.source || '',
      source_url: body.sourceUrl || body.source_url || '',
      image: body.image || '',
      status: 'saved',
    };
    const info = stmts.saveJob.run(job);
    json(res, { ok: true, id: info.lastInsertRowid });
  } catch (err) {
    console.error('[SaveJob]', err.message);
    json(res, { ok: false, error: err.message }, 400);
  }
}

function handleRemoveJob(req, res) {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const id = url.searchParams.get('id');
  if (!id) return json(res, { ok: false, error: 'id required' }, 400);
  stmts.removeJob.run(Number(id));
  json(res, { ok: true });
}

async function handleBulkDelete(req, res) {
  try {
    const body = JSON.parse(await readBody(req));
    const ids = body.ids || [];
    if (!ids.length) return json(res, { ok: false, error: 'ids required' }, 400);
    const placeholders = ids.map(() => '?').join(',');
    db.prepare(`DELETE FROM saved_jobs WHERE id IN (${placeholders})`).run(...ids.map(Number));
    json(res, { ok: true, deleted: ids.length });
  } catch (err) {
    console.error('[BulkDelete]', err.message);
    json(res, { ok: false, error: err.message }, 400);
  }
}

// ── API: Update Status ────────────────────────────────────────────────────────

async function handleUpdateStatus(req, res) {
  try {
    const body = JSON.parse(await readBody(req));
    const { id, status } = body;
    if (!id || !status) return json(res, { ok: false, error: 'id and status required' }, 400);
    stmts.updateStatus.run(status, status, Number(id));
    json(res, { ok: true });
  } catch (err) {
    console.error('[UpdateStatus]', err.message);
    json(res, { ok: false, error: err.message }, 400);
  }
}

// ── API: Update Notes ─────────────────────────────────────────────────────────

async function handleUpdateNotes(req, res) {
  try {
    const body = JSON.parse(await readBody(req));
    const { id, notes } = body;
    if (!id) return json(res, { ok: false, error: 'id required' }, 400);
    stmts.updateNotes.run(notes || '', Number(id));
    json(res, { ok: true });
  } catch (err) {
    console.error('[UpdateNotes]', err.message);
    json(res, { ok: false, error: err.message }, 400);
  }
}

// ── API: Check if saved ───────────────────────────────────────────────────────

function handleIsSaved(req, res) {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const listingId = url.searchParams.get('listing_id');
  if (!listingId) return json(res, { ok: false, error: 'listing_id required' }, 400);
  const row = stmts.isInSaved.get(listingId);
  json(res, { saved: !!row });
}

// ── API: Stats ────────────────────────────────────────────────────────────────

function handleStats(req, res) {
  const stats = stmts.getStats.get();
  const topKeywords = stmts.topKeywords.all();
  const savedByStatus = stmts.savedByStatus.all();
  json(res, { ...stats, topKeywords, savedByStatus });
}

// ── API: Search History ───────────────────────────────────────────────────────

function handleHistory(req, res) {
  const rows = db.prepare(`SELECT DISTINCT keyword FROM searches ORDER BY searched_at DESC LIMIT 20`).all();
  json(res, { keywords: rows.map(r => r.keyword) });
}

// ── Static file server ────────────────────────────────────────────────────────

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

// ── Router ────────────────────────────────────────────────────────────────────

const server = createServer(async (req, res) => {
  const method = req.method;
  const path = req.url.split('?')[0];

  // GET APIs
  if (method === 'GET') {
    if (path === '/api/listings') return handleListings(req, res);
    if (path === '/api/search-internet') return handleInternetSearch(req, res);
    if (path === '/api/saved') return handleGetSaved(req, res);
    if (path === '/api/saved/check') return handleIsSaved(req, res);
    if (path === '/api/stats') return handleStats(req, res);
    if (path === '/api/history') return handleHistory(req, res);
  }

  // POST APIs
  if (method === 'POST') {
    if (path === '/api/saved') return handleSaveJob(req, res);
    if (path === '/api/saved/remove') return handleRemoveJob(req, res);
    if (path === '/api/saved/bulk-delete') return handleBulkDelete(req, res);
    if (path === '/api/saved/status') return handleUpdateStatus(req, res);
    if (path === '/api/saved/notes') return handleUpdateNotes(req, res);
  }

  serveStatic(req, res);
});

server.listen(PORT, () => {
  console.log(`\n Zamora Homes — http://localhost:${PORT}\n`);
});
