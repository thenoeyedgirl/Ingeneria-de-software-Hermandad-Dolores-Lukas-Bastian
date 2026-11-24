# Sistema de Gestión de Citas y Operación Administrativa para Policlínicos

**Mandante:** Fundación Hermandad de Dolores (6 policlínicos presenciales + Telemedicina como 7.º policlínico lógico)  
**Patrocinador:** Universidad del Desarrollo (UDD)  
**Equipo:** Bastián Ignacio Fariña y Lukas Garrido (Equipo 2 · Sección 1)  
**Modalidad de demostración (Entrega 23/11/2026):** Demostración local reproducible con PostgreSQL (16 / 18), integración real opcional con **Meta WhatsApp Cloud API** y datos 100 % ficticios.

---

## 1. Arquitectura y patrones implementados

Aplicación web en **Arquitectura en Capas** construida con **Python 3.13 + FastAPI**, **PostgreSQL 16/18** (`psycopg` v3) y frontend **HTML/CSS/JavaScript**:

- `database/`: Scripts SQL reproducibles (`01_schema.sql` … `05_vista_reportes.sql`, y `06_seed_historico_graficos.sql` opcional) con índice único parcial `ux_cita_bloque_activa` (0 % dobles reservas, `RNF04`), entidad `documentos_respaldo`, tabla `responsables` y 8 vistas SQL analíticas (incluye `v_reporte_citas`, sin datos personales).
- `app/domain/`: Validador de RUT chileno módulo 11 (`rut.py`), enmascaramiento de privacidad `P10` y **Patrón State** (`IEstadoCita` + `EstadoConfirmacion` separado para cumplir `RF09`: *«el silencio no cancela»*).
- `app/repositories/`: **Patrón Repository** (`IRepositorioCita`, `IRepositorioCupo`), con `RepositorioCitaSQL` (PostgreSQL con `SELECT ... FOR UPDATE`) y `RepositorioCitaMemoria` (para pruebas unitarias aisladas).
- `app/services/`: **Patrón Facade** (`ServicioAgendamiento`) e **`IGestorNotificaciones`** desacoplado con dos implementaciones:
  - `GestorNotificacionesMetaWhatsApp`: integración directa con **Meta WhatsApp Cloud API** (recordatorio 24 h con botones interactivos *«Confirmar asistencia»* / *«Cancelar mi hora»*, recordatorio anticipado de 15 días, mensajes manuales de texto y webhook bidireccional `GET/POST /webhook`).
  - `GestorNotificacionesSimulado`: modo local automático cuando no existen credenciales de Meta en `.env` (permite evaluar todo el sistema sin cuenta de Meta).
- `app/web/`: Portal Pacientes (horas disponibles con selección directa, solicitud asistida con switch de tutor/apoderado obligatorio en menores de 18 años, folio documental opcional, pantalla de resumen con encuesta y consulta por RUT protegida) y Panel Institucional con barra lateral diferenciada para **TENS/TONS**, **Telemedicina** y **Administración** (con filtros combinables y 10 gráficos interactivos con Chart.js local).

> **Frontera administrativa (`RF18`):** El sistema no incluye ficha clínica electrónica, videollamada propia ni código de reserva (`P6` descartado).

---

## 2. Requisitos previos

- **Python 3.10 o superior** (probado en Python 3.13).
- **PostgreSQL 16 o 18** ejecutándose localmente (`psql` o **pgAdmin 4**).
- **Git**.
- *(Opcional para pruebas en vivo de WhatsApp)*: Cuenta Meta for Developers con número de prueba Cloud API y `cloudflared` (Cloudflare Tunnel) para exponer el webhook. **No es obligatorio para evaluar el sistema local.**

---

## 3. Instalación y ejecución local

### Paso 1: Crear la base de datos y ejecutar los scripts SQL en orden

Desde `psql` (o en **pgAdmin 4 → Query Tool** sobre la base `hermandad_dolores_mvp`):

```bash
psql -U postgres -c "CREATE DATABASE hermandad_dolores_mvp;"
psql -U postgres -d hermandad_dolores_mvp -f database/01_schema.sql
psql -U postgres -d hermandad_dolores_mvp -f database/02_seed_ficticio.sql
psql -U postgres -d hermandad_dolores_mvp -f database/03_seed_otros_policlinicos.sql
psql -U postgres -d hermandad_dolores_mvp -f database/04_ampliar_ficha_mvp.sql
psql -U postgres -d hermandad_dolores_mvp -f database/05_vista_reportes.sql
# Opcional (solo demo de gráficos): ~3.000 citas históricas 100 % ficticias de los últimos 6 meses
psql -U postgres -d hermandad_dolores_mvp -f database/06_seed_historico_graficos.sql
```

> `05` y `06` se pueden ejecutar varias veces sin error. `06` borra solo lo que insertó en su corrida anterior.

### Paso 2: Crear entorno virtual (`venv`) e instalar dependencias

En **Windows (PowerShell)**:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En **macOS / Linux**:
```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
```

### Paso 3: Configurar variables de entorno (`.env`)

Copia `.env.example` como `.env` y coloca tu contraseña local de PostgreSQL (si contiene `@` o `#`, codifícalos como `%40` y `%23`):

```env
DATABASE_URL=postgresql://postgres:TU_CONTRASEÑA_LOCAL@localhost:5432/hermandad_dolores_mvp
USE_MEMORY_REPO=false

# Opcional — Meta WhatsApp Cloud API (si se dejan vacíos, opera en modo simulado local)
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_API_VERSION=v25.0
WHATSAPP_VERIFY_TOKEN=hermandad_dolores_webhook_2026
WHATSAPP_TEST_TO=
```

### Paso 4: Levantar el servidor local

```powershell
python -m uvicorn app.main:app --reload
```

Abre en tu navegador:
- **Aplicación web:** http://127.0.0.1:8000
- **Verificación de estado:** http://127.0.0.1:8000/api/salud
- **Documentación API (Swagger):** http://127.0.0.1:8000/docs

---

## 4. Demostración opcional de WhatsApp Cloud API y Webhook

Si se configuran `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` y `WHATSAPP_TEST_TO` en `.env`:
1. Desde **Panel Operativo → Confirmaciones y seguimiento**, el personal puede disparar **«WhatsApp 24h (botones)»**, **«WhatsApp 15d»** o enviar un **«Mensaje manual»** (también disponible en **Recepción y asistencia** para citas ya confirmadas).
2. Para recibir respuestas y clics de botones en vivo en entorno local, exponer el puerto `8000` con Cloudflare Tunnel (`cloudflared tunnel --url http://127.0.0.1:8000`), registrar `https://<URL>/webhook` con el `WHATSAPP_VERIFY_TOKEN` en Meta for Developers y suscribir el campo `messages`.
3. Al presionar **«Confirmar asistencia»** o **«Cancelar mi hora»** en WhatsApp, el webhook actualiza automáticamente la cita en PostgreSQL y registra el intercambio en el historial por policlínico y RUT.

---

## 5. Cuentas demostrativas (datos 100 % ficticios)

| Rol | Sede / Alcance | Usuario | Contraseña demo |
| --- | --- | --- | --- |
| TENS/TONS | San Isidro (Casa Central) | `tens.sanisidro` | `demo123` |
| TENS/TONS | Sagrada Familia | `tens.sagradafamilia` | `demo123` |
| TENS/TONS | María Ayuda | `tens.mariaayuda` | `demo123` |
| TENS/TONS | Santa Teresa | `tens.santateresa` | `demo123` |
| TENS/TONS | Padre Hurtado | `tens.padrehurtado` | `demo123` |
| TENS/TONS | Oratorio Mariano | `tens.oratoriomariano` | `demo123` |
| Telemedicina | Telemedicina (7.º Policlínico) | `telemed.operador` | `demo123` |
| Administración | Todas las sedes (7 unidades) | `admin.fundacion` | `admin123` |

**RUTs ficticios de prueba (módulo 11):** `14.567.890-0`, `19.876.543-0`, `13.246.810-9`, `11.222.333-9`, `14.666.777-5`.

---

## 6. Pruebas automatizadas

```powershell
python -m pytest -v
```
*(También ejecutables con `python -m unittest discover -s tests -v`).* Incluye 20 pruebas (10 de dominio y API + 10 de filtros y gráficos): dominio, concurrencia anti doble reserva (`RNF04`), regla `RF09` (*el silencio no cancela*), consulta protegida `P10`, reportes CSV y webhook interactivo de Meta WhatsApp.

---

## 6b. Filtros y gráficos de Administración

`#/admin/reportes`: una barra única de filtros (período, agrupación día/semana/mes/semestre/año, tipo de fecha —de la cita o de solicitud—, policlínico, modalidad, especialidad, profesional, estado y canal) se aplica a los KPI, los gráficos, la tabla de indicadores y el CSV.

| Gráfico | Qué muestra |
|---|---|
| G0 Explorador | Métrica × dimensión × desglose × tipo, con hasta 5 vistas guardadas |
| G1 Citas en el tiempo | Líneas por período, separables por estado, policlínico, especialidad o profesional |
| G2 Horas más demandadas | Barras por hora de inicio (08–19 h) |
| G3 Citas por policlínico | Apiladas por estado (Telemedicina incluida) |
| G4 Citas por profesional | 10 primeros + «Otros» |
| G5 Tasas por policlínico | Asistencia, inasistencia, cancelación, confirmación y «confirma y no asiste» |
| G6 Ocupación de bloques | Ocupados ÷ publicados |
| G7 Caracterización | Tramo etario o nacionalidad (pacientes únicos; grupos < 3 en «Otras») |
| G8 Canal de registro / G9 Encuestas post-atención | Distribuciones |

- «Elegir qué ver» oculta/muestra gráficos (se recuerda en el navegador); «Ver tabla» muestra los datos de cada gráfico (accesibilidad); las tasas sin datos se muestran como «—», nunca «0 %».
- **Exportar CSV (filtrado):** `GET /api/reportes/dataset.csv` (UTF-8 con BOM) y deja `REPORTE_EXPORTAR` en la auditoría. El formato definitivo depende de la Fundación (R07).
- `GET /api/reportes/dataset` entrega las filas filtradas **sin RUT, nombre, teléfono ni correo** (RNF03). Como en el resto de la API de esta versión, no valida sesión: la vista de Administración envía `rol=ADMINISTRACION` y `usuario` para etiquetar la auditoría.
- Chart.js 4.4.4 está guardado en `app/web/vendor/` (la demo funciona sin internet).
- Con el seed `06`, los períodos pasados muestran ocupación ≈ 100 %: los bloques pasados se crean `OCUPADO` u `OCULTO` para que no aparezcan como disponibles en el agendamiento.

---

## 7. Seguridad y datos

- Todos los registros incluidos son **100 % ficticios y anonimizados**.
- El archivo `.env` está excluido en `.gitignore`; **no publicar contraseñas, tokens de Meta ni claves reales en el repositorio**.
