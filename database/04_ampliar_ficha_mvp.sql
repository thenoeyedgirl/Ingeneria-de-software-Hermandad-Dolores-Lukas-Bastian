-- ============================================================================
-- Actualización incremental de esquema — MVP Fase 1 (PostgreSQL 16 / 18)
-- Agrega:
--   1. fecha_nacimiento y nacionalidad en pacientes (caracterización RF21/RF22)
--   2. correo en responsables (contacto de tutor/apoderado RF02)
--   3. entidad documentos_respaldo conectada a pacientes (folio FONASA/CESFAM RF17)
-- Seguro de ejecutar sobre la base existente: NO borra ningún registro actual.
-- ============================================================================

-- 1. Ampliar tabla pacientes
ALTER TABLE pacientes
    ADD COLUMN IF NOT EXISTS fecha_nacimiento DATE,
    ADD COLUMN IF NOT EXISTS nacionalidad VARCHAR(60) NOT NULL DEFAULT 'Chilena';

-- 2. Ampliar tabla responsables (para contacto del tutor/apoderado)
ALTER TABLE responsables
    ADD COLUMN IF NOT EXISTS correo VARCHAR(120);

-- 3. Crear entidad documentos_respaldo vinculada a pacientes (folio FONASA / CESFAM)
CREATE TABLE IF NOT EXISTS documentos_respaldo (
    id               SERIAL PRIMARY KEY,
    paciente_id      INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    tipo_documento   VARCHAR(20) NOT NULL CHECK (tipo_documento IN ('FONASA', 'CESFAM', 'OTRO')),
    folio            VARCHAR(80) NOT NULL,
    estado_revision  VARCHAR(25) NOT NULL DEFAULT 'PENDIENTE'
                     CHECK (estado_revision IN ('PENDIENTE', 'EN_REVISION', 'VALIDADO', 'OBSERVADO')),
    registrado_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Completar fechas de nacimiento y nacionalidades ficticias en pacientes demo existentes
UPDATE pacientes SET fecha_nacimiento = DATE '1962-04-15', nacionalidad = 'Chilena'    WHERE rut = '14.567.890-0' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '1988-09-22', nacionalidad = 'Chilena'    WHERE rut = '19.876.543-0' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '1954-11-03', nacionalidad = 'Chilena'    WHERE rut = '13.246.810-9' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '2001-02-18', nacionalidad = 'Venezolana' WHERE rut = '20.111.222-2' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '1975-07-10', nacionalidad = 'Peruana'    WHERE rut = '10.203.040-0' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '1993-05-12', nacionalidad = 'Chilena'    WHERE rut = '11.222.333-9' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '1981-08-30', nacionalidad = 'Colombiana' WHERE rut = '12.444.555-8' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '1969-12-01', nacionalidad = 'Chilena'    WHERE rut = '13.555.666-1' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '2012-03-14', nacionalidad = 'Chilena'    WHERE rut = '14.666.777-5' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '1997-06-25', nacionalidad = 'Haitiana'   WHERE rut = '15.777.888-9' AND fecha_nacimiento IS NULL;
UPDATE pacientes SET fecha_nacimiento = DATE '1958-10-09', nacionalidad = 'Chilena'    WHERE rut = '16.888.999-2' AND fecha_nacimiento IS NULL;

-- 5. Folios demostrativos iniciales en documentos_respaldo (sin duplicar si ya existen)
INSERT INTO documentos_respaldo (paciente_id, tipo_documento, folio, estado_revision)
SELECT p.id, v.tipo, v.folio, v.est
FROM (VALUES
    ('14.567.890-0', 'FONASA', 'FON-2026-00145', 'VALIDADO'),
    ('13.246.810-9', 'CESFAM', 'CES-2026-00810', 'VALIDADO'),
    ('11.222.333-9', 'FONASA', 'FON-2026-00333', 'VALIDADO')
) AS v(rut, tipo, folio, est)
JOIN pacientes p ON p.rut = v.rut
WHERE NOT EXISTS (
    SELECT 1 FROM documentos_respaldo d WHERE d.paciente_id = p.id AND d.folio = v.folio
);
