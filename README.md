# 🤖 Agente de IA para Gestión de Inventario

Sistema de gestión de inventario que combina una **API REST** (FastAPI) con un **agente conversacional** impulsado por un **LLM (Groq)** para interactuar con el inventario en lenguaje natural.

---

## 📦 Arquitectura

```
┌───────────────────────────────────────────────────────────────┐
│                    Usuario (CLI)                               │
└──────────────────────┬────────────────────────────────────────┘
                       │  Lenguaje natural
                       ▼
┌───────────────────────────────────────────────────────────────┐
│                   agent.py (Agente LLM)                        │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────┐    ┌─────────────┐   │
│  │              │    │  Bucle iterativo │    │             │   │
│  │   Memoria    │◄──►│  (máx. 5 rondas) │◄──►│ Conversation│   │
│  │   (array)    │    │                  │    │   Log CSV   │   │
│  └──────────────┘    └──────┬──────┬────┘    └─────────────┘   │
│                             │      │                            │
│                       ┌─────┘      └─────┐                     │
│                       ▼                  ▼                     │
│                 ┌────────────┐   ┌──────────────┐              │
│                 │  Tools (4) │   │  Respuesta   │              │
│                 │  Ejecutar  │   │    final     │              │
│                 └──────┬─────┘   └──────────────┘              │
└────────────────────────┼───────────────────────────────────────┘
                         │  HTTP (httpx)
                         ▼
┌───────────────────────────────────────────────────────────────┐
│              api/app.py (FastAPI — REST)                       │
│                                                               │
│  GET /inventory    POST /inventory                            │
│  PATCH /inventory/{id}   GET /inventory/alerts                │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────────────┐
│                  products.csv (Datos)                          │
└───────────────────────────────────────────────────────────────┘
```

---

## 🧠 Características técnicas del agente

### 🤖 LLM
- **Proveedor:** Groq (API compatible con OpenAI)
- **Modelo:** `openai/gpt-oss-20b` (configurable vía `LLM_MODEL` en `.env`)
- **API Key:** Se carga desde el archivo `.env` con `python-dotenv`

### 🛠️ Tools (4 endpoints → 4 herramientas)

| Tool | Endpoint | Descripción |
|------|----------|-------------|
| `get_inventory()` | `GET /inventory` | Lista todos los productos del inventario |
| `add_product(name, quantity, unit)` | `POST /inventory` | Añade un nuevo producto |
| `update_stock(product_id, delta)` | `PATCH /inventory/{id}` | Actualiza stock (delta positivo = entrada, negativo = salida) |
| `get_alerts(threshold)` | `GET /inventory/alerts` | Muestra productos con stock bajo el umbral |

### 🧠 Memoria
- Mantiene el **historial completo de la conversación** en un array (`MEMORY`)
- El LLM tiene contexto de toda la interacción, permitiendo referencias a productos o acciones anteriores

### 🔄 Bucle iterativo de tools (máx. 5 rondas)
- El agente puede ejecutar **múltiples tools en secuencia** para una misma instrucción
- Por ejemplo, si el usuario pide *"quita 5 de café y muestra el inventario"*, el agente:
  1. **1ª ronda:** Ejecuta `update_stock(1, -5)` → ve el resultado
  2. **2ª ronda:** Ejecuta `get_inventory()` → obtiene la lista actualizada
  3. **3ª ronda:** Genera la respuesta final en lenguaje natural
- Si el LLM supera las **5 rondas sin dar una respuesta definitiva**, el agente informa al usuario y sugiere simplificar la solicitud

### 📝 Log de conversación
- Cada acción se registra automáticamente en **`conversation-log.csv`**
- Columnas: `timestamp`, `role`, `message`, `tool_used`, `tool_result`
- Permite auditar todas las operaciones realizadas por el agente

### 💬 Interfaz
- **Modo interactivo por terminal** (chat continuo)
- Comandos disponibles: `salir`, `exit`, `help`
- Respuestas en **español** con formato amigable y emojis

---

## 🚀 Requisitos

- **Python 3.10+**
- **API Key de Groq** (configurada en `.env` como `LLM_API_KEY`)
- Dependencias (instaladas automáticamente):

```
fastapi>=0.100.0
uvicorn>=0.20.0
openai>=1.0.0
python-dotenv>=1.0.0
httpx>=0.24.0
```

---

## 🔧 Configuración

El archivo `.env` debe contener:

```env
LLM_API_KEY=gsk_tu_api_key_aqui
LLM_MODEL=openai/gpt-oss-20b    # Opcional, por defecto openai/gpt-oss-20b
```

> ⚠️ **Importante:** El archivo `.env` ya está configurado en el proyecto. Verifica que `LLM_API_KEY` tenga un valor válido.

---

## ▶️ Cómo usar

### 1. Iniciar la API (primero y obligatorio)

```bash
cd api
uvicorn app:app --reload
```

La API quedará disponible en `http://127.0.0.1:8000`.

Puedes verificar que funciona visitando:
- Documentación interactiva: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Estado: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

> ⚠️ **Importante:** La API **debe** estar corriendo antes de ejecutar el agente, ya que el agente consume sus endpoints.

### 2. Ejecutar el agente (en otra terminal)

```bash
source myenv/bin/activate   # Si usas el entorno virtual
python agent.py
```

### 3. Interactuar en lenguaje natural

```
🤖 AGENTE DE GESTIÓN DE INVENTARIO
============================================================
Escribe 'salir' o 'exit' para terminar.
Escribe 'help' para ver los comandos disponibles.
------------------------------------------------------------

👤 Tú: Muéstrame el inventario
🧠 Pensando...
📦 **Inventario actual:**
  • ID 1: Café en granos — 25 kg
  • ID 2: Leche entera — 20 l
  • ID 3: Leche descremada — 25 l
  • ID 4: Cookies de vainilla — 15 unidades
  • ID 5: Cookies de chocolate — 5 unidades
  • ID 6: Sobres de azúcar — 35 unidades
  • ID 7: Edulcorante — 15 sobres
  • ID 8: Agitadores — 4 unidades
```

Ejemplo de **múltiples tools en una sola instrucción**:

```
👤 Tú: quita 5 kg de café y luego muéstrame el inventario actualizado
🧠 Pensando...
🔧 Ejecutando: update_stock({'product_id': 1, 'delta': -5})
   Resultado: ✅ Stock actualizado: 5 kg retirada de 'Café en granos'. Nuevo stock: 20 kg
🧠 Analizando resultados...
🔧 Ejecutando: get_inventory({})
   Resultado: 📦 **Inventario actual:** ...
🧠 Analizando resultados...
🤖 Asistente:
✅ Listo. Se retiraron 5 kg de Café en granos. El inventario quedó así:
  • Café en granos — 20 kg
  • Leche entera — 20 l
  ... (resto del inventario)
```

### 📋 Ejemplos de consultas

| Lo que dices | Lo que hace el agente |
|---|---|
| *"Muéstrame el inventario"* | Ejecuta `get_inventory()` |
| *"Agrega 10 litros de leche de almendras"* | Pide confirmación y ejecuta `add_product("leche de almendras", 10, "l")` |
| *"Registra una salida de 3 kg de café"* | Busca el producto y ejecuta `update_stock(1, -3)` |
| *"Llegaron 20 unidades de cookies de vainilla"* | Ejecuta `update_stock(4, 20)` |
| *"Qué productos tienen poco stock?"* | Ejecuta `get_alerts()` (umbral por defecto: 10) |
| *"Muéstrame productos con menos de 5 unidades"* | Ejecuta `get_alerts(threshold=5)` |

---

## 📄 Estructura del proyecto

```
.
├── agent.py              # 🤖 Agente conversacional con LLM
├── api/
│   ├── __init__.py
│   └── app.py            # 🌐 API REST (FastAPI)
├── products.csv          # 📊 Datos del inventario
├── conversation-log.csv  # 📝 Registro de acciones del agente
├── main.py               # Script de ejemplo (legacy)
├── .env                  # 🔑 Variables de entorno (API Key)
├── requirements.txt      # 📦 Dependencias
├── README.md             # 📖 Este documento
└── myenv/                # Entorno virtual de Python (opcional)
```

---

## 📁 conversation-log.csv

Cada vez que el agente ejecuta una acción, se registra en este archivo:

```csv
timestamp,role,message,tool_used,tool_result
2026-08-28T18:33:15,user,Muéstrame el inventario,,
2026-08-28T18:33:18,agent Explicó el inventario,,
2026-08-28T18:33:22,user,Agrega 10 litros de leche,,
2026-08-28T18:33:25,agent Explicó el inventario,add_product,"✅ Producto añadido: ID 9: Leche — 10 l"
```

---

## 🛑 Solución de problemas

| Problema | Posible causa | Solución |
|---|---|---|
| `Connection refused` al iniciar el agente | La API no está corriendo | Ejecuta `uvicorn app:app --reload` en `api/` |
| `LLM_API_KEY no encontrada` | Falta el `.env` | Verifica que `.env` exista y tenga la variable |
| `Error 400: invalid_request_error` | (Antiguo bug resuelto) Error de formato en tools o herramienta no encontrada | Revisa el mensaje específico del error o reinicia la sesión del agente |
| `Error: Tool choice is none...` | (Antiguo bug resuelto) Ocurría en la 2ª llamada sin tools | Ya no debería ocurrir tras la actualización del bucle iterativo |
| `ModuleNotFoundError` | Dependencias no instaladas | `pip install -r requirements.txt` |

---

## 🧪 API Reference

### `GET /inventory`
Devuelve todos los productos.

### `POST /inventory`
Añade un producto. Body: `{ "name": "...", "quantity": N, "unit": "..." }`

### `PATCH /inventory/{product_id}`
Actualiza stock. Body: `{ "delta": N }` (positivo = entrada, negativo = salida)

### `GET /inventory/alerts?threshold=N`
Productos con stock menor al umbral.

---

> Proyecto desarrollado con ❤️ usando FastAPI, Groq y Python.
