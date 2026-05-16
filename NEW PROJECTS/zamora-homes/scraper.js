import { request as httpsRequest } from 'node:https';
import { request as httpRequest } from 'node:http';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36';
const TIMEOUT = 12000;

function fetchHtml(url) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? httpsRequest : httpRequest;
    const parsed = new URL(url);
    const opts = {
      hostname: parsed.hostname,
      path: parsed.pathname + parsed.search,
      method: 'GET',
      headers: {
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'identity',
        'Referer': parsed.origin + '/',
      },
      timeout: TIMEOUT,
    };

    const req = mod(opts, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        const redirect = new URL(res.headers.location, url).href;
        if (redirect.split('/').length < 10) {
          res.resume();
          return reject(new Error(`too many redirects`));
        }
        return fetchHtml(redirect).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    });

    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.end();
  });
}

function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? httpsRequest : httpRequest;
    const parsed = new URL(url);
    const opts = {
      hostname: parsed.hostname,
      path: parsed.pathname + parsed.search,
      method: 'GET',
      headers: {
        'User-Agent': UA,
        'Accept': 'application/json',
      },
      timeout: TIMEOUT,
    };

    const req = mod(opts, (res) => {
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => {
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch (e) { reject(new Error(`JSON parse error: ${e.message}`)); }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.end();
  });
}

// ── URL Builders ─────────────────────────────────────────────────────────────

function buildInmuebles24Url(filters) {
  const opType = filters.type === 'renta' ? 'en-renta' : 'en-venta';
  const propMap = { casa: 'casa', departamento: 'departamento', terreno: 'terreno', local: 'local-comercial' };
  const prop = propMap[filters.property] || 'inmueble';
  const keyword = filters.keyword ? `-${filters.keyword.replace(/\s+/g, '-')}` : '';
  return `https://www.inmuebles24.com/propiedades/${prop}-${opType}-en-zamora-de-hidalgo-michoacan${keyword}.html`;
}

function buildMercadoLibreUrl(filters) {
  const op = filters.type === 'renta' ? 'renta' : 'venta';
  const propMap = { casa: 'casas', departamento: 'departamentos', terreno: 'terrenos-lotes', local: 'locales-oficinas' };
  const prop = propMap[filters.property] || 'casas';
  const keyword = filters.keyword ? `/_Keywords_${encodeURIComponent(filters.keyword)}` : '';
  return `https://inmuebles.mercadolibre.com.mx/${prop}/${op}/zamora-de-hidalgo-michoacan/${keyword}`;
}

function buildVivanunciosUrl(filters) {
  const op = filters.type === 'renta' ? 'renta' : 'venta';
  const propMap = { casa: 'casa', departamento: 'departamento', terreno: 'terreno', local: 'local-comercial' };
  const prop = propMap[filters.property] || 'inmueble';
  const keyword = filters.keyword ? `?q=${encodeURIComponent(filters.keyword)}` : '';
  return `https://www.vivanuncios.com.mx/s/${prop}-en-${op}-v/zamora-de-hidalgo-michoacan/${keyword}`;
}

function buildLamudiUrl(filters) {
  const op = filters.type === 'renta' ? 'renta' : 'venta';
  const propMap = { casa: 'casas', departamento: 'departamentos', terreno: 'terrenos', local: 'locales' };
  const prop = propMap[filters.property] || 'casas';
  const keyword = filters.keyword ? `?q=${encodeURIComponent(filters.keyword)}` : '';
  return `https://www.lamudi.com.mx/zamora-de-hidalgo/${op}/${prop}/${keyword}`;
}

// ── Parsers ───────────────────────────────────────────────────────────────────

function mapPropertyType(raw) {
  const s = (raw || '').toLowerCase();
  if (s.includes('departamento') || s.includes('apartment') || s.includes('depto')) return 'departamento';
  if (s.includes('terreno') || s.includes('land') || s.includes('lote')) return 'terreno';
  if (s.includes('local') || s.includes('commercial') || s.includes('oficina')) return 'local';
  return 'casa';
}

function parsePrice(priceObj) {
  if (typeof priceObj === 'number') return priceObj;
  if (typeof priceObj === 'object' && priceObj !== null) {
    return Number(priceObj.amount || priceObj.value || 0) || 0;
  }
  return 0;
}

function parsePriceString(s) {
  return Number((s || '').replace(/[^0-9]/g, '')) || 0;
}

function parseInmuebles24(html, url) {
  const listings = [];

  try {
    const m = html.match(/window\.__PRELOADED_STATE__\s*=\s*(\{[\s\S]*?)\s*;?\s*<\/script>/);
    if (m) {
      const raw = m[1].replace(/undefined/g, 'null');
      const state = JSON.parse(raw);
      const posts = state?.searchResults?.list || state?.listings || state?.listado?.list || [];
      for (const p of posts.slice(0, 20)) {
        listings.push({
          id: `i24-${p.postingId || p.id || Math.random().toString(36).slice(2,8)}`,
          title: p.title || p.postingTitle || p.subject || 'Inmueble en Zamora',
          type: String(p.operation || '').includes('rent') || String(p.operationType || '').includes('rent') ? 'renta' : 'venta',
          property: mapPropertyType(p.propertyType || p.realEstateType || ''),
          price: parsePrice(p.price || p.priceOperation || {}),
          currency: 'MXN',
          bedrooms: p.rooms || p.bedrooms || 0,
          bathrooms: p.bathrooms || 0,
          area: p.surface || p.area || p.lotArea || 0,
          neighborhood: p.location?.name || p.zone?.name || p.neighborhood || 'Zamora de Hidalgo',
          address: p.location?.address || '',
          description: p.description || '',
          features: (p.features || p.amenities || []).map(String),
          contact: p.publisher?.name || p.developer?.name || 'Inmuebles24',
          phone: p.publisher?.phone || '',
          source: 'Inmuebles24',
          sourceUrl: p.url || p.permalink || `https://www.inmuebles24.com/propiedad/${p.postingId}`,
          image: (p.images || p.gallery || [])[0]?.src || (p.images || [])[0]?.url || '',
        });
      }
      if (listings.length) return listings;
    }
  } catch (e) { console.error('[Inmuebles24 parse]', e.message); }

  const idRe = /data-posting-id="(\d+)"/gi;
  const titleRe = /class="[^"]*(?:postingTitle|PostingTitle|title)[^"]*"[^>]*>([^<]+)/gi;
  const priceRe = /data-price=["']([^"']+)["']/gi;
  const locRe = /class="[^"]*(?:postingLocation|location)[^"]*"[^>]*>([^<]+)/gi;

  const ids = [...html.matchAll(idRe)].map(m => m[1]).filter(Boolean);
  const titles = [...html.matchAll(titleRe)].map(m => m[1].trim());
  const prices = [...html.matchAll(priceRe)].map(m => m[1]);
  const locs = [...html.matchAll(locRe)].map(m => m[1].trim());

  const count = Math.min(ids.length, 20);
  for (let i = 0; i < count; i++) {
    listings.push({
      id: `i24-${ids[i]}`, title: titles[i] || 'Inmueble en Zamora', type: 'venta', property: 'casa',
      price: parsePriceString(prices[i] || '0'), currency: 'MXN', bedrooms: 0, bathrooms: 0, area: 0,
      neighborhood: locs[i] || 'Zamora de Hidalgo', address: '', description: 'Listado encontrado en Inmuebles24',
      features: [], contact: 'Inmuebles24', phone: '', source: 'Inmuebles24',
      sourceUrl: `https://www.inmuebles24.com/propiedades/${ids[i]}.html`, image: '',
    });
  }

  return listings;
}

function parseMercadoLibre(html, url) {
  const listings = [];

  try {
    const m = html.match(/__PRELOADED_STATE__\s*=\s*(\{[\s\S]*?)\s*;?\s*<\/script>/);
    if (m) {
      const raw = m[1].replace(/undefined/g, 'null');
      const state = JSON.parse(raw);
      const items = state?.components?.searchResults?.body?.results || [];
      for (const item of items.slice(0, 20)) {
        const attrs = item.attributes || [];
        const getAttr = id => attrs.find(a => a.id === id)?.value_name || '';
        listings.push({
          id: `ml-${item.id || Math.random().toString(36).slice(2,8)}`,
          title: item.title || '',
          type: String(item.title || '').toLowerCase().includes('renta') ? 'renta' : 'venta',
          property: mapPropertyType(getAttr('PROPERTY_TYPE') || ''),
          price: item.price || 0, currency: item.currency_id || 'MXN',
          bedrooms: parseInt(getAttr('BEDROOMS')) || 0,
          bathrooms: parseInt(getAttr('FULL_BATHROOMS')) || 0,
          area: parseInt(getAttr('COVERED_AREA') || getAttr('TOTAL_AREA')) || 0,
          neighborhood: item.address?.city?.name || 'Zamora', address: item.address?.state?.name || '',
          description: item.title || 'Inmueble en MercadoLibre',
          features: attrs.slice(0, 5).map(a => a.value_name).filter(Boolean),
          contact: 'MercadoLibre', phone: '', source: 'MercadoLibre',
          sourceUrl: item.permalink || `https://www.mercadolibre.com.mx/p/${item.id}`,
          image: (item.thumbnail || '').replace('-I.jpg', '-O.jpg'),
        });
      }
      if (listings.length) return listings;
    }
  } catch (e) { console.error('[MercadoLibre parse]', e.message); }

  const linkRe = /href="(https:\/\/www\.mercadolibre\.com\.mx\/[^"]+)"[^>]*>/gi;
  const titleRe = /class="[^"]*ui-search-item__title[^"]*"[^>]*>([^<]+)/gi;
  const priceRe = /class="[^"]*price-tag-fraction[^"]*"[^>]*>([^<]+)/gi;

  const links = [...html.matchAll(linkRe)].map(m => m[1]).filter((v, i, a) => a.indexOf(v) === i);
  const titles = [...html.matchAll(titleRe)].map(m => m[1].trim());
  const prices = [...html.matchAll(priceRe)].map(m => m[1].trim());

  const count = Math.min(links.length, 20);
  for (let i = 0; i < count; i++) {
    listings.push({
      id: `ml-${i}-${Date.now()}`, title: titles[i] || 'Inmueble en Zamora', type: 'venta', property: 'casa',
      price: parsePriceString(prices[i] || '0'), currency: 'MXN', bedrooms: 0, bathrooms: 0, area: 0,
      neighborhood: 'Zamora de Hidalgo', address: '', description: 'Listado encontrado en MercadoLibre',
      features: [], contact: 'MercadoLibre', phone: '', source: 'MercadoLibre',
      sourceUrl: links[i] || '', image: '',
    });
  }

  return listings;
}

function parseVivanuncios(html, url) {
  const listings = [];

  try {
    const m = html.match(/__INITIAL_STATE__\s*=\s*(\{[\s\S]*?)\s*;?\s*<\/script>/);
    if (m) {
      const raw = m[1].replace(/undefined/g, 'null');
      const state = JSON.parse(raw);
      const ads = state?.search?.results?.ads || state?.listings || [];
      for (const ad of ads.slice(0, 20)) {
        listings.push({
          id: `va-${ad.id || Math.random().toString(36).slice(2,8)}`,
          title: ad.subject || ad.title || '',
          type: String(ad.operation || '').includes('rent') ? 'renta' : 'venta',
          property: mapPropertyType(ad.propertyType || ''),
          price: parsePrice(ad.price || {}), currency: 'MXN',
          bedrooms: ad.bedrooms || 0, bathrooms: ad.bathrooms || 0, area: ad.area || 0,
          neighborhood: ad.location?.name || 'Zamora', address: ad.location?.address || '',
          description: ad.body || '', features: (ad.features || []).map(String),
          contact: 'Vivanuncios', phone: ad.contact?.phone || '', source: 'Vivanuncios',
          sourceUrl: ad.url || ad.permalink || '', image: (ad.images || [])[0]?.src || '',
        });
      }
      if (listings.length) return listings;
    }
  } catch (e) { console.error('[Vivanuncios parse]', e.message); }

  const idRe = /data-ad-id="([^"]+)"/gi;
  const titleRe = /class="[^"]*(?:ad-title|AdTitle)[^"]*"[^>]*>([^<]+)/gi;
  const priceRe = /class="[^"]*(?:ad-price|AdPrice)[^"]*"[^>]*>([^<]+)/gi;

  const ids = [...html.matchAll(idRe)].map(m => m[1]);
  const titles = [...html.matchAll(titleRe)].map(m => m[1].trim());
  const prices = [...html.matchAll(priceRe)].map(m => m[1].trim());

  const count = Math.min(ids.length, 20);
  for (let i = 0; i < count; i++) {
    listings.push({
      id: `va-${ids[i]}`, title: titles[i] || 'Inmueble en Zamora', type: 'venta', property: 'casa',
      price: parsePriceString(prices[i] || '0'), currency: 'MXN', bedrooms: 0, bathrooms: 0, area: 0,
      neighborhood: 'Zamora de Hidalgo', address: '', description: 'Listado encontrado en Vivanuncios',
      features: [], contact: 'Vivanuncios', phone: '', source: 'Vivanuncios',
      sourceUrl: `https://www.vivanuncios.com.mx/anuncio/${ids[i]}`, image: '',
    });
  }

  return listings;
}

// ── Lamudi Parser ──────────────────────────────────────────────────────────

function parseLamudi(html, url) {
  const listings = [];

  try {
    const m = html.match(/__NEXT_DATA__\s*=\s*(\{[\s\S]*?)\s*;?\s*<\/script>/);
    if (m) {
      const state = JSON.parse(m[1]);
      const items = state?.props?.pageProps?.listings || state?.props?.pageProps?.properties || [];
      for (const p of items.slice(0, 20)) {
        listings.push({
          id: `la-${p.id || Math.random().toString(36).slice(2,8)}`,
          title: p.title || 'Inmueble en Zamora',
          type: String(p.listing_type || p.operation || '').includes('rent') ? 'renta' : 'venta',
          property: mapPropertyType(p.property_type || p.category || ''),
          price: parsePrice(p.price || {}),
          currency: 'MXN',
          bedrooms: p.bedrooms || 0,
          bathrooms: p.bathrooms || 0,
          area: p.building_size || p.lot_size || p.area || 0,
          neighborhood: p.location?.name || p.location_name || 'Zamora de Hidalgo',
          address: p.location?.address || '',
          description: p.description || '',
          features: (p.amenities || p.features || []).map(String),
          contact: p.agent?.name || 'Lamudi',
          phone: p.agent?.phone || '',
          source: 'Lamudi',
          sourceUrl: p.url || p.permalink || `https://www.lamudi.com.mx/zamora-de-hidalgo/`,
          image: (p.images || [])[0]?.url || (p.gallery || [])[0]?.src || '',
        });
      }
      if (listings.length) return listings;
    }
  } catch (e) { console.error('[Lamudi parse]', e.message); }

  const linkRe = /href="(https:\/\/www\.lamudi\.com\.mx\/[^"]+)"[^>]*>/gi;
  const titleRe = /class="[^"]*ListingCell-Title[^"]*"[^>]*>([^<]+)/gi;
  const priceRe = /class="[^"]*Price[^"]*"[^>]*>([^<]+)/gi;

  const links = [...html.matchAll(linkRe)].map(m => m[1]).filter((v, i, a) => a.indexOf(v) === i);
  const titles = [...html.matchAll(titleRe)].map(m => m[1].trim());
  const prices = [...html.matchAll(priceRe)].map(m => m[1].trim());

  const count = Math.min(links.length, 20);
  for (let i = 0; i < count; i++) {
    listings.push({
      id: `la-${i}-${Date.now()}`, title: titles[i] || 'Inmueble en Zamora', type: 'venta', property: 'casa',
      price: parsePriceString(prices[i] || '0'), currency: 'MXN', bedrooms: 0, bathrooms: 0, area: 0,
      neighborhood: 'Zamora de Hidalgo', address: '', description: 'Listado encontrado en Lamudi',
      features: [], contact: 'Lamudi', phone: '', source: 'Lamudi',
      sourceUrl: links[i] || '', image: '',
    });
  }

  return listings;
}

// ── Main Search ──────────────────────────────────────────────────────────────

export async function searchInternet(filters) {
  const sources = [
    { name: 'Inmuebles24', buildUrl: buildInmuebles24Url, parse: parseInmuebles24 },
    { name: 'MercadoLibre', buildUrl: buildMercadoLibreUrl, parse: parseMercadoLibre },
    { name: 'Vivanuncios', buildUrl: buildVivanunciosUrl, parse: parseVivanuncios },
    { name: 'Lamudi', buildUrl: buildLamudiUrl, parse: parseLamudi },
  ];

  const results = await Promise.allSettled(
    sources.map(async (src) => {
      try {
        const url = src.buildUrl(filters);
        const html = await fetchHtml(url);
        const listings = src.parse(html, url);
        return { listings, url };
      } catch (err) {
        const url = src.buildUrl(filters);
        return { listings: [], url, error: err.message };
      }
    })
  );

  const allListings = [];
  const portalLinks = [];
  const errors = [];

  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    const src = sources[i];
    if (r.status === 'fulfilled') {
      const { listings, url, error } = r.value;
      allListings.push(...listings);
      portalLinks.push({ name: src.name, url });
      if (error || listings.length === 0) {
        errors.push({ source: src.name, error: error || 'blocked or no results', searchUrl: url });
      }
    } else {
      const url = src.buildUrl(filters);
      portalLinks.push({ name: src.name, url });
      errors.push({ source: src.name, error: r.reason?.message || 'failed', searchUrl: url });
    }
  }

  return { listings: allListings, portalLinks, errors };
}
