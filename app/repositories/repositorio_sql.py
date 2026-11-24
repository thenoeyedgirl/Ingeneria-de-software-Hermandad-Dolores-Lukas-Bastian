"""
RepositorioCitaSQL — Implementación oficial para PostgreSQL 16 (psycopg 3).
Aplica transacciones ACID con SELECT ... FOR UPDATE y aprovecha el índice único
parcial ux_cita_bloque_activa para garantizar 0 % dobles reservas (RNF04).
"""

from __future__ import annotations
from datetime import date, time, datetime
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row

from app.repositories.interfaces import (
    ErrorConflictoCupo,
    ErrorRecursoNoEncontrado,
    IRepositorioCita,
)


def _serializar(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, time):
            out[k] = v.strftime("%H:%M")
        else:
            out[k] = v
    return out


def _serializar_lista(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_serializar(r) for r in rows if r is not None]


class RepositorioCitaSQL(IRepositorioCita):
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _auditar(
        self,
        cur: psycopg.Cursor,
        usuario_nombre: str,
        rol: str,
        policlinico_id: Optional[int],
        operacion: str,
        entidad: str,
        entidad_id: Optional[int],
        detalle: str,
    ) -> None:
        cur.execute(
            """
            INSERT INTO auditoria_operaciones
                (usuario_nombre, rol, policlinico_id, operacion, entidad, entidad_id, detalle)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (usuario_nombre, rol, policlinico_id, operacion, entidad, entidad_id, detalle),
        )

    def autenticar_usuario(self, username: str, clave: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.nombre_completo, u.rol, u.policlinico_id,
                       COALESCE(p.nombre, 'Todas las sedes') AS policlinico_nombre
                FROM usuarios_sistema u
                LEFT JOIN policlinicos p ON p.id = u.policlinico_id
                WHERE u.username = %s AND u.clave_demo = %s AND u.activo = TRUE
                """,
                (username, clave),
            )
            return _serializar(cur.fetchone())

    def listar_usuarios_demo(self) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.nombre_completo, u.rol, u.policlinico_id,
                       COALESCE(p.nombre, 'Todas las sedes') AS policlinico_nombre
                FROM usuarios_sistema u
                LEFT JOIN policlinicos p ON p.id = u.policlinico_id
                WHERE u.activo = TRUE
                ORDER BY u.id
                """
            )
            return _serializar_lista(cur.fetchall())

    def listar_policlinicos(self) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM policlinicos WHERE activo = TRUE ORDER BY id")
            return _serializar_lista(cur.fetchall())

    def listar_especialidades(self) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM especialidades WHERE activa = TRUE ORDER BY id")
            return _serializar_lista(cur.fetchall())

    def listar_profesionales(self, policlinico_id: Optional[int] = None) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            if policlinico_id:
                cur.execute(
                    """
                    SELECT pr.*, e.nombre AS especialidad_nombre, pol.nombre AS policlinico_nombre
                    FROM profesionales pr
                    JOIN especialidades e ON e.id = pr.especialidad_id
                    JOIN policlinicos pol ON pol.id = pr.policlinico_id
                    WHERE pr.activo = TRUE AND pr.policlinico_id = %s
                    ORDER BY pr.id
                    """,
                    (policlinico_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT pr.*, e.nombre AS especialidad_nombre, pol.nombre AS policlinico_nombre
                    FROM profesionales pr
                    JOIN especialidades e ON e.id = pr.especialidad_id
                    JOIN policlinicos pol ON pol.id = pr.policlinico_id
                    WHERE pr.activo = TRUE
                    ORDER BY pr.id
                    """
                )
            return _serializar_lista(cur.fetchall())

    def listar_bloques(
        self,
        policlinico_id: Optional[int] = None,
        especialidad_id: Optional[int] = None,
        solo_disponibles: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if policlinico_id:
            clauses.append("b.policlinico_id = %s")
            params.append(policlinico_id)
        if especialidad_id:
            clauses.append("b.especialidad_id = %s")
            params.append(especialidad_id)
        if solo_disponibles:
            clauses.append(
                "b.estado_bloque = 'DISPONIBLE' AND b.publicado = TRUE "
                "AND NOT EXISTS (SELECT 1 FROM citas c WHERE c.bloque_id = b.id AND c.estado_cita IN ('RESERVADA', 'ASISTIDA'))"
            )

        sql = f"""
            SELECT b.id, b.policlinico_id, pol.nombre AS policlinico_nombre, pol.modalidad,
                   b.especialidad_id, e.nombre AS especialidad_nombre,
                   b.profesional_id, pr.nombre_completo AS profesional_nombre,
                   b.fecha, b.hora_inicio, b.hora_fin, b.estado_bloque, b.publicado
            FROM bloques_horarios b
            JOIN policlinicos pol ON pol.id = b.policlinico_id
            JOIN especialidades e ON e.id = b.especialidad_id
            JOIN profesionales pr ON pr.id = b.profesional_id
            WHERE {' AND '.join(clauses)}
            ORDER BY b.fecha, b.hora_inicio
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return _serializar_lista(cur.fetchall())

    def crear_bloque(self, datos: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bloques_horarios
                        (policlinico_id, especialidad_id, profesional_id, fecha, hora_inicio, hora_fin, estado_bloque, publicado)
                    VALUES (%s, %s, %s, %s, %s, %s, 'DISPONIBLE', %s)
                    RETURNING id
                    """,
                    (
                        datos["policlinico_id"],
                        datos["especialidad_id"],
                        datos["profesional_id"],
                        datos["fecha"],
                        datos["hora_inicio"],
                        datos["hora_fin"],
                        datos.get("publicado", True),
                    ),
                )
                bloque_id = cur.fetchone()["id"]
                self._auditar(
                    cur,
                    datos.get("usuario_nombre", "Administración"),
                    "ADMINISTRACION",
                    datos["policlinico_id"],
                    "CREAR_BLOQUE_AGENDA",
                    "bloques_horarios",
                    bloque_id,
                    f"Bloque creado {datos['fecha']} {datos['hora_inicio']}-{datos['hora_fin']} (RF12).",
                )
                cur.execute("SELECT * FROM bloques_horarios WHERE id = %s", (bloque_id,))
                return _serializar(cur.fetchone())  # type: ignore[return-value]

    def actualizar_estado_bloque(self, bloque_id: int, estado_bloque: str, usuario_nombre: str, motivo: str) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("SELECT * FROM bloques_horarios WHERE id = %s FOR UPDATE", (bloque_id,))
                bloque = cur.fetchone()
                if not bloque:
                    raise ErrorRecursoNoEncontrado("Bloque horario no encontrado.")
                cur.execute(
                    "UPDATE bloques_horarios SET estado_bloque = %s WHERE id = %s",
                    (estado_bloque, bloque_id),
                )
                cur.execute(
                    """
                    SELECT cita_id, paciente_nombre, paciente_telefono, estado_cita
                    FROM v_citas_detalle
                    WHERE bloque_id = %s AND estado_cita = 'RESERVADA'
                    """,
                    (bloque_id,),
                )
                afectadas = _serializar_lista(cur.fetchall())
                self._auditar(
                    cur,
                    usuario_nombre,
                    "ADMINISTRACION",
                    bloque["policlinico_id"],
                    "ACTUALIZAR_BLOQUE_AGENDA",
                    "bloques_horarios",
                    bloque_id,
                    f"Estado cambiado a {estado_bloque}. Citas afectadas: {len(afectadas)}. Motivo: {motivo}",
                )
                return {"bloque_id": bloque_id, "estado_bloque": estado_bloque, "citas_afectadas": afectadas}

    def buscar_paciente_por_rut(self, rut_formateado: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM pacientes WHERE rut = %s", (rut_formateado,))
            pac = _serializar(cur.fetchone())
            if not pac:
                return None
            cur.execute("SELECT * FROM responsables WHERE paciente_id = %s", (pac["id"],))
            pac["responsables"] = _serializar_lista(cur.fetchall())
            cur.execute(
                """
                SELECT o.*, e.nombre AS especialidad_nombre,
                       (o.sesiones_totales - o.sesiones_usadas) AS sesiones_disponibles
                FROM ordenes_medicas o
                JOIN especialidades e ON e.id = o.especialidad_id
                WHERE o.paciente_id = %s
                ORDER BY o.id
                """,
                (pac["id"],),
            )
            pac["ordenes_medicas"] = _serializar_lista(cur.fetchall())
            cur.execute(
                "SELECT * FROM documentos_respaldo WHERE paciente_id = %s ORDER BY id DESC",
                (pac["id"],),
            )
            pac["documentos_respaldo"] = _serializar_lista(cur.fetchall())
            return pac

    def listar_pacientes(self, busqueda: Optional[str] = None) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            if busqueda:
                like = f"%{busqueda.strip()}%"
                cur.execute(
                    "SELECT * FROM pacientes WHERE rut ILIKE %s OR nombre_completo ILIKE %s ORDER BY id DESC",
                    (like, like),
                )
            else:
                cur.execute("SELECT * FROM pacientes ORDER BY id DESC")
            return _serializar_lista(cur.fetchall())

    def crear_o_actualizar_paciente(self, datos: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("SELECT id FROM pacientes WHERE rut = %s", (datos["rut"],))
                existente = cur.fetchone()
                fnac = datos.get("fecha_nacimiento") or None
                nac = (datos.get("nacionalidad") or "Chilena").strip() or "Chilena"
                if existente:
                    pac_id = existente["id"]
                    cur.execute(
                        """
                        UPDATE pacientes
                        SET nombre_completo = %s,
                            fecha_nacimiento = COALESCE(%s, fecha_nacimiento),
                            nacionalidad = %s,
                            telefono = %s,
                            correo = COALESCE(%s, correo),
                            prevision = %s,
                            cesfam_origen = COALESCE(%s, cesfam_origen)
                        WHERE id = %s
                        """,
                        (
                            datos["nombre_completo"],
                            fnac,
                            nac,
                            datos["telefono"],
                            datos.get("correo"),
                            datos.get("prevision", "FONASA"),
                            datos.get("cesfam_origen"),
                            pac_id,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO pacientes
                            (rut, nombre_completo, fecha_nacimiento, nacionalidad, telefono, correo, prevision, cesfam_origen, consentimiento_datos)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            datos["rut"],
                            datos["nombre_completo"],
                            fnac,
                            nac,
                            datos["telefono"],
                            datos.get("correo"),
                            datos.get("prevision", "FONASA"),
                            datos.get("cesfam_origen"),
                            datos.get("consentimiento_datos", True),
                        ),
                    )
                    pac_id = cur.fetchone()["id"]
                if datos.get("responsable_nombre"):
                    cur.execute(
                        """
                        INSERT INTO responsables (paciente_id, nombre_completo, parentesco, telefono, correo)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            pac_id,
                            datos["responsable_nombre"],
                            datos.get("responsable_parentesco") or "Responsable",
                            datos.get("responsable_telefono") or datos["telefono"],
                            datos.get("responsable_correo"),
                        ),
                    )
                folio = (datos.get("folio_documento") or "").strip()
                if folio:
                    tipo_doc = (datos.get("tipo_documento") or "FONASA").upper()
                    if tipo_doc not in ("FONASA", "CESFAM", "OTRO"):
                        tipo_doc = "FONASA"
                    cur.execute(
                        """
                        INSERT INTO documentos_respaldo (paciente_id, tipo_documento, folio, estado_revision)
                        VALUES (%s, %s, %s, 'PENDIENTE')
                        """,
                        (pac_id, tipo_doc, folio),
                    )
        return self.buscar_paciente_por_rut(datos["rut"])  # type: ignore[return-value]

    def listar_citas(
        self,
        policlinico_id: Optional[int] = None,
        estado_cita: Optional[str] = None,
        rut_formateado: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if policlinico_id:
            clauses.append("policlinico_id = %s")
            params.append(policlinico_id)
        if estado_cita:
            clauses.append("estado_cita = %s")
            params.append(estado_cita)
        if rut_formateado:
            clauses.append("paciente_rut = %s")
            params.append(rut_formateado)

        sql = f"SELECT * FROM v_citas_detalle WHERE {' AND '.join(clauses)} ORDER BY fecha DESC, hora_inicio ASC"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return _serializar_lista(cur.fetchall())

    def obtener_cita(self, cita_id: int) -> Optional[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM v_citas_detalle WHERE cita_id = %s", (cita_id,))
            return _serializar(cur.fetchone())

    def crear_cita_transaccional(self, datos: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                # RNF04: Bloqueo pesimista SELECT FOR UPDATE sobre el bloque horario
                cur.execute(
                    "SELECT id, policlinico_id, estado_bloque, publicado FROM bloques_horarios WHERE id = %s FOR UPDATE",
                    (datos["bloque_id"],),
                )
                bloque = cur.fetchone()
                if not bloque:
                    raise ErrorRecursoNoEncontrado("Bloque horario no encontrado.")
                if bloque["estado_bloque"] != "DISPONIBLE" or not bloque["publicado"]:
                    raise ErrorConflictoCupo("El bloque horario ya no está disponible (RNF04: prevención de doble reserva).")

                try:
                    cur.execute(
                        """
                        INSERT INTO citas
                            (paciente_id, bloque_id, orden_medica_id, estado_cita, estado_confirmacion, canal_registro, creado_por_usuario_id)
                        VALUES (%s, %s, %s, 'RESERVADA', 'PENDIENTE', %s, %s)
                        RETURNING id
                        """,
                        (
                            datos["paciente_id"],
                            datos["bloque_id"],
                            datos.get("orden_medica_id"),
                            datos.get("canal_registro", "ASISTIDO_PRESENCIAL"),
                            datos.get("usuario_id"),
                        ),
                    )
                except psycopg.errors.UniqueViolation as exc:
                    raise ErrorConflictoCupo(
                        "Este bloque horario ya cuenta con una cita activa o asistida. Seleccione otro horario disponible."
                    ) from exc
                cita_id = cur.fetchone()["id"]
                cur.execute(
                    "UPDATE bloques_horarios SET estado_bloque = 'OCUPADO' WHERE id = %s",
                    (datos["bloque_id"],),
                )
                self._auditar(
                    cur,
                    datos.get("usuario_nombre", "TENS/TONS"),
                    datos.get("rol", "TENS_TONS"),
                    bloque["policlinico_id"],
                    "CREAR_CITA_ASISTIDA",
                    "citas",
                    cita_id,
                    f"Cita creada en bloque {datos['bloque_id']} por canal {datos.get('canal_registro')}. Sin código de reserva (RF28).",
                )
        return self.obtener_cita(cita_id)  # type: ignore[return-value]

    def actualizar_confirmacion(
        self,
        cita_id: int,
        nuevo_estado_cita: str,
        nuevo_estado_confirmacion: str,
        canal: str,
        resultado_seguimiento: str,
        observacion: str,
        usuario_id: Optional[int],
        usuario_nombre: str,
        rol: str,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.bloque_id, b.policlinico_id
                    FROM citas c JOIN bloques_horarios b ON b.id = c.bloque_id
                    WHERE c.id = %s FOR UPDATE
                    """,
                    (cita_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ErrorRecursoNoEncontrado("Cita no encontrada.")
                cur.execute(
                    """
                    UPDATE citas
                    SET estado_cita = %s, estado_confirmacion = %s, actualizada_en = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (nuevo_estado_cita, nuevo_estado_confirmacion, cita_id),
                )
                if nuevo_estado_cita == "CANCELADA":
                    cur.execute("UPDATE bloques_horarios SET estado_bloque = 'DISPONIBLE' WHERE id = %s", (row["bloque_id"],))
                cur.execute(
                    """
                    INSERT INTO registros_seguimiento (cita_id, usuario_id, canal, resultado, observacion)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (cita_id, usuario_id, canal, resultado_seguimiento, observacion),
                )
                self._auditar(
                    cur,
                    usuario_nombre,
                    rol,
                    row["policlinico_id"],
                    "ACTUALIZAR_CONFIRMACION",
                    "citas",
                    cita_id,
                    f"Confirmación={nuevo_estado_confirmacion}, Cita={nuevo_estado_cita} ({canal}). {observacion}",
                )
        return self.obtener_cita(cita_id)  # type: ignore[return-value]

    def cancelar_cita_transaccional(
        self,
        cita_id: int,
        origen_cancelacion: str,
        motivo: str,
        usuario_id: Optional[int],
        usuario_nombre: str,
        rol: str,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.bloque_id, b.policlinico_id
                    FROM citas c JOIN bloques_horarios b ON b.id = c.bloque_id
                    WHERE c.id = %s FOR UPDATE
                    """,
                    (cita_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ErrorRecursoNoEncontrado("Cita no encontrada.")
                cur.execute(
                    """
                    UPDATE citas
                    SET estado_cita = 'CANCELADA',
                        estado_confirmacion = CASE WHEN %s = 'WHATSAPP_PACIENTE' THEN 'RECHAZADA' ELSE estado_confirmacion END,
                        origen_cancelacion = %s,
                        motivo_cancelacion = %s,
                        actualizada_en = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (origen_cancelacion, origen_cancelacion, motivo, cita_id),
                )
                cur.execute("UPDATE bloques_horarios SET estado_bloque = 'DISPONIBLE' WHERE id = %s", (row["bloque_id"],))
                self._auditar(
                    cur,
                    usuario_nombre,
                    rol,
                    row["policlinico_id"],
                    "CANCELAR_CITA",
                    "citas",
                    cita_id,
                    f"Origen={origen_cancelacion}. Cupo bloque {row['bloque_id']} liberado. Motivo: {motivo}",
                )
        return self.obtener_cita(cita_id)  # type: ignore[return-value]

    def registrar_asistencia(
        self,
        cita_id: int,
        nuevo_estado_cita: str,
        observacion: str,
        usuario_id: Optional[int],
        usuario_nombre: str,
        rol: str,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.orden_medica_id, b.policlinico_id
                    FROM citas c JOIN bloques_horarios b ON b.id = c.bloque_id
                    WHERE c.id = %s FOR UPDATE
                    """,
                    (cita_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ErrorRecursoNoEncontrado("Cita no encontrada.")
                cur.execute(
                    "UPDATE citas SET estado_cita = %s, actualizada_en = CURRENT_TIMESTAMP WHERE id = %s",
                    (nuevo_estado_cita, cita_id),
                )
                if nuevo_estado_cita == "ASISTIDA" and row["orden_medica_id"]:
                    cur.execute(
                        """
                        UPDATE ordenes_medicas
                        SET sesiones_usadas = LEAST(sesiones_totales, sesiones_usadas + 1)
                        WHERE id = %s
                        """,
                        (row["orden_medica_id"],),
                    )
                self._auditar(
                    cur,
                    usuario_nombre,
                    rol,
                    row["policlinico_id"],
                    "REGISTRAR_ASISTENCIA",
                    "citas",
                    cita_id,
                    f"Estado final={nuevo_estado_cita}. {observacion}",
                )
        return self.obtener_cita(cita_id)  # type: ignore[return-value]

    def listar_pendientes_confirmacion(self, policlinico_id: Optional[int] = None) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            if policlinico_id:
                cur.execute(
                    "SELECT * FROM v_pendientes_confirmacion WHERE policlinico_id = %s",
                    (policlinico_id,),
                )
            else:
                cur.execute("SELECT * FROM v_pendientes_confirmacion")
            return _serializar_lista(cur.fetchall())

    def listar_lista_espera(self, policlinico_id: Optional[int] = None) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            base = """
                SELECT le.id, le.prioridad, le.estado, le.observacion, le.creada_en,
                       p.rut AS paciente_rut, p.nombre_completo AS paciente_nombre, p.telefono AS paciente_telefono,
                       pol.id AS policlinico_id, pol.nombre AS policlinico_nombre,
                       e.id AS especialidad_id, e.nombre AS especialidad_nombre
                FROM lista_espera le
                JOIN pacientes p ON p.id = le.paciente_id
                JOIN policlinicos pol ON pol.id = le.policlinico_id
                JOIN especialidades e ON e.id = le.especialidad_id
            """
            if policlinico_id:
                cur.execute(base + " WHERE le.policlinico_id = %s ORDER BY le.id DESC", (policlinico_id,))
            else:
                cur.execute(base + " ORDER BY le.id DESC")
            return _serializar_lista(cur.fetchall())

    def agregar_lista_espera(self, datos: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lista_espera (paciente_id, policlinico_id, especialidad_id, prioridad, estado, observacion, creado_por_id)
                    VALUES (%s, %s, %s, %s, 'PENDIENTE', %s, %s)
                    RETURNING id
                    """,
                    (
                        datos["paciente_id"],
                        datos["policlinico_id"],
                        datos["especialidad_id"],
                        datos.get("prioridad", "NORMAL"),
                        datos.get("observacion"),
                        datos.get("usuario_id"),
                    ),
                )
                item_id = cur.fetchone()["id"]
                self._auditar(
                    cur,
                    datos.get("usuario_nombre", "TENS/TONS"),
                    datos.get("rol", "TENS_TONS"),
                    datos["policlinico_id"],
                    "AGREGAR_LISTA_ESPERA",
                    "lista_espera",
                    item_id,
                    f"Solicitud asistida registrada (prioridad {datos.get('prioridad', 'NORMAL')}). Sin asignación automática (RF06).",
                )
        items = self.listar_lista_espera()
        return next(i for i in items if i["id"] == item_id)

    def actualizar_lista_espera(self, item_id: int, estado: str, observacion: Optional[str], usuario_nombre: str, rol: str) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("SELECT policlinico_id FROM lista_espera WHERE id = %s", (item_id,))
                row = cur.fetchone()
                if not row:
                    raise ErrorRecursoNoEncontrado("Registro en lista de espera no encontrado.")
                cur.execute(
                    "UPDATE lista_espera SET estado = %s, observacion = COALESCE(%s, observacion) WHERE id = %s",
                    (estado, observacion, item_id),
                )
                self._auditar(
                    cur,
                    usuario_nombre,
                    rol,
                    row["policlinico_id"],
                    "ACTUALIZAR_LISTA_ESPERA",
                    "lista_espera",
                    item_id,
                    f"Estado lista de espera actualizado a {estado}.",
                )
        items = self.listar_lista_espera()
        return next(i for i in items if i["id"] == item_id)

    def registrar_notificacion(self, cita_id: Optional[int], canal: str, tipo_mensaje: str, destinatario: str, estado_envio: str, detalle: str) -> None:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notificaciones_log (cita_id, canal, tipo_mensaje, destinatario, estado_envio, detalle)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (cita_id, canal, tipo_mensaje, destinatario, estado_envio, detalle),
                )

    def registrar_encuesta(self, cita_id: Optional[int], tipo: str, puntaje: int, comentario: Optional[str]) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO encuestas (cita_id, tipo, puntaje, comentario)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (cita_id, tipo, puntaje, comentario),
                )
                return _serializar(cur.fetchone())  # type: ignore[return-value]

    def listar_mensajes_whatsapp(self, policlinico_id: Optional[int] = None, rut: Optional[str] = None) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if policlinico_id:
            clauses.append("(v.policlinico_id = %s OR n.cita_id IS NULL)")
            params.append(policlinico_id)
        if rut:
            like = f"%{rut.strip()}%"
            clauses.append("(v.paciente_rut ILIKE %s OR n.destinatario ILIKE %s)")
            params.extend([like, like])
        query = f"""
            SELECT n.id, n.cita_id, n.canal, n.tipo_mensaje, n.destinatario,
                   n.estado_envio, n.detalle, n.enviado_en,
                   v.paciente_rut, v.paciente_nombre, v.policlinico_id, v.policlinico_nombre
            FROM notificaciones_log n
            LEFT JOIN v_citas_detalle v ON v.cita_id = n.cita_id
            WHERE {' AND '.join(clauses)}
            ORDER BY n.id DESC
            LIMIT 30
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            return _serializar_lista(cur.fetchall())

    def obtener_reportes(self) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM v_indicadores_citas")
            indicadores = _serializar_lista(cur.fetchall())
            cur.execute("SELECT * FROM v_ocupacion_policlinico")
            ocupacion = _serializar_lista(cur.fetchall())
            cur.execute("SELECT * FROM v_resumen_lista_espera")
            espera = _serializar_lista(cur.fetchall())
            cur.execute("SELECT * FROM v_encuestas_resumen")
            encuestas = _serializar_lista(cur.fetchall())
            cur.execute("SELECT * FROM notificaciones_log ORDER BY id DESC LIMIT 15")
            notificaciones = _serializar_lista(cur.fetchall())
            cur.execute(
                """
                SELECT
                    CASE
                        WHEN fecha_nacimiento IS NULL THEN 'Sin fecha'
                        WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, fecha_nacimiento)) < 18 THEN '0–17 años'
                        WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, fecha_nacimiento)) BETWEEN 18 AND 35 THEN '18–35 años'
                        WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, fecha_nacimiento)) BETWEEN 36 AND 59 THEN '36–59 años'
                        ELSE '60+ años'
                    END AS tramo,
                    COUNT(*) AS total
                FROM pacientes
                GROUP BY tramo
                ORDER BY tramo
                """
            )
            car_edad = _serializar_lista(cur.fetchall())
            cur.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(nacionalidad), ''), 'Chilena') AS nacionalidad, COUNT(*) AS total
                FROM pacientes
                GROUP BY 1
                ORDER BY total DESC, 1 ASC
                """
            )
            car_nac = _serializar_lista(cur.fetchall())
            return {
                "indicadores_por_sede": indicadores,
                "ocupacion_por_sede": ocupacion,
                "resumen_lista_espera": espera,
                "encuestas_resumen": encuestas,
                "notificaciones_recientes": notificaciones,
                "caracterizacion_edad": car_edad,
                "caracterizacion_nacionalidad": car_nac,
            }

    def listar_auditoria(self, limite: int = 40) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM v_auditoria_reciente LIMIT %s", (limite,))
            return _serializar_lista(cur.fetchall())

    # --- Gráficos y filtros de reportes (RF19–RF23, RNF03) ---
    def obtener_dataset_reportes(self, filtros: dict[str, Any]) -> dict[str, Any]:
        f = filtros or {}
        col_fecha = "fecha_solicitud" if f.get("tipo_fecha") == "solicitud" else "fecha_cita"
        # Citas (vista v_reporte_citas: solo dimensiones, sin datos personales)
        cl: list[str] = []
        pr: list[Any] = []
        if f.get("desde"):
            cl.append(f"{col_fecha} >= %s")
            pr.append(f["desde"])
        if f.get("hasta"):
            cl.append(f"{col_fecha} <= %s")
            pr.append(f["hasta"])
        for campo in ("policlinico_id", "modalidad", "especialidad_id", "profesional_id", "estado_cita", "canal_registro"):
            if f.get(campo) is not None:
                cl.append(f"{campo} = %s")
                pr.append(f[campo])
        where_c = ("WHERE " + " AND ".join(cl)) if cl else ""
        # Bloques (ocupación): misma ventana de fechas sobre la fecha del bloque
        bl: list[str] = []
        bp: list[Any] = []
        if f.get("desde"):
            bl.append("b.fecha >= %s")
            bp.append(f["desde"])
        if f.get("hasta"):
            bl.append("b.fecha <= %s")
            bp.append(f["hasta"])
        for campo, col in (("policlinico_id", "b.policlinico_id"), ("modalidad", "pol.modalidad"), ("especialidad_id", "b.especialidad_id"), ("profesional_id", "b.profesional_id")):
            if f.get(campo) is not None:
                bl.append(f"{col} = %s")
                bp.append(f[campo])
        where_b = ("WHERE " + " AND ".join(bl)) if bl else ""
        # Encuestas: fecha de registro; sede/especialidad/profesional a través de la cita
        el: list[str] = []
        ep: list[Any] = []
        if f.get("desde"):
            el.append("e.registrada_en::date >= %s")
            ep.append(f["desde"])
        if f.get("hasta"):
            el.append("e.registrada_en::date <= %s")
            ep.append(f["hasta"])
        for campo, col in (("policlinico_id", "b.policlinico_id"), ("modalidad", "pol.modalidad"), ("especialidad_id", "b.especialidad_id"), ("profesional_id", "b.profesional_id")):
            if f.get(campo) is not None:
                el.append(f"{col} = %s")
                ep.append(f[campo])
        where_e = ("WHERE " + " AND ".join(el)) if el else ""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT cita_id, fecha_cita, hora_inicio, fecha_solicitud, estado_cita, estado_confirmacion,
                       canal_registro, origen_cancelacion, policlinico_id, policlinico_nombre, modalidad,
                       especialidad_id, especialidad_nombre, profesional_id, profesional_nombre,
                       tramo_etario, nacionalidad, paciente_ref
                FROM v_reporte_citas {where_c}
                ORDER BY fecha_cita, hora_inicio, cita_id
                """,
                pr,
            )
            citas = _serializar_lista(cur.fetchall())
            cur.execute(
                f"""
                SELECT b.fecha, b.hora_inicio, b.policlinico_id, b.profesional_id, b.especialidad_id, b.estado_bloque, b.publicado
                FROM bloques_horarios b JOIN policlinicos pol ON pol.id = b.policlinico_id
                {where_b}
                ORDER BY b.fecha, b.hora_inicio
                """,
                bp,
            )
            bloques = _serializar_lista(cur.fetchall())
            cur.execute(
                f"""
                SELECT e.registrada_en::date AS fecha, b.policlinico_id, e.puntaje, e.tipo
                FROM encuestas e
                LEFT JOIN citas c ON c.id = e.cita_id
                LEFT JOIN bloques_horarios b ON b.id = c.bloque_id
                LEFT JOIN policlinicos pol ON pol.id = b.policlinico_id
                {where_e}
                ORDER BY e.registrada_en
                """,
                ep,
            )
            encuestas = _serializar_lista(cur.fetchall())
            cur.execute("SELECT id, nombre, modalidad FROM policlinicos ORDER BY id")
            pols = _serializar_lista(cur.fetchall())
            cur.execute("SELECT id, nombre FROM especialidades ORDER BY id")
            esps = _serializar_lista(cur.fetchall())
            cur.execute("SELECT id, nombre_completo AS nombre, especialidad_id, policlinico_id FROM profesionales ORDER BY id")
            profs = _serializar_lista(cur.fetchall())
        return {"citas": citas, "bloques": bloques, "encuestas": encuestas,
                "catalogos": {"policlinicos": pols, "especialidades": esps, "profesionales": profs}}

    def registrar_auditoria(
        self, usuario_nombre: str, rol: str, policlinico_id: Optional[int], operacion: str, entidad: str, entidad_id: Optional[int], detalle: str
    ) -> None:
        with self._connect() as conn:
            with conn.transaction(), conn.cursor() as cur:
                self._auditar(cur, usuario_nombre, rol, policlinico_id, operacion, entidad, entidad_id, detalle[:400])
