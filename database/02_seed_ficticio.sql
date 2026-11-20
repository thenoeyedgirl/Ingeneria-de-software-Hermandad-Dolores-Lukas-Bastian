-- ============================================================================
-- Semilla de DATOS 100 % FICTICIOS para demostración local reproducible
-- Fundación Hermandad de Dolores · MVP Fase 1
-- ADVERTENCIA: Todos los pacientes, RUTs, teléfonos y correos son ficticios.
-- ============================================================================

-- 1. 6 Policlínicos presenciales + Telemedicina como 7.º policlínico lógico
INSERT INTO policlinicos (codigo, nombre, modalidad, direccion, telefono) VALUES
('POL-SI', 'San Isidro (Casa Central)', 'PRESENCIAL', 'Av. San Isidro 100 (Referencial)', '+56 2 2000 0001'),
('POL-SF', 'Sagrada Familia', 'PRESENCIAL', 'Sector Sagrada Familia (Referencial)', '+56 2 2000 0002'),
('POL-MA', 'María Ayuda', 'PRESENCIAL', 'Sector María Ayuda (Referencial)', '+56 2 2000 0003'),
('POL-ST', 'Santa Teresa', 'PRESENCIAL', 'Sector Santa Teresa (Referencial)', '+56 2 2000 0004'),
('POL-PH', 'Padre Hurtado', 'PRESENCIAL', 'Sector Padre Hurtado (Referencial)', '+56 2 2000 0005'),
('POL-OM', 'Oratorio Mariano', 'PRESENCIAL', 'Sector Oratorio Mariano (Referencial)', '+56 2 2000 0006'),
('POL-TM', 'Telemedicina (7.º Policlínico)', 'TELEMEDICINA', 'Atención remota sin box físico', '+56 2 2000 0007');

-- 2. Especialidades
INSERT INTO especialidades (nombre, duracion_min, permite_telemed) VALUES
('Medicina General', 30, TRUE),
('Kinesiología', 45, FALSE),
('Psicología', 45, TRUE),
('Odontología', 30, FALSE),
('Nutrición', 30, TRUE),
('Fonoaudiología', 45, TRUE);

-- 3. Profesionales ficticios (RUTs válidos módulo 11)
INSERT INTO profesionales (rut, nombre_completo, especialidad_id, policlinico_id) VALUES
('11.111.111-1', 'Dra. Camila Rojas Paredes (Demo)', 1, 1),
('22.222.222-2', 'Klgo. Matías Soto Araya (Demo)', 2, 1),
('12.345.678-5', 'Ps. Valentina Lagos Núñez (Demo)', 3, 7),
('15.234.567-4', 'Dr. Felipe Herrera Muñoz (Demo)', 4, 2),
('16.345.678-8', 'Nut. Francisca Vega Silva (Demo)', 5, 3),
('17.456.789-1', 'Dra. Sofía Morales Díaz (Demo)', 1, 7),
('18.567.890-3', 'Flgo. Sebastián Castro Pinto (Demo)', 6, 4);

-- 4. Usuarios del sistema (solo credenciales demostrativas ficticias)
INSERT INTO usuarios_sistema (username, nombre_completo, rol, policlinico_id, clave_demo) VALUES
('tens.sanisidro', 'Paula Contreras (TENS San Isidro)', 'TENS_TONS', 1, 'demo123'),
('telemed.operador', 'Diego Fuentes (Operador Telemedicina)', 'TELEMEDICINA', 7, 'demo123'),
('admin.fundacion', 'Administración Central (Demo)', 'ADMINISTRACION', NULL, 'admin123');

-- 5. Pacientes 100 % ficticios (RUTs válidos módulo 11)
INSERT INTO pacientes (rut, nombre_completo, telefono, correo, prevision, cesfam_origen, estado_doc_fonasa) VALUES
('14.567.890-0', 'María Elena Pérez Demo', '+56 9 5000 0001', 'maria.demo@ejemplo.cl', 'FONASA A', 'CESFAM Norte Demo', 'VALIDADO'),
('19.876.543-0', 'Juan Carlos González Demo', '+56 9 5000 0002', 'juan.demo@ejemplo.cl', 'FONASA B', 'CESFAM Centro Demo', 'PENDIENTE'),
('13.246.810-9', 'Rosa Amelia Muñoz Demo', '+56 9 5000 0003', 'rosa.demo@ejemplo.cl', 'FONASA A', 'CESFAM Sur Demo', 'VALIDADO'),
('20.111.222-2', 'Pedro Antonio Silva Demo', '+56 9 5000 0004', 'pedro.demo@ejemplo.cl', 'FONASA C', 'CESFAM Poniente Demo', 'EN_REVISION'),
('10.203.040-0', 'Carmen Gloria Torres Demo', '+56 9 5000 0005', 'carmen.demo@ejemplo.cl', 'FONASA B', 'CESFAM Oriente Demo', 'VALIDADO');

-- 6. Adultos responsables ficticios
INSERT INTO responsables (paciente_id, nombre_completo, parentesco, telefono) VALUES
(1, 'Luis Pérez Demo', 'Hijo', '+56 9 5100 0001'),
(3, 'Andrea Muñoz Demo', 'Hija', '+56 9 5100 0003');

-- 7. Orden médica plurisesión ficticia (Kinesiología 10 sesiones)
INSERT INTO ordenes_medicas (paciente_id, especialidad_id, sesiones_totales, sesiones_usadas, estado_validacion) VALUES
(1, 2, 10, 2, 'VALIDADO'),
(3, 2, 6, 1, 'VALIDADO');

-- 8. Bloques horarios (próximos días desde la fecha actual de PostgreSQL)
INSERT INTO bloques_horarios (policlinico_id, especialidad_id, profesional_id, fecha, hora_inicio, hora_fin, estado_bloque, publicado) VALUES
(1, 1, 1, CURRENT_DATE + 1, '09:00', '09:30', 'OCUPADO', TRUE),
(1, 1, 1, CURRENT_DATE + 1, '09:30', '10:00', 'DISPONIBLE', TRUE),
(1, 1, 1, CURRENT_DATE + 1, '10:00', '10:30', 'DISPONIBLE', TRUE),
(1, 2, 2, CURRENT_DATE + 1, '10:30', '11:15', 'OCUPADO', TRUE),
(1, 2, 2, CURRENT_DATE + 1, '11:15', '12:00', 'DISPONIBLE', TRUE),
(7, 3, 3, CURRENT_DATE + 1, '15:00', '15:45', 'OCUPADO', TRUE),
(7, 3, 3, CURRENT_DATE + 1, '15:45', '16:30', 'DISPONIBLE', TRUE),
(7, 1, 6, CURRENT_DATE + 2, '11:00', '11:30', 'DISPONIBLE', TRUE),
(2, 4, 4, CURRENT_DATE + 2, '09:00', '09:30', 'DISPONIBLE', TRUE),
(3, 5, 5, CURRENT_DATE + 2, '10:00', '10:30', 'DISPONIBLE', TRUE),
(4, 6, 7, CURRENT_DATE + 2, '11:00', '11:45', 'BLOQUEADO', TRUE),
(1, 1, 1, CURRENT_DATE - 1, '09:00', '09:30', 'OCUPADO', TRUE),
(1, 2, 2, CURRENT_DATE - 1, '10:00', '10:45', 'OCUPADO', TRUE);

-- 9. Citas iniciales ficticias (demostrando estados separados RF09 y asistencia RF14)
INSERT INTO citas (paciente_id, bloque_id, orden_medica_id, estado_cita, estado_confirmacion, canal_registro, creado_por_usuario_id) VALUES
(1, 1, NULL, 'RESERVADA', 'SIN_RESPUESTA', 'ASISTIDO_PRESENCIAL', 1),
(1, 4, 1, 'RESERVADA', 'CONFIRMADA', 'ASISTIDO_TELEFONO', 1),
(2, 6, NULL, 'RESERVADA', 'PENDIENTE', 'ASISTIDO_TELEFONO', 2),
(3, 12, NULL, 'ASISTIDA', 'CONFIRMADA', 'ASISTIDO_PRESENCIAL', 1),
(4, 13, NULL, 'INASISTIDA', 'SIN_RESPUESTA', 'ASISTIDO_PRESENCIAL', 1);

-- 10. Registros de seguimiento (RF27)
INSERT INTO registros_seguimiento (cita_id, usuario_id, canal, resultado, observacion) VALUES
(1, 1, 'TELEFONO', 'NO_CONTESTA', 'Se llamó a las 10:15; cita se mantiene activa según regla RF09 (el silencio no cancela).'),
(2, 1, 'WHATSAPP', 'CONFIRMADA', 'Paciente confirmó asistencia vía botón WhatsApp simulado.');

-- 11. Lista de espera asistida (RF06)
INSERT INTO lista_espera (paciente_id, policlinico_id, especialidad_id, prioridad, estado, observacion, creado_por_id) VALUES
(5, 1, 1, 'ALTA', 'PENDIENTE', 'Solicita hora en horario mañana en San Isidro.', 1),
(4, 7, 3, 'MEDIA', 'CONTACTADO', 'Se ofreció horario de tarde en Telemedicina; espera confirmación.', 2);

-- 12. Encuestas iniciales ficticias (RF30 y RF36)
INSERT INTO encuestas (cita_id, tipo, puntaje, comentario) VALUES
(4, 'POST_ATENCION', 5, 'Excelente trato en mesón y puntualidad (dato ficticio).'),
(2, 'AGENDAMIENTO_WEB', 4, 'Comprobante claro y sin pasos complejos (dato ficticio).');

-- 13. Auditoría inicial (RF34)
INSERT INTO auditoria_operaciones (usuario_nombre, rol, policlinico_id, operacion, entidad, entidad_id, detalle) VALUES
('Paula Contreras (TENS San Isidro)', 'TENS_TONS', 1, 'CREAR_CITA_ASISTIDA', 'citas', 1, 'Reserva asistida creada sin código de reserva (RF04/RF28).'),
('Diego Fuentes (Operador Telemedicina)', 'TELEMEDICINA', 7, 'CREAR_CITA_ASISTIDA', 'citas', 3, 'Reserva en 7.º policlínico lógico Telemedicina (RF35).'),
('Administración Central (Demo)', 'ADMINISTRACION', 4, 'BLOQUEAR_AGENDA', 'bloques_horarios', 11, 'Bloqueo preventivo por capacitación interna (RF12).');
