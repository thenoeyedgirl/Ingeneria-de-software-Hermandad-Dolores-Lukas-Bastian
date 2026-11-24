"""
Interfaces del Patrón Repository (M4 — Actividad Clases y Patrones):
IRepositorioCita e IRepositorioCupo.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional


class ErrorRecursoNoEncontrado(LookupError):
    """Lanzado cuando no existe el registro solicitado."""


class ErrorConflictoCupo(RuntimeError):
    """Lanzado cuando un bloque horario ya está ocupado o bloqueado (RNF04)."""


class IRepositorioCupo(ABC):
    @abstractmethod
    def listar_policlinicos(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def listar_especialidades(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def listar_profesionales(self, policlinico_id: Optional[int] = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def listar_bloques(
        self,
        policlinico_id: Optional[int] = None,
        especialidad_id: Optional[int] = None,
        solo_disponibles: bool = False,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def crear_bloque(self, datos: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def actualizar_estado_bloque(self, bloque_id: int, estado_bloque: str, usuario_nombre: str, motivo: str) -> dict[str, Any]:
        ...


class IRepositorioCita(IRepositorioCupo, ABC):
    @abstractmethod
    def autenticar_usuario(self, username: str, clave: str) -> Optional[dict[str, Any]]:
        ...

    @abstractmethod
    def listar_usuarios_demo(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def buscar_paciente_por_rut(self, rut_formateado: str) -> Optional[dict[str, Any]]:
        ...

    @abstractmethod
    def listar_pacientes(self, busqueda: Optional[str] = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def crear_o_actualizar_paciente(self, datos: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def listar_citas(
        self,
        policlinico_id: Optional[int] = None,
        estado_cita: Optional[str] = None,
        rut_formateado: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def obtener_cita(self, cita_id: int) -> Optional[dict[str, Any]]:
        ...

    @abstractmethod
    def crear_cita_transaccional(self, datos: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def cancelar_cita_transaccional(
        self,
        cita_id: int,
        origen_cancelacion: str,
        motivo: str,
        usuario_id: Optional[int],
        usuario_nombre: str,
        rol: str,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    def registrar_asistencia(
        self,
        cita_id: int,
        nuevo_estado_cita: str,
        observacion: str,
        usuario_id: Optional[int],
        usuario_nombre: str,
        rol: str,
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    def listar_pendientes_confirmacion(self, policlinico_id: Optional[int] = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def listar_lista_espera(self, policlinico_id: Optional[int] = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def agregar_lista_espera(self, datos: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def actualizar_lista_espera(self, item_id: int, estado: str, observacion: Optional[str], usuario_nombre: str, rol: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def registrar_notificacion(self, cita_id: Optional[int], canal: str, tipo_mensaje: str, destinatario: str, estado_envio: str, detalle: str) -> None:
        ...

    @abstractmethod
    def registrar_encuesta(self, cita_id: Optional[int], tipo: str, puntaje: int, comentario: Optional[str]) -> dict[str, Any]:
        ...

    @abstractmethod
    def listar_mensajes_whatsapp(self, policlinico_id: Optional[int] = None, rut: Optional[str] = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def obtener_reportes(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def listar_auditoria(self, limite: int = 40) -> list[dict[str, Any]]:
        ...

    # --- Gráficos y filtros de reportes (RF19–RF23, RNF03) ---
    @abstractmethod
    def obtener_dataset_reportes(self, filtros: dict[str, Any]) -> dict[str, Any]:
        """Filas filtradas SIN datos personales para los gráficos y el CSV. Devuelve {citas, bloques, encuestas, catalogos}."""
        ...

    @abstractmethod
    def registrar_auditoria(
        self, usuario_nombre: str, rol: str, policlinico_id: Optional[int], operacion: str, entidad: str, entidad_id: Optional[int], detalle: str
    ) -> None:
        """Inserta un registro en la auditoría administrativa (p. ej. REPORTE_EXPORTAR, RF23/RF34)."""
        ...
