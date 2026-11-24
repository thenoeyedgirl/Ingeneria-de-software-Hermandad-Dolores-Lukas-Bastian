"""
Utilidades de reportería (F6 · RF20–RF23, RNF03).
Filtros del dataset, tramos etarios y columnas del CSV exportable. Sin datos personales del paciente.
"""

from __future__ import annotations
from datetime import date
from typing import Any, Optional

ESTADOS_CITA = ("RESERVADA", "ASISTIDA", "INASISTIDA", "CANCELADA")
CANALES = ("ASISTIDO_PRESENCIAL", "ASISTIDO_TELEFONO", "SOLICITUD_WEB")
MODALIDADES = ("PRESENCIAL", "TELEMEDICINA")
TIPOS_FECHA = ("cita", "solicitud")

# Campos que el dataset NUNCA debe exponer (RNF03). Los usa también la prueba automatizada.
CAMPOS_PROHIBIDOS = ("rut", "paciente_rut", "paciente_nombre", "nombre_completo", "telefono", "paciente_telefono", "correo")

# Columnas del CSV: (clave del dataset, encabezado en español)
COLUMNAS_CSV = [
    ("cita_id", "ID cita"),
    ("fecha_cita", "Fecha de la cita"),
    ("hora_inicio", "Hora de inicio"),
    ("fecha_solicitud", "Fecha en que se pidió la hora"),
    ("estado_cita", "Estado de la cita"),
    ("estado_confirmacion", "Estado de confirmación"),
    ("canal_registro", "Canal de registro"),
    ("origen_cancelacion", "Origen de la cancelación"),
    ("policlinico_nombre", "Policlínico"),
    ("modalidad", "Modalidad"),
    ("especialidad_nombre", "Especialidad"),
    ("profesional_nombre", "Profesional"),
    ("tramo_etario", "Tramo etario"),
    ("nacionalidad", "Nacionalidad"),
]


def tramo_etario(fecha_nacimiento: Optional[str], hoy: Optional[date] = None) -> str:
    """Mismos tramos que obtener_reportes / v_reporte_citas; 'Sin dato' si falta la fecha."""
    if not fecha_nacimiento:
        return "Sin dato"
    hoy = hoy or date.today()
    try:
        nac = date.fromisoformat(str(fecha_nacimiento)[:10])
    except ValueError:
        return "Sin dato"
    edad = hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))
    if edad < 18:
        return "0–17 años"
    if edad <= 35:
        return "18–35 años"
    if edad <= 59:
        return "36–59 años"
    return "60+ años"


def normalizar_filtros(
    desde: Optional[str], hasta: Optional[str], tipo_fecha: Optional[str], policlinico_id: Optional[int],
    modalidad: Optional[str], especialidad_id: Optional[int], profesional_id: Optional[int],
    estado_cita: Optional[str], canal_registro: Optional[str],
) -> dict[str, Any]:
    """Valida y normaliza los filtros. Lanza ValueError con un mensaje claro (la API lo traduce a HTTP 400)."""
    f: dict[str, Any] = {"tipo_fecha": (tipo_fecha or "cita").strip().lower()}
    if f["tipo_fecha"] not in TIPOS_FECHA:
        raise ValueError("tipo_fecha debe ser 'cita' o 'solicitud'.")
    fechas: dict[str, date] = {}
    for nombre, valor in (("desde", desde), ("hasta", hasta)):
        if valor:
            try:
                fechas[nombre] = date.fromisoformat(valor.strip())
            except ValueError:
                raise ValueError(f"'{nombre}' debe tener formato AAAA-MM-DD.")
            f[nombre] = fechas[nombre].isoformat()
    if "desde" in fechas and "hasta" in fechas and fechas["desde"] > fechas["hasta"]:
        raise ValueError("'desde' no puede ser posterior a 'hasta'.")
    for nombre, valor in (("policlinico_id", policlinico_id), ("especialidad_id", especialidad_id), ("profesional_id", profesional_id)):
        if valor is not None:
            f[nombre] = int(valor)
    for nombre, valor, validos in (
        ("modalidad", modalidad, MODALIDADES), ("estado_cita", estado_cita, ESTADOS_CITA), ("canal_registro", canal_registro, CANALES),
    ):
        if valor:
            v = valor.strip().upper()
            if v not in validos:
                raise ValueError(f"'{nombre}' inválido. Valores permitidos: {', '.join(validos)}.")
            f[nombre] = v
    return f


def celda_csv_segura(valor: Any) -> Any:
    """Evita inyección de fórmulas al abrir el CSV en Excel (= + - @ al inicio de un texto)."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return "" if valor is None else valor
