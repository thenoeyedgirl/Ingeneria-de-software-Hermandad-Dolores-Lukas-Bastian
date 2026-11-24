-- ============================================================================
-- 05 · Vista de reportería v_reporte_citas (Gráficos y filtros · RF19–RF23, RNF03)
-- Requiere: 01_schema.sql y 04_ampliar_ficha_mvp.sql (fecha_nacimiento, nacionalidad).
-- Se puede ejecutar varias veces sin error (CREATE OR REPLACE VIEW). Solo lectura.
-- Expone únicamente DIMENSIONES: NO incluye rut, nombre, teléfono ni correo del paciente.
-- Tramos etarios = los mismos de obtener_reportes ('0–17 años','18–35 años','36–59 años','60+ años'),
-- con 'Sin dato' cuando no hay fecha de nacimiento.
-- ============================================================================

CREATE OR REPLACE VIEW v_reporte_citas AS
SELECT
    c.id                         AS cita_id,
    b.fecha                      AS fecha_cita,
    b.hora_inicio                AS hora_inicio,
    c.creada_en::date            AS fecha_solicitud,
    c.estado_cita,
    c.estado_confirmacion,
    c.canal_registro,
    c.origen_cancelacion,
    pol.id                       AS policlinico_id,
    pol.nombre                   AS policlinico_nombre,
    pol.modalidad,
    e.id                         AS especialidad_id,
    e.nombre                     AS especialidad_nombre,
    prof.id                      AS profesional_id,
    prof.nombre_completo         AS profesional_nombre,
    CASE
        WHEN p.fecha_nacimiento IS NULL THEN 'Sin dato'
        WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.fecha_nacimiento)) < 18 THEN '0–17 años'
        WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.fecha_nacimiento)) BETWEEN 18 AND 35 THEN '18–35 años'
        WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.fecha_nacimiento)) BETWEEN 36 AND 59 THEN '36–59 años'
        ELSE '60+ años'
    END                          AS tramo_etario,
    COALESCE(NULLIF(TRIM(p.nacionalidad), ''), 'Sin dato') AS nacionalidad,
    c.paciente_id                AS paciente_ref   -- identificador interno opaco (solo para contar pacientes únicos); no es dato personal
FROM citas c
JOIN pacientes p        ON p.id = c.paciente_id
JOIN bloques_horarios b ON b.id = c.bloque_id
JOIN policlinicos pol   ON pol.id = b.policlinico_id
JOIN especialidades e   ON e.id = b.especialidad_id
JOIN profesionales prof ON prof.id = b.profesional_id;
