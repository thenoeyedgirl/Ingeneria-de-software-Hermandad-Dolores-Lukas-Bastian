/*
 * Gráficos interactivos del panel de Administración (#/admin/reportes) — F6 · RF19–RF23, RF35, RNF02, RNF03.
 * Usa Chart.js 4.4 local (vendor/chart.umd.min.js, sin CDN). Todo el trabajo parte de UN dataset filtrado
 * en el servidor (/api/reportes/dataset) y se agrupa en el navegador.
 *
 * Contenido: utilidades puras (testeables con Node) -> estado y filtros -> gráficos G1–G9 -> explorador G0.
 * Futuro (volumen alto): mover el GROUP BY al SQL, por dimensión.
 */
(function () {
  "use strict";

  // ===================================================================
  // 1. CONSTANTES Y UTILIDADES PURAS
  // ===================================================================
  const UMBRAL_AGRUPACION = 3; // grupos con menos de 3 pacientes se juntan en «Otras» (RNF03)
  const ESTADOS = ["RESERVADA", "ASISTIDA", "INASISTIDA", "CANCELADA"];
  const ETIQ_ESTADO = { RESERVADA: "Reservada", ASISTIDA: "Asistida", INASISTIDA: "Inasistida", CANCELADA: "Cancelada" };
  // Colores semánticos de estado: no se reutilizan para otras series.
  const COLOR_ESTADO = { RESERVADA: "#2563eb", ASISTIDA: "#16a34a", INASISTIDA: "#d97706", CANCELADA: "#dc2626" };
  // Paleta categórica fija (validada para daltonismo con el validador de dataviz), distinta de los colores de estado.
  const PALETA = ["#0d9488", "#c026d3", "#a8672a", "#6366f1", "#db2777", "#0284c7", "#7c3aed"];
  const COLOR_OTROS = "#94a3b8";
  const COLOR_UNICO = "#0f766e"; // var(--teal): gráficos de una sola serie
  const COLOR_TASAS = { asistencia: "#16a34a", inasistencia: "#d97706", cancelacion: "#dc2626", confirmacion: "#2563eb", confirmaNoAsiste: "#7c3aed" };
  const INK = "#1e293b";
  const INK_2 = "#5f6f84";
  const GRILLA = "rgba(100, 116, 139, 0.16)";
  const ETIQ_CANAL = { ASISTIDO_PRESENCIAL: "Presencial (mesón)", ASISTIDO_TELEFONO: "Telefónico", SOLICITUD_WEB: "Solicitud web" };
  const TRAMOS = ["0–17 años", "18–35 años", "36–59 años", "60+ años", "Sin dato"];
  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const PUNTOS = ["circle", "rect", "triangle", "rectRot", "star", "crossRot", "cross"];
  const MAX_SERIES = 7;
  const CLAVE_VISIBILIDAD = "ga_visibilidad";
  const CLAVE_VISTAS = "ga_vistas";
  const CLAVE_SECCIONES = "ga_secciones";
  const GRAFICOS = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"];
  const NOMBRES = {
    G0: "Explorador general", G1: "Citas en el tiempo", G2: "Horas más demandadas", G3: "Citas por policlínico",
    G4: "Citas por profesional", G5: "Tasas por policlínico", G6: "Ocupación de bloques",
    G7: "Caracterización de pacientes", G8: "Canal de registro", G9: "Encuestas post-atención",
  };

  const pad2 = (n) => String(n).padStart(2, "0");
  const escapar = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function tasa(num, den) { return den === 0 || den == null ? null : (100 * num) / den; } // null = sin datos (nunca 0 %)
  function formatPct(v) { return v === null || v === undefined || Number.isNaN(v) ? "—" : `${(Math.round(v * 10) / 10).toFixed(1).replace(".", ",")} %`; }
  function formatNum(v) { return v === null || v === undefined ? "—" : String(Math.round(v * 100) / 100).replace(".", ","); }

  function parseFecha(iso) { const [y, m, d] = String(iso).slice(0, 10).split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)); }
  function isoDe(d) { return d.toISOString().slice(0, 10); }
  function sumarDias(iso, n) { const d = parseFecha(iso); d.setUTCDate(d.getUTCDate() + n); return isoDe(d); }
  function hoyISO() { const n = new Date(); return `${n.getFullYear()}-${pad2(n.getMonth() + 1)}-${pad2(n.getDate())}`; }

  function semanaISO(iso) {
    const d = parseFecha(iso);
    const dia = (d.getUTCDay() + 6) % 7;
    d.setUTCDate(d.getUTCDate() - dia + 3); // jueves de esa semana
    const primerJueves = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
    const sem = 1 + Math.round(((d - primerJueves) / 86400000 - 3 + ((primerJueves.getUTCDay() + 6) % 7)) / 7);
    return { anio: d.getUTCFullYear(), sem };
  }

  // día (YYYY-MM-DD) · semana ISO (2026-S47) · mes (2026-11) · semestre (2026-S2) · año (2026)
  function claveTemporal(fecha, agrupacion) {
    const f = String(fecha).slice(0, 10);
    switch (agrupacion) {
      case "semana": { const { anio, sem } = semanaISO(f); return `${anio}-S${pad2(sem)}`; }
      case "mes": return f.slice(0, 7);
      case "semestre": return `${f.slice(0, 4)}-S${Number(f.slice(5, 7)) <= 6 ? 1 : 2}`;
      case "anio": return f.slice(0, 4);
      default: return f;
    }
  }

  // Todos los períodos entre dos fechas (inclusive), para completar con 0 y que la línea no salte.
  function periodosEntre(desde, hasta, agrupacion) {
    const claves = [];
    if (!desde || !hasta || desde > hasta) return claves;
    let d = desde, guard = 0;
    while (d <= hasta && guard++ < 4000) {
      const k = claveTemporal(d, agrupacion);
      if (claves[claves.length - 1] !== k) claves.push(k);
      d = sumarDias(d, 1);
    }
    return claves;
  }

  function etiquetaPeriodo(clave, agrupacion) {
    if (agrupacion === "dia") return `${Number(clave.slice(8, 10))} ${MESES[Number(clave.slice(5, 7)) - 1]}`;
    if (agrupacion === "mes") return `${MESES[Number(clave.slice(5, 7)) - 1]} ${clave.slice(0, 4)}`;
    return clave;
  }

  // Une en «Otras» los grupos con menos de `umbral` elementos (RNF03). items: [{label, value}]
  function agruparPequenos(items, umbral = UMBRAL_AGRUPACION) {
    const grandes = items.filter((i) => i.value >= umbral);
    const chicos = items.filter((i) => i.value < umbral);
    const sumaChicos = chicos.reduce((a, i) => a + i.value, 0);
    if (sumaChicos > 0) {
      const otras = grandes.find((g) => g.label === "Otras");
      if (otras) otras.value += sumaChicos; else grandes.push({ label: "Otras", value: sumaChicos });
    }
    return grandes;
  }

  function agrupar(filas, claveFn) {
    const m = new Map();
    for (const f of filas) {
      const k = claveFn(f);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(f);
    }
    return m;
  }

  const contar = (filas, estado) => filas.reduce((a, c) => a + (c.estado_cita === estado ? 1 : 0), 0);
  const nombreCorto = (n) => String(n || "").replace(/\s*\(.*\)\s*$/, "");

  // Tasas de un conjunto de citas (RF21). Cada una puede ser null (sin datos).
  function tasasDe(citas) {
    const total = citas.length;
    const asis = contar(citas, "ASISTIDA");
    const inas = contar(citas, "INASISTIDA");
    const canc = contar(citas, "CANCELADA");
    const conf = citas.filter((c) => c.estado_confirmacion === "CONFIRMADA").length;
    const confNoAsiste = citas.filter((c) => c.estado_confirmacion === "CONFIRMADA" && c.estado_cita === "INASISTIDA").length;
    return {
      total, asis, inas, canc, conf, confNoAsiste,
      asistencia: tasa(asis, asis + inas), inasistencia: tasa(inas, asis + inas),
      cancelacion: tasa(canc, total), confirmacion: tasa(conf, total), confirmaNoAsiste: tasa(confNoAsiste, conf),
    };
  }

  // Ocupación = OCUPADO ÷ bloques publicados (sin OCULTO ni BLOQUEADO) (RF21)
  function ocupacionDe(bloques) {
    const publicados = bloques.filter((b) => b.publicado && (b.estado_bloque === "OCUPADO" || b.estado_bloque === "DISPONIBLE"));
    const ocupados = publicados.filter((b) => b.estado_bloque === "OCUPADO").length;
    return { ocupados, publicados: publicados.length, sinOcupar: publicados.length - ocupados, pct: tasa(ocupados, publicados.length) };
  }

  // ===================================================================
  // 2. ESTADO
  // ===================================================================
  const FILTROS_DEFECTO = { periodo: "semestre", desde: "", hasta: "", agrupacion: "mes", tipo_fecha: "cita", policlinico_id: "", modalidad: "", especialidad_id: "", profesional_id: "", estado_cita: "", canal_registro: "" };
  const S = {
    filtros: { ...FILTROS_DEFECTO },
    aplicados: null, // filtros con los que se pidió el dataset vigente
    ds: { citas: [], bloques: [], encuestas: [], catalogos: { policlinicos: [], especialidades: [], profesionales: [] } },
    vis: Object.fromEntries(GRAFICOS.map((g) => [g, true])),
    charts: {},
    ocultas: {}, // series ocultadas desde la leyenda, por gráfico
    tablas: {},  // datos tabulares vigentes por gráfico
    listo: false,
    angosto: false,
  };

  const $ = (id) => (typeof document !== "undefined" ? document.getElementById(id) : null);
  function almacenar(clave, valor) { try { localStorage.setItem(clave, JSON.stringify(valor)); } catch (_) { /* sin almacenamiento */ } }
  function leerAlmacen(clave, defecto) { try { const v = localStorage.getItem(clave); return v ? JSON.parse(v) : defecto; } catch (_) { return defecto; } }

  // ===================================================================
  // 3. FILTROS (RF20)
  // ===================================================================
  function rangoDePeriodo(periodo, desdeManual, hastaManual) {
    const hoy = hoyISO();
    switch (periodo) {
      case "hoy": return { desde: hoy, hasta: hoy };
      case "7d": return { desde: sumarDias(hoy, -6), hasta: hoy };
      case "mes": return { desde: sumarDias(hoy, -29), hasta: hoy };
      case "semestre": return { desde: sumarDias(hoy, -181), hasta: hoy };
      case "anio": return { desde: sumarDias(hoy, -364), hasta: hoy };
      default: return { desde: desdeManual || "", hasta: hastaManual || "" };
    }
  }

  function leerFiltrosUI() {
    const v = (id) => ($(id) ? $(id).value : "");
    const f = {
      periodo: v("gaPeriodo") || "semestre", desde: v("gaDesde"), hasta: v("gaHasta"), agrupacion: v("gaAgrupacion") || "mes",
      tipo_fecha: v("gaTipoFecha") || "cita", policlinico_id: v("gaPoli"), modalidad: v("gaModalidad"),
      especialidad_id: v("gaEsp"), profesional_id: v("gaProf"), estado_cita: v("gaEstado"), canal_registro: v("gaCanal"),
    };
    return f;
  }

  function escribirFiltrosUI(f) {
    const set = (id, val) => { if ($(id)) $(id).value = val; };
    set("gaPeriodo", f.periodo); set("gaAgrupacion", f.agrupacion); set("gaTipoFecha", f.tipo_fecha);
    set("gaModalidad", f.modalidad); set("gaEstado", f.estado_cita); set("gaCanal", f.canal_registro);
    sincronizarFechasUI();
  }

  function sincronizarFechasUI() {
    const per = $("gaPeriodo") ? $("gaPeriodo").value : "semestre";
    const custom = per === "personalizado";
    if (!custom) {
      const r = rangoDePeriodo(per);
      $("gaDesde").value = r.desde; $("gaHasta").value = r.hasta;
    }
    $("gaDesde").disabled = !custom; $("gaHasta").disabled = !custom;
  }

  function parametrosApi(f, paraCsv = false) {
    const r = rangoDePeriodo(f.periodo, f.desde, f.hasta);
    const qs = new URLSearchParams();
    if (r.desde) qs.set("desde", r.desde);
    if (r.hasta) qs.set("hasta", r.hasta);
    qs.set("tipo_fecha", f.tipo_fecha);
    for (const k of ["policlinico_id", "modalidad", "especialidad_id", "profesional_id", "estado_cita", "canal_registro"]) {
      if (f[k]) qs.set(k, f[k]);
    }
    if (paraCsv && typeof state !== "undefined" && state.user) { // identifica quién exporta (queda en la auditoría)
      qs.set("usuario", state.user.nombre_completo);
      qs.set("rol", state.user.rol);
    }
    return qs;
  }

  function llenarSelect(id, opciones, valorActual, etiquetaTodos = "Todos") {
    const el = $(id);
    if (!el) return;
    el.innerHTML = `<option value="">${etiquetaTodos}</option>` + opciones.map((o) => `<option value="${escapar(o.id)}">${escapar(o.nombre)}</option>`).join("");
    el.value = opciones.some((o) => String(o.id) === String(valorActual)) ? String(valorActual) : "";
  }

  // Profesional y especialidad se acotan según el policlínico (y la especialidad) elegidos
  function actualizarSelectsDependientes() {
    const cat = S.ds.catalogos;
    const polId = $("gaPoli") ? $("gaPoli").value : "";
    const espAct = $("gaEsp") ? $("gaEsp").value : "";
    const profAct = $("gaProf") ? $("gaProf").value : "";
    const profsSede = cat.profesionales.filter((p) => !polId || String(p.policlinico_id) === polId);
    const espIds = new Set(profsSede.map((p) => p.especialidad_id));
    llenarSelect("gaEsp", cat.especialidades.filter((e) => !polId || espIds.has(e.id)), espAct);
    const esp = $("gaEsp").value;
    llenarSelect("gaProf", profsSede.filter((p) => !esp || String(p.especialidad_id) === esp), profAct);
  }

  function poblarCatalogos() {
    const cat = S.ds.catalogos;
    if (!cat.policlinicos.length) return;
    llenarSelect("gaPoli", cat.policlinicos.map((p) => ({ id: p.id, nombre: p.nombre })), $("gaPoli").value, "Todos (6 sedes + Telemedicina)");
    actualizarSelectsDependientes();
  }

  // ===================================================================
  // 4. CATÁLOGOS Y COLOR POR ENTIDAD
  // ===================================================================
  function nombrePoli(id) { const p = S.ds.catalogos.policlinicos.find((x) => x.id === id); return p ? p.nombre : `Sede ${id}`; }
  function colorEntidad(tipo, id) {
    // Asignado por ENTIDAD (posición estable en el catálogo completo), no por el orden de aparición:
    // filtrar no cambia los colores.
    const lista = tipo === "policlinico" ? S.ds.catalogos.policlinicos : tipo === "especialidad" ? S.ds.catalogos.especialidades : S.ds.catalogos.profesionales;
    const idx = lista.findIndex((x) => x.id === id);
    return PALETA[(idx < 0 ? 0 : idx) % PALETA.length];
  }
  function campoFecha() { return (S.aplicados || S.filtros).tipo_fecha === "solicitud" ? "fecha_solicitud" : "fecha_cita"; }
  function agrupacionVigente() { return (S.aplicados || S.filtros).agrupacion; }
  function rangoVigente() {
    const f = S.aplicados || S.filtros;
    let { desde, hasta } = rangoDePeriodo(f.periodo, f.desde, f.hasta);
    const fechas = S.ds.citas.map((c) => c[campoFecha()]).filter(Boolean).sort();
    if (!desde && fechas.length) desde = fechas[0];
    if (!hasta && fechas.length) hasta = fechas[fechas.length - 1];
    return { desde, hasta };
  }
  function periodosVigentes() { const r = rangoVigente(); return periodosEntre(r.desde, r.hasta, agrupacionVigente()); }

  // ===================================================================
  // 5. CHART.JS · construcción común
  // ===================================================================
  function hayChart() { return typeof Chart !== "undefined"; }

  function destruir(id) { if (S.charts[id]) { S.charts[id].destroy(); delete S.charts[id]; } }

  function tarjeta(id) { return typeof document !== "undefined" ? document.querySelector(`.ga-card[data-ga="${id}"]`) : null; }

  function mostrarVacio(id, vacio) {
    const card = tarjeta(id);
    if (!card) return;
    card.querySelector(".ga-canvas-wrap").classList.toggle("hidden", vacio);
    card.querySelector(".ga-empty").classList.toggle("hidden", !vacio);
    if (vacio) destruir(id);
  }

  function fijarAltura(id, px) { const card = tarjeta(id); if (card) card.querySelector(".ga-canvas-wrap").style.height = `${Math.round(px)}px`; }

  function opcionesBase({ horizontal = false, apilado = false, pct = false, leyenda = true, id, valorMax = null }) {
    const valorAxis = {
      stacked: apilado, beginAtZero: true, grid: { color: GRILLA, drawTicks: false }, border: { display: false },
      ticks: { color: INK_2, precision: 0, callback: (v) => (pct ? `${v} %` : v) },
    };
    if (pct) { valorAxis.min = 0; valorAxis.suggestedMax = 100; }
    if (valorMax) valorAxis.max = valorMax;
    const catAxis = { stacked: apilado, grid: { display: false }, border: { color: GRILLA }, ticks: { color: INK_2, autoSkip: !horizontal, maxRotation: horizontal ? 0 : 45 } };
    return {
      responsive: true, maintainAspectRatio: false, indexAxis: horizontal ? "y" : "x",
      animation: window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 250 },
      interaction: { mode: "index", intersect: false },
      layout: { padding: { top: 4, right: 8 } },
      plugins: {
        legend: {
          display: leyenda, position: "bottom",
          labels: { usePointStyle: true, boxWidth: 8, boxHeight: 8, color: INK, font: { size: 12 }, padding: 14 },
          onClick: (e, item, legend) => {
            // Un clic en la leyenda oculta o muestra la serie; se recuerda entre re-renderizados
            Chart.defaults.plugins.legend.onClick.call(legend, e, item, legend);
            const ch = legend.chart;
            S.ocultas[id] = ch.data.datasets.filter((d, i) => !ch.isDatasetVisible(i)).map((d) => d.label);
          },
        },
        tooltip: {
          backgroundColor: "#162840", titleColor: "#fff", bodyColor: "#fff", padding: 10, cornerRadius: 6,
          callbacks: {
            label: (ctx) => {
              const v = horizontal ? ctx.parsed.x : ctx.parsed.y;
              return ` ${ctx.dataset.label}: ${v === null || v === undefined ? "—" : pct ? formatPct(v) : formatNum(v)}`;
            },
          },
        },
      },
      scales: horizontal ? { x: valorAxis, y: catAxis } : { x: catAxis, y: valorAxis },
    };
  }

  function ocultoInicial(id, label) { return (S.ocultas[id] || []).includes(label); }

  function dibujar(id, config) {
    destruir(id);
    const canvas = $(`gaCanvas-${id}`);
    if (!canvas) return;
    S.charts[id] = new Chart(canvas, config);
  }

  function datasetBarra(id, label, data, color, extra = {}) {
    return { label, data, backgroundColor: color, borderColor: color, borderWidth: 0, borderRadius: 4, maxBarThickness: 38, hidden: ocultoInicial(id, label), ...extra };
  }

  // Barras genéricas. series: [{label, data, color}]
  function graficoBarras(id, { labels, series, apilado = false, horizontal = false, pct = false, leyenda = null, altoPorCategoria = 30 }) {
    if (!hayChart()) return;
    const vacio = !labels.length || series.every((s) => s.data.every((v) => v === null || v === 0));
    mostrarVacio(id, vacio);
    if (vacio) return;
    fijarAltura(id, horizontal ? Math.max(240, labels.length * altoPorCategoria * (apilado || series.length === 1 ? 1 : Math.min(series.length, 3) * 0.7) + 80) : 320);
    const datasets = series.map((s) => datasetBarra(id, s.label, s.data, s.color, apilado ? { borderColor: "#ffffff", borderWidth: 2, maxBarThickness: 46 } : {}));
    dibujar(id, {
      type: "bar", data: { labels, datasets },
      options: opcionesBase({ horizontal, apilado, pct, leyenda: leyenda === null ? series.length > 1 : leyenda, id }),
    });
  }

  function graficoLineas(id, { labels, series, pct = false }) {
    if (!hayChart()) return;
    const vacio = !labels.length || series.every((s) => s.data.every((v) => v === null || v === 0));
    mostrarVacio(id, vacio);
    if (vacio) return;
    fijarAltura(id, 320);
    const datasets = series.map((s, i) => ({
      label: s.label, data: s.data, borderColor: s.color, backgroundColor: s.color, borderWidth: 2, tension: 0, fill: false,
      pointRadius: labels.length > 40 ? 0 : 3, pointHoverRadius: 5, pointStyle: PUNTOS[i % PUNTOS.length], spanGaps: false,
      hidden: ocultoInicial(id, s.label),
    }));
    dibujar(id, { type: "line", data: { labels, datasets }, options: opcionesBase({ pct, leyenda: series.length > 1, id }) });
  }

  function guardarTabla(id, encabezados, filas, nota = "") { S.tablas[id] = { encabezados, filas, nota }; pintarTabla(id); }

  function pintarTabla(id) {
    const card = tarjeta(id);
    const t = S.tablas[id];
    if (!card || !t) return;
    const cont = card.querySelector(".ga-tabla");
    cont.innerHTML = `
      <div class="table-wrap"><table>
        <caption class="sr-only">${escapar(NOMBRES[id])}: datos del gráfico</caption>
        <thead><tr>${t.encabezados.map((h, i) => `<th scope="col"${i ? ' class="ga-num"' : ""}>${escapar(h)}</th>`).join("")}</tr></thead>
        <tbody>${t.filas.map((fila) => `<tr>${fila.map((c, i) => (i === 0 ? `<th scope="row">${escapar(c)}</th>` : `<td class="ga-num">${escapar(c)}</td>`)).join("")}</tr>`).join("")}</tbody>
      </table></div>${t.nota ? `<p class="ga-nota">${escapar(t.nota)}</p>` : ""}`;
  }

  function resumenAccesible(id, texto) { const c = $(`gaCanvas-${id}`); if (c) c.setAttribute("aria-label", `${NOMBRES[id]}. ${texto}`); }

  // Barras horizontales en pantallas angostas (evita etiquetas superpuestas)
  const esAngosto = () => { const g = $("gaGrid"); return (g ? g.clientWidth : window.innerWidth) < 640; };

  // ===================================================================
  // 6. KPI + TABLA DE INDICADORES (reaccionan a los filtros)
  // ===================================================================
  function renderKpis() {
    const t = tasasDe(S.ds.citas);
    const oc = ocupacionDe(S.ds.bloques);
    const pend = S.ds.citas.filter((c) => c.estado_cita === "RESERVADA" && ["PENDIENTE", "SIN_RESPUESTA"].includes(c.estado_confirmacion)).length;
    const kpi = (titulo, valor, sub) => `<div class="kpi-card"><div class="kpi-label">${escapar(titulo)}</div><div class="kpi-val">${escapar(valor)}</div><div class="kpi-sub">${escapar(sub)}</div></div>`;
    const dePct = (v, a, b) => (v === null ? "sin datos" : `${a} de ${b}`);
    const cerr = t.asis + t.inas;
    $("kpiGrid").innerHTML = [
      kpi("Citas registradas", String(t.total), `${pend} pendientes de confirmación`),
      kpi("Tasa de asistencia", formatPct(t.asistencia), dePct(t.asistencia, t.asis, cerr)),
      kpi("Tasa de inasistencia", formatPct(t.inasistencia), dePct(t.inasistencia, t.inas, cerr)),
      kpi("Tasa de cancelación", formatPct(t.cancelacion), dePct(t.cancelacion, t.canc, t.total)),
      kpi("Tasa de confirmación", formatPct(t.confirmacion), dePct(t.confirmacion, t.conf, t.total)),
      kpi("Confirma y no asiste", formatPct(t.confirmaNoAsiste), dePct(t.confirmaNoAsiste, t.confNoAsiste, t.conf)),
      kpi("Ocupación de bloques", formatPct(oc.pct), dePct(oc.pct, oc.ocupados, oc.publicados)),
      kpi("Bloques sin ocupar", String(oc.sinOcupar), "publicados en el período"),
    ].join("");
  }

  function renderTablaIndicadores() {
    const filas = S.ds.catalogos.policlinicos.map((p) => {
      const cs = S.ds.citas.filter((c) => c.policlinico_id === p.id);
      const t = tasasDe(cs);
      const pend = cs.filter((c) => c.estado_cita === "RESERVADA" && ["PENDIENTE", "SIN_RESPUESTA"].includes(c.estado_confirmacion)).length;
      return `<tr><td><strong>${escapar(p.nombre)}</strong></td><td>${escapar(p.modalidad)}</td><td>${t.total}</td><td>${cs.length - t.asis - t.inas - t.canc}</td>
        <td>${t.asis}</td><td>${t.inas}</td><td>${t.canc}</td><td>${pend}</td><td><strong>${formatPct(t.asistencia)}</strong></td></tr>`;
    });
    $("tablaIndicadores").innerHTML = filas.join("") || `<tr><td colspan="9" class="muted">Sin datos para los filtros seleccionados.</td></tr>`;
  }

  // ===================================================================
  // 7. G1 · CITAS EN EL TIEMPO
  // ===================================================================
  // Devuelve [{label, color, filas}] limitado a 7 series + «Otros»
  function seriesPor(filas, modo) {
    if (modo === "estado") return ESTADOS.map((e) => ({ label: ETIQ_ESTADO[e], color: COLOR_ESTADO[e], filas: filas.filter((c) => c.estado_cita === e) }));
    if (modo === "total") return [{ label: "Citas", color: COLOR_UNICO, filas }];
    const campo = modo === "policlinico" ? ["policlinico_id", "policlinico_nombre"] : modo === "especialidad" ? ["especialidad_id", "especialidad_nombre"] : ["profesional_id", "profesional_nombre"];
    const grupos = [...agrupar(filas, (c) => c[campo[0]]).entries()].map(([id, fs]) => ({ id, label: fs[0][campo[1]], filas: fs }));
    grupos.sort((a, b) => b.filas.length - a.filas.length);
    const top = grupos.slice(0, MAX_SERIES).map((g) => ({ label: nombreCorto(g.label), color: colorEntidad(modo, g.id), filas: g.filas }));
    const resto = grupos.slice(MAX_SERIES).flatMap((g) => g.filas);
    if (resto.length) top.push({ label: "Otros", color: COLOR_OTROS, filas: resto });
    return top;
  }

  function renderG1() {
    const agr = agrupacionVigente();
    const modo = $("gaG1Sep").value;
    const periodos = periodosVigentes();
    const campo = campoFecha();
    const series = seriesPor(S.ds.citas, modo).map((s) => {
      const porPeriodo = agrupar(s.filas, (c) => claveTemporal(c[campo], agr));
      return { label: s.label, color: s.color, data: periodos.map((p) => (porPeriodo.get(p) || []).length) };
    });
    const labels = periodos.map((p) => etiquetaPeriodo(p, agr));
    graficoLineas("G1", { labels, series });
    guardarTabla("G1", ["Período", ...series.map((s) => s.label)], periodos.map((p, i) => [labels[i], ...series.map((s) => s.data[i])]),
      campo === "fecha_solicitud" ? "Agrupado por la fecha en que se pidió la hora." : "Agrupado por la fecha de la cita.");
    resumenAccesible("G1", `Líneas de citas por ${agr}${modo === "total" ? "" : ", separadas por " + modo}. Use «Ver tabla» para los valores.`);
  }

  // ===================================================================
  // 8. G2 · HORAS MÁS DEMANDADAS
  // ===================================================================
  function renderG2() {
    const horas = S.ds.citas.map((c) => Number(String(c.hora_inicio).slice(0, 2)));
    const min = Math.min(8, ...horas), max = Math.max(19, ...horas);
    const rango = []; for (let h = min; h <= max; h++) rango.push(h);
    const cuentas = rango.map((h) => horas.filter((x) => x === h).length);
    const labels = rango.map((h) => `${pad2(h)}:00`);
    graficoBarras("G2", { labels, series: [{ label: "Citas", data: cuentas, color: COLOR_UNICO }], leyenda: false });
    guardarTabla("G2", ["Hora de inicio", "Citas"], labels.map((l, i) => [l, cuentas[i]]));
    resumenAccesible("G2", "Barras con la cantidad de citas por hora de inicio, de 08:00 a 19:00.");
  }

  // ===================================================================
  // 9. G3 · CITAS POR POLICLÍNICO (apiladas por estado)
  // ===================================================================
  function renderG3() {
    const pols = S.ds.catalogos.policlinicos;
    const labels = pols.map((p) => nombreCorto(p.nombre));
    const series = ESTADOS.map((e) => ({
      label: ETIQ_ESTADO[e], color: COLOR_ESTADO[e],
      data: pols.map((p) => S.ds.citas.filter((c) => c.policlinico_id === p.id && c.estado_cita === e).length),
    }));
    S.angosto = esAngosto();
    graficoBarras("G3", { labels, series, apilado: true, horizontal: S.angosto });
    guardarTabla("G3", ["Policlínico", ...series.map((s) => s.label), "Total"],
      pols.map((p, i) => [p.nombre, ...series.map((s) => s.data[i]), series.reduce((a, s) => a + s.data[i], 0)]));
    resumenAccesible("G3", "Barras apiladas por estado de la cita para cada policlínico, incluida Telemedicina.");
  }

  // ===================================================================
  // 10. G4 · CITAS POR PROFESIONAL (10 primeros + Otros)
  // ===================================================================
  function renderG4() {
    const metrica = $("gaG4Metrica").value;
    const pasa = (c) => metrica === "asistidas" ? c.estado_cita === "ASISTIDA" : metrica === "inasistidas" ? c.estado_cita === "INASISTIDA" : true;
    const base = S.ds.citas.filter(pasa);
    const grupos = [...agrupar(base, (c) => c.profesional_id).entries()].map(([id, fs]) => ({ id, nombre: fs[0].profesional_nombre, n: fs.length }));
    grupos.sort((a, b) => b.n - a.n);
    const top = grupos.slice(0, 10);
    const resto = grupos.slice(10).reduce((a, g) => a + g.n, 0);
    const labels = top.map((g) => nombreCorto(g.nombre)).concat(resto ? ["Otros"] : []);
    const datos = top.map((g) => g.n).concat(resto ? [resto] : []);
    const colores = top.map(() => COLOR_UNICO).concat(resto ? [COLOR_OTROS] : []);
    const nombreMetrica = { total: "Citas", asistidas: "Asistidas", inasistidas: "Inasistidas" }[metrica];
    graficoBarras("G4", { labels, series: [{ label: nombreMetrica, data: datos, color: colores }], horizontal: true, leyenda: false });
    guardarTabla("G4", ["Profesional", nombreMetrica], labels.map((l, i) => [l, datos[i]]), "Se muestran los 10 profesionales con más citas; el resto se agrupa en «Otros».");
    resumenAccesible("G4", `Barras horizontales de ${nombreMetrica.toLowerCase()} por profesional.`);
  }

  // ===================================================================
  // 11. G5 · TASAS POR POLICLÍNICO
  // ===================================================================
  function renderG5() {
    const pols = S.ds.catalogos.policlinicos;
    const tasas = pols.map((p) => tasasDe(S.ds.citas.filter((c) => c.policlinico_id === p.id)));
    const defs = [
      ["Asistencia", "asistencia"], ["Inasistencia", "inasistencia"], ["Cancelación", "cancelacion"],
      ["Confirmación", "confirmacion"], ["Confirma y no asiste", "confirmaNoAsiste"],
    ];
    // Las tasas sin datos (null) NO se dibujan como 0: se omiten en el gráfico y se muestran «—» en la tabla
    const series = defs.map(([label, k]) => ({ label, color: COLOR_TASAS[k], data: tasas.map((t) => t[k]) }));
    S.angosto = esAngosto();
    graficoBarras("G5", { labels: pols.map((p) => nombreCorto(p.nombre)), series, horizontal: S.angosto, pct: true });
    guardarTabla("G5", ["Policlínico", ...defs.map((d) => d[0])], pols.map((p, i) => [p.nombre, ...defs.map(([, k]) => formatPct(tasas[i][k]))]),
      "Asistencia e inasistencia sobre citas cerradas (asistidas + inasistidas); cancelación y confirmación sobre el total; «confirma y no asiste» = inasistidas que habían confirmado ÷ citas confirmadas. «—» = sin datos.");
    resumenAccesible("G5", "Barras agrupadas con las tasas de asistencia, inasistencia, cancelación, confirmación y confirma y no asiste, por policlínico.");
  }

  // ===================================================================
  // 12. G6 · OCUPACIÓN DE BLOQUES
  // ===================================================================
  function renderG6() {
    const pols = S.ds.catalogos.policlinicos;
    const oc = pols.map((p) => ocupacionDe(S.ds.bloques.filter((b) => b.policlinico_id === p.id)));
    S.angosto = esAngosto();
    graficoBarras("G6", { labels: pols.map((p) => nombreCorto(p.nombre)), series: [{ label: "Ocupación", data: oc.map((o) => o.pct), color: COLOR_UNICO }], horizontal: S.angosto, pct: true, leyenda: false });
    guardarTabla("G6", ["Policlínico", "Ocupados", "Publicados", "Ocupación"], pols.map((p, i) => [p.nombre, oc[i].ocupados, oc[i].publicados, formatPct(oc[i].pct)]),
      "Bloques ocupados ÷ bloques publicados en el período (sin ocultos ni bloqueados). Considera los bloques cuya fecha cae en el período.");
    resumenAccesible("G6", "Barras con el porcentaje de ocupación de bloques por policlínico.");
  }

  // ===================================================================
  // 13. G7 · CARACTERIZACIÓN DE PACIENTES (únicos con cita asistida)
  // ===================================================================
  function renderG7() {
    const modo = $("gaG7Modo").value; // tramo | nacionalidad
    const campo = modo === "tramo" ? "tramo_etario" : "nacionalidad";
    const unicos = new Map();
    for (const c of S.ds.citas) if (c.estado_cita === "ASISTIDA" && c.paciente_ref != null && !unicos.has(c.paciente_ref)) unicos.set(c.paciente_ref, c[campo]);
    const n = unicos.size;
    $("gaG7N").textContent = `n = ${n}`;
    let items = [...agrupar([...unicos.values()], (v) => v).entries()].map(([label, arr]) => ({ label, value: arr.length }));
    items = agruparPequenos(items, UMBRAL_AGRUPACION);
    if (modo === "tramo") items.sort((a, b) => TRAMOS.indexOf(a.label) - TRAMOS.indexOf(b.label) || (a.label === "Otras") - (b.label === "Otras"));
    else items.sort((a, b) => (a.label === "Otras") - (b.label === "Otras") || b.value - a.value);
    graficoBarras("G7", { labels: items.map((i) => i.label), series: [{ label: "Pacientes", data: items.map((i) => i.value), color: items.map((i) => (i.label === "Otras" ? COLOR_OTROS : COLOR_UNICO)) }], leyenda: false });
    guardarTabla("G7", [modo === "tramo" ? "Tramo etario" : "Nacionalidad", "Pacientes únicos"], items.map((i) => [i.label, i.value]),
      `Pacientes únicos con al menos una cita asistida en el período (n = ${n}). Los grupos con menos de ${UMBRAL_AGRUPACION} pacientes se juntan en «Otras» para proteger la privacidad.`);
    resumenAccesible("G7", `Barras de pacientes únicos atendidos por ${modo === "tramo" ? "tramo etario" : "nacionalidad"}, n = ${n}.`);
  }

  // ===================================================================
  // 14. G8 · CANAL DE REGISTRO · G9 · ENCUESTAS
  // ===================================================================
  function renderG8() {
    const claves = Object.keys(ETIQ_CANAL);
    const datos = claves.map((k) => S.ds.citas.filter((c) => c.canal_registro === k).length);
    graficoBarras("G8", { labels: claves.map((k) => ETIQ_CANAL[k]), series: [{ label: "Citas", data: datos, color: COLOR_UNICO }], leyenda: false });
    guardarTabla("G8", ["Canal de registro", "Citas"], claves.map((k, i) => [ETIQ_CANAL[k], datos[i]]));
    resumenAccesible("G8", "Barras con las citas según el canal de registro: presencial, telefónico o solicitud web.");
  }

  function renderG9() {
    const enc = S.ds.encuestas.filter((e) => e.tipo === "POST_ATENCION");
    const datos = [1, 2, 3, 4, 5].map((p) => enc.filter((e) => e.puntaje === p).length);
    const prom = enc.length ? enc.reduce((a, e) => a + e.puntaje, 0) / enc.length : null;
    $("gaG9N").textContent = enc.length ? `n = ${enc.length} · promedio ${formatNum(prom)}` : "n = 0";
    graficoBarras("G9", { labels: ["1", "2", "3", "4", "5"], series: [{ label: "Respuestas", data: datos, color: COLOR_UNICO }], leyenda: false });
    guardarTabla("G9", ["Puntaje", "Respuestas"], datos.map((n, i) => [String(i + 1), n]),
      "Solo encuestas post-atención (RF30). Las encuestas de agendamiento web (RF36) se analizan por separado.");
    resumenAccesible("G9", `Barras con la distribución de puntajes de 1 a 5 de las encuestas post-atención. n = ${enc.length}.`);
  }

  // ===================================================================
  // 15. G0 · EXPLORADOR GENERAL (métrica × dimensión × desglose × tipo)
  // ===================================================================
  const METRICAS = {
    total: { label: "Citas totales", pct: false, calc: (cs) => cs.length },
    asistidas: { label: "Citas asistidas", pct: false, calc: (cs) => contar(cs, "ASISTIDA") },
    inasistidas: { label: "Citas inasistidas", pct: false, calc: (cs) => contar(cs, "INASISTIDA") },
    canceladas: { label: "Citas canceladas", pct: false, calc: (cs) => contar(cs, "CANCELADA") },
    pct_asistencia: { label: "% asistencia", pct: true, calc: (cs) => tasasDe(cs).asistencia },
    pct_inasistencia: { label: "% inasistencia", pct: true, calc: (cs) => tasasDe(cs).inasistencia },
    pct_confirmacion: { label: "% confirmación", pct: true, calc: (cs) => tasasDe(cs).confirmacion },
    ocupacion: { label: "Ocupación %", pct: true, bloques: true, calc: (bs) => ocupacionDe(bs).pct },
  };
  const DIMENSIONES = {
    periodo: { label: "Período", temporal: true }, hora: { label: "Hora del día", temporal: true },
    policlinico: { label: "Policlínico" }, especialidad: { label: "Especialidad" }, profesional: { label: "Profesional" },
    tramo: { label: "Tramo etario", soloCitas: true }, nacionalidad: { label: "Nacionalidad", soloCitas: true },
    canal: { label: "Canal de registro", soloCitas: true }, estado: { label: "Estado de la cita", soloCitas: true },
  };
  const DESGLOSES = { ninguno: "Ninguno", estado: "Estado", policlinico: "Policlínico", especialidad: "Especialidad", modalidad: "Modalidad" };

  function clavesDim(dim, esBloque) {
    const agr = agrupacionVigente();
    const cat = S.ds.catalogos;
    const esp = (id) => (cat.especialidades.find((e) => e.id === id) || {}).nombre || `Especialidad ${id}`;
    const prof = (id) => (cat.profesionales.find((p) => p.id === id) || {}).nombre || `Profesional ${id}`;
    if (esBloque) {
      return {
        periodo: (b) => claveTemporal(b.fecha, agr), hora: (b) => `${String(b.hora_inicio).slice(0, 2)}:00`, policlinico: (b) => nombreCorto(nombrePoli(b.policlinico_id)),
        especialidad: (b) => esp(b.especialidad_id), profesional: (b) => nombreCorto(prof(b.profesional_id)),
      }[dim];
    }
    return {
      periodo: (c) => claveTemporal(c[campoFecha()], agr), hora: (c) => `${String(c.hora_inicio).slice(0, 2)}:00`, policlinico: (c) => nombreCorto(c.policlinico_nombre),
      especialidad: (c) => c.especialidad_nombre, profesional: (c) => nombreCorto(c.profesional_nombre), tramo: (c) => c.tramo_etario,
      nacionalidad: (c) => c.nacionalidad, canal: (c) => ETIQ_CANAL[c.canal_registro] || c.canal_registro, estado: (c) => ETIQ_ESTADO[c.estado_cita] || c.estado_cita,
    }[dim];
  }

  function clavesDesglose(desg, esBloque) {
    if (desg === "ninguno") return () => "";
    if (esBloque) {
      return { policlinico: (b) => nombreCorto(nombrePoli(b.policlinico_id)),
        especialidad: (b) => ((S.ds.catalogos.especialidades.find((e) => e.id === b.especialidad_id) || {}).nombre || "—"),
        modalidad: (b) => ((S.ds.catalogos.policlinicos.find((p) => p.id === b.policlinico_id) || {}).modalidad || "—") }[desg];
    }
    return { estado: (c) => ETIQ_ESTADO[c.estado_cita], policlinico: (c) => nombreCorto(c.policlinico_nombre), especialidad: (c) => c.especialidad_nombre, modalidad: (c) => c.modalidad }[desg];
  }

  function colorDeSerie(desg, label) {
    if (desg === "estado") { const e = ESTADOS.find((x) => ETIQ_ESTADO[x] === label); return e ? COLOR_ESTADO[e] : COLOR_OTROS; }
    if (label === "Otros") return COLOR_OTROS;
    if (desg === "policlinico") { const p = S.ds.catalogos.policlinicos.find((x) => nombreCorto(x.nombre) === label); return p ? colorEntidad("policlinico", p.id) : COLOR_OTROS; }
    if (desg === "especialidad") { const e = S.ds.catalogos.especialidades.find((x) => x.nombre === label); return e ? colorEntidad("especialidad", e.id) : COLOR_OTROS; }
    if (desg === "modalidad") return label === "TELEMEDICINA" ? PALETA[1] : PALETA[0];
    return COLOR_UNICO;
  }

  // Calcula el gráfico del explorador. Devuelve {categorias, series, pct, aviso}
  function calcularExplorador(metricaId, dimId, desgId) {
    const m = METRICAS[metricaId], dim = DIMENSIONES[dimId];
    if (m.bloques && (dim.soloCitas || desgId === "estado")) {
      return { aviso: "La ocupación se calcula sobre bloques: agrúpela por período, hora, policlínico, especialidad o profesional (y sin desglose por estado)." };
    }
    const filas = m.bloques ? S.ds.bloques : S.ds.citas;
    const kd = clavesDim(dimId, !!m.bloques), ks = clavesDesglose(desgId, !!m.bloques);
    // Categorías: períodos completos o por frecuencia (top 12 + «Otros»)
    let categorias;
    let kdFinal = kd;
    if (dimId === "periodo") categorias = periodosVigentes();
    else if (dimId === "hora") categorias = [...new Set(filas.map(kd))].sort();
    else if (dimId === "tramo") categorias = TRAMOS.filter((t) => filas.some((f) => kd(f) === t));
    else {
      const ord = [...agrupar(filas, kd).entries()].sort((a, b) => b[1].length - a[1].length);
      const top = new Set(ord.slice(0, 12).map(([k]) => k));
      categorias = ord.slice(0, 12).map(([k]) => k);
      if (ord.length > 12) { categorias.push("Otros"); kdFinal = (f) => (top.has(kd(f)) ? kd(f) : "Otros"); }
    }
    // Series (desglose): hasta 7 + «Otros»
    let ksFinal = ks;
    let nombresSeries = [""];
    if (desgId !== "ninguno") {
      const ord = [...agrupar(filas, ks).entries()].sort((a, b) => b[1].length - a[1].length);
      const top = new Set(ord.slice(0, MAX_SERIES).map(([k]) => k));
      nombresSeries = ord.slice(0, MAX_SERIES).map(([k]) => k);
      if (ord.length > MAX_SERIES) { nombresSeries.push("Otros"); ksFinal = (f) => (top.has(ks(f)) ? ks(f) : "Otros"); }
      if (desgId === "estado") nombresSeries = ESTADOS.map((e) => ETIQ_ESTADO[e]).filter((n) => ord.some(([k]) => k === n));
    }
    const celdas = agrupar(filas, (f) => `${kdFinal(f)}\u0000${ksFinal(f)}`);
    const series = nombresSeries.map((nombre) => ({
      label: desgId === "ninguno" ? m.label : nombre, color: desgId === "ninguno" ? COLOR_UNICO : colorDeSerie(desgId, nombre),
      data: categorias.map((cat) => {
        const fs = celdas.get(`${cat}\u0000${nombre}`) || [];
        return m.pct ? (fs.length ? m.calc(fs) : null) : m.calc(fs);
      }),
    }));
    const etiquetas = dimId === "periodo" ? categorias.map((c) => etiquetaPeriodo(c, agrupacionVigente())) : categorias;
    return { categorias: etiquetas, series, pct: m.pct, metrica: m, dim };
  }

  function sincronizarControlesExplorador() {
    const dim = DIMENSIONES[$("gaG0Dim").value];
    const metr = METRICAS[$("gaG0Metrica").value];
    const tipo = $("gaG0Tipo");
    tipo.querySelector('option[value="lineas"]').disabled = !dim.temporal;
    tipo.querySelector('option[value="apiladas"]').disabled = metr.pct; // apilar porcentajes no tiene sentido
    if (tipo.selectedOptions[0] && tipo.selectedOptions[0].disabled) tipo.value = "barras";
    const des = $("gaG0Desglose");
    des.querySelector('option[value="estado"]').disabled = !!metr.bloques;
    if (des.selectedOptions[0] && des.selectedOptions[0].disabled) des.value = "ninguno";
  }

  function renderG0() {
    sincronizarControlesExplorador();
    const metricaId = $("gaG0Metrica").value, dimId = $("gaG0Dim").value, desgId = $("gaG0Desglose").value, tipo = $("gaG0Tipo").value;
    const r = calcularExplorador(metricaId, dimId, desgId);
    const aviso = $("gaG0Aviso");
    if (r.aviso) {
      aviso.textContent = r.aviso; aviso.classList.remove("hidden");
      const card = tarjeta("G0");
      card.querySelector(".ga-canvas-wrap").classList.add("hidden");
      card.querySelector(".ga-empty").classList.add("hidden");
      destruir("G0");
      S.tablas.G0 = null; $("gaTabla-G0").innerHTML = "";
      return;
    }
    aviso.classList.add("hidden");
    if (tipo === "lineas") graficoLineas("G0", { labels: r.categorias, series: r.series, pct: r.pct });
    else graficoBarras("G0", { labels: r.categorias, series: r.series, apilado: tipo === "apiladas", horizontal: false, pct: r.pct, leyenda: r.series.length > 1 });
    const fmt = (v) => (r.pct ? formatPct(v) : formatNum(v));
    guardarTabla("G0", [DIMENSIONES[dimId].label, ...r.series.map((s) => s.label)], r.categorias.map((c, i) => [c, ...r.series.map((s) => fmt(s.data[i]))]),
      `${r.metrica.label} por ${DIMENSIONES[dimId].label.toLowerCase()}${desgId !== "ninguno" ? ", desglosado por " + DESGLOSES[desgId].toLowerCase() : ""}.`);
    resumenAccesible("G0", `${r.metrica.label} por ${DIMENSIONES[dimId].label.toLowerCase()}.`);
  }

  // --- Vistas guardadas (máximo 5, localStorage) ---
  function vistasGuardadas() { const v = leerAlmacen(CLAVE_VISTAS, []); return Array.isArray(v) ? v.slice(0, 5) : []; }
  function renderVistas() {
    const cont = $("gaVistas");
    if (!cont) return;
    const vistas = vistasGuardadas();
    cont.innerHTML = vistas.length
      ? vistas.map((v, i) => `<span class="ga-chip"><button type="button" class="ga-chip-main" data-vista="${i}" title="Aplicar esta vista">${escapar(v.nombre)}</button><button type="button" class="ga-chip-x" data-borrar="${i}" aria-label="Eliminar la vista ${escapar(v.nombre)}">×</button></span>`).join("")
      : `<span class="muted ga-nota">Aún no hay vistas guardadas (máx. 5).</span>`;
  }
  function guardarVista() {
    const nombre = ($("gaVistaNombre").value || "").trim().slice(0, 30);
    if (!nombre) { toast("Escribe un nombre para la vista.", true); return; }
    const vistas = vistasGuardadas();
    const nueva = { nombre, metrica: $("gaG0Metrica").value, dimension: $("gaG0Dim").value, desglose: $("gaG0Desglose").value, tipo: $("gaG0Tipo").value };
    const idx = vistas.findIndex((v) => v.nombre.toLowerCase() === nombre.toLowerCase());
    if (idx >= 0) vistas[idx] = nueva;
    else if (vistas.length >= 5) { toast("Ya hay 5 vistas guardadas: elimina una para guardar otra.", true); return; }
    else vistas.push(nueva);
    almacenar(CLAVE_VISTAS, vistas);
    $("gaVistaNombre").value = "";
    renderVistas();
    toast(`Vista «${nombre}» guardada.`);
  }
  function aplicarVista(i) {
    const v = vistasGuardadas()[i];
    if (!v) return;
    $("gaG0Metrica").value = v.metrica; $("gaG0Dim").value = v.dimension; $("gaG0Desglose").value = v.desglose; $("gaG0Tipo").value = v.tipo;
    renderGrafico("G0");
  }

  // ===================================================================
  // 16. VISIBILIDAD («Elegir qué ver») Y ORQUESTACIÓN
  // ===================================================================
  const RENDERS = { G0: renderG0, G1: renderG1, G2: renderG2, G3: renderG3, G4: renderG4, G5: renderG5, G6: renderG6, G7: renderG7, G8: renderG8, G9: renderG9 };

  function toast(msg, error) { if (typeof showToast === "function") showToast(msg, error); }

  // Una sección plegada no se dibuja (ahorra CPU y evita lienzos de tamaño 0); se dibuja al abrirla.
  function seccionAbierta(id) {
    const card = tarjeta(id);
    const det = card ? card.closest("details.ga-seccion") : null;
    return !det || det.open;
  }

  function renderGrafico(id) {
    if (!S.vis[id]) return; // un gráfico oculto no se renderiza (ahorra CPU)
    if (!seccionAbierta(id)) { destruir(id); return; }
    try { RENDERS[id](); } catch (err) { console.error(`Error al dibujar ${id}`, err); }
  }

  function guardarSecciones() {
    const estado = {};
    document.querySelectorAll("details.ga-seccion").forEach((d) => { estado[d.dataset.seccion] = d.open; });
    almacenar(CLAVE_SECCIONES, estado);
  }

  function fijarSecciones(abrir) {
    document.querySelectorAll("details.ga-seccion").forEach((d) => { d.open = abrir; });
  }

  // «Más filtros»: contador de filtros secundarios activos
  function actualizarMasFiltros(abrirSiHay = false) {
    const n = ["gaModalidad", "gaEsp", "gaProf", "gaEstado", "gaCanal"].filter((id) => $(id) && $(id).value).length;
    const badge = $("gaMasContador");
    badge.textContent = `${n} activo${n === 1 ? "" : "s"}`;
    badge.classList.toggle("hidden", n === 0);
    if (abrirSiHay && n > 0) $("gaMasFiltros").open = true;
  }

  function aplicarVisibilidad() {
    for (const g of GRAFICOS) {
      const card = tarjeta(g);
      if (card) card.classList.toggle("hidden", !S.vis[g]);
      const chk = $(`gaVis-${g}`);
      if (chk) chk.checked = !!S.vis[g];
      if (!S.vis[g]) destruir(g);
    }
    document.querySelectorAll("details.ga-seccion").forEach((d) => {
      const todosOcultos = [...d.querySelectorAll(".ga-card")].every((c) => c.classList.contains("hidden"));
      d.classList.toggle("hidden", todosOcultos);
    });
  }

  function cambiarVisibilidad(mapa) {
    Object.assign(S.vis, mapa);
    almacenar(CLAVE_VISIBILIDAD, S.vis);
    aplicarVisibilidad();
    for (const g of GRAFICOS) if (mapa[g] && !S.charts[g]) renderGrafico(g);
  }

  function renderTodo() {
    renderKpis();
    renderTablaIndicadores();
    $("gaResumenFiltros").textContent = textoFiltros();
    for (const g of GRAFICOS) renderGrafico(g);
  }

  function textoFiltros() {
    const f = S.aplicados || S.filtros;
    const r = rangoDePeriodo(f.periodo, f.desde, f.hasta);
    const partes = [`${r.desde || "inicio"} → ${r.hasta || "hoy"}`, f.tipo_fecha === "solicitud" ? "según fecha en que se pidió la hora" : "según fecha de la cita"];
    const nombreSel = (id) => { const el = $(id); return el && el.value ? el.selectedOptions[0].textContent : ""; };
    for (const [id, pref] of [["gaPoli", ""], ["gaModalidad", ""], ["gaEsp", ""], ["gaProf", ""], ["gaEstado", "estado "], ["gaCanal", "canal "]]) {
      const t = nombreSel(id); if (t) partes.push(pref + t);
    }
    return `${S.ds.citas.length} citas · ${partes.join(" · ")}`;
  }

  async function aplicarFiltros(mostrarAviso = true) {
    const f = leerFiltrosUI();
    const r = rangoDePeriodo(f.periodo, f.desde, f.hasta);
    if (r.desde && r.hasta && r.desde > r.hasta) { toast("La fecha «desde» no puede ser posterior a «hasta».", true); return; }
    S.filtros = f;
    const btn = $("gaAplicar");
    if (btn) { btn.disabled = true; btn.textContent = "Cargando..."; }
    try {
      const data = await api(`/api/reportes/dataset?${parametrosApi(f)}`);
      S.ds = { citas: data.citas, bloques: data.bloques, encuestas: data.encuestas, catalogos: data.catalogos };
      S.aplicados = { ...f };
      poblarCatalogos();
      actualizarMasFiltros(true);
      renderTodo();
      if (mostrarAviso && !data.citas.length) toast("Sin datos para los filtros seleccionados.");
    } catch (err) {
      toast(err.message, true);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Aplicar"; }
    }
  }

  async function exportarCsv() {
    const btn = $("gaExportar");
    const f = leerFiltrosUI();
    const r = rangoDePeriodo(f.periodo, f.desde, f.hasta);
    if (r.desde && r.hasta && r.desde > r.hasta) { toast("La fecha «desde» no puede ser posterior a «hasta».", true); return; }
    btn.disabled = true;
    try {
      // fetch con cabecera Authorization (un enlace directo no enviaría la sesión)
      const res = await fetch(`/api/reportes/dataset.csv?${parametrosApi(f, true)}`, { headers: window.hdAuthHeaders ? window.hdAuthHeaders() : {} });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Error HTTP ${res.status}`); }
      const blob = await res.blob();
      const m = /filename=([^;]+)/.exec(res.headers.get("Content-Disposition") || "");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = m ? m[1].replace(/"/g, "") : "reporte_citas.csv";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      toast("CSV exportado. La descarga quedó registrada en la auditoría.");
    } catch (err) { toast(err.message, true); }
    finally { btn.disabled = false; }
  }

  function limpiarFiltros() {
    S.filtros = { ...FILTROS_DEFECTO };
    escribirFiltrosUI(S.filtros);
    $("gaPoli").value = ""; actualizarSelectsDependientes();
    actualizarMasFiltros();
    aplicarFiltros(false);
  }

  // ===================================================================
  // 17. INICIALIZACIÓN DE LA INTERFAZ (una sola vez)
  // ===================================================================
  function iniciarUI() {
    if (S.listo) return;
    S.listo = true;
    Object.assign(S.vis, leerAlmacen(CLAVE_VISIBILIDAD, {}));
    for (const g of GRAFICOS) S.vis[g] = S.vis[g] !== false;
    if (hayChart()) {
      Chart.defaults.font.family = '"Segoe UI", system-ui, -apple-system, sans-serif';
      Chart.defaults.color = INK_2;
    } else {
      toast("No se pudo cargar la librería de gráficos (vendor/chart.umd.min.js). Las tablas siguen disponibles.", true);
    }
    escribirFiltrosUI(S.filtros);

    // Secciones plegables: se recuerda cuáles quedaron abiertas (por defecto, solo la primera)
    const guardadas = leerAlmacen(CLAVE_SECCIONES, null);
    if (guardadas) document.querySelectorAll("details.ga-seccion").forEach((d) => { if (d.dataset.seccion in guardadas) d.open = !!guardadas[d.dataset.seccion]; });
    document.querySelectorAll("details.ga-seccion").forEach((d) => d.addEventListener("toggle", () => {
      guardarSecciones();
      if (d.open) d.querySelectorAll(".ga-card").forEach((c) => renderGrafico(c.dataset.ga)); // se dibuja al abrir
    }));
    $("gaExpandir").addEventListener("click", () => fijarSecciones(true));
    $("gaContraer").addEventListener("click", () => fijarSecciones(false));
    ["gaModalidad", "gaEsp", "gaProf", "gaEstado", "gaCanal"].forEach((id) => $(id).addEventListener("change", () => actualizarMasFiltros()));

    $("gaPeriodo").addEventListener("change", sincronizarFechasUI);
    $("gaPoli").addEventListener("change", actualizarSelectsDependientes);
    $("gaEsp").addEventListener("change", actualizarSelectsDependientes);
    $("gaAplicar").addEventListener("click", () => aplicarFiltros());
    $("gaLimpiar").addEventListener("click", limpiarFiltros);
    $("gaExportar").addEventListener("click", exportarCsv);
    document.querySelectorAll(".ga-filtros select, .ga-filtros input").forEach((el) => el.addEventListener("keydown", (e) => { if (e.key === "Enter") aplicarFiltros(); }));

    // Selectores propios de cada gráfico: se re-dibuja solo ese gráfico
    [["gaG1Sep", "G1"], ["gaG4Metrica", "G4"], ["gaG7Modo", "G7"], ["gaG0Metrica", "G0"], ["gaG0Dim", "G0"], ["gaG0Desglose", "G0"], ["gaG0Tipo", "G0"]]
      .forEach(([sel, g]) => $(sel).addEventListener("change", () => renderGrafico(g)));

    // Ver tabla (RNF02)
    document.querySelectorAll(".ga-btn-tabla").forEach((btn) => btn.addEventListener("click", () => {
      const card = btn.closest(".ga-card");
      const cont = card.querySelector(".ga-tabla");
      const abrir = cont.classList.contains("hidden");
      cont.classList.toggle("hidden", !abrir);
      btn.setAttribute("aria-expanded", String(abrir));
      btn.textContent = abrir ? "Ocultar tabla" : "Ver tabla";
    }));

    // Panel «Elegir qué ver»
    $("gaVisChecks").innerHTML = GRAFICOS.map((g) => `<label class="ga-check"><input type="checkbox" id="gaVis-${g}" data-g="${g}" /> <span><strong>${g}</strong> · ${NOMBRES[g]}</span></label>`).join("");
    $("gaVisChecks").addEventListener("change", (e) => { const g = e.target.dataset.g; if (g) cambiarVisibilidad({ [g]: e.target.checked }); });
    $("gaVisTodo").addEventListener("click", () => cambiarVisibilidad(Object.fromEntries(GRAFICOS.map((g) => [g, true]))));
    $("gaVisReset").addEventListener("click", () => cambiarVisibilidad(Object.fromEntries(GRAFICOS.map((g) => [g, true]))));
    aplicarVisibilidad();

    // Vistas guardadas del explorador
    $("gaVistaGuardar").addEventListener("click", guardarVista);
    $("gaVistas").addEventListener("click", (e) => {
      const ap = e.target.closest("[data-vista]"), bo = e.target.closest("[data-borrar]");
      if (ap) aplicarVista(Number(ap.dataset.vista));
      if (bo) { const v = vistasGuardadas(); v.splice(Number(bo.dataset.borrar), 1); almacenar(CLAVE_VISTAS, v); renderVistas(); }
    });
    renderVistas();

    // Cambio de ancho (móvil <-> escritorio): barras horizontales en pantallas angostas
    let t = null;
    window.addEventListener("resize", () => {
      clearTimeout(t);
      t = setTimeout(() => {
        const ang = esAngosto();
        if (ang !== S.angosto && $("route-admin-reportes").classList.contains("active")) { for (const g of ["G3", "G5", "G6"]) renderGrafico(g); }
      }, 200);
    });
  }

  // Punto de entrada: lo invoca cargarDatosAdmin() de app.js
  if (typeof window !== "undefined") window.cargarGraficosAdmin = async function cargarGraficosAdmin() {
    const vista = $("route-admin-reportes");
    if (!vista || !vista.classList.contains("active")) return; // solo con la vista de reportes abierta
    iniciarUI();
    await aplicarFiltros(false);
  };

  // API de pruebas (Node) y depuración
  const API = { tasa, formatPct, claveTemporal, periodosEntre, semanaISO, agruparPequenos, agrupar, tasasDe, ocupacionDe, etiquetaPeriodo, rangoDePeriodo, sumarDias, UMBRAL_AGRUPACION, PALETA, COLOR_ESTADO };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else if (typeof window !== "undefined") window.HDGraficos = API;
})();
