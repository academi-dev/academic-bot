# Academic Bot 🤖🎓

> Bot de Telegram para recordatorios de entregas, consulta de asignaturas y asistente inteligente (RAG) para el sistema de gestión universitaria **Academic**.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![python-telegram-bot v20+](https://img.shields.io/badge/python--telegram--bot-v20+-brightgreen.svg)](https://python-telegram-bot.org/)
[![Code style](https://img.shields.io/badge/code%20style-PEP%208-orange.svg)](https://peps.python.org/pep-0008/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Características Principales

- 🔐 **Autenticación Segura:** Inicio de sesión (`/login`) y registro de estudiantes (`/registro`) mediante `ConversationHandler` paso a paso, con almacenamiento de sesión JWT en memoria (`chat_id -> token`).
- 📚 **Gestión de Asignaturas:** Consulta tus materias matriculadas, códigos y docentes asignados (`/materias`).
- 📋 **Control de Tareas:** Visualización completa de tareas (`/tareas`) y filtrado especializado de entregas urgentes para los próximos 7 días (`/pendientes`).
- ⏰ **Recordatorios Inteligentes:** Programación de alertas temporizadas con la cola de trabajos (`job_queue` de `python-telegram-bot` y `APScheduler`) mediante `/recordar`. Admite tanto flujo guiado como atajos directos (ej. `/recordar 30m Estudiar Álgebra`).
- 🤖 **Asistente Académico (RAG):** Consulta dudas académicas y contenidos de clase con `/preguntar`, obteniendo respuestas fundamentadas con citas bibliográficas y porcentaje de relevancia documental.
- 🐳 **Contenedorizado:** Listo para despliegue en producción con Docker y Docker Compose.
- 🧪 **Suite de Pruebas:** Pruebas unitarias completas con `pytest` y `pytest-asyncio`.

---

## 🛠️ Stack Tecnológico

- **Lenguaje:** Python 3.11+
- **Framework de Bot:** `python-telegram-bot[job-queue] >= 20.7` (arquitectura asíncrona `async/await`)
- **Cliente HTTP:** `httpx >= 0.27.0` (asíncrono)
- **Planificador:** `APScheduler` integrado a la cola de trabajos de Telegram
- **Configuración:** `python-dotenv`
- **Testing:** `pytest` y `pytest-asyncio`
- **Contenedores:** Docker y Docker Compose

---

## 📁 Estructura del Proyecto

```text
academic-bot/
├── .env.example              # Plantilla de variables de entorno
├── Dockerfile                # Imagen optimizada en python:3.11-slim
├── docker-compose.yml        # Orquestación del servicio
├── requirements.txt          # Dependencias del proyecto
├── README.md                 # Documentación técnica
├── bot/
│   ├── __init__.py           # Metadatos del paquete
│   ├── config.py             # Carga y validación de variables de entorno
│   ├── main.py               # ApplicationBuilder, registro de handlers y polling
│   ├── handlers/
│   │   ├── __init__.py       # Registro centralizado de manejadores
│   │   ├── start.py          # /start y /help con bienvenida y menú
│   │   ├── auth.py           # ConversationHandlers para /login, /registro y /logout
│   │   ├── materias.py       # /materias para listar asignaturas vía API
│   │   ├── tareas.py         # /tareas y /pendientes (filtro de 7 días)
│   │   ├── recordatorios.py  # /recordar con job_queue
│   │   └── preguntas.py      # /preguntar conectado al servicio RAG con citas
│   ├── services/
│   │   ├── __init__.py       # Exportación de clientes HTTP y excepciones
│   │   ├── api_client.py     # Cliente HTTP asíncrono para academic-api
│   │   └── rag_client.py     # Cliente HTTP asíncrono para academic-rag
│   └── utils/
│       ├── __init__.py       # Exportación de utilidades
│       ├── auth_storage.py   # Almacén de tokens JWT en memoria (chat_id -> token)
│       └── formatters.py     # Formateo visual en Markdown y utilidades de fechas
└── tests/
    ├── __init__.py
    └── test_formatters.py    # Pruebas unitarias para formateadores y auth_storage
```

---

## ⚙️ Configuración y Variables de Entorno

Copia el archivo `.env.example` como `.env` y configura los valores requeridos:

```bash
cp .env.example .env
```

Variables disponibles:

| Variable | Descripción | Valor por defecto |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Token otorgado por [@BotFather](https://t.me/BotFather) en Telegram | _Requerido_ |
| `API_BASE_URL` | Endpoint base de academic-api | `http://localhost:8000/api/v1` |
| `RAG_BASE_URL` | Endpoint base de academic-rag | `http://localhost:8001/api/v1` |
| `LOG_LEVEL` | Nivel de detalle de los logs (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |

---

## 🚀 Cómo Correrlo

### Opción 1: Entorno Virtual Local (Recomendado para desarrollo)

1. **Crear y activar el entorno virtual:**
   ```bash
   python -m venv venv
   # En Windows:
   .\venv\Scripts\activate
   # En Linux / macOS:
   source venv/bin/activate
   ```

2. **Instalar dependencias:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Ejecutar las pruebas unitarias:**
   ```bash
   pytest -v
   ```

4. **Iniciar el bot en Telegram:**
   ```bash
   python -m bot.main
   ```

---

### Opción 2: En WhatsApp por Código QR (sin API de Meta ni Twilio)

El proyecto incluye el conector `whatsapp_qr/` (basado en `@whiskeysockets/baileys`) conectado en tiempo real al motor Python (`bot.whatsapp.processor`). Permite vincular tu propio número de celular escaneando un código QR desde **Dispositivos vinculados**:

1. **Ejecutar el script de arranque rápido (PowerShell):**
   ```powershell
   .\iniciar_whatsapp.ps1
   ```
   *(O manualmente: `cd whatsapp_qr && npm install && node index.js`)*

2. **Escanear el código QR:**
   - Aparecerá directamente en la terminal o en el panel web local **`http://localhost:3005`**.
   - En tu celular abre **WhatsApp → Dispositivos vinculados → Vincular un dispositivo** y escanea el QR.
   - Envía `/start`, `/login`, `/materias`, `/tareas`, `/pendientes`, `/recordar` o `/preguntar` desde WhatsApp.

---

### Opción 3: Con Docker Compose

Para desplegar el bot en un contenedor Docker:

```bash
docker compose up -d --build
```

Para ver los registros en tiempo real:
```bash
docker compose logs -f academic-bot
```

---

## 🤖 Comandos Disponibles en Telegram

| Comando | Descripción |
| :--- | :--- |
| `/start` | Da la bienvenida al usuario, muestra estado de sesión y accesos rápidos. |
| `/help` | Despliega el catálogo completo de comandos y guía de uso. |
| `/login` | Inicia sesión interactivamente ingresando correo y contraseña. |
| `/registro` | Permite crear una nueva cuenta estudiantil paso a paso. |
| `/logout` | Cierra la sesión activa en el chat y elimina el token de memoria. |
| `/materias` | Muestra tus asignaturas inscritas con créditos y docente a cargo. |
| `/tareas` | Lista todas tus tareas con sus respectivos estados (Pendiente / En progreso / Entregada). |
| `/pendientes` | **Filtra exclusivamente las tareas que vencen en los próximos 7 días.** |
| `/recordar` | Programa un aviso automático para una tarea (ej. `/recordar 2h Estudiar Física`). |
| `/preguntar` | Envía una consulta al asistente inteligente (RAG) y muestra respuestas con citas. |
| `/cancelar` | Cancela el flujo o conversación interactiva en curso. |

---

## 👥 Equipo de Desarrollo

- **Jean Mena** — [@hilton45](https://github.com/hilton45)
- **Eyfer Mena** — [@eyfer3174-commits](https://github.com/eyfer3174-commits)

**Organización:** [academic-dev](https://github.com/academic-dev)

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más información.
