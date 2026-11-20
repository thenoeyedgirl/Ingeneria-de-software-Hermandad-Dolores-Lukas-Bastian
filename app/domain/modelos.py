"""Modelos Pydantic de entrada y salida para la API REST del MVP."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    clave: str


class PacienteCreate(BaseModel):
    rut: str = Field(..., min_length=8, max_length=15)
    nombre_completo: str = Field(..., min_length=3, max_length=150)
    fecha_nacimiento: Optional[str] = None  # YYYY-MM-DD
    nacionalidad: str = "Chilena"
    telefono: str = Field(..., min_length=6, max_length=30)
    correo: Optional[str] = None
    prevision: str = "FONASA"
    cesfam_origen: Optional[str] = None
    usa_tutor: bool = False
    responsable_nombre: Optional[str] = None
    responsable_parentesco: Optional[str] = None
    responsable_telefono: Optional[str] = None
    responsable_correo: Optional[str] = None
    tipo_documento: Optional[str] = None  # FONASA | CESFAM | OTRO
    folio_documento: Optional[str] = None
    consentimiento_datos: bool = True


class CitaCreate(BaseModel):
    paciente_rut: str
    bloque_id: int
    canal_registro: str = "ASISTIDO_PRESENCIAL"
    orden_medica_id: Optional[int] = None
    usuario_id: Optional[int] = None
    usuario_nombre: str = "TENS/TONS Demo"
    rol: str = "TENS_TONS"


class SolicitudPacienteCreate(BaseModel):
    rut: str
    nombre_completo: str
    fecha_nacimiento: Optional[str] = None
    nacionalidad: str = "Chilena"
    telefono: str
    correo: Optional[str] = None
    prevision: str = "FONASA"
    policlinico_id: int
    especialidad_id: int
    bloque_preferido_id: Optional[int] = None
    usa_tutor: bool = False
    responsable_nombre: Optional[str] = None
    responsable_parentesco: Optional[str] = None
    responsable_telefono: Optional[str] = None
    responsable_correo: Optional[str] = None
    tipo_documento: Optional[str] = None
    folio_documento: Optional[str] = None
    observacion: Optional[str] = None


class ConfirmacionUpdate(BaseModel):
    estado_confirmacion: str  # CONFIRMADA | SIN_RESPUESTA | RECHAZADA
    canal: str = "TELEFONO"
    observacion: Optional[str] = None
    usuario_id: Optional[int] = None
    usuario_nombre: str = "TENS/TONS Demo"
    rol: str = "TENS_TONS"


class CancelacionRequest(BaseModel):
    origen_cancelacion: str = "ASISTIDA_TENS"
    motivo: str = "Cancelación solicitada por paciente"
    usuario_id: Optional[int] = None
    usuario_nombre: str = "TENS/TONS Demo"
    rol: str = "TENS_TONS"


class AsistenciaRequest(BaseModel):
    asistio: bool
    observacion: Optional[str] = None
    usuario_id: Optional[int] = None
    usuario_nombre: str = "TENS/TONS Demo"
    rol: str = "TENS_TONS"


class ListaEsperaCreate(BaseModel):
    paciente_rut: str
    policlinico_id: int
    especialidad_id: int
    prioridad: str = "NORMAL"
    observacion: Optional[str] = None
    usuario_id: Optional[int] = None
    usuario_nombre: str = "TENS/TONS Demo"
    rol: str = "TENS_TONS"


class ListaEsperaEstadoUpdate(BaseModel):
    estado: str
    observacion: Optional[str] = None
    usuario_nombre: str = "TENS/TONS Demo"
    rol: str = "TENS_TONS"


class BloqueCreate(BaseModel):
    policlinico_id: int
    especialidad_id: int
    profesional_id: int
    fecha: str
    hora_inicio: str
    hora_fin: str
    publicado: bool = True
    usuario_nombre: str = "Administración Central (Demo)"


class BloqueEstadoUpdate(BaseModel):
    estado_bloque: str
    motivo: Optional[str] = None
    usuario_nombre: str = "Administración Central (Demo)"


class EncuestaCreate(BaseModel):
    cita_id: Optional[int] = None
    tipo: str
    puntaje: int = Field(..., ge=1, le=5)
    comentario: Optional[str] = None
