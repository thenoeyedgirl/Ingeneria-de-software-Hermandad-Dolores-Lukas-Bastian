"""
Abstracción desacoplada IGestorNotificaciones (RF07, RF08, RF28, RF30).
Soporta dos modos:
  1. GestorNotificacionesMetaWhatsApp: envía mensajes reales y botones interactivos
     usando Meta WhatsApp Cloud API (sin intermediarios).
  2. GestorNotificacionesSimulado: modo local/pruebas sin credenciales externas.
Si el canal externo falla, emite una AlertaOperativa sin perder jamás la cita.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
import re
from typing import Optional

import httpx


def normalizar_telefono_wa(numero: str) -> str:
    """Convierte un teléfono (+56 9 5000 0001) a solo dígitos E.164 (56950000001)."""
    return re.sub(r"\D", "", numero or "")


@dataclass
class ResultadoNotificacion:
    canal: str
    tipo_mensaje: str
    destinatario: str
    estado_envio: str
    detalle: str
    alerta_operativa: bool = False


class IGestorNotificaciones(ABC):
    @abstractmethod
    def enviar_comprobante_sin_codigo(self, cita: dict) -> ResultadoNotificacion:
        ...

    @abstractmethod
    def enviar_recordatorio(self, cita: dict, tipo: str = "RECORDATORIO_24H") -> ResultadoNotificacion:
        ...

    @abstractmethod
    def enviar_invitacion_encuesta_post_atencion(self, cita: dict) -> ResultadoNotificacion:
        ...

    def enviar_texto_simple(self, destinatario: str, texto: str) -> ResultadoNotificacion:
        return ResultadoNotificacion(
            canal="WHATSAPP",
            tipo_mensaje="RESPUESTA_BOT",
            destinatario=destinatario,
            estado_envio="ENVIADO_SIMULADO",
            detalle=texto,
            alerta_operativa=False,
        )


class GestorNotificacionesSimulado(IGestorNotificaciones):
    """Implementación local demostrativa (sin credenciales externas)."""

    def __init__(self, simular_fallo: bool = False) -> None:
        self.simular_fallo = simular_fallo

    def _despachar(self, canal: str, tipo_mensaje: str, destinatario: str, texto: str) -> ResultadoNotificacion:
        if self.simular_fallo:
            return ResultadoNotificacion(
                canal=canal,
                tipo_mensaje=tipo_mensaje,
                destinatario=destinatario,
                estado_envio="FALLO_ALERTA_OPERATIVA",
                detalle=f"AlertaOperativa: fallo simulado de canal externo. Cita conservada. ({texto})",
                alerta_operativa=True,
            )
        return ResultadoNotificacion(
            canal=canal,
            tipo_mensaje=tipo_mensaje,
            destinatario=destinatario,
            estado_envio="ENVIADO_SIMULADO",
            detalle=texto,
            alerta_operativa=False,
        )

    def enviar_comprobante_sin_codigo(self, cita: dict) -> ResultadoNotificacion:
        texto = (
            f"Comprobante administrativo (sin código): {cita['paciente_nombre']} ({cita['paciente_rut']}) · "
            f"{cita['policlinico_nombre']} · {cita['especialidad_nombre']} · "
            f"{cita['profesional_nombre']} · {cita['fecha']} {cita['hora_inicio']}."
        )
        return self._despachar("WHATSAPP", "COMPROBANTE", cita["paciente_telefono"], texto)

    def enviar_recordatorio(self, cita: dict, tipo: str = "RECORDATORIO_24H") -> ResultadoNotificacion:
        if tipo == "RECORDATORIO_15D":
            texto = (
                f"Recordatorio anticipado (15 días): mantiene una cita el {cita['fecha']} a las {cita['hora_inicio']} "
                f"en {cita['policlinico_nombre']} ({cita['especialidad_nombre']}). El día anterior le enviaremos "
                "un mensaje con botones para confirmar su asistencia."
            )
            return self._despachar("WHATSAPP", "RECORDATORIO_7D", cita["paciente_telefono"], texto)
        texto = (
            f"Recordatorio 24h: cita mañana {cita['fecha']} a las {cita['hora_inicio']} en "
            f"{cita['policlinico_nombre']}. Botones: [Confirmar asistencia] / [Cancelar mi hora]. "
            "Si no responde, su cita se mantiene activa (RF09)."
        )
        return self._despachar("WHATSAPP", "RECORDATORIO_24H", cita["paciente_telefono"], texto)

    def enviar_invitacion_encuesta_post_atencion(self, cita: dict) -> ResultadoNotificacion:
        texto = (
            f"Encuesta post-atención (RF30): agradecemos evaluar su atención del {cita['fecha']} "
            f"en {cita['policlinico_nombre']}."
        )
        return self._despachar("WHATSAPP", "ENCUESTA_POST_ATENCION", cita["paciente_telefono"], texto)


class GestorNotificacionesMetaWhatsApp(IGestorNotificaciones):
    """
    Integración directa con Meta WhatsApp Cloud API (sin intermediarios).
    Envía mensajes de texto y mensajes interactivos con botones de respuesta rápida:
      - CONFIRMAR_<cita_id> -> «Confirmar asistencia»
      - CANCELAR_<cita_id>  -> «Cancelar mi hora»
    """

    def __init__(
        self,
        token: str,
        phone_number_id: str,
        api_version: str = "v25.0",
        test_to_override: Optional[str] = None,
    ) -> None:
        self.token = token.strip()
        self.phone_number_id = phone_number_id.strip()
        self.api_version = api_version.strip() or "v25.0"
        self.test_to_override = normalizar_telefono_wa(test_to_override or "")
        self.endpoint = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"

    def _destino(self, telefono_paciente: str) -> str:
        # En modo prueba Meta solo entrega a números autorizados; WHATSAPP_TEST_TO
        # permite enrutar citas ficticias al celular de demostración del equipo.
        if self.test_to_override:
            return self.test_to_override
        return normalizar_telefono_wa(telefono_paciente)

    def _post_meta(self, payload: dict, tipo_mensaje: str, destinatario: str, resumen: str) -> ResultadoNotificacion:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(self.endpoint, headers=headers, json=payload)
            if 200 <= resp.status_code < 300:
                msg_id = ""
                try:
                    msg_id = resp.json().get("messages", [{}])[0].get("id", "")
                except Exception:
                    pass
                return ResultadoNotificacion(
                    canal="WHATSAPP",
                    tipo_mensaje=tipo_mensaje,
                    destinatario=destinatario,
                    estado_envio="ENVIADO_SIMULADO",  # Compatible con CHECK existente en BD
                    detalle=f"[Meta Cloud API OK {msg_id}] {resumen}"[:295],
                    alerta_operativa=False,
                )
            return ResultadoNotificacion(
                canal="WHATSAPP",
                tipo_mensaje=tipo_mensaje,
                destinatario=destinatario,
                estado_envio="FALLO_ALERTA_OPERATIVA",
                detalle=f"AlertaOperativa Meta HTTP {resp.status_code}: {resp.text[:180]}",
                alerta_operativa=True,
            )
        except Exception as exc:
            return ResultadoNotificacion(
                canal="WHATSAPP",
                tipo_mensaje=tipo_mensaje,
                destinatario=destinatario,
                estado_envio="FALLO_ALERTA_OPERATIVA",
                detalle=f"AlertaOperativa conexión Meta: {str(exc)[:180]}",
                alerta_operativa=True,
            )

    def enviar_texto_simple(self, destinatario: str, texto: str) -> ResultadoNotificacion:
        to_num = self._destino(destinatario)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_num,
            "type": "text",
            "text": {"preview_url": False, "body": texto},
        }
        return self._post_meta(payload, "COMPROBANTE", to_num, texto)

    def enviar_comprobante_sin_codigo(self, cita: dict) -> ResultadoNotificacion:
        to_num = self._destino(cita["paciente_telefono"])
        texto = (
            "Fundación Hermandad de Dolores · Comprobante de cita\n\n"
            f"Paciente: {cita['paciente_nombre']} ({cita['paciente_rut']})\n"
            f"Policlínico: {cita['policlinico_nombre']}\n"
            f"Especialidad: {cita['especialidad_nombre']}\n"
            f"Profesional: {cita['profesional_nombre']}\n"
            f"Fecha y hora: {cita['fecha']} a las {cita['hora_inicio']}\n\n"
            "No requiere código de reserva. Presente su cédula de identidad al llegar."
        )
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_num,
            "type": "text",
            "text": {"preview_url": False, "body": texto},
        }
        return self._post_meta(payload, "COMPROBANTE", to_num, f"Comprobante cita #{cita['cita_id']} enviado vía Meta.")

    def enviar_recordatorio(self, cita: dict, tipo: str = "RECORDATORIO_24H") -> ResultadoNotificacion:
        to_num = self._destino(cita["paciente_telefono"])
        if tipo == "RECORDATORIO_15D":
            texto = (
                "Fundación Hermandad de Dolores · Recordatorio anticipado\n\n"
                f"Hola {cita['paciente_nombre']}, te recordamos que tienes una cita agendada con anticipación:\n"
                f"• Fecha y hora: {cita['fecha']} a las {cita['hora_inicio']}\n"
                f"• Policlínico: {cita['policlinico_nombre']}\n"
                f"• Especialidad: {cita['especialidad_nombre']} ({cita['profesional_nombre']})\n\n"
                "El día anterior a tu atención te enviaremos un mensaje con botones para confirmar asistencia."
            )
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to_num,
                "type": "text",
                "text": {"preview_url": False, "body": texto},
            }
            return self._post_meta(payload, "RECORDATORIO_7D", to_num, f"Recordatorio anticipado 15d cita #{cita['cita_id']}.")

        # Recordatorio día anterior (24h) con botones interactivos
        cuerpo = (
            f"Hola {cita['paciente_nombre']}, te recordamos tu cita para el {cita['fecha']} a las {cita['hora_inicio']}.\n\n"
            f"• Policlínico: {cita['policlinico_nombre']}\n"
            f"• Especialidad: {cita['especialidad_nombre']}\n"
            f"• Profesional: {cita['profesional_nombre']}\n\n"
            "Por favor selecciona una opción. Si no respondes, tu cita se mantiene activa."
        )
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_num,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": "Fundación Hermandad de Dolores"},
                "body": {"text": cuerpo},
                "footer": {"text": "Confirmación de asistencia · Sin código de reserva"},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": f"CONFIRMAR_{cita['cita_id']}", "title": "Confirmar asistencia"},
                        },
                        {
                            "type": "reply",
                            "reply": {"id": f"CANCELAR_{cita['cita_id']}", "title": "Cancelar mi hora"},
                        },
                    ]
                },
            },
        }
        return self._post_meta(payload, "RECORDATORIO_24H", to_num, f"Recordatorio 24h con botones cita #{cita['cita_id']}.")

    def enviar_invitacion_encuesta_post_atencion(self, cita: dict) -> ResultadoNotificacion:
        to_num = self._destino(cita["paciente_telefono"])
        texto = (
            f"Gracias por asistir a tu cita del {cita['fecha']} en {cita['policlinico_nombre']}.\n"
            "Tu opinión nos ayuda a mejorar la atención en nuestros policlínicos."
        )
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_num,
            "type": "text",
            "text": {"preview_url": False, "body": texto},
        }
        return self._post_meta(payload, "ENCUESTA_POST_ATENCION", to_num, f"Invitación encuesta post-atención cita #{cita['cita_id']}.")


def crear_notificador_desde_entorno() -> tuple[IGestorNotificaciones, str]:
    token = os.getenv("WHATSAPP_TOKEN", "").strip()
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    if token and phone_id:
        api_ver = os.getenv("WHATSAPP_API_VERSION", "v25.0").strip()
        test_to = os.getenv("WHATSAPP_TEST_TO", "").strip()
        return (
            GestorNotificacionesMetaWhatsApp(token, phone_id, api_ver, test_to),
            "Meta WhatsApp Cloud API (Activo)",
        )
    return GestorNotificacionesSimulado(simular_fallo=False), "Simulado local (Sin token Meta)"
