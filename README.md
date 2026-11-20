# Sistema de Gestión de Citas y Operación Administrativa para Policlínicos

**Mandante:** Fundación Hermandad de Dolores (6 policlínicos presenciales + Telemedicina como 7.º policlínico lógico)  
**Patrocinador:** Universidad del Desarrollo (UDD)  
**Equipo:** Bastián Ignacio Fariña y Lukas Garrido  
**Modalidad de demostración (Entrega 23/11/2026):** Demostración local reproducible con PostgreSQL (16 / 18) y datos 100 % ficticios.

---

## 1. Arquitectura y patrones implementados

Aplicación web en **Arquitectura en Capas** construida con **Python 3.13 + FastAPI**, **PostgreSQL 16/18** (`psycopg` v3) y frontend **HTML/CSS/JavaScript**:

- `database/`: Scripts SQL reproducibles (`01_schema.sql`, `02_seed_ficticio.sql`, `03_seed_otros_policlinicos.sql`, `04_ampliar_ficha_mvp.sql`) con índice único parcial `ux_cita_bloque_activa` (0 % dobles reservas, `RNF04`), entidad `documentos_respaldo`, tabla `responsables` y 7 vistas SQL analíticas.
- `app/domain/`: Validador de RUT chileno módulo 11 (`rut.py`), enmascaramiento de privacidad `P10` y **Patrón State** (`IEstadoCita` + `EstadoConfirmacion` separado para cumplir `RF09`: *«el silencio no cancela»*).
- `app/repositories/`: **Patrón Repository** (`IRepositorioCita`, `IRepositorioCupo`), con `RepositorioCitaSQL` (PostgreSQL con `SELECT ... FOR UPDATE`) y `RepositorioCitaMemoria` (para pruebas unitarias aisladas).
- `app/services/`: **Patrón Facade** (`ServicioAgendamiento`) y `IGestorNotificaciones` desacoplado (comprobantes sin código `RF28` y `AlertaOperativa`).
- `app/web/`: Portal Pacientes (horas disponibles con selección directa, solicitud asistida con switch de tutor/apoderado según edad, folio documental opcional, pantalla de resumen con encuesta y consulta por RUT con datos protegidos) y Panel Institucional con barra lateral diferenciada para **TENS/TONS**, **Telemedicina** y **Administración** (con gráficos de gestión y caracterización).

> **Frontera administrativa (`RF18`):** El sistema no incluye ficha clínica electrónica, videollamada propia ni código de reserva (`P6` descartado).

---

## 2. Requisitos previos

- **Python 3.10 o superior** (probado en Python 3.13).
- **PostgreSQL 16 o 18** ejecutándose localmente (con `psql` o **pgAdmin 4**).
- **Git**.

---

## 3. Instalación y ejecución local

### Paso 1: Crear la base de datos y ejecutar los 4 scripts SQL en orden

Desde `psql` (o desde **pgAdmin 4 → Query Tool** sobre la base `hermandad_dolores_mvp`):

```bash
psql -U postgres -c "CREATE DATABASE hermandad_dolores_mvp;"
psql -U postgres -d hermandad_dolores_mvp -f database/01_schema.sql
psql -U postgres -d hermandad_dolores_mvp -f database/02_seed_ficticio.sql
psql -U postgres -d hermandad_dolores_mvp -f database/03_seed_otros_policlinicos.sql
psql -U postgres -d hermandad_dolores_mvp -f database/04_ampliar_ficha_mvp.sql
```

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

Copia `.env.example` como `.env` y ajusta tu contraseña local de PostgreSQL (si la clave contiene `@` o `#`, codifícalos como `%40` y `%23`):

```env
DATABASE_URL=postgresql://postgres:TU_CONTRASEÑA_LOCAL@localhost:5432/hermandad_dolores_mvp
USE_MEMORY_REPO=false
```

### Paso 4: Levantar el servidor local

```powershell
python -m uvicorn app.main:app --reload
```

Abre en tu navegador:
- **Aplicación web:** http://127.0.0.1:8000
- **Documentación API (Swagger):** http://127.0.0.1:8000/docs

---

## 4. Cuentas demostrativas (datos 100 % ficticios)

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

## 5. Pruebas automatizadas

```powershell
python -m pytest -v
```
*(También ejecutables con `python -m unittest discover -s tests -v`).*

---

## 6. Seguridad y datos

- Todos los registros incluidos son **100 % ficticios y anonimizados**.
- El archivo `.env` está excluido en `.gitignore`; **no publicar contraseñas ni claves reales en el repositorio**.
