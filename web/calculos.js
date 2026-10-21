// Cálculos de las consultas. Funciones puras: no saben de Firebase ni del DOM.
// Mismas reglas que la app móvil (ver CONTRATO_DATOS.md):
//  - Se agrupa en hora de Costa Rica (UTC-6, sin horario de verano).
//  - Horas o días sin lecturas se omiten (null), no cuentan como 0.
//  - Lecturas sin valor para el sensor se ignoran.
//  - En un empate de máximo o mínimo gana la lectura más antigua.

export const SENSORES = {
  temp_int:  { nombre: 'Temperatura interna', unidad: '°C', dec: 1 },
  temp_ext:  { nombre: 'Temperatura externa', unidad: '°C', dec: 1 },
  peso:      { nombre: 'Peso', unidad: 'kg', dec: 2 },
  actividad: { nombre: 'Actividad', unidad: '%', dec: 0 },
  gas:       { nombre: 'Gas (aire)', unidad: 'ADC', dec: 0 },
  luz:       { nombre: 'Luz', unidad: '%', dec: 0 },
};

const DESFASE_MS = -6 * 3600 * 1000;
const DIA_MS = 24 * 3600 * 1000;

/** Date "falso" en UTC cuyos getUTC* muestran la hora de reloj de Costa Rica. */
export const relojCR = (fecha) => new Date(fecha.getTime() + DESFASE_MS);

/** "2026-10-15" -> Date de la medianoche de ese día en Costa Rica (06:00 UTC). */
export function inicioDiaCR(isoFecha) {
  const [a, m, d] = isoFecha.split('-').map(Number);
  return new Date(Date.UTC(a, m - 1, d) - DESFASE_MS);
}

/** Inicio del día siguiente al indicado (fin exclusivo de un rango). */
export const finDiaCR = (isoFecha) => new Date(inicioDiaCR(isoFecha).getTime() + DIA_MS);

/** Date -> "2026-10-15" según el calendario de Costa Rica. */
export const fechaISOCR = (fecha) => relojCR(fecha).toISOString().slice(0, 10);

const dos = (n) => String(n).padStart(2, '0');
export const textoFecha = (iso) => { const [a, m, d] = iso.split('-'); return `${d}/${m}/${a}`; };
export function textoFechaHoraCR(fecha) {
  const c = relojCR(fecha);
  return `${dos(c.getUTCDate())}/${dos(c.getUTCMonth() + 1)}/${c.getUTCFullYear()} ` +
         `${dos(c.getUTCHours())}:${dos(c.getUTCMinutes())}`;
}
export const formatear = (sensor, v) =>
  `${v.toFixed(SENSORES[sensor].dec)} ${SENSORES[sensor].unidad}`;

const valor = (l, s) => (typeof l[s] === 'number' && Number.isFinite(l[s]) ? l[s] : null);

/** 24 posiciones (hora 0-23 de CR); null si no hubo datos. */
export function promedioPorHora(lecturas, sensor) {
  const suma = new Array(24).fill(0), n = new Array(24).fill(0);
  for (const l of lecturas) {
    const v = valor(l, sensor);
    if (v === null) continue;
    const h = relojCR(l.ts).getUTCHours();
    suma[h] += v; n[h]++;
  }
  return suma.map((s, h) => (n[h] ? s / n[h] : null));
}

/** [{dia: "2026-10-15", promedio}] ordenado por fecha; solo días con datos. */
export function promedioPorDia(lecturas, sensor) {
  const acc = new Map();
  for (const l of lecturas) {
    const v = valor(l, sensor);
    if (v === null) continue;
    const dia = fechaISOCR(l.ts);
    const a = acc.get(dia) ?? { s: 0, n: 0 };
    a.s += v; a.n++;
    acc.set(dia, a);
  }
  return [...acc.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([dia, { s, n }]) => ({ dia, promedio: s / n }));
}

function extremo(lecturas, sensor, mejor) {
  let res = null;
  for (const l of lecturas) {
    const v = valor(l, sensor);
    if (v === null) continue;
    if (res === null || mejor(v, res.valor) || (v === res.valor && l.ts < res.ts)) {
      res = { valor: v, ts: l.ts };
    }
  }
  return res;
}
export const maximo = (lecturas, s) => extremo(lecturas, s, (a, b) => a > b);
export const minimo = (lecturas, s) => extremo(lecturas, s, (a, b) => a < b);
