"""
Patrón Facade — ServicioAgendamiento (M4: Actividad Clases y Patrones).
Orquesta validación de RUT, Repository (PostgreSQL/Memoria), máquina de estados
(IEstadoCita + EstadoConfirmacion) y notificaciones desacopladas (IGestorNotificaciones).
"""

from __future__ import annotations
from typing import Any, Optional

from app.domain.estados import (
    EstadoConfirmacion,
    aplicar_regla_confirmacion,
    obtener_estado_cita,
)
from app.domain.rut import enmascarar_nombre, formatear_rut
from app.repositories.interfaces import ErrorRecursoNoEncontrado, IRepositorioCita
from app.services.notificaciones import IGestorNotificaciones


class ServicioAgendamiento:
    def __init__(self, repo: IRepositorioCita, notificador: IGestorNotificaciones) -> None:
        self.repo = repo
        self.notificador = notificador

    def registrar_o_actualizar_paciente(self, payload: dict[str, Any]) -> dict[str, Any]:
        rut_fmt = formatear_rut(payload["rut"])
        datos = {**payload, "rut": rut_fmt}
        # Si usa tutor/apoderado, los datos de contacto se toman del tutor
        if datos.get("usa_tutor"):
            if datos.get("responsable_telefono"):
                datos["telefono"] = datos["responsable_telefono"]
            datos["correo"] = None  # No almacenar correo como personal del paciente si es del tutor
        return self.repo.crear_o_actualizar_paciente(datos)

    def buscar_paciente(self, rut: str) -> Optional[dict[str, Any]]:
        rut_fmt = formatear_rut(rut)
        return self.repo.buscar_paciente_por_rut(rut_fmt)

    def verificar_documento_previo(self, rut: str) -> dict[str, Any]:
        """Verificación mínima sin exponer datos personales (solo indica si ya tiene folio previo)."""
        rut_fmt = formatear_rut(rut)
        pac = self.repo.buscar_paciente_por_rut(rut_fmt)
        if not pac:
            return {"existe_paciente": False, "tiene_documento": False}
        docs = pac.get("documentos_respaldo") or []
        return {"existe_paciente": True, "tiene_documento": len(docs) > 0}

    def consultar_estado_por_rut_solo_lectura(self, rut: str) -> dict[str, Any]:
        """RF29 con control de privacidad P10: solo lectura, sin cuenta, sin código y datos enmascarados."""
        rut_fmt = formatear_rut(rut)
        paciente = self.repo.buscar_paciente_por_rut(rut_fmt)
        if not paciente:
            return {
                "encontrado": False,
                "aviso_privacidad": "Consulta en solo lectura protegida por políticas de privacidad. No expone antecedentes clínicos ni datos de contacto.",
                "citas": [],
                "solicitudes": [],
            }
        citas = self.repo.listar_citas(rut_formateado=rut_fmt)
        citas_minimas = [
            {
                "policlinico_nombre": c["policlinico_nombre"],
                "modalidad": c["modalidad"],
                "especialidad_nombre": c["especialidad_nombre"],
                "profesional_nombre": c["profesional_nombre"],
                "fecha": c["fecha"],
                "hora_inicio": c["hora_inicio"],
                "estado_cita": c["estado_cita"],
                "estado_confirmacion": c["estado_confirmacion"],
            }
            for c in citas
        ]
        espera_todas = self.repo.listar_lista_espera()
        solicitudes_pac = [
            {
                "policlinico_nombre": s["policlinico_nombre"],
                "especialidad_nombre": s["especialidad_nombre"],
                "estado": s["estado"],
                "prioridad": s["prioridad"],
                "observacion": s.get("observacion"),
                "creada_en": s.get("creada_en"),
            }
            for s in espera_todas
            if s.get("paciente_rut") == rut_fmt
        ]
        tiene_tutor = len(paciente.get("responsables") or []) > 0
        tiene_doc = len(paciente.get("documentos_respaldo") or []) > 0
        return {
            "encontrado": True,
            "paciente_enmascarado": enmascarar_nombre(paciente["nombre_completo"]),
            "rut": rut_fmt,
            "tiene_tutor": tiene_tutor,
            "tiene_documento_respaldo": tiene_doc,
            "aviso_privacidad": "Por protección de datos personales, los apellidos, teléfono, correo y folios se mantienen ocultos en esta vista.",
            "citas": citas_minimas,
            "solicitudes": solicitudes_pac,
        }

    def agendar_cita_asistida(self, payload: dict[str, Any]) -> dict[str, Any]:
        """RF04, RF05, RNF04, RF28: reserva transaccional sin dobles cupos y comprobante sin código."""
        rut_fmt = formatear_rut(payload["paciente_rut"])
        paciente = self.repo.buscar_paciente_por_rut(rut_fmt)
        if not paciente:
            raise ErrorRecursoNoEncontrado(
                f"No existe ficha administrativa para el RUT {rut_fmt}. Regístrela primero."
            )

        cita = self.repo.crear_cita_transaccional(
            {
                "paciente_id": paciente["id"],
                "bloque_id": payload["bloque_id"],
                "orden_medica_id": payload.get("orden_medica_id"),
                "canal_registro": payload.get("canal_registro", "ASISTIDO_PRESENCIAL"),
                "usuario_id": payload.get("usuario_id"),
                "usuario_nombre": payload.get("usuario_nombre", "TENS/TONS Demo"),
                "rol": payload.get("rol", "TENS_TONS"),
            }
        )

        notif = self.notificador.enviar_comprobante_sin_codigo(cita)
        self.repo.registrar_notificacion(
            cita["cita_id"],
            notif.canal,
            notif.tipo_mensaje,
            notif.destinatario,
            notif.estado_envio,
            notif.detalle,
        )
        return {
            "cita": cita,
            "comprobante_sin_codigo": {
                "paciente": cita["paciente_nombre"],
                "rut": cita["paciente_rut"],
                "policlinico": cita["policlinico_nombre"],
                "modalidad": cita["modalidad"],
                "especialidad": cita["especialidad_nombre"],
                "profesional": cita["profesional_nombre"],
                "fecha": cita["fecha"],
                "hora": cita["hora_inicio"],
                "nota": "Comprobante administrativo sin código de reserva.",
            },
            "notificacion": {
                "estado_envio": notif.estado_envio,
                "alerta_operativa": notif.alerta_operativa,
                "detalle": notif.detalle,
            },
        }

    def registrar_solicitud_paciente(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Registra una solicitud asistida en lista de espera (sin autoagendamiento directo)."""
        paciente = self.registrar_o_actualizar_paciente(
            {
                "rut": payload["rut"],
                "nombre_completo": payload["nombre_completo"],
                "fecha_nacimiento": payload.get("fecha_nacimiento"),
                "nacionalidad": payload.get("nacionalidad") or "Chilena",
                "telefono": payload["telefono"],
                "correo": payload.get("correo"),
                "prevision": payload.get("prevision", "FONASA"),
                "usa_tutor": payload.get("usa_tutor", False),
                "responsable_nombre": payload.get("responsable_nombre"),
                "responsable_parentesco": payload.get("responsable_parentesco"),
                "responsable_telefono": payload.get("responsable_telefono"),
                "responsable_correo": payload.get("responsable_correo"),
                "tipo_documento": payload.get("tipo_documento"),
                "folio_documento": payload.get("folio_documento"),
            }
        )

        detalle_bloque = None
        if payload.get("bloque_preferido_id"):
            bloques = self.repo.listar_bloques(solo_disponibles=False)
            b = next((x for x in bloques if x["id"] == payload["bloque_preferido_id"]), None)
            if b:
                detalle_bloque = f"Horario solicitado: {b['fecha']} {b['hora_inicio']} ({b['profesional_nombre']})"

        partes_obs = []
        if detalle_bloque:
            partes_obs.append(detalle_bloque)
        if payload.get("usa_tutor") and payload.get("responsable_nombre"):
            partes_obs.append(
                f"Tutor: {payload['responsable_nombre']} ({payload.get('responsable_parentesco') or 'Responsable'})"
            )
        if payload.get("observacion"):
            partes_obs.append(f"Comentario: {payload['observacion']}")
        obs_final = " · ".join(partes_obs) if partes_obs else "Solicitud ingresada desde portal de pacientes."

        item = self.repo.agregar_lista_espera(
            {
                "paciente_id": paciente["id"],
                "policlinico_id": payload["policlinico_id"],
                "especialidad_id": payload["especialidad_id"],
                "prioridad": "NORMAL",
                "observacion": obs_final,
                "usuario_nombre": "Portal Pacientes (Solicitud asistida)",
                "rol": "PACIENTE",
            }
        )
        return {
            "solicitud": item,
            "resumen": {
                "paciente_nombre": paciente["nombre_completo"],
                "paciente_rut": paciente["rut"],
                "policlinico_nombre": item["policlinico_nombre"],
                "especialidad_nombre": item["especialidad_nombre"],
                "detalle_horario": detalle_bloque or "Sin horario específico (sujeto a disponibilidad)",
                "usa_tutor": bool(payload.get("usa_tutor")),
                "tutor_nombre": payload.get("responsable_nombre"),
                "tutor_parentesco": payload.get("responsable_parentesco"),
                "folio_registrado": bool(payload.get("folio_documento")),
                "comentario": payload.get("observacion") or "",
                "estado": item["estado"],
            },
            "mensaje": "Tu solicitud quedó registrada correctamente. Nuestro equipo te contactará por teléfono o WhatsApp para confirmar tu hora.",
        }

    def actualizar_confirmacion_cita(self, cita_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        cita = self.repo.obtener_cita(cita_id)
        if not cita:
            raise ErrorRecursoNoEncontrado("Cita no encontrada.")

        nuevo_conf = EstadoConfirmacion(payload["estado_confirmacion"].upper())
        nuevo_estado_cita, nuevo_estado_conf = aplicar_regla_confirmacion(cita["estado_cita"], nuevo_conf)

        mapa_res = {
            "CONFIRMADA": "CONFIRMADA",
            "SIN_RESPUESTA": "NO_CONTESTA",
            "RECHAZADA": "CANCELADA",
            "PENDIENTE": "AVISO_ENVIADO",
        }
        obs = payload.get("observacion") or (
            "Sin respuesta registrada; la cita permanece RESERVADA conforme a RF09."
            if nuevo_estado_conf == "SIN_RESPUESTA"
            else f"Confirmación actualizada a {nuevo_estado_conf}."
        )
        return self.repo.actualizar_confirmacion(
            cita_id=cita_id,
            nuevo_estado_cita=nuevo_estado_cita,
            nuevo_estado_confirmacion=nuevo_estado_conf,
            canal=payload.get("canal", "TELEFONO"),
            resultado_seguimiento=mapa_res[nuevo_estado_conf],
            observacion=obs,
            usuario_id=payload.get("usuario_id"),
            usuario_nombre=payload.get("usuario_nombre", "TENS/TONS Demo"),
            rol=payload.get("rol", "TENS_TONS"),
        )

    def cancelar_cita(self, cita_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        cita = self.repo.obtener_cita(cita_id)
        if not cita:
            raise ErrorRecursoNoEncontrado("Cita no encontrada.")
        estado_obj = obtener_estado_cita(cita["estado_cita"])
        estado_obj.cancelar()
        return self.repo.cancelar_cita_transaccional(
            cita_id=cita_id,
            origen_cancelacion=payload.get("origen_cancelacion", "ASISTIDA_TENS"),
            motivo=payload.get("motivo", "Cancelación administrativa"),
            usuario_id=payload.get("usuario_id"),
            usuario_nombre=payload.get("usuario_nombre", "TENS/TONS Demo"),
            rol=payload.get("rol", "TENS_TONS"),
        )

    def registrar_asistencia_cita(self, cita_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        cita = self.repo.obtener_cita(cita_id)
        if not cita:
            raise ErrorRecursoNoEncontrado("Cita no encontrada.")
        estado_obj = obtener_estado_cita(cita["estado_cita"])
        nuevo_estado = estado_obj.registrar_asistencia() if payload["asistio"] else estado_obj.registrar_inasistencia()
        actualizada = self.repo.registrar_asistencia(
            cita_id=cita_id,
            nuevo_estado_cita=nuevo_estado,
            observacion=payload.get("observacion") or f"Marcada como {nuevo_estado} en recepción.",
            usuario_id=payload.get("usuario_id"),
            usuario_nombre=payload.get("usuario_nombre", "TENS/TONS Demo"),
            rol=payload.get("rol", "TENS_TONS"),
        )
        invitacion_encuesta = None
        if nuevo_estado == "ASISTIDA":
            notif = self.notificador.enviar_invitacion_encuesta_post_atencion(actualizada)
            self.repo.registrar_notificacion(
                cita_id, notif.canal, notif.tipo_mensaje, notif.destinatario, notif.estado_envio, notif.detalle
            )
            invitacion_encuesta = notif.detalle
        return {"cita": actualizada, "invitacion_encuesta_post_atencion": invitacion_encuesta}

    def agregar_a_lista_espera(self, payload: dict[str, Any]) -> dict[str, Any]:
        rut_fmt = formatear_rut(payload["paciente_rut"])
        paciente = self.repo.buscar_paciente_por_rut(rut_fmt)
        if not paciente:
            raise ErrorRecursoNoEncontrado(f"No existe ficha para el RUT {rut_fmt}.")
        return self.repo.agregar_lista_espera({**payload, "paciente_id": paciente["id"]})
