-- ============================================================================
-- Sistema de Gestión de Citas y Operación Administrativa para Policlínicos
-- Fundación Hermandad de Dolores · MVP Fase 1 (PostgreSQL 16)
-- Equipo: Bastián Ignacio Fariña y Lukas Garrido (Patrocina: UDD)
-- NOTA: Frontera estrictamente administrativa (sin ficha clínica ni código de reserva).
-- ============================================================================

DROP VIEW IF EXISTS v_citas_detalle CASCADE;
DROP VIEW IF EXISTS v_indicadores_citas CASCADE;
DROP VIEW IF EXISTS v_ocupacion_policlinico CASCADE;
DROP VIEW IF EXISTS v_pendientes_confirmacion CASCADE;
DROP VIEW IF EXISTS v_resumen_lista_espera CASCADE;
DROP VIEW IF EXISTS v_encuestas_resumen CASCADE;
DROP VIEW IF EXISTS v_auditoria_reciente CASCADE;

DROP TABLE IF EXISTS auditoria_operaciones CASCADE;
DROP TABLE IF EXISTS encuestas CASCADE;
DROP TABLE IF EXISTS notificaciones_log CASCADE;
DROP TABLE IF EXISTS registros_seguimiento CASCADE;
DROP TABLE IF EXISTS lista_espera CASCADE;
DROP TABLE IF EXISTS citas CASCADE;
DROP TABLE IF EXISTS bloques_horarios CASCADE;
DROP TABLE IF EXISTS ordenes_medicas CASCADE;
DROP TABLE IF EXISTS responsables CASCADE;
DROP TABLE IF EXISTS pacientes CASCADE;
DROP TABLE IF EXISTS usuarios_sistema CASCADE;
DROP TABLE IF EXISTS profesionales CASCADE;
DROP TABLE IF EXISTS especialidades CASCADE;
DROP TABLE IF EXISTS policlinicos CASCADE;

-- 1. Catálogo de Policlínicos (6 presenciales + Telemedicina como 7.º policlínico lógico)
CREATE TABLE policlinicos (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) NOT NULL UNIQUE,
    nombre          VARCHAR(120) NOT NULL,
    modalidad       VARCHAR(20) NOT NULL CHECK (modalidad IN ('PRESENCIAL', 'TELEMEDICINA')),
    direccion       VARCHAR(200) NOT NULL,
    telefono        VARCHAR(30) NOT NULL,
    activo          BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2. Especialidades / Prestaciones administrativas
CREATE TABLE especialidades (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL UNIQUE,
    duracion_min    INTEGER NOT NULL DEFAULT 30 CHECK (duracion_min > 0),
    permite_telemed BOOLEAN NOT NULL DEFAULT FALSE,
    activa          BOOLEAN NOT NULL DEFAULT TRUE
);

-- 3. Profesionales
CREATE TABLE profesionales (
    id               SERIAL PRIMARY KEY,
    rut              VARCHAR(15) NOT NULL UNIQUE,
    nombre_completo  VARCHAR(150) NOT NULL,
    especialidad_id  INTEGER NOT NULL REFERENCES especialidades(id),
    policlinico_id   INTEGER NOT NULL REFERENCES policlinicos(id),
    activo           BOOLEAN NOT NULL DEFAULT TRUE
);

-- 4. Usuarios del sistema (RBAC: TENS_TONS, TELEMEDICINA, ADMINISTRACION)
CREATE TABLE usuarios_sistema (
    id               SERIAL PRIMARY KEY,
    username         VARCHAR(50) NOT NULL UNIQUE,
    nombre_completo  VARCHAR(120) NOT NULL,
    rol              VARCHAR(20) NOT NULL CHECK (rol IN ('TENS_TONS', 'TELEMEDICINA', 'ADMINISTRACION')),
    policlinico_id   INTEGER REFERENCES policlinicos(id),
    clave_demo       VARCHAR(120) NOT NULL, -- Solo para demo local con datos ficticios
    activo           BOOLEAN NOT NULL DEFAULT TRUE
);

-- 5. Ficha administrativa única de Pacientes (RF01, RF18 sin historia clínica)
CREATE TABLE pacientes (
    id                  SERIAL PRIMARY KEY,
    rut                 VARCHAR(15) NOT NULL UNIQUE,
    nombre_completo     VARCHAR(150) NOT NULL,
    telefono            VARCHAR(30) NOT NULL,
    correo              VARCHAR(120),
    prevision           VARCHAR(40) NOT NULL DEFAULT 'FONASA',
    cesfam_origen       VARCHAR(120),
    estado_doc_fonasa   VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE'
                        CHECK (estado_doc_fonasa IN ('PENDIENTE', 'EN_REVISION', 'VALIDADO', 'OBSERVADO')),
    consentimiento_datos BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. Adultos responsables / tutores (RF02)
CREATE TABLE responsables (
    id               SERIAL PRIMARY KEY,
    paciente_id      INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    nombre_completo  VARCHAR(150) NOT NULL,
    parentesco       VARCHAR(50) NOT NULL,
    telefono         VARCHAR(30) NOT NULL
);

-- 7. Órdenes médicas plurisesión (RF17 - solo control administrativo de saldo)
CREATE TABLE ordenes_medicas (
    id                  SERIAL PRIMARY KEY,
    paciente_id         INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    especialidad_id     INTEGER NOT NULL REFERENCES especialidades(id),
    sesiones_totales    INTEGER NOT NULL CHECK (sesiones_totales > 0),
    sesiones_usadas     INTEGER NOT NULL DEFAULT 0 CHECK (sesiones_usadas >= 0),
    estado_validacion   VARCHAR(30) NOT NULL DEFAULT 'VALIDADO'
                        CHECK (estado_validacion IN ('PENDIENTE', 'VALIDADO', 'RECHAZADO')),
    creada_en           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (sesiones_usadas <= sesiones_totales)
);

-- 8. Bloques horarios / Cupos (M3: RF03, RF12, RF13)
CREATE TABLE bloques_horarios (
    id               SERIAL PRIMARY KEY,
    policlinico_id   INTEGER NOT NULL REFERENCES policlinicos(id),
    especialidad_id  INTEGER NOT NULL REFERENCES especialidades(id),
    profesional_id   INTEGER NOT NULL REFERENCES profesionales(id),
    fecha            DATE NOT NULL,
    hora_inicio      TIME NOT NULL,
    hora_fin         TIME NOT NULL,
    estado_bloque    VARCHAR(20) NOT NULL DEFAULT 'DISPONIBLE'
                     CHECK (estado_bloque IN ('DISPONIBLE', 'OCUPADO', 'BLOQUEADO', 'OCULTO')),
    publicado        BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (profesional_id, fecha, hora_inicio)
);

-- 9. Citas administrativas (M4: RF04, RF05, RF09, RF11, RF14, RF15, RF28 sin código de reserva)
CREATE TABLE citas (
    id                    SERIAL PRIMARY KEY,
    paciente_id           INTEGER NOT NULL REFERENCES pacientes(id),
    bloque_id             INTEGER NOT NULL REFERENCES bloques_horarios(id),
    orden_medica_id       INTEGER REFERENCES ordenes_medicas(id),
    estado_cita           VARCHAR(20) NOT NULL DEFAULT 'RESERVADA'
                          CHECK (estado_cita IN ('RESERVADA', 'ASISTIDA', 'INASISTIDA', 'CANCELADA')),
    -- RF09: Estado de confirmación separado del estado de la cita ("el silencio no cancela")
    estado_confirmacion   VARCHAR(25) NOT NULL DEFAULT 'PENDIENTE'
                          CHECK (estado_confirmacion IN ('PENDIENTE', 'CONFIRMADA', 'SIN_RESPUESTA', 'RECHAZADA')),
    canal_registro        VARCHAR(25) NOT NULL DEFAULT 'ASISTIDO_PRESENCIAL'
                          CHECK (canal_registro IN ('ASISTIDO_PRESENCIAL', 'ASISTIDO_TELEFONO', 'SOLICITUD_WEB')),
    origen_cancelacion    VARCHAR(30)
                          CHECK (origen_cancelacion IN ('WHATSAPP_PACIENTE', 'ASISTIDA_TENS', 'CAMBIO_AGENDA')),
    motivo_cancelacion    VARCHAR(250),
    creado_por_usuario_id INTEGER REFERENCES usuarios_sistema(id),
    creada_en             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizada_en        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- RNF04: Índice único parcial que garantiza 0 % dobles reservas activas en un mismo bloque horario
CREATE UNIQUE INDEX ux_cita_bloque_activa
    ON citas (bloque_id)
    WHERE estado_cita IN ('RESERVADA', 'ASISTIDA');

-- 10. Registro de seguimiento telefónico/presencial por TENS/TONS (RF10, RF27)
CREATE TABLE registros_seguimiento (
    id               SERIAL PRIMARY KEY,
    cita_id          INTEGER NOT NULL REFERENCES citas(id) ON DELETE CASCADE,
    usuario_id       INTEGER REFERENCES usuarios_sistema(id),
    canal            VARCHAR(25) NOT NULL CHECK (canal IN ('TELEFONO', 'PRESENCIAL', 'WHATSAPP', 'CORREO')),
    resultado        VARCHAR(40) NOT NULL
                     CHECK (resultado IN ('CONFIRMADA', 'NO_CONTESTA', 'REAGENDAR', 'CANCELADA', 'AVISO_ENVIADO')),
    observacion      VARCHAR(300),
    registrado_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 11. Lista de espera asistida (RF06, RF35 - gestión manual por TENS/TONS)
CREATE TABLE lista_espera (
    id               SERIAL PRIMARY KEY,
    paciente_id      INTEGER NOT NULL REFERENCES pacientes(id),
    policlinico_id   INTEGER NOT NULL REFERENCES policlinicos(id),
    especialidad_id  INTEGER NOT NULL REFERENCES especialidades(id),
    prioridad        VARCHAR(20) NOT NULL DEFAULT 'NORMAL'
                     CHECK (prioridad IN ('ALTA', 'MEDIA', 'NORMAL')),
    estado           VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
                     CHECK (estado IN ('PENDIENTE', 'CONTACTADO', 'AGENDADO', 'DESCARTADO')),
    observacion      VARCHAR(300),
    creado_por_id    INTEGER REFERENCES usuarios_sistema(id),
    creada_en        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 12. Bitácora de notificaciones externas desacopladas (RF07, RF08, RF28, RF30)
CREATE TABLE notificaciones_log (
    id               SERIAL PRIMARY KEY,
    cita_id          INTEGER REFERENCES citas(id) ON DELETE SET NULL,
    canal            VARCHAR(20) NOT NULL CHECK (canal IN ('WHATSAPP', 'CORREO')),
    tipo_mensaje     VARCHAR(35) NOT NULL
                     CHECK (tipo_mensaje IN ('COMPROBANTE', 'RECORDATORIO_7D', 'RECORDATORIO_24H', 'ENCUESTA_WEB', 'ENCUESTA_POST_ATENCION', 'CAMBIO_AGENDA')),
    destinatario     VARCHAR(120) NOT NULL,
    estado_envio     VARCHAR(25) NOT NULL CHECK (estado_envio IN ('ENVIADO_SIMULADO', 'FALLO_ALERTA_OPERATIVA')),
    detalle          VARCHAR(300),
    enviado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 13. Encuestas diferenciadas (RF30 post-atención y RF36 experiencia agendamiento)
CREATE TABLE encuestas (
    id               SERIAL PRIMARY KEY,
    cita_id          INTEGER REFERENCES citas(id) ON DELETE SET NULL,
    tipo             VARCHAR(25) NOT NULL CHECK (tipo IN ('AGENDAMIENTO_WEB', 'POST_ATENCION')),
    puntaje          INTEGER NOT NULL CHECK (puntaje BETWEEN 1 AND 5),
    comentario       VARCHAR(300),
    registrada_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 14. Auditoría administrativa inmutable (RF16, RF34, RNF06)
CREATE TABLE auditoria_operaciones (
    id               SERIAL PRIMARY KEY,
    usuario_nombre   VARCHAR(120) NOT NULL,
    rol              VARCHAR(30) NOT NULL,
    policlinico_id   INTEGER REFERENCES policlinicos(id),
    operacion        VARCHAR(80) NOT NULL,
    entidad          VARCHAR(50) NOT NULL,
    entidad_id       INTEGER,
    detalle          VARCHAR(400) NOT NULL,
    registrado_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 7 VISTAS SQL ANALÍTICAS (M8 Reportería en solo lectura: RF19–RF23)
-- ============================================================================

CREATE VIEW v_citas_detalle AS
SELECT
    c.id AS cita_id,
    c.estado_cita,
    c.estado_confirmacion,
    c.canal_registro,
    c.origen_cancelacion,
    c.motivo_cancelacion,
    c.creada_en,
    p.id AS paciente_id,
    p.rut AS paciente_rut,
    p.nombre_completo AS paciente_nombre,
    p.telefono AS paciente_telefono,
    p.prevision,
    p.estado_doc_fonasa,
    b.id AS bloque_id,
    b.fecha,
    b.hora_inicio,
    b.hora_fin,
    pol.id AS policlinico_id,
    pol.nombre AS policlinico_nombre,
    pol.modalidad,
    e.id AS especialidad_id,
    e.nombre AS especialidad_nombre,
    prof.id AS profesional_id,
    prof.nombre_completo AS profesional_nombre
FROM citas c
JOIN pacientes p ON p.id = c.paciente_id
JOIN bloques_horarios b ON b.id = c.bloque_id
JOIN policlinicos pol ON pol.id = b.policlinico_id
JOIN especialidades e ON e.id = b.especialidad_id
JOIN profesionales prof ON prof.id = b.profesional_id;

CREATE VIEW v_indicadores_citas AS
SELECT
    pol.id AS policlinico_id,
    pol.nombre AS policlinico_nombre,
    pol.modalidad,
    COUNT(c.id) AS total_citas,
    COUNT(c.id) FILTER (WHERE c.estado_cita = 'RESERVADA') AS reservadas,
    COUNT(c.id) FILTER (WHERE c.estado_cita = 'ASISTIDA') AS asistidas,
    COUNT(c.id) FILTER (WHERE c.estado_cita = 'INASISTIDA') AS inasistidas,
    COUNT(c.id) FILTER (WHERE c.estado_cita = 'CANCELADA') AS canceladas,
    COUNT(c.id) FILTER (WHERE c.estado_cita = 'RESERVADA' AND c.estado_confirmacion IN ('PENDIENTE', 'SIN_RESPUESTA')) AS pendientes_confirmacion,
    CASE
        WHEN COUNT(c.id) FILTER (WHERE c.estado_cita IN ('ASISTIDA', 'INASISTIDA')) > 0
        THEN ROUND(
            100.0 * COUNT(c.id) FILTER (WHERE c.estado_cita = 'ASISTIDA') /
            COUNT(c.id) FILTER (WHERE c.estado_cita IN ('ASISTIDA', 'INASISTIDA')), 1
        )
        ELSE 0
    END AS tasa_asistencia_pct
FROM policlinicos pol
LEFT JOIN bloques_horarios b ON b.policlinico_id = pol.id
LEFT JOIN citas c ON c.bloque_id = b.id
GROUP BY pol.id, pol.nombre, pol.modalidad
ORDER BY pol.id;

CREATE VIEW v_ocupacion_policlinico AS
SELECT
    pol.id AS policlinico_id,
    pol.nombre AS policlinico_nombre,
    COUNT(b.id) AS bloques_totales,
    COUNT(b.id) FILTER (WHERE b.estado_bloque = 'DISPONIBLE' AND b.publicado) AS bloques_disponibles,
    COUNT(b.id) FILTER (WHERE b.estado_bloque = 'OCUPADO') AS bloques_ocupados,
    COUNT(b.id) FILTER (WHERE b.estado_bloque = 'BLOQUEADO') AS bloques_bloqueados,
    CASE
        WHEN COUNT(b.id) FILTER (WHERE b.estado_bloque IN ('DISPONIBLE', 'OCUPADO')) > 0
        THEN ROUND(
            100.0 * COUNT(b.id) FILTER (WHERE b.estado_bloque = 'OCUPADO') /
            COUNT(b.id) FILTER (WHERE b.estado_bloque IN ('DISPONIBLE', 'OCUPADO')), 1
        )
        ELSE 0
    END AS ocupacion_pct
FROM policlinicos pol
LEFT JOIN bloques_horarios b ON b.policlinico_id = pol.id
GROUP BY pol.id, pol.nombre
ORDER BY pol.id;

CREATE VIEW v_pendientes_confirmacion AS
SELECT
    cita_id,
    paciente_rut,
    paciente_nombre,
    paciente_telefono,
    policlinico_id,
    policlinico_nombre,
    especialidad_nombre,
    profesional_nombre,
    fecha,
    hora_inicio,
    estado_cita,
    estado_confirmacion
FROM v_citas_detalle
WHERE estado_cita = 'RESERVADA'
  AND estado_confirmacion IN ('PENDIENTE', 'SIN_RESPUESTA')
ORDER BY fecha, hora_inicio;

CREATE VIEW v_resumen_lista_espera AS
SELECT
    pol.nombre AS policlinico_nombre,
    e.nombre AS especialidad_nombre,
    COUNT(le.id) FILTER (WHERE le.estado = 'PENDIENTE') AS pendientes,
    COUNT(le.id) FILTER (WHERE le.estado = 'CONTACTADO') AS contactados,
    COUNT(le.id) FILTER (WHERE le.estado = 'AGENDADO') AS agendados
FROM lista_espera le
JOIN policlinicos pol ON pol.id = le.policlinico_id
JOIN especialidades e ON e.id = le.especialidad_id
GROUP BY pol.nombre, e.nombre;

CREATE VIEW v_encuestas_resumen AS
SELECT
    tipo,
    COUNT(*) AS total_respuestas,
    ROUND(AVG(puntaje), 2) AS promedio_puntaje
FROM encuestas
GROUP BY tipo;

CREATE VIEW v_auditoria_reciente AS
SELECT
    a.id,
    a.registrado_en,
    a.usuario_nombre,
    a.rol,
    COALESCE(pol.nombre, 'Todas las sedes') AS policlinico_nombre,
    a.operacion,
    a.entidad,
    a.entidad_id,
    a.detalle
FROM auditoria_operaciones a
LEFT JOIN policlinicos pol ON pol.id = a.policlinico_id
ORDER BY a.registrado_en DESC, a.id DESC;
