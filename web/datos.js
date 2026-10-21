// Fuentes de datos. La interfaz solo usa estos 3 métodos:
//   entre(desde, hasta)            lecturas con desde <= ts < hasta, ordenadas
//   extremoHistorico(sensor, max)  {valor, ts} de toda la colección
//   rango()                        {primero, ultimo} o null
import { maximo, minimo, SENSORES } from './calculos.js';

const VERSION_FIREBASE = '10.12.2';

export async function crearRepoFirestore(config, coleccion = 'lecturas') {
  const base = `https://www.gstatic.com/firebasejs/${VERSION_FIREBASE}`;
  const { initializeApp } = await import(`${base}/firebase-app.js`);
  const fs = await import(`${base}/firebase-firestore.js`);
  const db = fs.getFirestore(initializeApp(config));
  const col = fs.collection(db, coleccion);

  const aLectura = (doc) => {
    const d = doc.data();
    const l = { ts: d.ts.toDate(), origen: d.origen ?? 'real' };
    for (const s of Object.keys(SENSORES)) if (typeof d[s] === 'number') l[s] = d[s];
    return l;
  };
  let rangoCache = null;

  return {
    fuente: `Firebase · ${config.projectId} · ${coleccion}`,

    // Un día cada 5 min = 288 lecturas de Firestore; 7 días ≈ 2 016.
    async entre(desde, hasta) {
      const q = fs.query(col,
        fs.where('ts', '>=', fs.Timestamp.fromDate(desde)),
        fs.where('ts', '<', fs.Timestamp.fromDate(hasta)),
        fs.orderBy('ts'));
      return (await fs.getDocs(q)).docs.map(aLectura);
    },

    // 1 lectura de Firestore: ordenar por el sensor y tomar el primero.
    async extremoHistorico(sensor, esMaximo) {
      const q = fs.query(col, fs.orderBy(sensor, esMaximo ? 'desc' : 'asc'), fs.limit(1));
      const snap = await fs.getDocs(q);
      if (snap.empty) return null;
      const l = aLectura(snap.docs[0]);
      return { valor: l[sensor], ts: l.ts };
    },

    async rango() {
      if (rangoCache) return rangoCache;
      const [a, b] = await Promise.all([
        fs.getDocs(fs.query(col, fs.orderBy('ts'), fs.limit(1))),
        fs.getDocs(fs.query(col, fs.orderBy('ts', 'desc'), fs.limit(1))),
      ]);
      if (a.empty) return null;
      rangoCache = { primero: aLectura(a.docs[0]).ts, ultimo: aLectura(b.docs[0]).ts };
      return rangoCache;
    },
  };
}

/** Datos inventados (7 días cada 5 min) para trabajar sin Firebase. */
export function crearRepoDemo() {
  let semilla = 42; // mulberry32: aleatorio repetible
  const rnd = () => {
    let t = (semilla = (semilla + 0x6d2b79f5) | 0);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const ruido = (a) => (rnd() - 0.5) * 2 * a;
  const DESF = 6 * 3600e3;
  const hoyCR = new Date(Date.now() - DESF); hoyCR.setUTCHours(0, 0, 0, 0);
  const fin = hoyCR.getTime() + DESF, inicio = fin - 7 * 864e5;
  const datos = [];
  let peso = 24, nub = 1, diaAct = -1;
  for (let t = inicio; t < fin; t += 300e3) {
    const c = new Date(t - DESF), h = c.getUTCHours() + c.getUTCMinutes() / 60;
    if (c.getUTCDate() !== diaAct) { diaAct = c.getUTCDate(); nub = 0.6 + rnd() * 0.4; }
    const dia = h >= 6 && h < 18;
    peso += h >= 9 && h < 16 ? 0.0025 * nub : -0.0008;
    const lim = (v) => Math.round(Math.min(100, Math.max(0, v)));
    datos.push({
      ts: new Date(t), origen: 'aumentado',
      temp_int: +(34.5 + 0.3 * Math.sin(2 * Math.PI * (h - 9) / 24) + ruido(0.15)).toFixed(2),
      temp_ext: +(26 + 4 * Math.sin(2 * Math.PI * (h - 9) / 24) + ruido(0.4)).toFixed(2),
      peso: +(peso + ruido(0.01)).toFixed(2),
      actividad: lim(dia ? 85 * nub * Math.exp(-((h - 11) ** 2) / 12.5) + ruido(4) : Math.abs(ruido(1))),
      gas: Math.round(200 + ruido(15)),
      luz: lim(dia ? 100 * Math.sin(Math.PI * (h - 6) / 12) * nub + ruido(3) : 2 + ruido(2)),
    });
  }
  const espera = () => new Promise((r) => setTimeout(r, 250));
  return {
    fuente: 'Datos de demostración (sin Firebase)',
    async entre(desde, hasta) { await espera(); return datos.filter((l) => l.ts >= desde && l.ts < hasta); },
    async extremoHistorico(s, esMax) { await espera(); return esMax ? maximo(datos, s) : minimo(datos, s); },
    async rango() { return { primero: datos[0].ts, ultimo: datos.at(-1).ts }; },
  };
}
