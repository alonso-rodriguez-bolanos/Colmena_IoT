import { test } from 'node:test';
import assert from 'node:assert/strict';
import { promedioPorHora, promedioPorDia, maximo, minimo, inicioDiaCR, fechaISOCR, textoFechaHoraCR } from '../calculos.js';

const l = (iso, peso) => ({ ts: new Date(iso), peso });

test('medianoche CR = 06:00 UTC', () => {
  assert.equal(inicioDiaCR('2026-10-15').toISOString(), '2026-10-15T06:00:00.000Z');
  assert.equal(fechaISOCR(new Date('2026-10-15T05:30:00Z')), '2026-10-14');
  assert.equal(textoFechaHoraCR(new Date('2026-10-15T15:35:00Z')), '15/10/2026 09:35');
});

test('promedio por hora en hora CR, omite vacías', () => {
  const r = promedioPorHora([l('2026-10-15T15:00:00Z', 10), l('2026-10-15T15:30:00Z', 20), l('2026-10-15T18:00:00Z', 7)], 'peso');
  assert.equal(r.length, 24); assert.equal(r[9], 15); assert.equal(r[12], 7); assert.equal(r[10], null);
});

test('promedio por día separa según CR', () => {
  const r = promedioPorDia([l('2026-10-15T05:00:00Z', 10), l('2026-10-15T07:00:00Z', 20), l('2026-10-15T20:00:00Z', 30)], 'peso');
  assert.deepEqual(r, [{ dia: '2026-10-14', promedio: 10 }, { dia: '2026-10-15', promedio: 25 }]);
});

test('extremos: empate gana el más antiguo; vacío = null; ignora faltantes', () => {
  const d = [l('2026-10-15T13:00:00Z', 30), l('2026-10-15T12:00:00Z', 30), l('2026-10-15T13:00:00Z', 5), { ts: new Date(), gas: 1 }];
  assert.equal(maximo(d, 'peso').ts.toISOString(), '2026-10-15T12:00:00.000Z');
  assert.equal(minimo(d, 'peso').valor, 5);
  assert.equal(maximo([], 'peso'), null);
});
