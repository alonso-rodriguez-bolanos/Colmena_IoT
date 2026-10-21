import { firebaseConfig, COLECCION, MAX_DIAS_RANGO } from './config.js';
import { crearRepoFirestore, crearRepoDemo } from './datos.js';
import {
  SENSORES, promedioPorHora, promedioPorDia, maximo, minimo, inicioDiaCR, finDiaCR,
  fechaISOCR, textoFecha, textoFechaHoraCR, formatear,
} from './calculos.js';

const CONSULTAS = {
  hora: {
    sensor: 'actividad',
    descripcion: 'Promedio de un sensor en cada hora de un día. Por defecto, actividad: ¿a qué horas salen las abejas a buscar alimento?',
  },
  dia: {
    sensor: 'peso',
    descripcion: 'Promedio diario de un sensor en un rango de fechas. Por defecto, peso: ¿la colmena gana o pierde reservas?',
  },
  maxmin: {
    sensor: 'temp_int',
    descripcion: 'Valor máximo y mínimo de un sensor dentro de las fechas que elija, con el momento en que ocurrieron.',
  },
  historico: {
    sensor: 'temp_ext',
    descripcion: 'Valor máximo y mínimo de un sensor en todos los datos guardados.',
  },
};

const $ = (id) => document.getElementById(id);
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
let repo, consulta = 'hora', grafico = null;

/** Error causado por los filtros del usuario (se muestra tal cual). */
class ErrorUsuario extends Error {}

// ---------- interfaz ----------
function mostrarMensaje(texto, esError = false) {
  const m = $('mensaje');
  m.textContent = texto;
  m.className = 'mensaje' + (esError ? ' error' : '');
  m.hidden = !texto;
}

function elegirConsulta(nueva) {
  consulta = nueva;
  for (const b of document.querySelectorAll('[role=tab]')) {
    b.setAttribute('aria-selected', String(b.dataset.consulta === nueva));
  }
  $('descripcion').textContent = CONSULTAS[nueva].descripcion;
  $('sensor').value = CONSULTAS[nueva].sensor;
  for (const l of document.querySelectorAll('[data-para]')) {
    const visible = l.dataset.para.split(' ').includes(nueva);
    l.hidden = !visible;
    l.querySelector('input').disabled = !visible;
  }
  $('resultado').hidden = true;
  mostrarMensaje('');
}

async function prepararFechas() {
  const r = await repo.rango();
  if (!r) { mostrarMensaje('La colección está vacía: todavía no hay datos subidos.', true); return; }
  const min = fechaISOCR(r.primero), max = fechaISOCR(r.ultimo);
  for (const id of ['dia', 'desde', 'hasta']) { $(id).min = min; $(id).max = max; }
  $('dia').value = max;
  $('hasta').value = max;
  const d = new Date(inicioDiaCR(max).getTime() - 6 * 864e5);
  $('desde').value = fechaISOCR(d) < min ? min : fechaISOCR(d);
}

// ---------- gráficos ----------
function dibujar(tipo, etiquetas, valores, sensor, ejeX) {
  const s = SENSORES[sensor];
  const serie = css('--serie'), rejilla = css('--rejilla'), texto2 = css('--texto-2');
  grafico?.destroy();
  $('zona-grafico').hidden = false;
  grafico = new Chart($('grafico'), {
    type: tipo,
    data: {
      labels: etiquetas,
      datasets: [{
        label: `${s.nombre} (${s.unidad})`,
        data: valores,
        backgroundColor: tipo === 'bar' ? serie : serie + '22',
        borderColor: serie,
        borderWidth: tipo === 'bar' ? 0 : 2,
        borderRadius: tipo === 'bar' ? { topLeft: 4, topRight: 4 } : 0,
        pointRadius: tipo === 'line' ? 4 : 0,
        pointHoverRadius: 6,
        fill: tipo === 'line',
        tension: 0.25,
        spanGaps: false,
      }],
    },
    options: {
      maintainAspectRatio: false,
      animation: { duration: 250 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (it) => (ejeX === 'hora' ? `${it[0].label} (hora CR)` : it[0].label),
            label: (it) => (it.raw === null ? 'Sin datos' : formatear(sensor, it.raw)),
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: ejeX === 'hora' ? 'Hora del día' : 'Día', color: texto2 },
          grid: { display: false }, ticks: { color: texto2, maxRotation: 0, autoSkip: true },
        },
        y: {
          // Sin forzar 0: la temperatura interna (34-35 °C) se vería plana.
          beginAtZero: false,
          title: { display: true, text: s.unidad, color: texto2 },
          grid: { color: rejilla }, border: { display: false }, ticks: { color: texto2 },
        },
      },
    },
  });
}

function tabla(encabezados, filas) {
  $('tabla').innerHTML =
    `<thead><tr>${encabezados.map((h) => `<th>${h}</th>`).join('')}</tr></thead>` +
    `<tbody>${filas.map((f) => `<tr>${f.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody>`;
  $('detalle-tabla').hidden = false;
}

const FLECHA_ARRIBA = '<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4l7 8h-5v8h-4v-8H5z" fill="currentColor"/></svg>';
const FLECHA_ABAJO = '<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20l-7-8h5V4h4v8h5z" fill="currentColor"/></svg>';

function tarjetas(sensor, max, min, sufijo = '') {
  const t = (clase, icono, nombre, e) => `
    <div class="tarjeta ${clase}">
      <div class="etq">${icono}${nombre}${sufijo}</div>
      <div class="val">${e ? formatear(sensor, e.valor) : '—'}</div>
      <div class="cuando">${e ? textoFechaHoraCR(e.ts) : 'Sin datos'}</div>
    </div>`;
  $('extremos').innerHTML = t('alto', FLECHA_ARRIBA, 'Máximo', max) + t('bajo', FLECHA_ABAJO, 'Mínimo', min);
  $('zona-grafico').hidden = true;
  grafico?.destroy(); grafico = null;
  $('detalle-tabla').hidden = true;
}

// ---------- consultas ----------
function leerRango() {
  const desde = $('desde').value, hasta = $('hasta').value;
  if (!desde || !hasta) throw new ErrorUsuario('Elija las dos fechas.');
  if (desde > hasta) throw new ErrorUsuario('La fecha "Desde" debe ser anterior o igual a "Hasta".');
  const dias = (inicioDiaCR(hasta) - inicioDiaCR(desde)) / 864e5 + 1;
  if (dias > MAX_DIAS_RANGO) throw new ErrorUsuario(`El rango máximo es de ${MAX_DIAS_RANGO} días.`);
  return { desde, hasta, dias };
}

async function ejecutar() {
  const sensor = $('sensor').value, s = SENSORES[sensor];
  $('extremos').innerHTML = '';

  if (consulta === 'hora') {
    const dia = $('dia').value;
    if (!dia) throw new ErrorUsuario('Elija un día.');
    const lecturas = await repo.entre(inicioDiaCR(dia), finDiaCR(dia));
    const prom = promedioPorHora(lecturas, sensor);
    if (prom.every((v) => v === null)) return mostrarMensaje('No hay datos para ese día.');
    $('titulo-resultado').textContent = `${s.nombre} · promedio por hora · ${textoFecha(dia)} · ${lecturas.length} lecturas`;
    const horas = prom.map((_, h) => `${h}:00`);
    dibujar('bar', horas, prom, sensor, 'hora');
    tabla(['Hora', `Promedio (${s.unidad})`],
      prom.map((v, h) => [horas[h], v === null ? 'sin datos' : v.toFixed(s.dec + 1)]));
  }

  if (consulta === 'dia') {
    const { desde, hasta, dias } = leerRango();
    const lecturas = await repo.entre(inicioDiaCR(desde), finDiaCR(hasta));
    const prom = promedioPorDia(lecturas, sensor);
    if (!prom.length) return mostrarMensaje('No hay datos en ese rango.');
    $('titulo-resultado').textContent =
      `${s.nombre} · promedio diario · ${textoFecha(desde)} a ${textoFecha(hasta)} · ${prom.length} de ${dias} días con datos`;
    const etiquetas = prom.map((p) => textoFecha(p.dia).slice(0, 5));
    dibujar('line', etiquetas, prom.map((p) => p.promedio), sensor, 'dia');
    tabla(['Día', `Promedio (${s.unidad})`], prom.map((p) => [textoFecha(p.dia), p.promedio.toFixed(s.dec + 1)]));
  }

  if (consulta === 'maxmin') {
    const { desde, hasta } = leerRango();
    const lecturas = await repo.entre(inicioDiaCR(desde), finDiaCR(hasta));
    if (!lecturas.length) return mostrarMensaje('No hay datos en ese rango.');
    $('titulo-resultado').textContent =
      `${s.nombre} · ${textoFecha(desde)} a ${textoFecha(hasta)} · ${lecturas.length} lecturas`;
    tarjetas(sensor, maximo(lecturas, sensor), minimo(lecturas, sensor));
  }

  if (consulta === 'historico') {
    const [max, min] = await Promise.all([repo.extremoHistorico(sensor, true), repo.extremoHistorico(sensor, false)]);
    $('titulo-resultado').textContent = `${s.nombre} · todo el histórico`;
    tarjetas(sensor, max, min, ' histórico');
  }

  mostrarMensaje('');
  $('resultado').hidden = false;
}

// ---------- arranque ----------
async function iniciar() {
  $('sensor').innerHTML = Object.entries(SENSORES)
    .map(([k, s]) => `<option value="${k}">${s.nombre} (${s.unidad})</option>`).join('');
  document.querySelectorAll('[role=tab]').forEach((b) =>
    b.addEventListener('click', () => elegirConsulta(b.dataset.consulta)));
  elegirConsulta('hora');

  const demo = new URLSearchParams(location.search).has('demo') || !firebaseConfig.projectId;
  try {
    repo = demo ? crearRepoDemo() : await crearRepoFirestore(firebaseConfig, COLECCION);
    $('fuente').textContent = `Fuente: ${repo.fuente}`;
    await prepararFechas();
  } catch (e) {
    console.error(e);
    $('fuente').textContent = 'Sin conexión a Firebase';
    mostrarMensaje(`No se pudo conectar a Firebase: ${e.message}`, true);
  }

  $('filtros').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (!repo) return;
    const boton = $('consultar');
    boton.disabled = true; boton.textContent = 'Consultando…';
    try {
      await ejecutar();
    } catch (e) {
      if (!(e instanceof ErrorUsuario)) console.error(e);
      $('resultado').hidden = true;
      mostrarMensaje(e instanceof ErrorUsuario ? e.message
        : `Error al consultar (revise la conexión): ${e.message}`, true);
    } finally {
      boton.disabled = false; boton.textContent = 'Consultar';
    }
  });
}

iniciar();
