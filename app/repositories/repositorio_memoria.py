"""
RepositorioCitaMemoria — Implementación en memoria del patrón Repository.
Utilizada exclusivamente para pruebas unitarias automatizadas (pytest / unittest)
sin requerir una instancia activa de PostgreSQL durante la ejecución de pruebas.
"""

from __future__ import annotations
from datetime import date, datetime, timedelta
import threading
from typing import Any, Optional

from app.repositories.interfaces import (
    ErrorConflictoCupo,
    ErrorRecursoNoEncontrado,
    IRepositorioCita,
)


class RepositorioCitaMemoria(IRepositorioCita):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cargar_semilla()

    def _cargar_semilla(self) -> None:
        hoy = date.today()
        manana = (hoy + timedelta(days=1)).isoformat()
        pasado = (hoy + timedelta(days=2)).isoformat()
        ayer = (hoy - timedelta(days=1)).isoformat()

        self.policlinicos = [
            {"id": 1, "codigo": "POL-SI", "nombre": "San Isidro (Casa Central)", "modalidad": "PRESENCIAL", "direccion": "Av. San Isidro 100 (Referencial)", "telefono": "+56 2 2000 0001", "activo": True},
            {"id": 2, "codigo": "POL-SF", "nombre": "Sagrada Familia", "modalidad": "PRESENCIAL", "direccion": "Sector Sagrada Familia (Referencial)", "telefono": "+56 2 2000 0002", "activo": True},
            {"id": 3, "codigo": "POL-MA", "nombre": "María Ayuda", "modalidad": "PRESENCIAL", "direccion": "Sector María Ayuda (Referencial)", "telefono": "+56 2 2000 0003", "activo": True},
            {"id": 4, "codigo": "POL-ST", "nombre": "Santa Teresa", "modalidad": "PRESENCIAL", "direccion": "Sector Santa Teresa (Referencial)", "telefono": "+56 2 2000 0004", "activo": True},
            {"id": 5, "codigo": "POL-PH", "nombre": "Padre Hurtado", "modalidad": "PRESENCIAL", "direccion": "Sector Padre Hurtado (Referencial)", "telefono": "+56 2 2000 0005", "activo": True},
            {"id": 6, "codigo": "POL-OM", "nombre": "Oratorio Mariano", "modalidad": "PRESENCIAL", "direccion": "Sector Oratorio Mariano (Referencial)", "telefono": "+56 2 2000 0006", "activo": True},
            {"id": 7, "codigo": "POL-TM", "nombre": "Telemedicina (7.º Policlínico)", "modalidad": "TELEMEDICINA", "direccion": "Atención remota sin box físico", "telefono": "+56 2 2000 0007", "activo": True},
        ]
        self.especialidades = [
            {"id": 1, "nombre": "Medicina General", "duracion_min": 30, "permite_telemed": True, "activa": True},
            {"id": 2, "nombre": "Kinesiología", "duracion_min": 45, "permite_telemed": False, "activa": True},
            {"id": 3, "nombre": "Psicología", "duracion_min": 45, "permite_telemed": True, "activa": True},
            {"id": 4, "nombre": "Odontología", "duracion_min": 30, "permite_telemed": False, "activa": True},
            {"id": 5, "nombre": "Nutrición", "duracion_min": 30, "permite_telemed": True, "activa": True},
            {"id": 6, "nombre": "Fonoaudiología", "duracion_min": 45, "permite_telemed": True, "activa": True},
        ]
        self.profesionales = [
            {"id": 1, "rut": "11.111.111-1", "nombre_completo": "Dra. Camila Rojas Paredes (Demo)", "especialidad_id": 1, "policlinico_id": 1, "activo": True},
            {"id": 2, "rut": "22.222.222-2", "nombre_completo": "Klgo. Matías Soto Araya (Demo)", "especialidad_id": 2, "policlinico_id": 1, "activo": True},
            {"id": 3, "rut": "12.345.678-5", "nombre_completo": "Ps. Valentina Lagos Núñez (Demo)", "especialidad_id": 3, "policlinico_id": 7, "activo": True},
            {"id": 4, "rut": "15.234.567-4", "nombre_completo": "Dr. Felipe Herrera Muñoz (Demo)", "especialidad_id": 4, "policlinico_id": 2, "activo": True},
            {"id": 5, "rut": "16.345.678-8", "nombre_completo": "Nut. Francisca Vega Silva (Demo)", "especialidad_id": 5, "policlinico_id": 3, "activo": True},
            {"id": 6, "rut": "17.456.789-1", "nombre_completo": "Dra. Sofía Morales Díaz (Demo)", "especialidad_id": 1, "policlinico_id": 7, "activo": True},
        ]
        self.usuarios = [
            {"id": 1, "username": "tens.sanisidro", "nombre_completo": "Paula Contreras (TENS San Isidro)", "rol": "TENS_TONS", "policlinico_id": 1, "clave_demo": "demo123", "activo": True},
            {"id": 2, "username": "telemed.operador", "nombre_completo": "Diego Fuentes (Operador Telemedicina)", "rol": "TELEMEDICINA", "policlinico_id": 7, "clave_demo": "demo123", "activo": True},
            {"id": 3, "username": "admin.fundacion", "nombre_completo": "Administración Central (Demo)", "rol": "ADMINISTRACION", "policlinico_id": None, "clave_demo": "admin123", "activo": True},
        ]
        self.pacientes = [
            {"id": 1, "rut": "14.567.890-0", "nombre_completo": "María Elena Pérez Demo", "telefono": "+56 9 5000 0001", "correo": "maria.demo@ejemplo.cl", "prevision": "FONASA A", "cesfam_origen": "CESFAM Norte Demo", "estado_doc_fonasa": "VALIDADO", "fecha_nacimiento": "1985-05-10", "nacionalidad": "Chilena", "consentimiento_datos": True},
            {"id": 2, "rut": "19.876.543-0", "nombre_completo": "Juan Carlos González Demo", "telefono": "+56 9 5000 0002", "correo": "juan.demo@ejemplo.cl", "prevision": "FONASA B", "cesfam_origen": "CESFAM Centro Demo", "estado_doc_fonasa": "PENDIENTE", "fecha_nacimiento": "1985-05-10", "nacionalidad": "Chilena", "consentimiento_datos": True},
            {"id": 3, "rut": "13.246.810-9", "nombre_completo": "Rosa Amelia Muñoz Demo", "telefono": "+56 9 5000 0003", "correo": "rosa.demo@ejemplo.cl", "prevision": "FONASA A", "cesfam_origen": "CESFAM Sur Demo", "estado_doc_fonasa": "VALIDADO", "fecha_nacimiento": "1985-05-10", "nacionalidad": "Chilena", "consentimiento_datos": True},
        ]
        self.documentos = [{"id": 1, "paciente_id": 1, "tipo_documento": "FONASA", "folio": "FON-2026-00145", "estado_revision": "VALIDADO"}]
        self.responsables = [
            {"id": 1, "paciente_id": 1, "nombre_completo": "Luis Pérez Demo", "parentesco": "Hijo", "telefono": "+56 9 5100 0001"},
        ]
        self.ordenes = [
            {"id": 1, "paciente_id": 1, "especialidad_id": 2, "sesiones_totales": 10, "sesiones_usadas": 2, "estado_validacion": "VALIDADO"},
        ]
        self.bloques = [
            {"id": 1, "policlinico_id": 1, "especialidad_id": 1, "profesional_id": 1, "fecha": manana, "hora_inicio": "09:00", "hora_fin": "09:30", "estado_bloque": "OCUPADO", "publicado": True},
            {"id": 2, "policlinico_id": 1, "especialidad_id": 1, "profesional_id": 1, "fecha": manana, "hora_inicio": "09:30", "hora_fin": "10:00", "estado_bloque": "DISPONIBLE", "publicado": True},
            {"id": 3, "policlinico_id": 1, "especialidad_id": 2, "profesional_id": 2, "fecha": manana, "hora_inicio": "10:30", "hora_fin": "11:15", "estado_bloque": "DISPONIBLE", "publicado": True},
            {"id": 4, "policlinico_id": 7, "especialidad_id": 3, "profesional_id": 3, "fecha": manana, "hora_inicio": "15:00", "hora_fin": "15:45", "estado_bloque": "DISPONIBLE", "publicado": True},
            {"id": 5, "policlinico_id": 2, "especialidad_id": 4, "profesional_id": 4, "fecha": pasado, "hora_inicio": "09:00", "hora_fin": "09:30", "estado_bloque": "DISPONIBLE", "publicado": True},
            {"id": 6, "policlinico_id": 1, "especialidad_id": 1, "profesional_id": 1, "fecha": ayer, "hora_inicio": "09:00", "hora_fin": "09:30", "estado_bloque": "OCUPADO", "publicado": True},
        ]
        self.citas = [
            {"id": 1, "paciente_id": 1, "bloque_id": 1, "orden_medica_id": None, "estado_cita": "RESERVADA", "estado_confirmacion": "SIN_RESPUESTA", "canal_registro": "ASISTIDO_PRESENCIAL", "origen_cancelacion": None, "motivo_cancelacion": None, "creada_en": datetime.now().isoformat()},
            {"id": 2, "paciente_id": 3, "bloque_id": 6, "orden_medica_id": None, "estado_cita": "ASISTIDA", "estado_confirmacion": "CONFIRMADA", "canal_registro": "ASISTIDO_PRESENCIAL", "origen_cancelacion": None, "motivo_cancelacion": None, "creada_en": datetime.now().isoformat()},
        ]
        self.seguimientos: list[dict[str, Any]] = []
        self.lista_espera = [
            {"id": 1, "paciente_id": 2, "policlinico_id": 1, "especialidad_id": 1, "prioridad": "ALTA", "estado": "PENDIENTE", "observacion": "Horario mañana", "creada_en": datetime.now().isoformat()},
        ]
        self.notificaciones: list[dict[str, Any]] = []
        self.encuestas = [
            {"id": 1, "cita_id": 2, "tipo": "POST_ATENCION", "puntaje": 5, "comentario": "Muy buena atención (demo)", "registrada_en": datetime.now().isoformat()},
        ]
        self.auditoria: list[dict[str, Any]] = [
            {"id": 1, "registrado_en": datetime.now().isoformat(), "usuario_nombre": "Paula Contreras (TENS San Isidro)", "rol": "TENS_TONS", "policlinico_id": 1, "policlinico_nombre": "San Isidro (Casa Central)", "operacion": "CREAR_CITA_ASISTIDA", "entidad": "citas", "entidad_id": 1, "detalle": "Cita demostrativa inicial."},
        ]

    def _pol(self, pid: int) -> dict[str, Any]:
        return next(p for p in self.policlinicos if p["id"] == pid)

    def _esp(self, eid: int) -> dict[str, Any]:
        return next(e for e in self.especialidades if e["id"] == eid)

    def _prof(self, prid: int) -> dict[str, Any]:
        return next(p for p in self.profesionales if p["id"] == prid)

    def _pac(self, pid: int) -> dict[str, Any]:
        return next(p for p in self.pacientes if p["id"] == pid)

    def _bloque(self, bid: int) -> dict[str, Any]:
        return next(b for b in self.bloques if b["id"] == bid)

    def _detalle_cita(self, c: dict[str, Any]) -> dict[str, Any]:
        p = self._pac(c["paciente_id"])
        b = self._bloque(c["bloque_id"])
        pol = self._pol(b["policlinico_id"])
        e = self._esp(b["especialidad_id"])
        pr = self._prof(b["profesional_id"])
        return {
            "cita_id": c["id"],
            "estado_cita": c["estado_cita"],
            "estado_confirmacion": c["estado_confirmacion"],
            "canal_registro": c["canal_registro"],
            "origen_cancelacion": c["origen_cancelacion"],
            "motivo_cancelacion": c["motivo_cancelacion"],
            "creada_en": c["creada_en"],
            "paciente_id": p["id"],
            "paciente_rut": p["rut"],
            "paciente_nombre": p["nombre_completo"],
            "paciente_telefono": p["telefono"],
            "prevision": p["prevision"],
            "estado_doc_fonasa": p["estado_doc_fonasa"],
            "bloque_id": b["id"],
            "fecha": b["fecha"],
            "hora_inicio": b["hora_inicio"],
            "hora_fin": b["hora_fin"],
            "policlinico_id": pol["id"],
            "policlinico_nombre": pol["nombre"],
            "modalidad": pol["modalidad"],
            "especialidad_id": e["id"],
            "especialidad_nombre": e["nombre"],
            "profesional_id": pr["id"],
            "profesional_nombre": pr["nombre_completo"],
        }

    def _auditar(self, usuario_nombre: str, rol: str, policlinico_id: Optional[int], operacion: str, entidad: str, entidad_id: Optional[int], detalle: str) -> None:
        self.auditoria.insert(0, {
            "id": len(self.auditoria) + 1,
            "registrado_en": datetime.now().isoformat(),
            "usuario_nombre": usuario_nombre,
            "rol": rol,
            "policlinico_id": policlinico_id,
            "policlinico_nombre": self._pol(policlinico_id)["nombre"] if policlinico_id else "Todas las sedes",
            "operacion": operacion,
            "entidad": entidad,
            "entidad_id": entidad_id,
            "detalle": detalle,
        })

    def autenticar_usuario(self, username: str, clave: str) -> Optional[dict[str, Any]]:
        for u in self.usuarios:
            if u["username"] == username and u["clave_demo"] == clave and u["activo"]:
                return {
                    "id": u["id"],
                    "username": u["username"],
                    "nombre_completo": u["nombre_completo"],
                    "rol": u["rol"],
                    "policlinico_id": u["policlinico_id"],
                    "policlinico_nombre": self._pol(u["policlinico_id"])["nombre"] if u["policlinico_id"] else "Todas las sedes",
                }
        return None

    def listar_usuarios_demo(self) -> list[dict[str, Any]]:
        return [
            {
                "id": u["id"],
                "username": u["username"],
                "nombre_completo": u["nombre_completo"],
                "rol": u["rol"],
                "policlinico_id": u["policlinico_id"],
                "policlinico_nombre": self._pol(u["policlinico_id"])["nombre"] if u["policlinico_id"] else "Todas las sedes",
            }
            for u in self.usuarios
        ]

    def listar_policlinicos(self) -> list[dict[str, Any]]:
        return list(self.policlinicos)

    def listar_especialidades(self) -> list[dict[str, Any]]:
        return list(self.especialidades)

    def listar_profesionales(self, policlinico_id: Optional[int] = None) -> list[dict[str, Any]]:
        res = []
        for pr in self.profesionales:
            if policlinico_id and pr["policlinico_id"] != policlinico_id:
                continue
            item = dict(pr)
            item["especialidad_nombre"] = self._esp(pr["especialidad_id"])["nombre"]
            item["policlinico_nombre"] = self._pol(pr["policlinico_id"])["nombre"]
            res.append(item)
        return res

    def listar_bloques(self, policlinico_id: Optional[int] = None, especialidad_id: Optional[int] = None, solo_disponibles: bool = False) -> list[dict[str, Any]]:
        res = []
        for b in self.bloques:
            if policlinico_id and b["policlinico_id"] != policlinico_id:
                continue
            if especialidad_id and b["especialidad_id"] != especialidad_id:
                continue
            if solo_disponibles and not (b["estado_bloque"] == "DISPONIBLE" and b["publicado"]):
                continue
            pol = self._pol(b["policlinico_id"])
            res.append({
                **b,
                "policlinico_nombre": pol["nombre"],
                "modalidad": pol["modalidad"],
                "especialidad_nombre": self._esp(b["especialidad_id"])["nombre"],
                "profesional_nombre": self._prof(b["profesional_id"])["nombre_completo"],
            })
        return res

    def crear_bloque(self, datos: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            bid = max((b["id"] for b in self.bloques), default=0) + 1
            nuevo = {
                "id": bid,
                "policlinico_id": datos["policlinico_id"],
                "especialidad_id": datos["especialidad_id"],
                "profesional_id": datos["profesional_id"],
                "fecha": datos["fecha"],
                "hora_inicio": datos["hora_inicio"],
                "hora_fin": datos["hora_fin"],
                "estado_bloque": "DISPONIBLE",
                "publicado": datos.get("publicado", True),
            }
            self.bloques.append(nuevo)
            self._auditar(datos.get("usuario_nombre", "Administración"), "ADMINISTRACION", datos["policlinico_id"], "CREAR_BLOQUE_AGENDA", "bloques_horarios", bid, "Bloque creado (RF12).")
            return nuevo

    def actualizar_estado_bloque(self, bloque_id: int, estado_bloque: str, usuario_nombre: str, motivo: str) -> dict[str, Any]:
        with self._lock:
            bloque = next((b for b in self.bloques if b["id"] == bloque_id), None)
            if not bloque:
                raise ErrorRecursoNoEncontrado("Bloque horario no encontrado.")
            bloque["estado_bloque"] = estado_bloque
            afectadas = [self._detalle_cita(c) for c in self.citas if c["bloque_id"] == bloque_id and c["estado_cita"] == "RESERVADA"]
            self._auditar(usuario_nombre, "ADMINISTRACION", bloque["policlinico_id"], "ACTUALIZAR_BLOQUE_AGENDA", "bloques_horarios", bloque_id, f"Estado={estado_bloque}. {motivo}")
            return {"bloque_id": bloque_id, "estado_bloque": estado_bloque, "citas_afectadas": afectadas}

    def buscar_paciente_por_rut(self, rut_formateado: str) -> Optional[dict[str, Any]]:
        pac = next((p for p in self.pacientes if p["rut"] == rut_formateado), None)
        if not pac:
            return None
        res = dict(pac)
        res["responsables"] = [r for r in self.responsables if r["paciente_id"] == pac["id"]]
        res["ordenes_medicas"] = [
            {**o, "especialidad_nombre": self._esp(o["especialidad_id"])["nombre"], "sesiones_disponibles": o["sesiones_totales"] - o["sesiones_usadas"]}
            for o in self.ordenes if o["paciente_id"] == pac["id"]
        ]
        res["documentos_respaldo"] = [d for d in self.documentos if d["paciente_id"] == pac["id"]]
        return res

    def listar_pacientes(self, busqueda: Optional[str] = None) -> list[dict[str, Any]]:
        if not busqueda:
            return list(self.pacientes)
        q = busqueda.lower()
        return [p for p in self.pacientes if q in p["rut"].lower() or q in p["nombre_completo"].lower()]

    def crear_o_actualizar_paciente(self, datos: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            pac = next((p for p in self.pacientes if p["rut"] == datos["rut"]), None)
            if pac:
                pac.update({
                    "fecha_nacimiento": datos.get("fecha_nacimiento") or pac.get("fecha_nacimiento"),
                    "nacionalidad": datos.get("nacionalidad") or pac.get("nacionalidad", "Chilena"),
                    "nombre_completo": datos["nombre_completo"],
                    "telefono": datos["telefono"],
                    "correo": datos.get("correo"),
                    "prevision": datos.get("prevision", "FONASA"),
                    "cesfam_origen": datos.get("cesfam_origen"),
                })
            else:
                pid = max((p["id"] for p in self.pacientes), default=0) + 1
                pac = {
                    "id": pid,
                    "rut": datos["rut"],
                    "fecha_nacimiento": datos.get("fecha_nacimiento"),
                    "nacionalidad": datos.get("nacionalidad") or "Chilena",
                    "nombre_completo": datos["nombre_completo"],
                    "telefono": datos["telefono"],
                    "correo": datos.get("correo"),
                    "prevision": datos.get("prevision", "FONASA"),
                    "cesfam_origen": datos.get("cesfam_origen"),
                    "estado_doc_fonasa": "PENDIENTE",
                    "consentimiento_datos": datos.get("consentimiento_datos", True),
                }
                self.pacientes.append(pac)
            if (datos.get("folio_documento") or "").strip():
                self.documentos.append({"id": len(self.documentos) + 1, "paciente_id": pac["id"], "tipo_documento": (datos.get("tipo_documento") or "FONASA").upper(), "folio": datos["folio_documento"].strip(), "estado_revision": "PENDIENTE"})
            if datos.get("responsable_nombre"):
                self.responsables.append({
                    "id": len(self.responsables) + 1,
                    "paciente_id": pac["id"],
                    "nombre_completo": datos["responsable_nombre"],
                    "parentesco": datos.get("responsable_parentesco") or "Responsable",
                    "telefono": datos.get("responsable_telefono") or datos["telefono"],
                })
        return self.buscar_paciente_por_rut(datos["rut"])  # type: ignore[return-value]

    def listar_citas(self, policlinico_id: Optional[int] = None, estado_cita: Optional[str] = None, rut_formateado: Optional[str] = None) -> list[dict[str, Any]]:
        res = [self._detalle_cita(c) for c in self.citas]
        if policlinico_id:
            res = [r for r in res if r["policlinico_id"] == policlinico_id]
        if estado_cita:
            res = [r for r in res if r["estado_cita"] == estado_cita]
        if rut_formateado:
            res = [r for r in res if r["paciente_rut"] == rut_formateado]
        return res

    def obtener_cita(self, cita_id: int) -> Optional[dict[str, Any]]:
        c = next((x for x in self.citas if x["id"] == cita_id), None)
        return self._detalle_cita(c) if c else None

    def crear_cita_transaccional(self, datos: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            bloque = next((b for b in self.bloques if b["id"] == datos["bloque_id"]), None)
            if not bloque:
                raise ErrorRecursoNoEncontrado("Bloque horario no encontrado.")
            if bloque["estado_bloque"] != "DISPONIBLE" or not bloque["publicado"]:
                raise ErrorConflictoCupo("El bloque horario ya no está disponible (RNF04: prevención de doble reserva).")
            cid = max((c["id"] for c in self.citas), default=0) + 1
            nueva = {
                "id": cid,
                "paciente_id": datos["paciente_id"],
                "bloque_id": datos["bloque_id"],
                "orden_medica_id": datos.get("orden_medica_id"),
                "estado_cita": "RESERVADA",
                "estado_confirmacion": "PENDIENTE",
                "canal_registro": datos.get("canal_registro", "ASISTIDO_PRESENCIAL"),
                "origen_cancelacion": None,
                "motivo_cancelacion": None,
                "creada_en": datetime.now().isoformat(),
            }
            self.citas.append(nueva)
            bloque["estado_bloque"] = "OCUPADO"
            self._auditar(datos.get("usuario_nombre", "TENS/TONS"), datos.get("rol", "TENS_TONS"), bloque["policlinico_id"], "CREAR_CITA_ASISTIDA", "citas", cid, "Cita creada sin código de reserva (RF28).")
            return self._detalle_cita(nueva)

    def actualizar_confirmacion(self, cita_id: int, nuevo_estado_cita: str, nuevo_estado_confirmacion: str, canal: str, resultado_seguimiento: str, observacion: str, usuario_id: Optional[int], usuario_nombre: str, rol: str) -> dict[str, Any]:
        with self._lock:
            c = next((x for x in self.citas if x["id"] == cita_id), None)
            if not c:
                raise ErrorRecursoNoEncontrado("Cita no encontrada.")
            c["estado_cita"] = nuevo_estado_cita
            c["estado_confirmacion"] = nuevo_estado_confirmacion
            b = self._bloque(c["bloque_id"])
            if nuevo_estado_cita == "CANCELADA":
                b["estado_bloque"] = "DISPONIBLE"
            self.seguimientos.append({"cita_id": cita_id, "canal": canal, "resultado": resultado_seguimiento, "observacion": observacion})
            self._auditar(usuario_nombre, rol, b["policlinico_id"], "ACTUALIZAR_CONFIRMACION", "citas", cita_id, f"Confirmación={nuevo_estado_confirmacion}, Cita={nuevo_estado_cita}.")
            return self._detalle_cita(c)

    def cancelar_cita_transaccional(self, cita_id: int, origen_cancelacion: str, motivo: str, usuario_id: Optional[int], usuario_nombre: str, rol: str) -> dict[str, Any]:
        with self._lock:
            c = next((x for x in self.citas if x["id"] == cita_id), None)
            if not c:
                raise ErrorRecursoNoEncontrado("Cita no encontrada.")
            c["estado_cita"] = "CANCELADA"
            if origen_cancelacion == "WHATSAPP_PACIENTE":
                c["estado_confirmacion"] = "RECHAZADA"
            c["origen_cancelacion"] = origen_cancelacion
            c["motivo_cancelacion"] = motivo
            b = self._bloque(c["bloque_id"])
            b["estado_bloque"] = "DISPONIBLE"
            self._auditar(usuario_nombre, rol, b["policlinico_id"], "CANCELAR_CITA", "citas", cita_id, f"Origen={origen_cancelacion}. Cupo liberado.")
            return self._detalle_cita(c)

    def registrar_asistencia(self, cita_id: int, nuevo_estado_cita: str, observacion: str, usuario_id: Optional[int], usuario_nombre: str, rol: str) -> dict[str, Any]:
        with self._lock:
            c = next((x for x in self.citas if x["id"] == cita_id), None)
            if not c:
                raise ErrorRecursoNoEncontrado("Cita no encontrada.")
            c["estado_cita"] = nuevo_estado_cita
            if nuevo_estado_cita == "ASISTIDA" and c.get("orden_medica_id"):
                orden = next((o for o in self.ordenes if o["id"] == c["orden_medica_id"]), None)
                if orden and orden["sesiones_usadas"] < orden["sesiones_totales"]:
                    orden["sesiones_usadas"] += 1
            b = self._bloque(c["bloque_id"])
            self._auditar(usuario_nombre, rol, b["policlinico_id"], "REGISTRAR_ASISTENCIA", "citas", cita_id, f"Estado={nuevo_estado_cita}. {observacion}")
            return self._detalle_cita(c)

    def listar_pendientes_confirmacion(self, policlinico_id: Optional[int] = None) -> list[dict[str, Any]]:
        citas = self.listar_citas(policlinico_id=policlinico_id, estado_cita="RESERVADA")
        return [c for c in citas if c["estado_confirmacion"] in ("PENDIENTE", "SIN_RESPUESTA")]

    def listar_lista_espera(self, policlinico_id: Optional[int] = None) -> list[dict[str, Any]]:
        res = []
        for le in self.lista_espera:
            if policlinico_id and le["policlinico_id"] != policlinico_id:
                continue
            p = self._pac(le["paciente_id"])
            res.append({
                **le,
                "paciente_rut": p["rut"],
                "paciente_nombre": p["nombre_completo"],
                "paciente_telefono": p["telefono"],
                "policlinico_nombre": self._pol(le["policlinico_id"])["nombre"],
                "especialidad_nombre": self._esp(le["especialidad_id"])["nombre"],
            })
        return list(reversed(res))

    def agregar_lista_espera(self, datos: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            iid = max((x["id"] for x in self.lista_espera), default=0) + 1
            item = {
                "id": iid,
                "paciente_id": datos["paciente_id"],
                "policlinico_id": datos["policlinico_id"],
                "especialidad_id": datos["especialidad_id"],
                "prioridad": datos.get("prioridad", "NORMAL"),
                "estado": "PENDIENTE",
                "observacion": datos.get("observacion"),
                "creada_en": datetime.now().isoformat(),
            }
            self.lista_espera.append(item)
            self._auditar(datos.get("usuario_nombre", "TENS/TONS"), datos.get("rol", "TENS_TONS"), datos["policlinico_id"], "AGREGAR_LISTA_ESPERA", "lista_espera", iid, "Solicitud asistida en lista de espera (RF06).")
        return next(x for x in self.listar_lista_espera() if x["id"] == iid)

    def actualizar_lista_espera(self, item_id: int, estado: str, observacion: Optional[str], usuario_nombre: str, rol: str) -> dict[str, Any]:
        with self._lock:
            item = next((x for x in self.lista_espera if x["id"] == item_id), None)
            if not item:
                raise ErrorRecursoNoEncontrado("Registro en lista de espera no encontrado.")
            item["estado"] = estado
            if observacion:
                item["observacion"] = observacion
            self._auditar(usuario_nombre, rol, item["policlinico_id"], "ACTUALIZAR_LISTA_ESPERA", "lista_espera", item_id, f"Estado={estado}.")
        return next(x for x in self.listar_lista_espera() if x["id"] == item_id)

    def registrar_notificacion(self, cita_id: Optional[int], canal: str, tipo_mensaje: str, destinatario: str, estado_envio: str, detalle: str) -> None:
        self.notificaciones.insert(0, {
            "id": len(self.notificaciones) + 1,
            "cita_id": cita_id,
            "canal": canal,
            "tipo_mensaje": tipo_mensaje,
            "destinatario": destinatario,
            "estado_envio": estado_envio,
            "detalle": detalle,
            "enviado_en": datetime.now().isoformat(),
        })

    def registrar_encuesta(self, cita_id: Optional[int], tipo: str, puntaje: int, comentario: Optional[str]) -> dict[str, Any]:
        item = {
            "id": len(self.encuestas) + 1,
            "cita_id": cita_id,
            "tipo": tipo,
            "puntaje": puntaje,
            "comentario": comentario,
            "registrada_en": datetime.now().isoformat(),
        }
        self.encuestas.append(item)
        return item

    def listar_mensajes_whatsapp(self, policlinico_id: Optional[int] = None, rut: Optional[str] = None) -> list[dict[str, Any]]:
        res = []
        for n in self.notificaciones:
            c = self.obtener_cita(n["cita_id"]) if n.get("cita_id") else None
            if policlinico_id and c and c["policlinico_id"] != policlinico_id:
                continue
            item = {
                **n,
                "paciente_rut": c["paciente_rut"] if c else None,
                "paciente_nombre": c["paciente_nombre"] if c else None,
                "policlinico_id": c["policlinico_id"] if c else None,
                "policlinico_nombre": c["policlinico_nombre"] if c else None,
            }
            if rut:
                q = rut.strip().lower()
                if q not in (item["paciente_rut"] or "").lower() and q not in (item["destinatario"] or "").lower():
                    continue
            res.append(item)
        return res[:30]

    def obtener_reportes(self) -> dict[str, Any]:
        detalles = self.listar_citas()
        indicadores = []
        ocupacion = []
        for pol in self.policlinicos:
            cs = [c for c in detalles if c["policlinico_id"] == pol["id"]]
            asist = sum(1 for c in cs if c["estado_cita"] == "ASISTIDA")
            inasist = sum(1 for c in cs if c["estado_cita"] == "INASISTIDA")
            tasa = round(100.0 * asist / (asist + inasist), 1) if (asist + inasist) else 0.0
            indicadores.append({
                "policlinico_id": pol["id"],
                "policlinico_nombre": pol["nombre"],
                "modalidad": pol["modalidad"],
                "total_citas": len(cs),
                "reservadas": sum(1 for c in cs if c["estado_cita"] == "RESERVADA"),
                "asistidas": asist,
                "inasistidas": inasist,
                "canceladas": sum(1 for c in cs if c["estado_cita"] == "CANCELADA"),
                "pendientes_confirmacion": sum(1 for c in cs if c["estado_cita"] == "RESERVADA" and c["estado_confirmacion"] in ("PENDIENTE", "SIN_RESPUESTA")),
                "tasa_asistencia_pct": tasa,
            })
            bs = [b for b in self.bloques if b["policlinico_id"] == pol["id"]]
            disp = sum(1 for b in bs if b["estado_bloque"] == "DISPONIBLE" and b["publicado"])
            ocup = sum(1 for b in bs if b["estado_bloque"] == "OCUPADO")
            bloq = sum(1 for b in bs if b["estado_bloque"] == "BLOQUEADO")
            ocupacion.append({
                "policlinico_id": pol["id"],
                "policlinico_nombre": pol["nombre"],
                "bloques_totales": len(bs),
                "bloques_disponibles": disp,
                "bloques_ocupados": ocup,
                "bloques_bloqueados": bloq,
                "ocupacion_pct": round(100.0 * ocup / (disp + ocup), 1) if (disp + ocup) else 0.0,
            })
        enc_res = []
        for tipo in ("AGENDAMIENTO_WEB", "POST_ATENCION"):
            xs = [e["puntaje"] for e in self.encuestas if e["tipo"] == tipo]
            if xs:
                enc_res.append({"tipo": tipo, "total_respuestas": len(xs), "promedio_puntaje": round(sum(xs) / len(xs), 2)})
        return {
            "indicadores_por_sede": indicadores,
            "ocupacion_por_sede": ocupacion,
            "resumen_lista_espera": [],
            "encuestas_resumen": enc_res,
            "notificaciones_recientes": self.notificaciones[:15],
            "caracterizacion_edad": [{"tramo": "36–59 años", "total": len(self.pacientes)}],
            "caracterizacion_nacionalidad": [{"nacionalidad": "Chilena", "total": len(self.pacientes)}],
        }

    def listar_auditoria(self, limite: int = 40) -> list[dict[str, Any]]:
        return self.auditoria[:limite]
