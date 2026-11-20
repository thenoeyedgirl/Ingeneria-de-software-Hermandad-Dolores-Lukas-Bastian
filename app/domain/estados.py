"""
Patrón State en el Ciclo de Vida de la Cita (M4 — RF09, RF11, RF14, RF15).
Mantiene estrictamente separado el estado administrativo de la cita (IEstadoCita)
del estado de confirmación (EstadoConfirmacion), garantizando la regla RF09:
«El silencio no cancela la cita».
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum


class EstadoConfirmacion(str, Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADA = "CONFIRMADA"
    SIN_RESPUESTA = "SIN_RESPUESTA"
    RECHAZADA = "RECHAZADA"


class ErrorTransicionEstado(ValueError):
    """Error lanzado cuando se intenta una transición no permitida en el ciclo de vida."""


class IEstadoCita(ABC):
    """Interfaz del Patrón State para el estado administrativo de una cita."""

    nombre: str

    @abstractmethod
    def registrar_asistencia(self) -> str:
        ...

    @abstractmethod
    def registrar_inasistencia(self) -> str:
        ...

    @abstractmethod
    def cancelar(self) -> str:
        ...

    def libera_cupo_al_cancelar(self) -> bool:
        return False


class EstadoReservada(IEstadoCita):
    nombre = "RESERVADA"

    def registrar_asistencia(self) -> str:
        return "ASISTIDA"

    def registrar_inasistencia(self) -> str:
        return "INASISTIDA"

    def cancelar(self) -> str:
        return "CANCELADA"

    def libera_cupo_al_cancelar(self) -> bool:
        return True


class EstadoAsistida(IEstadoCita):
    nombre = "ASISTIDA"

    def registrar_asistencia(self) -> str:
        raise ErrorTransicionEstado("La cita ya fue marcada como ASISTIDA.")

    def registrar_inasistencia(self) -> str:
        raise ErrorTransicionEstado("No se puede marcar INASISTIDA una cita ya ASISTIDA.")

    def cancelar(self) -> str:
        raise ErrorTransicionEstado("No se puede cancelar una cita ya ASISTIDA.")


class EstadoInasistida(IEstadoCita):
    nombre = "INASISTIDA"

    def registrar_asistencia(self) -> str:
        raise ErrorTransicionEstado("No se puede marcar ASISTIDA una cita ya cerrada como INASISTIDA.")

    def registrar_inasistencia(self) -> str:
        raise ErrorTransicionEstado("La cita ya fue registrada como INASISTIDA.")

    def cancelar(self) -> str:
        raise ErrorTransicionEstado("No se puede cancelar una cita ya cerrada como INASISTIDA.")


class EstadoCancelada(IEstadoCita):
    nombre = "CANCELADA"

    def registrar_asistencia(self) -> str:
        raise ErrorTransicionEstado("No se puede registrar asistencia en una cita CANCELADA.")

    def registrar_inasistencia(self) -> str:
        raise ErrorTransicionEstado("No se puede registrar inasistencia en una cita CANCELADA.")

    def cancelar(self) -> str:
        raise ErrorTransicionEstado("La cita ya se encuentra CANCELADA.")


_ESTADOS: dict[str, IEstadoCita] = {
    "RESERVADA": EstadoReservada(),
    "ASISTIDA": EstadoAsistida(),
    "INASISTIDA": EstadoInasistida(),
    "CANCELADA": EstadoCancelada(),
}


def obtener_estado_cita(nombre_estado: str) -> IEstadoCita:
    estado = _ESTADOS.get((nombre_estado or "").upper())
    if not estado:
        raise ErrorTransicionEstado(f"Estado de cita desconocido: {nombre_estado}")
    return estado


def aplicar_regla_confirmacion(estado_cita_actual: str, nuevo_estado_confirmacion: EstadoConfirmacion) -> tuple[str, str]:
    """
    Aplica RF09: actualizar la confirmación a PENDIENTE, CONFIRMADA o SIN_RESPUESTA
    JAMÁS cancela automáticamente la cita. Solo RECHAZADA (acción explícita
    «Cancelar mi hora») se tramita mediante el flujo de cancelación.
    """
    if estado_cita_actual != "RESERVADA":
        raise ErrorTransicionEstado(
            f"Solo se puede gestionar confirmación en citas RESERVADAS (actual: {estado_cita_actual})."
        )
    if nuevo_estado_confirmacion == EstadoConfirmacion.SIN_RESPUESTA:
        return ("RESERVADA", EstadoConfirmacion.SIN_RESPUESTA.value)
    if nuevo_estado_confirmacion == EstadoConfirmacion.CONFIRMADA:
        return ("RESERVADA", EstadoConfirmacion.CONFIRMADA.value)
    if nuevo_estado_confirmacion == EstadoConfirmacion.PENDIENTE:
        return ("RESERVADA", EstadoConfirmacion.PENDIENTE.value)
    return ("CANCELADA", EstadoConfirmacion.RECHAZADA.value)
