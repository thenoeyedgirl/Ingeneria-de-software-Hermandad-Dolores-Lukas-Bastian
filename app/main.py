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

from datetime import date, timedelta
from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
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
from app.services.notificaciones import GestorNotificacionesSimulado, crear_notificador_desde_entorno
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

    if repo is None:
        notificador, modo_wa = crear_notificador_desde_entorno()
    else:
        notificador, modo_wa = GestorNotificacionesSimulado(simular_fallo=False), "Simulado (Pruebas)"
    servicio = ServicioAgendamiento(repo_inst, notificador)
    app.state.repo = repo_inst
    app.state.servicio = servicio
    app.state.notificador = notificador
    app.state.modo_repo = modo_repo
    app.state.modo_wa = modo_wa

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
            "whatsapp": app.state.modo_wa,
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

    # --- M5: Recordatorios WhatsApp (24h con botones y 15d anticipado) + Webhook Meta ---
    @app.post("/api/citas/{cita_id}/recordatorio-whatsapp")
    def enviar_recordatorio_whatsapp(cita_id: int, payload: dict = Body(default={"tipo": "RECORDATORIO_24H"})):
        cita = app.state.repo.obtener_cita(cita_id)
        if not cita:
            raise HTTPException(status_code=404, detail="Cita no encontrada.")
        tipo = (payload.get("tipo") or "RECORDATORIO_24H").upper()
        if tipo not in ("RECORDATORIO_24H", "RECORDATORIO_15D"):
            raise HTTPException(status_code=400, detail="Tipo de recordatorio inválido (use RECORDATORIO_24H o RECORDATORIO_15D).")
        notif = app.state.notificador.enviar_recordatorio(cita, tipo=tipo)
        app.state.repo.registrar_notificacion(
            cita_id, notif.canal, notif.tipo_mensaje, notif.destinatario, notif.estado_envio, notif.detalle
        )
        return {
            "cita_id": cita_id,
            "tipo": tipo,
            "modo_whatsapp": app.state.modo_wa,
            "estado_envio": notif.estado_envio,
            "alerta_operativa": notif.alerta_operativa,
            "detalle": notif.detalle,
        }

    @app.post("/api/whatsapp/ejecutar-recordatorios")
    def ejecutar_barrido_recordatorios():
        hoy = date.today()
        manana = (hoy + timedelta(days=1)).isoformat()
        en_15d = (hoy + timedelta(days=15)).isoformat()
        en_7d = (hoy + timedelta(days=7)).isoformat()
        citas_res = app.state.repo.listar_citas(estado_cita="RESERVADA")
        enviados = []
        for c in citas_res:
            if c["fecha"] == manana and c["estado_confirmacion"] in ("PENDIENTE", "SIN_RESPUESTA"):
                n = app.state.notificador.enviar_recordatorio(c, tipo="RECORDATORIO_24H")
                app.state.repo.registrar_notificacion(c["cita_id"], n.canal, n.tipo_mensaje, n.destinatario, n.estado_envio, n.detalle)
                enviados.append({"cita_id": c["cita_id"], "tipo": "RECORDATORIO_24H", "alerta": n.alerta_operativa})
            elif c["fecha"] in (en_15d, en_7d):
                n = app.state.notificador.enviar_recordatorio(c, tipo="RECORDATORIO_15D")
                app.state.repo.registrar_notificacion(c["cita_id"], n.canal, n.tipo_mensaje, n.destinatario, n.estado_envio, n.detalle)
                enviados.append({"cita_id": c["cita_id"], "tipo": "RECORDATORIO_15D", "alerta": n.alerta_operativa})
        return {"fecha_referencia": hoy.isoformat(), "procesados": len(enviados), "detalle": enviados}


    @app.post("/api/citas/{cita_id}/mensaje-whatsapp")
    def enviar_mensaje_manual_whatsapp(cita_id: int, payload: dict = Body(...)):
        cita = app.state.repo.obtener_cita(cita_id)
        if not cita:
            raise HTTPException(status_code=404, detail="Cita no encontrada.")
        texto = (payload.get("mensaje") or "").strip()
        if not texto:
            raise HTTPException(status_code=400, detail="Escribe un mensaje de texto antes de enviar.")
        cuerpo = f"Fundación Hermandad de Dolores ({cita['policlinico_nombre']}): {texto}"
        notif = app.state.notificador.enviar_texto_simple(cita["paciente_telefono"], cuerpo)
        app.state.repo.registrar_notificacion(
            cita_id, notif.canal, "CAMBIO_AGENDA", notif.destinatario, notif.estado_envio, f"[MANUAL] {texto}"[:295]
        )
        return {
            "cita_id": cita_id,
            "modo_whatsapp": app.state.modo_wa,
            "estado_envio": notif.estado_envio,
            "alerta_operativa": notif.alerta_operativa,
            "detalle": notif.detalle,
        }

    @app.get("/api/whatsapp/mensajes")
    def listar_mensajes_whatsapp(policlinico_id: Optional[int] = None, rut: Optional[str] = None):
        return app.state.repo.listar_mensajes_whatsapp(policlinico_id=policlinico_id, rut=rut)

    @app.post("/api/whatsapp/suscribir-waba")
    def suscribir_waba_meta(payload: dict = Body(default={})):
        import httpx as _httpx
        token = os.getenv("WHATSAPP_TOKEN", "").strip()
        waba_id = (payload.get("waba_id") or os.getenv("WHATSAPP_WABA_ID", "1051254647997426")).strip()
        api_ver = os.getenv("WHATSAPP_API_VERSION", "v25.0").strip()
        if not token:
            raise HTTPException(status_code=400, detail="No hay WHATSAPP_TOKEN configurado en .env.")
        url = f"https://graph.facebook.com/{api_ver}/{waba_id}/subscribed_apps"
        try:
            with _httpx.Client(timeout=15.0) as client:
                r = client.post(url, headers={"Authorization": f"Bearer {token}"})
            return {"status_code": r.status_code, "waba_id": waba_id, "respuesta": r.json()}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error suscribiendo WABA en Meta: {exc}")

    @app.get("/webhook", include_in_schema=True)
    def verificar_webhook_meta(
        hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
        hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
        hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
    ):
        esperado = os.getenv("WHATSAPP_VERIFY_TOKEN", "hermandad_dolores_webhook_2026").strip()
        if hub_mode == "subscribe" and hub_verify_token == esperado and hub_challenge is not None:
            return PlainTextResponse(content=hub_challenge, status_code=200)
        raise HTTPException(status_code=403, detail="Token de verificación webhook inválido.")

    @app.post("/webhook", include_in_schema=True)
    async def recibir_webhook_meta(request: Request):
        body = await request.json()
        acciones_procesadas = []
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    remitente = msg.get("from", "")
                    mtype = msg.get("type", "")
                    accion_id = ""
                    texto_entrante = ""
                    if mtype == "interactive":
                        br = msg.get("interactive", {}).get("button_reply", {})
                        accion_id = br.get("id", "")
                        texto_entrante = f"Botón: {br.get('title', accion_id)}"
                    elif mtype == "button":
                        accion_id = msg.get("button", {}).get("payload", "")
                        texto_entrante = f"Botón: {msg.get('button', {}).get('text', accion_id)}"
                    elif mtype == "text":
                        texto_entrante = msg.get("text", {}).get("body", "").strip()
                    else:
                        texto_entrante = f"[{mtype or 'archivo'} no soportado por este canal]"
                        app.state.notificador.enviar_texto_simple(
                            remitente,
                            "Por este canal solo recibimos mensajes de texto o selección de botones. Para documentos FONASA/CESFAM, ingrésalos como folio en el portal o preséntalos en tu policlínico.",
                        )

                    print(f"[WEBHOOK META] De={remitente} Tipo={mtype} Texto={texto_entrante}")
                    if texto_entrante:
                        app.state.repo.registrar_notificacion(
                            None, "WHATSAPP", "CAMBIO_AGENDA", remitente, "ENVIADO_SIMULADO", f"[RECIBIDO] {texto_entrante}"[:295]
                        )

                    if accion_id.startswith("CONFIRMAR_"):
                        cita_id = int(accion_id.split("_", 1)[1])
                        try:
                            cita = app.state.servicio.actualizar_confirmacion_cita(
                                cita_id,
                                {
                                    "estado_confirmacion": "CONFIRMADA",
                                    "canal": "WHATSAPP",
                                    "observacion": "Paciente presionó «Confirmar asistencia» en WhatsApp.",
                                    "usuario_nombre": "Bot WhatsApp (Paciente)",
                                    "rol": "PACIENTE",
                                },
                            )
                            app.state.notificador.enviar_texto_simple(
                                remitente,
                                f"¡Gracias! Tu asistencia para el {cita['fecha']} a las {cita['hora_inicio']} en {cita['policlinico_nombre']} quedó confirmada.",
                            )
                            acciones_procesadas.append({"cita_id": cita_id, "accion": "CONFIRMADA"})
                        except Exception as exc:
                            acciones_procesadas.append({"cita_id": cita_id, "error": str(exc)})

                    elif accion_id.startswith("CANCELAR_"):
                        cita_id = int(accion_id.split("_", 1)[1])
                        try:
                            cita = app.state.servicio.cancelar_cita(
                                cita_id,
                                {
                                    "origen_cancelacion": "WHATSAPP_PACIENTE",
                                    "motivo": "Paciente seleccionó «Cancelar mi hora» mediante botón de WhatsApp.",
                                    "usuario_nombre": "Bot WhatsApp (Paciente)",
                                    "rol": "PACIENTE",
                                },
                            )
                            app.state.notificador.enviar_texto_simple(
                                remitente,
                                f"Tu cita del {cita['fecha']} a las {cita['hora_inicio']} en {cita['policlinico_nombre']} fue cancelada y el cupo quedó liberado.",
                            )
                            acciones_procesadas.append({"cita_id": cita_id, "accion": "CANCELADA"})
                        except Exception as exc:
                            acciones_procesadas.append({"cita_id": cita_id, "error": str(exc)})
        return {"status": "ok", "acciones": acciones_procesadas}

    return app


app = crear_app()
