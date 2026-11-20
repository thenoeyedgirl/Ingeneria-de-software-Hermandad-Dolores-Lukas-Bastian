-- ============================================================================
-- Semilla complementaria de DATOS 100 % FICTICIOS para los otros 5 policlínicos
-- (Sagrada Familia, María Ayuda, Santa Teresa, Padre Hurtado y Oratorio Mariano)
-- Seguro de ejecutar sobre la base existente: no toca San Isidro ni el RUT 12.345.678-5.
-- ============================================================================

-- 1. Cuentas TENS/TONS por policlínico (ignora si ya fueron insertadas)
INSERT INTO usuarios_sistema (username, nombre_completo, rol, policlinico_id, clave_demo) VALUES
('tens.sagradafamilia', 'Carolina Morales (TENS Sagrada Familia)', 'TENS_TONS', 2, 'demo123'),
('tens.mariaayuda', 'Rodrigo Alarcón (TENS María Ayuda)', 'TENS_TONS', 3, 'demo123'),
('tens.santateresa', 'Marcela Pinto (TENS Santa Teresa)', 'TENS_TONS', 4, 'demo123'),
('tens.padrehurtado', 'Cristián Navarro (TENS Padre Hurtado)', 'TENS_TONS', 5, 'demo123'),
('tens.oratoriomariano', 'Verónica Cáceres (TENS Oratorio Mariano)', 'TENS_TONS', 6, 'demo123')
ON CONFLICT (username) DO NOTHING;

-- 2. Profesionales ficticios adicionales para cubrir los 6 policlínicos presenciales
INSERT INTO profesionales (rut, nombre_completo, especialidad_id, policlinico_id) VALUES
('13.111.222-K', 'Dra. Daniela Araya Castro (Demo)', 1, 5),       -- Padre Hurtado · Medicina General
('14.222.333-3', 'Klgo. Ignacio Vera Palma (Demo)', 2, 6),        -- Oratorio Mariano · Kinesiología
('15.333.444-7', 'Dra. Beatriz Riquelme Tapia (Demo)', 1, 2),     -- Sagrada Familia · Medicina General
('16.444.555-0', 'Ps. Alejandro Espinoza Flores (Demo)', 3, 3)    -- María Ayuda · Psicología
ON CONFLICT (rut) DO NOTHING;

-- 3. Pacientes 100 % ficticios adicionales (RUTs válidos módulo 11, distintos a los existentes)
INSERT INTO pacientes (rut, nombre_completo, telefono, correo, prevision, cesfam_origen, estado_doc_fonasa) VALUES
('11.222.333-9', 'Elena Patricia Vargas Demo', '+56 9 5200 0001', 'elena.demo@ejemplo.cl', 'FONASA A', 'CESFAM Sagrada Familia Demo', 'VALIDADO'),
('12.444.555-8', 'Roberto Andrés Campos Demo', '+56 9 5200 0002', 'roberto.demo@ejemplo.cl', 'FONASA B', 'CESFAM María Ayuda Demo', 'EN_REVISION'),
('13.555.666-1', 'Patricia Soledad Riquelme Demo', '+56 9 5200 0003', 'patricia.demo@ejemplo.cl', 'FONASA A', 'CESFAM Santa Teresa Demo', 'VALIDADO'),
('14.666.777-5', 'Héctor Mauricio Tapia Demo', '+56 9 5200 0004', 'hector.demo@ejemplo.cl', 'FONASA C', 'CESFAM Padre Hurtado Demo', 'PENDIENTE'),
('15.777.888-9', 'Lucía Fernanda Figueroa Demo', '+56 9 5200 0005', 'lucia.demo@ejemplo.cl', 'FONASA B', 'CESFAM Oratorio Demo', 'VALIDADO'),
('16.888.999-2', 'Jorge Eduardo Salinas Demo', '+56 9 5200 0006', 'jorge.demo@ejemplo.cl', 'FONASA A', 'CESFAM Surponiente Demo', 'VALIDADO')
ON CONFLICT (rut) DO NOTHING;

-- 4. Bloques horarios disponibles y ocupados para los 5 policlínicos
--    (Sagrada Familia=2, María Ayuda=3, Santa Teresa=4, Padre Hurtado=5, Oratorio Mariano=6)
INSERT INTO bloques_horarios (policlinico_id, especialidad_id, profesional_id, fecha, hora_inicio, hora_fin, estado_bloque, publicado)
VALUES
-- Sagrada Familia (policlinico_id = 2)
(2, 4, (SELECT id FROM profesionales WHERE rut = '15.234.567-4'), CURRENT_DATE + 1, '09:30', '10:00', 'OCUPADO', TRUE),
(2, 4, (SELECT id FROM profesionales WHERE rut = '15.234.567-4'), CURRENT_DATE + 1, '10:00', '10:30', 'DISPONIBLE', TRUE),
(2, 1, (SELECT id FROM profesionales WHERE rut = '15.333.444-7'), CURRENT_DATE + 2, '10:30', '11:00', 'DISPONIBLE', TRUE),
(2, 1, (SELECT id FROM profesionales WHERE rut = '15.333.444-7'), CURRENT_DATE + 2, '11:00', '11:30', 'DISPONIBLE', TRUE),

-- María Ayuda (policlinico_id = 3)
(3, 5, (SELECT id FROM profesionales WHERE rut = '16.345.678-8'), CURRENT_DATE + 1, '10:00', '10:30', 'OCUPADO', TRUE),
(3, 5, (SELECT id FROM profesionales WHERE rut = '16.345.678-8'), CURRENT_DATE + 1, '10:30', '11:00', 'DISPONIBLE', TRUE),
(3, 3, (SELECT id FROM profesionales WHERE rut = '16.444.555-0'), CURRENT_DATE + 2, '15:00', '15:45', 'DISPONIBLE', TRUE),
(3, 3, (SELECT id FROM profesionales WHERE rut = '16.444.555-0'), CURRENT_DATE + 2, '15:45', '16:30', 'DISPONIBLE', TRUE),

-- Santa Teresa (policlinico_id = 4)
(4, 6, (SELECT id FROM profesionales WHERE rut = '18.567.890-3'), CURRENT_DATE + 1, '09:00', '09:45', 'OCUPADO', TRUE),
(4, 6, (SELECT id FROM profesionales WHERE rut = '18.567.890-3'), CURRENT_DATE + 1, '09:45', '10:30', 'DISPONIBLE', TRUE),
(4, 6, (SELECT id FROM profesionales WHERE rut = '18.567.890-3'), CURRENT_DATE + 2, '10:00', '10:45', 'DISPONIBLE', TRUE),

-- Padre Hurtado (policlinico_id = 5)
(5, 1, (SELECT id FROM profesionales WHERE rut = '13.111.222-K'), CURRENT_DATE + 1, '09:00', '09:30', 'OCUPADO', TRUE),
(5, 1, (SELECT id FROM profesionales WHERE rut = '13.111.222-K'), CURRENT_DATE + 1, '09:30', '10:00', 'DISPONIBLE', TRUE),
(5, 1, (SELECT id FROM profesionales WHERE rut = '13.111.222-K'), CURRENT_DATE + 1, '10:00', '10:30', 'DISPONIBLE', TRUE),
(5, 1, (SELECT id FROM profesionales WHERE rut = '13.111.222-K'), CURRENT_DATE - 1, '09:30', '10:00', 'OCUPADO', TRUE),

-- Oratorio Mariano (policlinico_id = 6)
(6, 2, (SELECT id FROM profesionales WHERE rut = '14.222.333-3'), CURRENT_DATE + 1, '11:00', '11:45', 'OCUPADO', TRUE),
(6, 2, (SELECT id FROM profesionales WHERE rut = '14.222.333-3'), CURRENT_DATE + 1, '11:45', '12:30', 'DISPONIBLE', TRUE),
(6, 2, (SELECT id FROM profesionales WHERE rut = '14.222.333-3'), CURRENT_DATE + 2, '09:00', '09:45', 'DISPONIBLE', TRUE),
(6, 2, (SELECT id FROM profesionales WHERE rut = '14.222.333-3'), CURRENT_DATE - 1, '11:00', '11:45', 'OCUPADO', TRUE)
ON CONFLICT (profesional_id, fecha, hora_inicio) DO NOTHING;

-- 5. Citas ficticias (activas pendientes de confirmación, confirmadas y cerradas)
INSERT INTO citas (paciente_id, bloque_id, estado_cita, estado_confirmacion, canal_registro, creado_por_usuario_id)
SELECT p.id, b.id, v.est_cita, v.est_conf, v.canal, u.id
FROM (VALUES
    ('11.222.333-9', '15.234.567-4', CURRENT_DATE + 1, TIME '09:30', 'RESERVADA', 'PENDIENTE',     'ASISTIDO_PRESENCIAL', 'tens.sagradafamilia'),
    ('12.444.555-8', '16.345.678-8', CURRENT_DATE + 1, TIME '10:00', 'RESERVADA', 'SIN_RESPUESTA', 'ASISTIDO_TELEFONO',   'tens.mariaayuda'),
    ('13.555.666-1', '18.567.890-3', CURRENT_DATE + 1, TIME '09:00', 'RESERVADA', 'CONFIRMADA',    'ASISTIDO_PRESENCIAL', 'tens.santateresa'),
    ('14.666.777-5', '13.111.222-K', CURRENT_DATE + 1, TIME '09:00', 'RESERVADA', 'PENDIENTE',     'ASISTIDO_TELEFONO',   'tens.padrehurtado'),
    ('16.888.999-2', '13.111.222-K', CURRENT_DATE - 1, TIME '09:30', 'ASISTIDA',  'CONFIRMADA',    'ASISTIDO_PRESENCIAL', 'tens.padrehurtado'),
    ('15.777.888-9', '14.222.333-3', CURRENT_DATE + 1, TIME '11:00', 'RESERVADA', 'SIN_RESPUESTA', 'ASISTIDO_PRESENCIAL', 'tens.oratoriomariano'),
    ('11.222.333-9', '14.222.333-3', CURRENT_DATE - 1, TIME '11:00', 'ASISTIDA',  'CONFIRMADA',    'ASISTIDO_PRESENCIAL', 'tens.oratoriomariano')
) AS v(pac_rut, prof_rut, f_bloque, h_ini, est_cita, est_conf, canal, usr)
JOIN pacientes p ON p.rut = v.pac_rut
JOIN profesionales pr ON pr.rut = v.prof_rut
JOIN bloques_horarios b ON b.profesional_id = pr.id AND b.fecha = v.f_bloque AND b.hora_inicio = v.h_ini
LEFT JOIN usuarios_sistema u ON u.username = v.usr
WHERE NOT EXISTS (
    SELECT 1 FROM citas c WHERE c.bloque_id = b.id AND c.estado_cita IN ('RESERVADA', 'ASISTIDA')
);

-- 6. Solicitudes en lista de espera asistida para los 5 policlínicos
INSERT INTO lista_espera (paciente_id, policlinico_id, especialidad_id, prioridad, estado, observacion, creado_por_id)
SELECT p.id, v.pol_id, v.esp_id, v.prio, v.est, v.obs, u.id
FROM (VALUES
    ('16.888.999-2', 2, 4, 'ALTA',   'PENDIENTE',  'Solicita control odontológico en horario mañana.',      'tens.sagradafamilia'),
    ('11.222.333-9', 3, 3, 'MEDIA',  'PENDIENTE',  'Prefiere atención psicológica por la tarde.',           'tens.mariaayuda'),
    ('12.444.555-8', 4, 6, 'NORMAL', 'CONTACTADO', 'Se llamó por teléfono; confirma disponibilidad mañana.', 'tens.santateresa'),
    ('15.777.888-9', 5, 1, 'ALTA',   'PENDIENTE',  'Solicita hora de Medicina General esta semana.',        'tens.padrehurtado'),
    ('14.666.777-5', 6, 2, 'MEDIA',  'PENDIENTE',  'Requiere iniciar sesiones de kinesiología.',            'tens.oratoriomariano')
) AS v(pac_rut, pol_id, esp_id, prio, est, obs, usr)
JOIN pacientes p ON p.rut = v.pac_rut
LEFT JOIN usuarios_sistema u ON u.username = v.usr;

-- 7. Registros iniciales en auditoría
INSERT INTO auditoria_operaciones (usuario_nombre, rol, policlinico_id, operacion, entidad, entidad_id, detalle) VALUES
('Carolina Morales (TENS Sagrada Familia)', 'TENS_TONS', 2, 'CREAR_CITA_ASISTIDA', 'citas', NULL, 'Carga demostrativa inicial para policlínico Sagrada Familia.'),
('Rodrigo Alarcón (TENS María Ayuda)', 'TENS_TONS', 3, 'CREAR_CITA_ASISTIDA', 'citas', NULL, 'Carga demostrativa inicial para policlínico María Ayuda.'),
('Marcela Pinto (TENS Santa Teresa)', 'TENS_TONS', 4, 'CREAR_CITA_ASISTIDA', 'citas', NULL, 'Carga demostrativa inicial para policlínico Santa Teresa.'),
('Cristián Navarro (TENS Padre Hurtado)', 'TENS_TONS', 5, 'CREAR_CITA_ASISTIDA', 'citas', NULL, 'Carga demostrativa inicial para policlínico Padre Hurtado.'),
('Verónica Cáceres (TENS Oratorio Mariano)', 'TENS_TONS', 6, 'CREAR_CITA_ASISTIDA', 'citas', NULL, 'Carga demostrativa inicial para policlínico Oratorio Mariano.');