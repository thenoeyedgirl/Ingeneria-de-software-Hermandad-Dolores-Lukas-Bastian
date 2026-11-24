"""
Demostración en vivo de RNF04 (0 dobles reservas) contra PostgreSQL real.

Lanza 5 reservas SIMULTÁNEAS sobre el mismo bloque horario con 5 pacientes distintos.
Resultado esperado: exactamente 1 cita creada (201) y 4 rechazos controlados (409).

Uso (con el servidor corriendo en otra terminal):
    python demo_concurrencia.py
"""
import concurrent.futures as cf
import sys

import httpx

BASE = "http://127.0.0.1:8000"
RUTS = ["14.567.890-0", "19.876.543-0", "13.246.810-9", "11.222.333-9", "14.666.777-5"]

bloques = httpx.get(f"{BASE}/api/bloques", params={"solo_disponibles": True}).json()
if not bloques:
    sys.exit("No hay bloques disponibles: recarga los scripts SQL de la base de datos.")
b = bloques[-1]
print(f"\nBloque elegido: #{b['id']} · {b['fecha']} {b['hora_inicio']} · {b['policlinico_nombre']} · {b['profesional_nombre']}")
print(f"Enviando {len(RUTS)} reservas simultáneas sobre el MISMO bloque...\n")


def reservar(rut):
    r = httpx.post(f"{BASE}/api/citas", json={"paciente_rut": rut, "bloque_id": b["id"]}, timeout=10)
    return rut, r.status_code, r.json().get("detail", "Cita creada")


with cf.ThreadPoolExecutor(len(RUTS)) as ex:
    resultados = list(ex.map(reservar, RUTS))

for rut, status, msg in resultados:
    marca = "OK      " if status == 201 else "RECHAZO "
    print(f"  {marca} {rut:>13}  HTTP {status}  {msg}")

creadas = sum(1 for _, s, _ in resultados if s == 201)
print(f"\nResultado: {creadas} cita creada, {len(RUTS) - creadas} rechazos -> "
      f"{'0 dobles reservas (RNF04 cumple)' if creadas == 1 else 'REVISAR'}\n")
