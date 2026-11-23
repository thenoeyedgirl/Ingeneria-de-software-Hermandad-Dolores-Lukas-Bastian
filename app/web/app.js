const state = {
  user: null,
  catalogos: { policlinicos: [], especialidades: [], profesionales: [] },
  selectedSlot: null,
  bloquesPublicos: [],
  todosBloquesDisp: [],
  listaEsperaItems: [],
  solicitudEnCurso: null,
  resumenActual: null, // { modo: "solicitud" | "consulta", datos: {...} }
  pendingSubmitAction: null,
  waManualCitaId: null,
};

// ===================== VALIDACIONES (RUT, TELÉFONO, CORREO, EDAD) =====================
function limpiarRut(valor) {
  return (valor || "").replace(/[^0-9kK]/g, "").toUpperCase().slice(0, 9);
}

function formatearRutEnVivo(valor) {
  const limpio = limpiarRut(valor);
  if (limpio.length <= 1) return limpio;
  const cuerpo = limpio.slice(0, -1);
  const dv = limpio.slice(-1);
  return `${cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, ".")}-${dv}`;
}

function validarRutModulo11(valor) {
  const limpio = limpiarRut(valor);
  if (limpio.length < 8 || limpio.length > 9) return false;
  const cuerpo = limpio.slice(0, -1);
  const dv = limpio.slice(-1);
  let suma = 0, mult = 2;
  for (let i = cuerpo.length - 1; i >= 0; i--) {
    suma += parseInt(cuerpo[i], 10) * mult;
    mult = mult === 7 ? 2 : mult + 1;
  }
  const resto = 11 - (suma % 11);
  const esperado = resto === 11 ? "0" : resto === 10 ? "K" : String(resto);
  return dv === esperado;
}

function validarTelefonoInternacional(valor) {
  const txt = (valor || "").trim();
  if (!/^\+?[0-9\s\-()]+$/.test(txt)) return false;
  const digitos = txt.replace(/\D/g, "");
  return digitos.length >= 8 && digitos.length <= 15;
}

function validarCorreo(valor) {
  const txt = (valor || "").trim();
  if (!txt) return true; // Opcional
  return /^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$/.test(txt);
}

function calcularEdad(fechaIso) {
  if (!fechaIso) return null;
  const hoy = new Date();
  const nac = new Date(`${fechaIso}T00:00:00`);
  if (Number.isNaN(nac.getTime()) || nac > hoy) return null;
  let edad = hoy.getFullYear() - nac.getFullYear();
  const m = hoy.getMonth() - nac.getMonth();
  if (m < 0 || (m === 0 && hoy.getDate() < nac.getDate())) edad--;
  return edad;
}

function configurarTutorPorEdad(fechaId, edadHintId, chkId, avisoId, camposId, lblTelId, lblCorId, nombreId) {
  const fechaEl = document.getElementById(fechaId);
  const edadHint = document.getElementById(edadHintId);
  const chk = document.getElementById(chkId);
  const aviso = document.getElementById(avisoId);
  const campos = document.getElementById(camposId);
  const lblTel = document.getElementById(lblTelId);
  const lblCor = document.getElementById(lblCorId);
  const nombreTutor = document.getElementById(nombreId);

  function sincronizar() {
    const edad = calcularEdad(fechaEl.value);
    const esMenor = edad !== null && edad < 18;
    if (edad === null) {
      edadHint.textContent = "";
      edadHint.className = "field-hint";
    } else {
      edadHint.textContent = `${edad} años`;
      edadHint.className = "field-hint ok";
    }

    if (esMenor) {
      chk.checked = true;
      chk.disabled = true;
      aviso.textContent = "Paciente menor de 18 años: se requiere registrar un tutor o adulto responsable a cargo.";
      aviso.className = "field-hint warn";
    } else {
      chk.disabled = false;
      aviso.textContent = chk.checked
        ? "Los datos de contacto se guardarán asociados al tutor o responsable."
        : "";
      aviso.className = "field-hint";
    }

    const activo = chk.checked;
    campos.classList.toggle("hidden", !activo);
    nombreTutor.required = activo;
    lblTel.textContent = activo ? "Teléfono de contacto del tutor / apoderado *" : "Teléfono de contacto del paciente *";
    lblCor.textContent = activo ? "Correo electrónico del tutor / apoderado (opcional)" : "Correo electrónico del paciente (opcional)";
  }

  fechaEl.addEventListener("change", sincronizar);
  chk.addEventListener("change", sincronizar);
  return sincronizar;
}

function inicializarCamposRut() {
  document.querySelectorAll('input[data-rut-input="true"]').forEach(input => {
    input.addEventListener("input", async () => {
      const formateado = formatearRutEnVivo(input.value);
      input.value = formateado;
      const hint = document.getElementById(`hint-${input.id}`);
      if (!hint) return;
      const limpio = limpiarRut(formateado);
      if (!limpio) {
        hint.textContent = "";
        hint.className = "field-hint";
      } else if (limpio.length < 8) {
        hint.textContent = "Sigue escribiendo el RUT...";
        hint.className = "field-hint";
      } else if (validarRutModulo11(formateado)) {
        hint.textContent = "✓ RUT válido";
        hint.className = "field-hint ok";
        // Si es el formulario público de solicitud, comprobar si ya tiene folio registrado
        if (input.id === "solRut") {
          const folioHint = document.getElementById("hint-solFolio");
          try {
            const ver = await api(`/api/publico/verificar-documento?rut=${encodeURIComponent(formateado)}`);
            if (ver.tiene_documento) {
              folioHint.textContent = "✓ Ya cuentas con un documento de respaldo registrado previamente (este campo es opcional).";
              folioHint.className = "field-hint ok";
            } else {
              folioHint.textContent = "Opcional: puedes ingresar tu folio FONASA o CESFAM si lo tienes a mano.";
              folioHint.className = "field-hint";
            }
          } catch (_) {}
        }
      } else {
        hint.textContent = "Revisa el dígito verificador";
        hint.className = "field-hint err";
      }
    });
  });
}

// ===================== API Y TOAST =====================
async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Error HTTP ${res.status}`);
  return data;
}

function showToast(msg, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast" + (isError ? " error" : "");
  setTimeout(() => el.classList.add("hidden"), 4400);
}

function pillEstado(val) {
  if (["RESERVADA", "PENDIENTE"].includes(val)) return `<span class="pill pill-blue">${val}</span>`;
  if (["ASISTIDA", "CONFIRMADA", "DISPONIBLE", "VALIDADO", "AGENDADO"].includes(val)) return `<span class="pill pill-green">${val}</span>`;
  if (["SIN_RESPUESTA", "CONTACTADO", "EN_REVISION"].includes(val)) return `<span class="pill pill-amber">${val}</span>`;
  return `<span class="pill pill-red">${val}</span>`;
}

function fillSelect(id, items, labelKey = "nombre", includeAll = false) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = includeAll ? `<option value="">Todos</option>` : "";
  items.forEach(it => {
    const opt = document.createElement("option");
    opt.value = it.id;
    opt.textContent = it[labelKey];
    el.appendChild(opt);
  });
}

// ===================== ROUTER CON HISTORIAL DEL NAVEGADOR =====================
const STAFF_TITLES = {
  "panel/agendar": ["Agendamiento asistido", "Búsqueda de ficha por RUT y asignación de cupos disponibles"],
  "panel/confirmaciones": ["Confirmaciones y seguimiento", "Gestión de citas pendientes o sin respuesta"],
  "panel/asistencia": ["Recepción y asistencia", "Registro diario de asistencia, inasistencia o cancelación"],
  "panel/espera": ["Lista de espera asistida", "Seguimiento manual de solicitudes por sede y especialidad"],
  "admin/agendas": ["Agendas y bloqueos", "Publicación de horarios y detección de citas afectadas"],
  "admin/reportes": ["Reportes e indicadores", "Gráficos de gestión y caracterización de pacientes"],
  "admin/auditoria": ["Auditoría administrativa", "Historial de operaciones recientes del personal"],
};

function navigateTo(route) {
  const target = `#/${route}`;
  if (window.location.hash !== target) {
    window.location.hash = target;
  } else {
    renderRoute();
  }
}

function renderRoute() {
  const raw = (window.location.hash || "#/pacientes/horas").replace(/^#\/?/, "");
  const route = raw || "pacientes/horas";
  const isStaffRoute = route.startsWith("panel/") || route.startsWith("admin/");

  if (isStaffRoute && !state.user) {
    navigateTo("acceso");
    return;
  }
  if (route.startsWith("admin/") && state.user?.rol !== "ADMINISTRACION") {
    navigateTo("panel/agendar");
    return;
  }

  document.getElementById("publicShell").classList.toggle("hidden", isStaffRoute);
  document.getElementById("staffShell").classList.toggle("hidden", !isStaffRoute);

  document.querySelectorAll(".route-view").forEach(v => v.classList.remove("active"));
  const viewId = `route-${route.replace("/", "-")}`;
  const targetEl = document.getElementById(viewId);
  if (targetEl) {
    targetEl.classList.add("active");
  } else {
    navigateTo("pacientes/horas");
    return;
  }

  document.querySelectorAll(".pub-nav-link, .pub-nav-btn, .sb-link").forEach(a => {
    a.classList.toggle("active", a.dataset.route === route);
  });

  if (isStaffRoute && STAFF_TITLES[route]) {
    document.getElementById("staffViewTitle").textContent = STAFF_TITLES[route][0];
    document.getElementById("staffViewSubtitle").textContent = STAFF_TITLES[route][1];
  }

  if (route === "pacientes/horas") cargarDisponibilidadPublica();
  if (route === "pacientes/solicitar") prepararVistaSolicitar();
  if (route === "pacientes/resumen") renderizarPantallaResumen();
  if (route.startsWith("panel/")) cargarDatosOperativos();
  if (route.startsWith("admin/")) cargarDatosAdmin();
}

window.addEventListener("hashchange", renderRoute);

// ===================== SESIÓN PERSISTENTE =====================
function aplicarSesion(usuario, redirigir = true) {
  state.user = usuario;
  if (usuario) {
    sessionStorage.setItem("hd_user", JSON.stringify(usuario));
    document.getElementById("sbUserName").textContent = usuario.nombre_completo;
    document.getElementById("sbUserSede").textContent = usuario.policlinico_nombre;
    const pill = document.getElementById("sbRolePill");
    if (usuario.rol === "ADMINISTRACION") {
      pill.textContent = "ADMINISTRACIÓN";
      pill.className = "sb-role-pill sb-role-admin";
      document.getElementById("menuAdmin").classList.remove("hidden");
    } else if (usuario.rol === "TELEMEDICINA") {
      pill.textContent = "TELEMEDICINA";
      pill.className = "sb-role-pill sb-role-telemed";
      document.getElementById("menuAdmin").classList.add("hidden");
    } else {
      pill.textContent = "TENS / TONS";
      pill.className = "sb-role-pill sb-role-tens";
      document.getElementById("menuAdmin").classList.add("hidden");
    }
    if (redirigir) navigateTo(usuario.rol === "ADMINISTRACION" ? "admin/reportes" : "panel/agendar");
  } else {
    sessionStorage.removeItem("hd_user");
    if (redirigir) navigateTo("pacientes/horas");
  }
}

// ===================== PORTAL PACIENTES =====================
async function cargarDisponibilidadPublica() {
  const pol = document.getElementById("pubFiltroPol").value;
  const esp = document.getElementById("pubFiltroEsp").value;
  const qs = new URLSearchParams({ solo_disponibles: "true" });
  if (pol) qs.set("policlinico_id", pol);
  if (esp) qs.set("especialidad_id", esp);

  const bloques = await api(`/api/bloques?${qs}`);
  state.bloquesPublicos = bloques;
  const grid = document.getElementById("slotsGrid");
  if (!bloques.length) {
    grid.innerHTML = `<p class="muted">No hay horas disponibles para este filtro. Puedes ingresar una solicitud en <strong>Solicitar hora</strong> y nuestro equipo te contactará.</p>`;
    return;
  }
  grid.innerHTML = bloques.map(b => `
    <article class="slot-card">
      <div>
        <div class="slot-top">
          <span class="slot-date">${b.fecha}</span>
          <span class="slot-time">${b.hora_inicio} – ${b.hora_fin}</span>
        </div>
        <div class="slot-meta mt-8">
          <strong>${b.especialidad_nombre}</strong>
          <span>${b.policlinico_nombre} (${b.modalidad === "TELEMEDICINA" ? "Atención remota" : "Presencial"})</span>
          <span>${b.profesional_nombre}</span>
        </div>
      </div>
      <button type="button" class="btn btn-primary btn-block" onclick="seleccionarHoraPaciente(${b.id})">
        Solicitar esta hora
      </button>
    </article>
  `).join("");
}

window.seleccionarHoraPaciente = (bloqueId) => {
  const slot = state.bloquesPublicos.find(b => b.id === bloqueId) || state.todosBloquesDisp.find(b => b.id === bloqueId);
  if (!slot) return;
  state.selectedSlot = slot;
  document.getElementById("solPol").value = slot.policlinico_id;
  document.getElementById("solEsp").value = slot.especialidad_id;
  navigateTo("pacientes/solicitar");
};

async function prepararVistaSolicitar() {
  const banner = document.getElementById("selectedSlotBanner");
  const manualBox = document.getElementById("bloqueSeleccionManual");

  if (state.selectedSlot) {
    const s = state.selectedSlot;
    banner.classList.remove("hidden");
    manualBox.classList.add("hidden");
    document.getElementById("selectedSlotText").textContent =
      `${s.fecha} · ${s.hora_inicio} a ${s.hora_fin} · ${s.policlinico_nombre} · ${s.especialidad_nombre} (${s.profesional_nombre})`;
  } else {
    banner.classList.add("hidden");
    manualBox.classList.remove("hidden");
    await actualizarHorariosEnTiempoReal();
  }
}

async function actualizarHorariosEnTiempoReal() {
  const polId = Number(document.getElementById("solPol").value);
  const espId = Number(document.getElementById("solEsp").value);
  state.todosBloquesDisp = await api("/api/bloques?solo_disponibles=true");

  const exactos = state.todosBloquesDisp.filter(b => b.policlinico_id === polId && b.especialidad_id === espId);
  const selBloque = document.getElementById("solBloque");
  const altBox = document.getElementById("solAltBox");

  if (exactos.length) {
    selBloque.innerHTML = `<option value="">-- Selecciona un horario disponible (o sin preferencia) --</option>` +
      exactos.map(b => `<option value="${b.id}">${b.fecha} · ${b.hora_inicio}–${b.hora_fin} · ${b.profesional_nombre}</option>`).join("");
    altBox.classList.add("hidden");
  } else {
    selBloque.innerHTML = `<option value="">Sin bloques publicados para esta combinación (quedará en lista de espera)</option>`;
    const enMismoPol = state.todosBloquesDisp.filter(b => b.policlinico_id === polId).slice(0, 4);
    const mismaEspOtros = state.todosBloquesDisp.filter(b => b.especialidad_id === espId && b.policlinico_id !== polId).slice(0, 4);

    let html = `<strong>No hay bloques disponibles</strong> para esta especialidad en el policlínico elegido. Puedes enviar igual tu solicitud para lista de espera`;
    if (enMismoPol.length || mismaEspOtros.length) {
      html += `, o elegir uno de estos horarios disponibles ahora:`;
      html += `<div class="alt-chip-list">`;
      [...enMismoPol, ...mismaEspOtros].forEach(b => {
        html += `<button type="button" class="alt-chip" onclick="seleccionarHoraPaciente(${b.id})">${b.policlinico_nombre} · ${b.especialidad_nombre} (${b.fecha} ${b.hora_inicio})</button>`;
      });
      html += `</div>`;
    } else {
      html += `.`;
    }
    altBox.innerHTML = html;
    altBox.classList.remove("hidden");
  }
}

// ===================== PANTALLA DE RESUMEN / DETALLE PROTEGIDO =====================
function renderizarPantallaResumen() {
  const box = document.getElementById("resumenDetalleBody");
  const privBanner = document.getElementById("resumenPrivacidadBanner");
  const encBox = document.getElementById("encuestaWebBox");

  if (!state.resumenActual) {
    box.innerHTML = `<p class="muted">No hay una solicitud o cita seleccionada para mostrar.</p>`;
    privBanner.classList.add("hidden");
    encBox.classList.add("hidden");
    return;
  }

  const { modo, datos } = state.resumenActual;
  if (modo === "solicitud") {
    document.getElementById("resumenTitulo").textContent = "Solicitud registrada correctamente";
    document.getElementById("resumenSubtitulo").textContent = "Nuestro equipo te contactará por teléfono o WhatsApp para confirmar tu atención.";
    privBanner.classList.add("hidden");
    encBox.classList.remove("hidden");
    box.innerHTML = `
      <div class="summary-item"><div class="summary-label">Paciente</div><div class="summary-value">${datos.paciente_nombre} (${datos.paciente_rut})</div></div>
      <div class="summary-item"><div class="summary-label">Estado</div><div class="summary-value">${pillEstado(datos.estado)}</div></div>
      <div class="summary-item"><div class="summary-label">Policlínico</div><div class="summary-value">${datos.policlinico_nombre}</div></div>
      <div class="summary-item"><div class="summary-label">Especialidad</div><div class="summary-value">${datos.especialidad_nombre}</div></div>
      <div class="summary-item"><div class="summary-label">Horario solicitado</div><div class="summary-value">${datos.detalle_horario}</div></div>
      <div class="summary-item"><div class="summary-label">Contacto / Responsable</div><div class="summary-value">${datos.usa_tutor ? `${datos.tutor_nombre} (${datos.tutor_parentesco})` : "Contacto directo del paciente"}</div></div>
      ${datos.comentario ? `<div class="summary-item span-2"><div class="summary-label">Comentario adicional</div><div class="summary-value">${datos.comentario}</div></div>` : ""}
    `;
  } else {
    document.getElementById("resumenTitulo").textContent = datos.es_solicitud ? "Detalle de solicitud (vista protegida)" : "Detalle de cita (vista protegida)";
    document.getElementById("resumenSubtitulo").textContent = "Información administrativa en modo de solo lectura.";
    privBanner.classList.remove("hidden");
    encBox.classList.add("hidden");
    box.innerHTML = `
      <div class="summary-item"><div class="summary-label">Paciente (protegido)</div><div class="summary-value">${datos.paciente_enmascarado} (${datos.rut})</div></div>
      <div class="summary-item"><div class="summary-label">Estado</div><div class="summary-value">${pillEstado(datos.estado_principal)} ${datos.estado_secundario ? pillEstado(datos.estado_secundario) : ""}</div></div>
      <div class="summary-item"><div class="summary-label">Policlínico</div><div class="summary-value">${datos.policlinico_nombre}</div></div>
      <div class="summary-item"><div class="summary-label">Especialidad</div><div class="summary-value">${datos.especialidad_nombre}</div></div>
      <div class="summary-item"><div class="summary-label">Fecha y horario</div><div class="summary-value">${datos.fecha_horario}</div></div>
      <div class="summary-item"><div class="summary-label">Datos de contacto y folios</div><div class="summary-value">Censurados por protección de datos</div></div>
    `;
  }
}

window.verDetalleCensurado = (payloadStr) => {
  state.resumenActual = { modo: "consulta", datos: JSON.parse(decodeURIComponent(payloadStr)) };
  navigateTo("pacientes/resumen");
};

// ===================== PANEL OPERATIVO =====================
async function cargarDatosOperativos() {
  const polId = state.user?.policlinico_id || "";
  const qsBloques = new URLSearchParams({ solo_disponibles: "true" });
  if (polId) qsBloques.set("policlinico_id", polId);

  const [bloques, pendientes, citas, espera] = await Promise.all([
    api(`/api/bloques?${qsBloques}`),
    api(`/api/citas/pendientes-confirmacion${polId ? `?policlinico_id=${polId}` : ""}`),
    api(`/api/citas${polId ? `?policlinico_id=${polId}` : ""}`),
    api(`/api/lista-espera${polId ? `?policlinico_id=${polId}` : ""}`),
  ]);

  const selBloque = document.getElementById("citaBloque");
  selBloque.innerHTML = bloques.length
    ? bloques.map(b => `<option value="${b.id}">${b.fecha} ${b.hora_inicio} · ${b.policlinico_nombre} · ${b.especialidad_nombre} (${b.profesional_nombre})</option>`).join("")
    : `<option value="">Sin bloques disponibles</option>`;

  document.getElementById("tablaPendientesConf").innerHTML = pendientes.length
    ? pendientes.map(c => `
      <tr>
        <td>${c.fecha}<br><strong>${c.hora_inicio}</strong></td>
        <td>${c.paciente_nombre}<br><small class="muted">${c.paciente_rut} · ${c.paciente_telefono}</small></td>
        <td>${c.policlinico_nombre}<br><small class="muted">${c.profesional_nombre}</small></td>
        <td>${pillEstado(c.estado_cita)}</td>
        <td>${pillEstado(c.estado_confirmacion)}</td>
        <td>
          <button class="btn-sm btn-ok" onclick="enviarWhatsApp(this, ${c.cita_id}, 'RECORDATORIO_24H')">WhatsApp 24h (botones)</button>
          <button class="btn-sm btn-neutral" onclick="enviarWhatsApp(this, ${c.cita_id}, 'RECORDATORIO_15D')">WhatsApp 15d</button>
          <button class="btn-sm btn-neutral" onclick="abrirMensajeManual(${c.cita_id}, '${c.paciente_nombre.replace(/'/g, "")}')">Mensaje manual</button>
          <button class="btn-sm btn-ok" onclick="confirmarCita(${c.cita_id}, 'CONFIRMADA')">Confirmar</button>
          <button class="btn-sm btn-warn" onclick="confirmarCita(${c.cita_id}, 'SIN_RESPUESTA')">Sin respuesta</button>
          <button class="btn-sm btn-danger" onclick="cancelarCita(${c.cita_id}, 'WHATSAPP_PACIENTE')">Cancelar hora</button>
        </td>
      </tr>
    `).join("")
    : `<tr><td colspan="6">No hay citas pendientes de confirmación.</td></tr>`;

  document.getElementById("tablaCitasOp").innerHTML = citas.map(c => `
    <tr>
      <td>${c.fecha}<br><strong>${c.hora_inicio}</strong></td>
      <td>${c.paciente_nombre}<br><small class="muted">${c.paciente_rut}</small></td>
      <td>${c.policlinico_nombre}<br><small class="muted">${c.especialidad_nombre}</small></td>
      <td>${pillEstado(c.estado_cita)}</td>
      <td>${pillEstado(c.estado_confirmacion)}</td>
      <td>
        ${c.estado_cita === "RESERVADA" ? `
          <button class="btn-sm btn-ok" onclick="marcarAsistencia(${c.cita_id}, true)">Asistió</button>
          <button class="btn-sm btn-warn" onclick="marcarAsistencia(${c.cita_id}, false)">Inasistió</button>
          <button class="btn-sm btn-neutral" onclick="abrirMensajeManual(${c.cita_id}, '${c.paciente_nombre.replace(/'/g, "")}')">Mensaje manual</button>
          <button class="btn-sm btn-danger" onclick="cancelarCita(${c.cita_id}, 'ASISTIDA_TENS')">Cancelar</button>
        ` : `<small class="muted">Cita cerrada</small>`}
      </td>
    </tr>
  `).join("");

  state.listaEsperaItems = espera;
  actualizarBannerSolicitud();
  cargarMensajesWhatsApp();
  document.getElementById("tablaListaEspera").innerHTML = espera.map(le => `
    <tr>
      <td>${le.paciente_nombre}<br><small class="muted">${le.paciente_rut} · ${le.paciente_telefono}</small></td>
      <td>${le.policlinico_nombre}<br><small class="muted">${le.especialidad_nombre}</small></td>
      <td><strong>${le.prioridad}</strong></td>
      <td>${pillEstado(le.estado)}</td>
      <td>${le.observacion || "—"}</td>
      <td>
        ${["PENDIENTE", "CONTACTADO"].includes(le.estado) ? `<button class="btn-sm btn-ok" onclick="agendarDesdeSolicitud(${le.id})">Agendar solicitud</button>` : ""}
        <button class="btn-sm btn-warn" onclick="cambiarEspera(${le.id}, 'CONTACTADO')">Contactado</button>
        <button class="btn-sm btn-neutral" onclick="cambiarEspera(${le.id}, 'DESCARTADO')">Descartar</button>
      </td>
    </tr>
  `).join("");
}

function actualizarBannerSolicitud() {
  const banner = document.getElementById("activeWaitlistBanner");
  if (!banner) return;
  if (!state.solicitudEnCurso) {
    banner.classList.add("hidden");
    return;
  }
  const s = state.solicitudEnCurso;
  banner.classList.remove("hidden");
  document.getElementById("activeWaitlistText").textContent =
    `${s.paciente_nombre} (${s.paciente_rut}) · ${s.policlinico_nombre} · ${s.especialidad_nombre}${s.observacion ? " · " + s.observacion : ""}`;
}

function renderFichaPaciente(p) {
  const box = document.getElementById("fichaPacienteBox");
  box.classList.remove("hidden");
  const ordenes = (p.ordenes_medicas || []).map(o => `${o.especialidad_nombre}: ${o.sesiones_disponibles}/${o.sesiones_totales} ses.`).join(" · ") || "Sin órdenes plurisesión";
  const tutores = (p.responsables || []).map(r => `${r.nombre_completo} (${r.parentesco} · ${r.telefono})`).join(" | ") || "Sin tutor registrado";
  const docs = (p.documentos_respaldo || []).map(d => `${d.tipo_documento}: ${d.folio} (${d.estado_revision})`).join(" | ") || "Sin folio registrado";
  const edad = calcularEdad(p.fecha_nacimiento);
  box.innerHTML = `
    <strong>${p.nombre_completo}</strong> (${p.rut}) · ${p.nacionalidad || "Chilena"}${edad !== null ? ` · ${edad} años` : ""}<br>
    Teléfono: ${p.telefono} · Previsión: ${p.prevision}<br>
    <small class="muted"><strong>Tutor/Responsable:</strong> ${tutores}</small><br>
    <small class="muted"><strong>Documentos:</strong> ${docs}</small><br>
    <small class="muted"><strong>Órdenes:</strong> ${ordenes}</small>
  `;
}

window.agendarDesdeSolicitud = async (itemId) => {
  const item = state.listaEsperaItems.find(x => x.id === itemId);
  if (!item) return;
  state.solicitudEnCurso = item;
  document.getElementById("opRutBuscar").value = item.paciente_rut;
  document.getElementById("citaRut").value = item.paciente_rut;
  navigateTo("panel/agendar");
  actualizarBannerSolicitud();
  try {
    const p = await api(`/api/pacientes/buscar?rut=${encodeURIComponent(item.paciente_rut)}`);
    renderFichaPaciente(p);
  } catch (_) {}
};

async function cargarMensajesWhatsApp() {
  const tbody = document.getElementById("tablaMensajesWa");
  if (!tbody) return;
  try {
    const qs = new URLSearchParams();
    if (state.user?.policlinico_id) qs.set("policlinico_id", state.user.policlinico_id);
    const filtroRut = (document.getElementById("filtroWaRut")?.value || "").trim();
    if (filtroRut) qs.set("rut", filtroRut);
    const msgs = await api(`/api/whatsapp/mensajes${qs.toString() ? "?" + qs.toString() : ""}`);
    if (!msgs.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="muted">Sin mensajes registrados para este filtro.</td></tr>`;
      return;
    }
    tbody.innerHTML = msgs.map(m => {
      const det = m.detalle || "";
      const esRecibido = det.startsWith("[RECIBIDO]");
      const badge = esRecibido
        ? `<span class="pill pill-green">RECIBIDO</span>`
        : (m.estado_envio === "FALLO_ALERTA_OPERATIVA"
            ? `<span class="pill pill-red">ALERTA</span>`
            : `<span class="pill pill-blue">ENVIADO</span>`);
      const limpio = det.replace(/^\[(RECIBIDO|MANUAL)\]\s*/, "");
      const pacInfo = m.paciente_rut
        ? `<strong>${m.paciente_nombre || ""}</strong><br><small class="muted">${m.paciente_rut}</small>`
        : `<small class="muted">Respuesta entrante</small>`;
      return `
        <tr>
          <td><small>${(m.enviado_en || "").replace("T", " ").slice(0, 19)}</small></td>
          <td>${badge}</td>
          <td>${pacInfo}</td>
          <td><small>${m.destinatario || "—"}</small></td>
          <td>${limpio}</td>
        </tr>
      `;
    }).join("");
  } catch (_) {}
}

window.enviarWhatsApp = async (btn, citaId, tipo) => {
  const textoOriginal = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Enviando...";
  }
  showToast("Enviando mensaje por WhatsApp...");
  try {
    const res = await api(`/api/citas/${citaId}/recordatorio-whatsapp`, {
      method: "POST",
      body: JSON.stringify({ tipo }),
    });
    if (res.alerta_operativa) {
      showToast(`Aviso WhatsApp con alerta: ${res.detalle}`, true);
    } else {
      showToast(tipo === "RECORDATORIO_15D"
        ? "Recordatorio anticipado (15d) enviado por WhatsApp."
        : "Recordatorio 24h con botones enviado por WhatsApp.");
    }
    cargarMensajesWhatsApp();
  } catch (err) {
    showToast(err.message, true);
  } finally {
    if (btn) {
      setTimeout(() => {
        btn.disabled = false;
        btn.textContent = textoOriginal;
      }, 2500);
    }
  }
};

window.abrirMensajeManual = (citaId, pacienteNombre) => {
  state.waManualCitaId = citaId;
  document.getElementById("waManualInfo").textContent = `Destinatario: ${pacienteNombre} (Cita #${citaId})`;
  document.getElementById("waManualTexto").value = "";
  document.getElementById("waManualModal").classList.remove("hidden");
  document.getElementById("waManualTexto").focus();
};

window.confirmarCita = async (citaId, estadoConf) => {
  try {
    await api(`/api/citas/${citaId}/confirmacion`, {
      method: "PATCH",
      body: JSON.stringify({ estado_confirmacion: estadoConf, canal: "TELEFONO", usuario_id: state.user?.id, usuario_nombre: state.user?.nombre_completo, rol: state.user?.rol }),
    });
    showToast(estadoConf === "SIN_RESPUESTA" ? "Seguimiento registrado sin respuesta. La cita se mantiene activa." : "Confirmación registrada.");
    cargarDatosOperativos();
  } catch (err) { showToast(err.message, true); }
};

window.cancelarCita = async (citaId, origen) => {
  try {
    await api(`/api/citas/${citaId}/cancelar`, {
      method: "POST",
      body: JSON.stringify({ origen_cancelacion: origen, motivo: "Cancelación registrada en panel", usuario_id: state.user?.id, usuario_nombre: state.user?.nombre_completo, rol: state.user?.rol }),
    });
    showToast("Cita cancelada y cupo liberado en agenda.");
    cargarDatosOperativos();
  } catch (err) { showToast(err.message, true); }
};

window.marcarAsistencia = async (citaId, asistio) => {
  try {
    await api(`/api/citas/${citaId}/asistencia`, {
      method: "POST",
      body: JSON.stringify({ asistio, usuario_id: state.user?.id, usuario_nombre: state.user?.nombre_completo, rol: state.user?.rol }),
    });
    showToast(asistio ? "Asistencia registrada e invitación a encuesta enviada." : "Inasistencia registrada.");
    cargarDatosOperativos();
  } catch (err) { showToast(err.message, true); }
};

window.cambiarEspera = async (itemId, estado) => {
  try {
    await api(`/api/lista-espera/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ estado, usuario_nombre: state.user?.nombre_completo, rol: state.user?.rol }),
    });
    showToast(`Solicitud actualizada a ${estado}.`);
    cargarDatosOperativos();
  } catch (err) { showToast(err.message, true); }
};

// ===================== PANEL ADMINISTRACIÓN + GRÁFICOS =====================
function renderBarChart(containerId, items, colorClass = "") {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!items.length) {
    el.innerHTML = `<p class="muted">Sin datos suficientes todavía.</p>`;
    return;
  }
  const maxVal = Math.max(...items.map(i => Number(i.value) || 0), 1);
  el.innerHTML = items.map(it => {
    const pct = Math.round(((Number(it.value) || 0) / maxVal) * 100);
    const cls = it.color || colorClass;
    return `
      <div class="bar-row">
        <div class="bar-meta"><span>${it.label}</span><span>${it.value}</span></div>
        <div class="bar-track"><div class="bar-fill ${cls}" style="width:${pct}%"></div></div>
      </div>
    `;
  }).join("");
}

async function cargarDatosAdmin() {
  const [bloques, rep, aud] = await Promise.all([
    api("/api/bloques"),
    api("/api/reportes"),
    api("/api/auditoria"),
  ]);

  document.getElementById("tablaBloquesAdmin").innerHTML = bloques.map(b => `
    <tr>
      <td>${b.fecha}</td>
      <td>${b.hora_inicio} – ${b.hora_fin}</td>
      <td>${b.policlinico_nombre}</td>
      <td>${b.profesional_nombre}</td>
      <td>${pillEstado(b.estado_bloque)}</td>
      <td>
        ${b.estado_bloque !== "BLOQUEADO"
          ? `<button class="btn-sm btn-danger" onclick="cambiarBloque(${b.id}, 'BLOQUEADO')">Bloquear</button>`
          : `<button class="btn-sm btn-ok" onclick="cambiarBloque(${b.id}, 'DISPONIBLE')">Desbloquear</button>`}
      </td>
    </tr>
  `).join("");

  const inds = rep.indicadores_por_sede;
  const totCitas = inds.reduce((a, x) => a + x.total_citas, 0);
  const totAsist = inds.reduce((a, x) => a + x.asistidas, 0);
  const totRes = inds.reduce((a, x) => a + x.reservadas, 0);
  const totInas = inds.reduce((a, x) => a + x.inasistidas, 0);
  const totCanc = inds.reduce((a, x) => a + x.canceladas, 0);
  const totPend = inds.reduce((a, x) => a + x.pendientes_confirmacion, 0);
  const totDisp = rep.ocupacion_por_sede.reduce((a, x) => a + x.bloques_disponibles, 0);

  document.getElementById("kpiGrid").innerHTML = `
    <div class="kpi-card"><div class="kpi-label">Citas registradas</div><div class="kpi-val">${totCitas}</div></div>
    <div class="kpi-card"><div class="kpi-label">Citas asistidas</div><div class="kpi-val">${totAsist}</div></div>
    <div class="kpi-card"><div class="kpi-label">Pendientes de confirmación</div><div class="kpi-val">${totPend}</div></div>
    <div class="kpi-card"><div class="kpi-label">Cupos disponibles</div><div class="kpi-val">${totDisp}</div></div>
  `;

  renderBarChart("chartSedes", inds.map(r => ({ label: r.policlinico_nombre, value: r.total_citas })), "navy");
  renderBarChart("chartEstados", [
    { label: "Reservadas activas", value: totRes, color: "blue" },
    { label: "Asistidas", value: totAsist, color: "green" },
    { label: "Inasistidas", value: totInas, color: "amber" },
    { label: "Canceladas", value: totCanc, color: "red" },
  ]);
  renderBarChart("chartEdad", (rep.caracterizacion_edad || []).map(x => ({ label: x.tramo, value: x.total })), "");
  renderBarChart("chartNacionalidad", (rep.caracterizacion_nacionalidad || []).map(x => ({ label: x.nacionalidad, value: x.total })), "navy");

  document.getElementById("tablaIndicadores").innerHTML = inds.map(r => `
    <tr>
      <td><strong>${r.policlinico_nombre}</strong></td>
      <td>${r.modalidad}</td>
      <td>${r.total_citas}</td>
      <td>${r.reservadas}</td>
      <td>${r.asistidas}</td>
      <td>${r.inasistidas}</td>
      <td>${r.canceladas}</td>
      <td>${r.pendientes_confirmacion}</td>
      <td><strong>${r.tasa_asistencia_pct} %</strong></td>
    </tr>
  `).join("");

  document.getElementById("tablaAuditoria").innerHTML = aud.map(a => `
    <tr>
      <td><small>${a.registrado_en.replace("T", " ").slice(0, 19)}</small></td>
      <td>${a.usuario_nombre}</td>
      <td><small>${a.rol}</small></td>
      <td>${a.policlinico_nombre}</td>
      <td><code>${a.operacion}</code></td>
      <td>${a.detalle}</td>
    </tr>
  `).join("");
}

window.cambiarBloque = async (bloqueId, nuevoEstado) => {
  try {
    const res = await api(`/api/bloques/${bloqueId}/estado`, {
      method: "PATCH",
      body: JSON.stringify({ estado_bloque: nuevoEstado, motivo: "Ajuste desde Administración", usuario_nombre: state.user?.nombre_completo }),
    });
    const n = res.citas_afectadas.length;
    showToast(n > 0 ? `Bloque actualizado a ${nuevoEstado}. Atención: ${n} cita(s) afectada(s).` : `Bloque actualizado a ${nuevoEstado}.`);
    cargarDatosAdmin();
  } catch (err) { showToast(err.message, true); }
};

// ===================== EVENTOS Y FORMULARIOS =====================
document.getElementById("btnBuscarDisp").addEventListener("click", cargarDisponibilidadPublica);

// Al hacer clic en "Solicitar hora" en el encabezado, limpiar horario seleccionado previo
document.getElementById("navSolicitarDirecto").addEventListener("click", () => {
  state.selectedSlot = null;
});
document.getElementById("btnLimpiarSlot").addEventListener("click", () => {
  state.selectedSlot = null;
  navigateTo("pacientes/horas");
});
document.getElementById("solPol").addEventListener("change", actualizarHorariosEnTiempoReal);
document.getElementById("solEsp").addEventListener("change", actualizarHorariosEnTiempoReal);

// Validación en vivo de teléfono y correo del formulario paciente
document.getElementById("solTelefono").addEventListener("input", (e) => {
  const hint = document.getElementById("hint-solTelefono");
  const v = e.target.value.trim();
  if (!v) { hint.textContent = ""; hint.className = "field-hint"; }
  else if (validarTelefonoInternacional(v)) { hint.textContent = "✓ Teléfono válido"; hint.className = "field-hint ok"; }
  else { hint.textContent = "Ingresa entre 8 y 15 dígitos (ej: +56 9 5000 0000 o número extranjero)"; hint.className = "field-hint err"; }
});

document.getElementById("solCorreo").addEventListener("input", (e) => {
  const hint = document.getElementById("hint-solCorreo");
  const v = e.target.value.trim();
  if (!v) { hint.textContent = ""; hint.className = "field-hint"; }
  else if (validarCorreo(v)) { hint.textContent = "✓ Correo válido"; hint.className = "field-hint ok"; }
  else { hint.textContent = "Formato no válido (si continúas así, se omitirá el correo)"; hint.className = "field-hint warn"; }
});

// Modal de correo opcional inválido
document.getElementById("btnEmailCorregir").addEventListener("click", () => {
  document.getElementById("emailModal").classList.add("hidden");
  state.pendingSubmitAction = null;
  document.getElementById("solCorreo").focus();
});
document.getElementById("btnEmailOmitir").addEventListener("click", async () => {
  document.getElementById("emailModal").classList.add("hidden");
  if (state.pendingSubmitAction) {
    const fn = state.pendingSubmitAction;
    state.pendingSubmitAction = null;
    await fn();
  }
});

async function ejecutarEnvioSolicitud(payload) {
  try {
    const res = await api("/api/publico/solicitud", { method: "POST", body: JSON.stringify(payload) });
    state.selectedSlot = null;
    document.getElementById("formSolicitudPaciente").reset();
    state.resumenActual = { modo: "solicitud", datos: res.resumen };
    showToast("Solicitud enviada correctamente.");
    navigateTo("pacientes/resumen");
  } catch (err) {
    showToast(err.message, true);
  }
}

document.getElementById("formSolicitudPaciente").addEventListener("submit", async (e) => {
  e.preventDefault();
  const rut = document.getElementById("solRut").value;
  if (!validarRutModulo11(rut)) {
    showToast("Ingresa un RUT chileno válido antes de enviar.", true);
    return;
  }
  const tel = document.getElementById("solTelefono").value.trim();
  if (!validarTelefonoInternacional(tel)) {
    showToast("Ingresa un teléfono válido (8 a 15 dígitos, nacional o extranjero).", true);
    return;
  }
  const usaTutor = document.getElementById("solUsaTutor").checked;
  const tutorNombre = document.getElementById("solTutorNombre").value.trim();
  if (usaTutor && !tutorNombre) {
    showToast("Ingresa el nombre del tutor o apoderado a cargo.", true);
    return;
  }

  const correoIngresado = document.getElementById("solCorreo").value.trim();
  const polId = state.selectedSlot ? state.selectedSlot.policlinico_id : Number(document.getElementById("solPol").value);
  const espId = state.selectedSlot ? state.selectedSlot.especialidad_id : Number(document.getElementById("solEsp").value);
  const bloqueId = state.selectedSlot
    ? state.selectedSlot.id
    : (document.getElementById("solBloque").value ? Number(document.getElementById("solBloque").value) : null);

  const construirPayload = (correoFinal) => ({
    rut,
    nombre_completo: document.getElementById("solNombre").value.trim(),
    fecha_nacimiento: document.getElementById("solFechaNac").value || null,
    nacionalidad: document.getElementById("solNacionalidad").value,
    telefono: tel,
    correo: usaTutor ? null : correoFinal,
    policlinico_id: polId,
    especialidad_id: espId,
    bloque_preferido_id: bloqueId,
    usa_tutor: usaTutor,
    responsable_nombre: usaTutor ? tutorNombre : null,
    responsable_parentesco: usaTutor ? document.getElementById("solTutorParentesco").value : null,
    responsable_telefono: usaTutor ? tel : null,
    responsable_correo: usaTutor ? correoFinal : null,
    tipo_documento: document.getElementById("solTipoDoc").value,
    folio_documento: document.getElementById("solFolio").value.trim() || null,
    observacion: document.getElementById("solObs").value.trim() || null,
  });

  if (correoIngresado && !validarCorreo(correoIngresado)) {
    document.getElementById("emailModalText").textContent =
      `El correo «${correoIngresado}» no tiene un formato válido (ejemplo: usuario@dominio.cl). Como es opcional, puedes enviar tu solicitud sin guardar el correo o volver para corregirlo.`;
    state.pendingSubmitAction = () => ejecutarEnvioSolicitud(construirPayload(null));
    document.getElementById("emailModal").classList.remove("hidden");
    return;
  }

  await ejecutarEnvioSolicitud(construirPayload(correoIngresado || null));
});

document.getElementById("formEncuestaWeb").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/encuestas", {
      method: "POST",
      body: JSON.stringify({
        tipo: "AGENDAMIENTO_WEB",
        puntaje: Number(document.getElementById("encWebPuntaje").value),
        comentario: document.getElementById("encWebComentario").value || null,
      }),
    });
    document.getElementById("encuestaWebBox").classList.add("hidden");
    showToast("¡Gracias por compartir tu opinión!");
  } catch (err) { showToast(err.message, true); }
});

document.getElementById("formConsultaRut").addEventListener("submit", async (e) => {
  e.preventDefault();
  const rut = document.getElementById("inputConsultaRut").value;
  if (!validarRutModulo11(rut)) {
    showToast("Ingresa un RUT válido para consultar.", true);
    return;
  }
  try {
    const res = await api(`/api/publico/consulta-rut?rut=${encodeURIComponent(rut)}`);
    const box = document.getElementById("resConsultaRut");
    box.classList.remove("hidden");
    if (!res.encontrado) {
      box.innerHTML = `<div class="result-box"><strong>Sin registros:</strong> No encontramos citas ni solicitudes asociadas a ese RUT.</div>`;
      return;
    }

    const cardsCitas = (res.citas || []).map(c => {
      const detalle = encodeURIComponent(JSON.stringify({
        es_solicitud: false,
        paciente_enmascarado: res.paciente_enmascarado,
        rut: res.rut,
        policlinico_nombre: c.policlinico_nombre,
        especialidad_nombre: c.especialidad_nombre,
        fecha_horario: `${c.fecha} · ${c.hora_inicio} (${c.profesional_nombre})`,
        estado_principal: c.estado_cita,
        estado_secundario: c.estado_confirmacion,
      }));
      return `
        <div class="consulta-card">
          <div>
            <strong>${c.fecha} ${c.hora_inicio}</strong> · ${c.policlinico_nombre} (${c.especialidad_nombre})<br>
            <small class="muted">${c.profesional_nombre}</small> · ${pillEstado(c.estado_cita)} ${pillEstado(c.estado_confirmacion)}
          </div>
          <button type="button" class="btn btn-ghost" onclick="verDetalleCensurado('${detalle}')">Ver resumen</button>
        </div>
      `;
    }).join("");

    const cardsSol = (res.solicitudes || []).map(s => {
      const detalle = encodeURIComponent(JSON.stringify({
        es_solicitud: true,
        paciente_enmascarado: res.paciente_enmascarado,
        rut: res.rut,
        policlinico_nombre: s.policlinico_nombre,
        especialidad_nombre: s.especialidad_nombre,
        fecha_horario: "Solicitud en espera de confirmación",
        estado_principal: s.estado,
        estado_secundario: "",
      }));
      return `
        <div class="consulta-card">
          <div>
            <strong>Solicitud</strong> · ${s.policlinico_nombre} (${s.especialidad_nombre})<br>
            ${pillEstado(s.estado)}
          </div>
          <button type="button" class="btn btn-ghost" onclick="verDetalleCensurado('${detalle}')">Ver resumen</button>
        </div>
      `;
    }).join("");

    box.innerHTML = `
      <div class="alert-info"><strong>Paciente:</strong> ${res.paciente_enmascarado} (${res.rut}) · ${res.aviso_privacidad}</div>
      ${cardsCitas}
      ${cardsSol}
      ${(!cardsCitas && !cardsSol) ? `<p class="muted">No registra citas ni solicitudes activas.</p>` : ""}
    `;
  } catch (err) { showToast(err.message, true); }
});

document.getElementById("btnLimpiarSolicitud").addEventListener("click", () => { state.solicitudEnCurso = null; actualizarBannerSolicitud(); });
document.getElementById("btnLogout").addEventListener("click", () => aplicarSesion(null, true));

document.getElementById("formLogin").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const u = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: document.getElementById("loginUser").value.trim(), clave: document.getElementById("loginPass").value }),
    });
    document.getElementById("formLogin").reset();
    aplicarSesion(u, true);
    showToast(`Bienvenido/a, ${u.nombre_completo}`);
  } catch (err) { showToast(err.message, true); }
});

document.getElementById("formBuscarPac").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const p = await api(`/api/pacientes/buscar?rut=${encodeURIComponent(document.getElementById("opRutBuscar").value)}`);
    document.getElementById("citaRut").value = p.rut;
    renderFichaPaciente(p);
  } catch (err) { showToast(err.message, true); }
});

document.getElementById("formNuevoPac").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(e.target).entries());
  if (!validarRutModulo11(fd.rut)) { showToast("RUT inválido.", true); return; }
  if (!validarTelefonoInternacional(fd.telefono)) { showToast("Teléfono inválido (8 a 15 dígitos).", true); return; }
  const usaTutor = document.getElementById("newPacUsaTutor").checked;
  const tutorNombre = document.getElementById("newPacTutorNombre").value.trim();
  if (usaTutor && !tutorNombre) { showToast("Ingresa el nombre del tutor o apoderado.", true); return; }

  const correoLimpio = validarCorreo(fd.correo) ? (fd.correo.trim() || null) : null;
  const payload = {
    ...fd,
    correo: usaTutor ? null : correoLimpio,
    usa_tutor: usaTutor,
    responsable_nombre: usaTutor ? tutorNombre : null,
    responsable_parentesco: usaTutor ? document.getElementById("newPacTutorParentesco").value : null,
    responsable_telefono: usaTutor ? fd.telefono : null,
    responsable_correo: usaTutor ? correoLimpio : null,
    folio_documento: (fd.folio_documento || "").trim() || null,
  };
  try {
    const p = await api("/api/pacientes", { method: "POST", body: JSON.stringify(payload) });
    document.getElementById("citaRut").value = p.rut;
    renderFichaPaciente(p);
    showToast(`Ficha guardada para ${p.nombre_completo}.`);
    e.target.reset();
  } catch (err) { showToast(err.message, true); }
});

document.getElementById("formAgendarCita").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await api("/api/citas", {
      method: "POST",
      body: JSON.stringify({
        paciente_rut: document.getElementById("citaRut").value,
        bloque_id: Number(document.getElementById("citaBloque").value),
        canal_registro: document.getElementById("citaCanal").value,
        usuario_id: state.user?.id,
        usuario_nombre: state.user?.nombre_completo,
        rol: state.user?.rol,
      }),
    });
    const c = res.comprobante_sin_codigo;
    const box = document.getElementById("comprobanteBox");
    box.classList.remove("hidden");
    box.innerHTML = `
      <strong>Comprobante de cita</strong><br>
      Paciente: ${c.paciente} (${c.rut})<br>
      Sede: ${c.policlinico} · ${c.especialidad}<br>
      Profesional: ${c.profesional} · Fecha: <strong>${c.fecha} ${c.hora}</strong>
    `;
    if (state.solicitudEnCurso) {
      await api(`/api/lista-espera/${state.solicitudEnCurso.id}`, {
        method: "PATCH",
        body: JSON.stringify({ estado: "AGENDADO", usuario_nombre: state.user?.nombre_completo, rol: state.user?.rol }),
      }).catch(() => {});
      state.solicitudEnCurso = null;
      actualizarBannerSolicitud();
      showToast("Cita agendada y solicitud marcada como AGENDADO.");
    } else {
      showToast("Cita agendada correctamente.");
    }
    cargarDatosOperativos();
  } catch (err) { showToast(err.message, true); }
});

document.getElementById("formListaEspera").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(e.target).entries());
  fd.policlinico_id = Number(fd.policlinico_id);
  fd.especialidad_id = Number(fd.especialidad_id);
  fd.usuario_id = state.user?.id;
  fd.usuario_nombre = state.user?.nombre_completo;
  fd.rol = state.user?.rol;
  try {
    await api("/api/lista-espera", { method: "POST", body: JSON.stringify(fd) });
    showToast("Solicitud agregada a lista de espera.");
    e.target.reset();
    cargarDatosOperativos();
  } catch (err) { showToast(err.message, true); }
});

document.getElementById("formCrearBloque").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(e.target).entries());
  fd.policlinico_id = Number(fd.policlinico_id);
  fd.especialidad_id = Number(fd.especialidad_id);
  fd.profesional_id = Number(fd.profesional_id);
  fd.usuario_nombre = state.user?.nombre_completo;
  try {
    await api("/api/bloques", { method: "POST", body: JSON.stringify(fd) });
    showToast("Bloque publicado en agenda.");
    cargarDatosAdmin();
  } catch (err) { showToast(err.message, true); }
});


document.getElementById("btnWaManualCancelar")?.addEventListener("click", () => {
  document.getElementById("waManualModal").classList.add("hidden");
  state.waManualCitaId = null;
});

document.getElementById("formWaManual")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.waManualCitaId) return;
  const btn = document.getElementById("btnWaManualEnviar");
  const txt = document.getElementById("waManualTexto").value.trim();
  if (!txt) return;
  btn.disabled = true;
  btn.textContent = "Enviando...";
  showToast("Enviando mensaje personalizado por WhatsApp...");
  try {
    const res = await api(`/api/citas/${state.waManualCitaId}/mensaje-whatsapp`, {
      method: "POST",
      body: JSON.stringify({ mensaje: txt }),
    });
    document.getElementById("waManualModal").classList.add("hidden");
    state.waManualCitaId = null;
    if (res.alerta_operativa) {
      showToast(`Error al enviar: ${res.detalle}`, true);
    } else {
      showToast("Mensaje personalizado enviado correctamente.");
    }
    cargarMensajesWhatsApp();
  } catch (err) {
    showToast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Enviar mensaje";
  }
});

document.getElementById("filtroWaRut")?.addEventListener("input", cargarMensajesWhatsApp);
document.getElementById("btnRefrescarWa")?.addEventListener("click", async () => {
  await cargarDatosOperativos();
  showToast("Mensajes y confirmaciones actualizados.");
});

document.getElementById("btnSuscribirWaba")?.addEventListener("click", async (e) => {
  const btn = e.target;
  btn.disabled = true;
  btn.textContent = "Activando...";
  try {
    const res = await api("/api/whatsapp/suscribir-waba", { method: "POST", body: JSON.stringify({}) });
    if (res.status_code >= 200 && res.status_code < 300) {
      showToast("Recepción webhook activada en Meta (subscribed_apps OK).");
    } else {
      showToast(`Meta respondió HTTP ${res.status_code}: ${JSON.stringify(res.respuesta)}`, true);
    }
  } catch (err) {
    showToast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Activar recepción webhook";
  }
});

// ===================== INICIALIZACIÓN =====================
async function init() {
  inicializarCamposRut();
  configurarTutorPorEdad("solFechaNac", "hint-solEdad", "solUsaTutor", "solTutorAviso", "solTutorCampos", "lblSolTelefono", "lblSolCorreo", "solTutorNombre");
  configurarTutorPorEdad("newPacFechaNac", "hint-newPacEdad", "newPacUsaTutor", "newPacTutorAviso", "newPacTutorCampos", "lblNewPacTel", "lblNewPacCorreo", "newPacTutorNombre");

  try {
    state.catalogos = await api("/api/catalogos");
    fillSelect("pubFiltroPol", state.catalogos.policlinicos, "nombre", true);
    fillSelect("pubFiltroEsp", state.catalogos.especialidades, "nombre", true);
    fillSelect("solPol", state.catalogos.policlinicos, "nombre", false);
    fillSelect("solEsp", state.catalogos.especialidades, "nombre", false);
    fillSelect("lePol", state.catalogos.policlinicos, "nombre", false);
    fillSelect("leEsp", state.catalogos.especialidades, "nombre", false);
    fillSelect("admPol", state.catalogos.policlinicos, "nombre", false);
    fillSelect("admEsp", state.catalogos.especialidades, "nombre", false);
    fillSelect("admProf", state.catalogos.profesionales, "nombre_completo", false);

    const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
    document.getElementById("admFecha").value = tomorrow;

    const saved = sessionStorage.getItem("hd_user");
    if (saved) aplicarSesion(JSON.parse(saved), false);

    if (!window.location.hash) window.location.replace("#/pacientes/horas");
    renderRoute();
  } catch (err) {
    showToast(`Error al cargar datos: ${err.message}`, true);
  }
}

init();
