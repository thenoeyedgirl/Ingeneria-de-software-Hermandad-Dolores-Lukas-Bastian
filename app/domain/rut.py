"""Validación y normalización de RUT chileno (Módulo 11) — RF01."""

from __future__ import annotations
import re


def limpiar_rut(rut: str) -> str:
    """Elimina puntos, espacios y guiones; retorna cuerpo + dígito verificador en mayúscula."""
    return re.sub(r"[^0-9kK]", "", (rut or "").strip()).upper()


def calcular_dv(cuerpo: str) -> str:
    """Calcula el dígito verificador chileno mediante algoritmo módulo 11."""
    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - (suma % 11)
    if resto == 11:
        return "0"
    if resto == 10:
        return "K"
    return str(resto)


def validar_rut(rut: str) -> bool:
    """Retorna True si el RUT cumple formato y dígito verificador módulo 11."""
    limpio = limpiar_rut(rut)
    if len(limpio) < 8 or len(limpio) > 9:
        return False
    cuerpo, dv = limpio[:-1], limpio[-1]
    if not cuerpo.isdigit():
        return False
    return calcular_dv(cuerpo) == dv


def formatear_rut(rut: str) -> str:
    """Normaliza un RUT válido a formato XX.XXX.XXX-D."""
    limpio = limpiar_rut(rut)
    if not validar_rut(limpio):
        raise ValueError(f"RUT inválido según módulo 11: {rut}")
    cuerpo, dv = limpio[:-1], limpio[-1]
    partes = []
    while len(cuerpo) > 3:
        partes.insert(0, cuerpo[-3:])
        cuerpo = cuerpo[:-3]
    if cuerpo:
        partes.insert(0, cuerpo)
    return f"{'.'.join(partes)}-{dv}"


def enmascarar_nombre(nombre_completo: str) -> str:
    """Enmascara apellidos para consulta por RUT en solo lectura (control de privacidad P10 / RF29)."""
    partes = [p for p in (nombre_completo or "").strip().split() if p]
    if not partes:
        return "***"
    if len(partes) == 1:
        return partes[0][0] + "***"
    return f"{partes[0]} " + " ".join(f"{p[0]}***" for p in partes[1:])
