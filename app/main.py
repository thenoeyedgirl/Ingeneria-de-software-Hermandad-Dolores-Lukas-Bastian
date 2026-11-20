"""
Aplicación Web FastAPI — MVP Fase 1
Sistema de Gestión de Citas y Operación Administrativa para Policlínicos
Fundación Hermandad de Dolores · Equipo: Bastián Ignacio Fariña y Lukas Garrido (Patrocina: UDD)
"""

from __future__ import annotations
import csv
import io
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.domain.estados import ErrorTransicionEstado
from app.domain.modelos import (
    AsistenciaRequest,
    BloqueCreate,
    BloqueEstadoUpdate,
    CancelacionRequest,
    CitaCreate,
    ConfirmacionUpdate,
    EncuestaCreate,
    ListaEsperaCreate,
    ListaEsperaEstadoUpdate,
    LoginRequest,
    PacienteCreate,
    SolicitudPacienteCreate,
)
from app.repositories.interfaces import (
    ErrorConflictoCupo,
    ErrorRecursoNoEncontrado,
    IRepositorioCita,
)
from app.repositories.repositorio_memoria import RepositorioCitaMemoria
from app.services.notificaciones import GestorNotificacionesSimulado
from app.services.servicio_agendamiento import ServicioAgendamiento



def _to_dict(model) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def crear_repositorio() -> tuple[IRepositorioCita, str]:
    usar_memoria = os.getenv("USE_MEMORY_REPO", "false").lower() in ("1", "true", "yes")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if usar_memoria or not database_url:
        return RepositorioCitaMemoria(), "MEMORIA (Pruebas / Demo sin BD)"
    from app.repositories.repositorio_sql import RepositorioCitaSQL
    return RepositorioCitaSQL(database_url), "PostgreSQL 16 (RepositorioCitaSQL)"


def crear_app(repo: Optional[IRepositorioCita] = None) -> FastAPI:
    app = FastAPI(
        title="Sistema de Gestión de Citas — Fundación Hermandad de Dolores",
        description="MVP Fase 1 (Arquitectura en Capas · FastAPI + PostgreSQL 16). Sin ficha clínica ni código de reserva.",
        version="1.0.0",
    )

    if repo is None:
        repo_inst, modo_repo = crear_repositorio()
    else:
        repo_inst, modo_repo = repo, "INYECTADO (Pruebas)"

    notificador = GestorNotificacionesSimulado(simular_fallo=False)
    servicio = ServicioAgendamiento(repo_inst, notificador)
    app.state.repo = repo_inst
    app.state.servicio = servicio
    app.state.modo_repo = modo_repo

    web_dir = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def inicio():
        return FileResponse(str(web_dir / "index.html"))

    @app.get("/api/salud")
    def salud():
        return {
            "estado": "ok",
            "proyecto": "Fundación Hermandad de Dolores — MVP Fase 1",
            "repositorio": app.state.modo_repo,
            "datos": "100 % ficticios para demostración local reproducible",
        }

    # --- Autenticación demostrativa (RBAC) ---
    @app.get("/api/auth/usuarios-demo")
    def usuarios_demo():
        return app.state.repo.listar_usuarios_demo()

    @app.post("/api/auth/login")
    def login(payload: LoginRequest):
        usuario = app.state.repo.autenticar_usuario(payload.username, payload.clave)
        if not usuario:
            raise HTTPException(status_code=401, detail="Credenciales inválidas (ver usuarios demo en pantalla).")
        return usuario

    # --- Catálogos ---
    @app.get("/api/catalogos")
    def catalogos():
        return {
            "policlinicos": app.state.repo.listar_policlinicos(),
            "especialidades": app.state.repo.listar_especialidades(),
            "profesionales": app.state.repo.listar_profesionales(),
        }

    # --- M1: Pacientes (RF01, RF02, RF18) ---
    @app.get("/api/pacientes")
    def listar_pacientes(q: Optional[str] = None):
        return app.state.repo.listar_pacientes(q)

    @app.get("/api/pacientes/buscar")
    def buscar_paciente(rut: str = Query(...)):
        try:
            pac = app.state.servicio.buscar_paciente(rut)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not pac:
            raise HTTPException(status_code=404, detail="Paciente no encontrado para el RUT ingresado.")
        return pac

    @app.post("/api/pacientes", status_code=201)
    def crear_paciente(payload: PacienteCreate):
        try:
            return app.state.servicio.registrar_o_actualizar_paciente(_to_dict(payload))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # --- Portal Pacientes (RF03, RF29 con P10, solicitud asistida) ---
    @app.get("/api/publico/verificar-documento")
    def verificar_documento_previo(rut: str = Query(...)):
        try:
            return app.state.servicio.verificar_documento_previo(rut)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/publico/consulta-rut")
    def consulta_rut_solo_lectura(rut: str = Query(...)):
        try:
            return app.state.servicio.consultar_estado_por_rut_solo_lectura(rut)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/publico/solicitud", status_code=201)
    def crear_solicitud_paciente(payload: SolicitudPacienteCreate):
        try:
            return app.state.servicio.registrar_solicitud_paciente(_to_dict(payload))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # --- M3: Bloques y Agendas (RF03, RF12, RF13) ---
    @app.get("/api/bloques")
    def listar_bloques(
        policlinico_id: Optional[int] = None,
        especialidad_id: Optional[int] = None,
        solo_disponibles: bool = False,
    ):
        return app.state.repo.listar_bloques(policlinico_id, especialidad_id, solo_disponibles)

    @app.post("/api/bloques", status_code=201)
    def crear_bloque(payload: BloqueCreate):
        try:
            return app.state.repo.crear_bloque(_to_dict(payload))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"No fue posible crear el bloque: {exc}")

    @app.patch("/api/bloques/{bloque_id}/estado")
    def actualizar_bloque(bloque_id: int, payload: BloqueEstadoUpdate):
        try:
            return app.state.repo.actualizar_estado_bloque(
                bloque_id,
                payload.estado_bloque,
                payload.usuario_nombre,
                payload.motivo or "Ajuste de agenda administrativa",
            )
        except ErrorRecursoNoEncontrado as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    # --- M4: Citas, Confirmaciones, Cancelación y Asistencia ---
    @app.get("/api/citas")
    def listar_citas(policlinico_id: Optional[int] = None, estado_cita: Optional[str] = None):
        return app.state.repo.listar_citas(policlinico_id=policlinico_id, estado_cita=estado_cita)

    @app.post("/api/citas", status_code=201)
    def crear_cita(payload: CitaCreate):
        try:
            return app.state.servicio.agendar_cita_asistida(_to_dict(payload))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except ErrorRecursoNoEncontrado as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ErrorConflictoCupo as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.get("/api/citas/pendientes-confirmacion")
    def pendientes_confirmacion(policlinico_id: Optional[int] = None):
        return app.state.repo.listar_pendientes_confirmacion(policlinico_id)

    @app.patch("/api/citas/{cita_id}/confirmacion")
    def actualizar_confirmacion(cita_id: int, payload: ConfirmacionUpdate):
        try:
            return app.state.servicio.actualizar_confirmacion_cita(cita_id, _to_dict(payload))
        except ErrorRecursoNoEncontrado as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except (ValueError, ErrorTransicionEstado) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/citas/{cita_id}/cancelar")
    def cancelar_cita(cita_id: int, payload: CancelacionRequest):
        try:
            return app.state.servicio.cancelar_cita(cita_id, _to_dict(payload))
        except ErrorRecursoNoEncontrado as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ErrorTransicionEstado as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/citas/{cita_id}/asistencia")
    def registrar_asistencia(cita_id: int, payload: AsistenciaRequest):
        try:
            return app.state.servicio.registrar_asistencia_cita(cita_id, _to_dict(payload))
        except ErrorRecursoNoEncontrado as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ErrorTransicionEstado as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # --- M5: Lista de Espera Asistida (RF06, RF35) ---
    @app.get("/api/lista-espera")
    def listar_lista_espera(policlinico_id: Optional[int] = None):
        return app.state.repo.listar_lista_espera(policlinico_id)

    @app.post("/api/lista-espera", status_code=201)
    def agregar_lista_espera(payload: ListaEsperaCreate):
        try:
            return app.state.servicio.agregar_a_lista_espera(_to_dict(payload))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except ErrorRecursoNoEncontrado as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.patch("/api/lista-espera/{item_id}")
    def actualizar_lista_espera(item_id: int, payload: ListaEsperaEstadoUpdate):
        try:
            return app.state.repo.actualizar_lista_espera(
                item_id, payload.estado, payload.observacion, payload.usuario_nombre, payload.rol
            )
        except ErrorRecursoNoEncontrado as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    # --- Encuestas diferenciadas (RF30 y RF36) ---
    @app.post("/api/encuestas", status_code=201)
    def crear_encuesta(payload: EncuestaCreate):
        if payload.tipo not in ("AGENDAMIENTO_WEB", "POST_ATENCION"):
            raise HTTPException(status_code=400, detail="Tipo de encuesta inválido.")
        return app.state.repo.registrar_encuesta(payload.cita_id, payload.tipo, payload.puntaje, payload.comentario)

    # --- M8: Reportes, Exportación CSV y Auditoría (RF19–RF23, RF34) ---
    @app.get("/api/reportes")
    def reportes():
        return app.state.repo.obtener_reportes()

    @app.get("/api/reportes/exportar-csv")
    def exportar_reportes_csv():
        data = app.state.repo.obtener_reportes()["indicadores_por_sede"]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Policlínico", "Modalidad", "Total Citas", "Reservadas",
            "Asistidas", "Inasistidas", "Canceladas", "Pendientes Confirmación", "Tasa Asistencia (%)"
        ])
        for r in data:
            writer.writerow([
                r["policlinico_nombre"], r["modalidad"], r["total_citas"], r["reservadas"],
                r["asistidas"], r["inasistidas"], r["canceladas"], r["pendientes_confirmacion"], r["tasa_asistencia_pct"]
            ])
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=reporte_indicadores_hermandad_dolores.csv"},
        )

    @app.get("/api/auditoria")
    def auditoria(limite: int = 40):
        return app.state.repo.listar_auditoria(limite)

    return app


app = crear_app()
