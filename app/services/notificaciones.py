"""
Abstracción desacoplada IGestorNotificaciones (RF07, RF08, RF28, RF30).
En la entrega local reproducible simula el envío de comprobantes sin código,
recordatorios e invitaciones a encuesta sin depender de APIs externas pagas.
Si un canal externo falla, emite una AlertaOperativa sin perder la cita.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


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


class GestorNotificacionesSimulado(IGestorNotificaciones):
    """Implementación local demostrativa (sin cobros ni credenciales externas)."""

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
        # RF28: Comprobante claro SIN código de reserva (P6 descartado)
        texto = (
            f"Comprobante administrativo (sin código): {cita['paciente_nombre']} ({cita['paciente_rut']}) · "
            f"{cita['policlinico_nombre']} · {cita['especialidad_nombre']} · "
            f"{cita['profesional_nombre']} · {cita['fecha']} {cita['hora_inicio']}."
        )
        return self._despachar("WHATSAPP", "COMPROBANTE", cita["paciente_telefono"], texto)

    def enviar_recordatorio(self, cita: dict, tipo: str = "RECORDATORIO_24H") -> ResultadoNotificacion:
        texto = (
            f"Recordatorio {tipo}: cita el {cita['fecha']} a las {cita['hora_inicio']} en "
            f"{cita['policlinico_nombre']}. Opciones: [Confirmar] / [Cancelar mi hora]. "
            "Si no responde, su cita se mantiene activa (RF09)."
        )
        return self._despachar("WHATSAPP", tipo, cita["paciente_telefono"], texto)

    def enviar_invitacion_encuesta_post_atencion(self, cita: dict) -> ResultadoNotificacion:
        texto = (
            f"Encuesta post-atención (RF30): agradecemos evaluar su atención del {cita['fecha']} "
            f"en {cita['policlinico_nombre']}."
        )
        return self._despachar("WHATSAPP", "ENCUESTA_POST_ATENCION", cita["paciente_telefono"], texto)
