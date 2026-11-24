-- ============================================================================
-- 06 · SEED HISTÓRICO FICTICIO — SOLO PARA LA DEMO DE GRÁFICOS (opcional)
-- ----------------------------------------------------------------------------
-- NO ejecutar en un ambiente real. Datos 100 % ficticios: pacientes con la palabra «Demo»,
-- RUT válidos (módulo 11) del rango 9.000.001+, sin relación con personas reales.
-- Requiere: 01..04 y 05_vista_reportes.sql. Se puede ejecutar varias veces:
-- cada corrida BORRA SOLO lo que insertó la anterior (registrado en seed_historico_graficos)
-- y lo vuelve a generar (setseed fija el azar: mismo resultado en cada corrida).
--
-- Genera (días hábiles, 08:00–19:00, las 7 sedes y todos los profesionales activos):
--   · citas de los últimos 6 meses: ~70 % ASISTIDA, ~12 % INASISTIDA, ~15 % CANCELADA y ~3 % RESERVADA futura.
--   · bloques del pasado OCUPADO (o OCULTO si la cita se canceló) para que NO aparezcan como disponibles
--     en el agendamiento. Por eso la ocupación de los períodos pasados marca ~100 %; los bloques futuros
--     (próximas 2 semanas) sí quedan en parte DISPONIBLES.
--   · 60 pacientes ficticios con edades y nacionalidades variadas.
--   · encuestas POST_ATENCION para ~40 % de las citas asistidas (y algunas de AGENDAMIENTO_WEB).
-- ============================================================================

SELECT setseed(0.42);

CREATE TABLE IF NOT EXISTS seed_historico_graficos (
    entidad     VARCHAR(20) NOT NULL,
    registro_id INTEGER NOT NULL,
    PRIMARY KEY (entidad, registro_id)
);

-- 0. Limpieza de la corrida anterior (solo filas registradas por este script)
DELETE FROM encuestas WHERE id IN (SELECT registro_id FROM seed_historico_graficos WHERE entidad = 'encuestas');
DELETE FROM citas WHERE id IN (SELECT registro_id FROM seed_historico_graficos WHERE entidad = 'citas');
DELETE FROM bloques_horarios WHERE id IN (SELECT registro_id FROM seed_historico_graficos WHERE entidad = 'bloques');
DELETE FROM pacientes WHERE id IN (SELECT registro_id FROM seed_historico_graficos WHERE entidad = 'pacientes');
DELETE FROM seed_historico_graficos;

-- Dígito verificador chileno (módulo 11)
CREATE OR REPLACE FUNCTION pg_temp.dv_rut(cuerpo INT) RETURNS TEXT AS $$
DECLARE s INT := 0; m INT := 2; n INT := cuerpo; r INT;
BEGIN
    WHILE n > 0 LOOP
        s := s + (n % 10) * m;
        m := CASE WHEN m = 7 THEN 2 ELSE m + 1 END;
        n := n / 10;
    END LOOP;
    r := 11 - (s % 11);
    RETURN CASE r WHEN 11 THEN '0' WHEN 10 THEN 'K' ELSE r::TEXT END;
END;
$$ LANGUAGE plpgsql;

DROP TABLE IF EXISTS _pac_ins, _slots, _bloques_ins;

-- 1. Pacientes ficticios
CREATE TEMP TABLE _pac_ins (n INT, id INT);
WITH nuevos AS (
    INSERT INTO pacientes (rut, nombre_completo, telefono, correo, prevision, cesfam_origen, estado_doc_fonasa,
                           consentimiento_datos, fecha_nacimiento, nacionalidad)
    SELECT replace(to_char(9000000 + g, 'FM9,999,999'), ',', '.') || '-' || pg_temp.dv_rut(9000000 + g),
           'Paciente Demo Histórico ' || lpad(g::TEXT, 3, '0'),
           '+56 9 5900 ' || lpad(g::TEXT, 4, '0'),
           NULL, 'FONASA A', NULL, 'PENDIENTE', TRUE,
           CURRENT_DATE - ((1 + random() * 88) * 365)::INT,
           CASE WHEN r < 0.70 THEN 'Chilena' WHEN r < 0.80 THEN 'Venezolana' WHEN r < 0.86 THEN 'Peruana'
                WHEN r < 0.91 THEN 'Colombiana' WHEN r < 0.95 THEN 'Haitiana' WHEN r < 0.98 THEN 'Boliviana' ELSE 'Argentina' END
    FROM (SELECT g, random() AS r FROM generate_series(1, 60) g) q
    RETURNING id, rut
)
INSERT INTO _pac_ins SELECT row_number() OVER (ORDER BY id), id FROM nuevos;
INSERT INTO seed_historico_graficos SELECT 'pacientes', id FROM _pac_ins;

-- 2. Bloques candidatos: días hábiles de los últimos 6 meses y las próximas 2 semanas (hoy se omite)
CREATE TEMP TABLE _slots AS
SELECT pr.id AS prof_id, pr.especialidad_id, pr.policlinico_id, d::DATE AS fecha,
       make_time(m / 60, m % 60, 0) AS hi,
       (make_time(m / 60, m % 60, 0) + (e.duracion_min || ' minutes')::INTERVAL)::TIME AS hf,
       random() AS r_uso, random() AS r_estado, random() AS r_conf, random() AS r_canal,
       random() AS r_pac, random() AS r_ant, random() AS r_hora
FROM profesionales pr
JOIN especialidades e ON e.id = pr.especialidad_id
CROSS JOIN generate_series(CURRENT_DATE - 180, CURRENT_DATE + 14, INTERVAL '1 day') d
CROSS JOIN generate_series(8 * 60, 19 * 60, 30) m
WHERE pr.activo
  AND EXTRACT(ISODOW FROM d) < 6
  AND d::DATE <> CURRENT_DATE
  AND (m / 60) BETWEEN 8 AND 19
  AND random() < 0.095
  AND NOT EXISTS (SELECT 1 FROM bloques_horarios b WHERE b.profesional_id = pr.id AND b.fecha = d::DATE AND b.hora_inicio = make_time(m / 60, m % 60, 0));

CREATE TEMP TABLE _bloques_ins (id INT, prof_id INT, fecha DATE, hi TIME);
WITH ins AS (
    INSERT INTO bloques_horarios (policlinico_id, especialidad_id, profesional_id, fecha, hora_inicio, hora_fin, estado_bloque, publicado)
    SELECT policlinico_id, especialidad_id, prof_id, fecha, hi, hf,
           CASE
               WHEN fecha < CURRENT_DATE AND r_estado >= 0.86 THEN 'OCULTO'           -- cita cancelada
               WHEN fecha < CURRENT_DATE THEN 'OCUPADO'                               -- asistida / inasistida
               WHEN r_uso < 0.20 THEN 'OCUPADO'                                       -- futura con cita RESERVADA
               ELSE 'DISPONIBLE'
           END,
           TRUE
    FROM _slots
    RETURNING id, profesional_id, fecha, hora_inicio
)
INSERT INTO _bloques_ins SELECT * FROM ins;
INSERT INTO seed_historico_graficos SELECT 'bloques', id FROM _bloques_ins;

-- 3. Citas (una por bloque OCUPADO/OCULTO generado)
INSERT INTO citas (paciente_id, bloque_id, estado_cita, estado_confirmacion, canal_registro, origen_cancelacion,
                   motivo_cancelacion, creada_en, actualizada_en)
SELECT p.id, bi.id,
       CASE WHEN s.fecha >= CURRENT_DATE THEN 'RESERVADA'
            WHEN s.r_estado < 0.74 THEN 'ASISTIDA' WHEN s.r_estado < 0.86 THEN 'INASISTIDA' ELSE 'CANCELADA' END,
       CASE WHEN s.fecha >= CURRENT_DATE THEN (CASE WHEN s.r_conf < 0.4 THEN 'CONFIRMADA' ELSE 'PENDIENTE' END)
            WHEN s.r_estado < 0.74 THEN (CASE WHEN s.r_conf < 0.80 THEN 'CONFIRMADA' WHEN s.r_conf < 0.92 THEN 'SIN_RESPUESTA' ELSE 'PENDIENTE' END)
            WHEN s.r_estado < 0.86 THEN (CASE WHEN s.r_conf < 0.35 THEN 'CONFIRMADA' WHEN s.r_conf < 0.85 THEN 'SIN_RESPUESTA' ELSE 'PENDIENTE' END)
            ELSE 'RECHAZADA' END,
       CASE WHEN s.r_canal < 0.55 THEN 'ASISTIDO_PRESENCIAL' WHEN s.r_canal < 0.80 THEN 'ASISTIDO_TELEFONO' ELSE 'SOLICITUD_WEB' END,
       CASE WHEN s.fecha < CURRENT_DATE AND s.r_estado >= 0.86
            THEN (CASE WHEN s.r_conf < 0.55 THEN 'WHATSAPP_PACIENTE' WHEN s.r_conf < 0.85 THEN 'ASISTIDA_TENS' ELSE 'CAMBIO_AGENDA' END) END,
       CASE WHEN s.fecha < CURRENT_DATE AND s.r_estado >= 0.86 THEN 'Cancelación (dato ficticio de demostración)' END,
       LEAST(((s.fecha - (1 + floor(s.r_ant * 20))::INT)::TIMESTAMP + INTERVAL '8 hours' + s.r_hora * INTERVAL '10 hours'), now()::TIMESTAMP),
       LEAST(s.fecha::TIMESTAMP + s.hi, now()::TIMESTAMP)
FROM _slots s
JOIN _bloques_ins bi ON bi.prof_id = s.prof_id AND bi.fecha = s.fecha AND bi.hi = s.hi
JOIN _pac_ins p ON p.n = 1 + floor(s.r_pac * 60)::INT
WHERE s.fecha < CURRENT_DATE OR (s.fecha > CURRENT_DATE AND s.r_uso < 0.20);

INSERT INTO seed_historico_graficos
SELECT 'citas', c.id FROM citas c WHERE c.bloque_id IN (SELECT registro_id FROM seed_historico_graficos WHERE entidad = 'bloques');

-- 4. Encuestas: ~40 % de las citas asistidas (POST_ATENCION) y algunas del agendamiento web
INSERT INTO encuestas (cita_id, tipo, puntaje, comentario, registrada_en)
SELECT c.id, 'POST_ATENCION',
       CASE WHEN r < 0.50 THEN 5 WHEN r < 0.78 THEN 4 WHEN r < 0.90 THEN 3 WHEN r < 0.96 THEN 2 ELSE 1 END,
       NULL, (b.fecha + b.hora_inicio + INTERVAL '2 hours')::TIMESTAMP
FROM (SELECT c.*, random() AS r, random() AS sel FROM citas c) c
JOIN bloques_horarios b ON b.id = c.bloque_id
WHERE c.id IN (SELECT registro_id FROM seed_historico_graficos WHERE entidad = 'citas')
  AND c.estado_cita = 'ASISTIDA' AND c.sel < 0.40;

INSERT INTO encuestas (cita_id, tipo, puntaje, comentario, registrada_en)
SELECT c.id, 'AGENDAMIENTO_WEB', CASE WHEN r < 0.55 THEN 5 WHEN r < 0.85 THEN 4 ELSE 3 END, NULL, c.creada_en
FROM (SELECT c.*, random() AS r, random() AS sel FROM citas c) c
WHERE c.id IN (SELECT registro_id FROM seed_historico_graficos WHERE entidad = 'citas')
  AND c.canal_registro = 'SOLICITUD_WEB' AND c.sel < 0.30;

INSERT INTO seed_historico_graficos
SELECT 'encuestas', e.id FROM encuestas e
WHERE e.cita_id IN (SELECT registro_id FROM seed_historico_graficos WHERE entidad = 'citas');

DROP TABLE IF EXISTS _pac_ins, _slots, _bloques_ins;
