"""
Agente de IA para la Gestión de Inventario
============================================
Usa un LLM (Groq) para procesar solicitudes en lenguaje natural y
modificar el inventario a través de los endpoints de la API.

Cada endpoint de la API es una "tool" que el agente puede invocar.
Mantiene una memoria (array) de la conversación y registra cada
acción en conversation-log.csv.
"""

import os
import csv
import json
import datetime
from typing import List, Dict, Optional, Any

import httpx
from dotenv import load_dotenv
from openai import OpenAI

# ─── Cargar variables de entorno ───────────────────────────────────────────
load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
if not API_KEY:
    raise ValueError("❌ No se encontró LLM_API_KEY en el archivo .env")

# ─── Configuración ─────────────────────────────────────────────────────────
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

API_BASE_URL = "http://127.0.0.1:8000"

MEMORY: List[Dict[str, str]] = []  # Memoria del agente (historial conversacional)
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conversation-log.csv")
LOG_HEADERS = ["timestamp", "role", "message", "tool_used", "tool_result"]

# ─── Inicializar cliente LLM ───────────────────────────────────────────────
client = OpenAI(
    api_key=API_KEY,
    base_url=GROQ_BASE_URL,
)


# ─── Funciones de log ──────────────────────────────────────────────────────

def _init_log():
    """Crea el archivo de log con encabezados si no existe."""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(LOG_HEADERS)


def _log_entry(role: str, message: str, tool_used: str = "", tool_result: str = ""):
    """Registra una entrada en el conversation-log.csv."""
    timestamp = datetime.datetime.now().isoformat()
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, role, message, tool_used, tool_result])


# ─── Cliente HTTP para consumir la API ─────────────────────────────────────

class InventoryAPI:
    """Cliente para consumir los endpoints de la API de inventario."""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=10.0)

    def get_inventory(self) -> str:
        """GET /inventory - Obtener todos los productos."""
        try:
            resp = self.client.get("/inventory")
            resp.raise_for_status()
            products = resp.json()
            if not products:
                return "📭 El inventario está vacío."
            lines = ["📦 **Inventario actual:**"]
            for p in products:
                lines.append(
                    f"  • ID {p['product_id']}: {p['name']} — "
                    f"{p['quantity']} {p['unit']}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error al obtener inventario: {e}"

    def add_product(self, name: str, quantity: int, unit: str) -> str:
        """POST /inventory - Agregar un nuevo producto."""
        try:
            payload = {"name": name, "quantity": quantity, "unit": unit}
            resp = self.client.post("/inventory", json=payload)
            resp.raise_for_status()
            p = resp.json()
            return (
                f"✅ Producto añadido exitosamente:\n"
                f"  • ID {p['product_id']}: {p['name']} — "
                f"{p['quantity']} {p['unit']}"
            )
        except Exception as e:
            return f"❌ Error al añadir producto: {e}"

    def update_stock(self, product_id: int, delta: int) -> str:
        """PATCH /inventory/{product_id} - Actualizar stock (delta positivo=entrada, negativo=salida)."""
        try:
            payload = {"delta": delta}
            resp = self.client.patch(f"/inventory/{product_id}", json=payload)
            resp.raise_for_status()
            p = resp.json()
            action = "ingresada" if delta >= 0 else "retirada"
            return (
                f"✅ Stock actualizado: {abs(delta)} {p['unit']} {action} "
                f"de '{p['name']}'. Nuevo stock: {p['quantity']} {p['unit']}"
            )
        except Exception as e:
            return f"❌ Error al actualizar stock: {e}"

    def get_alerts(self, threshold: int = 10) -> str:
        """GET /inventory/alerts?threshold= - Productos con stock bajo."""
        try:
            resp = self.client.get("/inventory/alerts", params={"threshold": threshold})
            resp.raise_for_status()
            products = resp.json()
            if not products:
                return f"✅ No hay productos con stock por debajo de {threshold}."
            lines = [f"⚠️ **Alertas de stock (umbral < {threshold}):**"]
            for p in products:
                lines.append(
                    f"  • ID {p['product_id']}: {p['name']} — "
                    f"solo {p['quantity']} {p['unit']}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error al obtener alertas: {e}"

    def close(self):
        self.client.close()


# ─── Definición de Tools para el LLM ──────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_inventory",
            "description": "Obtiene la lista completa de productos del inventario.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_product",
            "description": "Añade un nuevo producto al inventario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nombre del producto",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Cantidad inicial en stock",
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unidad de medida (ej: kg, unidades, litros)",
                    },
                },
                "required": ["name", "quantity", "unit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_stock",
            "description": "Actualiza el stock de un producto existente. Usa delta positivo para entrada de stock y delta negativo para salida.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "ID del producto a actualizar",
                    },
                    "delta": {
                        "type": "integer",
                        "description": "Variación de stock: positivo para entrada, negativo para salida",
                    },
                },
                "required": ["product_id", "delta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_alerts",
            "description": "Obtiene productos con stock por debajo de un umbral.",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "integer",
                        "description": "Umbral mínimo de stock para generar alerta (por defecto 10)",
                    },
                },
                "required": [],
            },
        },
    },
]

SYSTEM_PROMPT = """Eres un asistente experto en gestión de inventario de una tienda de suministros para cafeterías. Tu función es ayudar al usuario a:

1. **Consultar** el inventario actual
2. **Añadir** nuevos productos
3. **Actualizar** el stock (entradas y salidas)
4. **Generar alertas** de stock bajo

Tienes acceso a las siguientes herramientas (cada una corresponde a un endpoint de la API REST):

- `get_inventory` → Muestra todos los productos con su ID, nombre, cantidad y unidad.
- `add_product(name, quantity, unit)` → Agrega un nuevo producto al inventario.
- `update_stock(product_id, delta)` → Actualiza el stock. Usa delta positivo para entrada, negativo para salida.
- `get_alerts(threshold)` → Muestra productos con stock por debajo del umbral.

**Reglas importantes:**
- Siempre confirma las acciones importantes (añadir/actualizar) con el usuario antes de ejecutarlas, a menos que el usuario sea muy explícito.
- Después de ejecutar una tool, informa claramente el resultado al usuario.
- Si el usuario pide "salida" o "retiro" de stock, usa delta negativo.
- Si no se especifica el umbral para alertas, usa 10 por defecto.
- Tu lenguaje debe ser amable, profesional y en español.
- Si ocurre un error, explícale al usuario qué pasó y sugiere una solución.
- IMPORTANTE: Siempre responde basado en los datos reales obtenidos de las tools, NO inventes información.
- Cuando muestres productos, incluye siempre su ID para que el usuario pueda referenciarlos después."""


# ─── Lógica principal del agente ──────────────────────────────────────────

def run_tool(tool_name: str, arguments: dict, api: InventoryAPI) -> str:
    """Ejecuta una tool y devuelve el resultado como texto."""
    if tool_name == "get_inventory":
        return api.get_inventory()
    elif tool_name == "add_product":
        return api.add_product(
            name=arguments["name"],
            quantity=arguments["quantity"],
            unit=arguments["unit"],
        )
    elif tool_name == "update_stock":
        return api.update_stock(
            product_id=arguments["product_id"],
            delta=arguments["delta"],
        )
    elif tool_name == "get_alerts":
        threshold = arguments.get("threshold", 10)
        return api.get_alerts(threshold=threshold)
    else:
        return f"❌ Tool desconocida: {tool_name}"


def process_tool_calls(response, api: InventoryAPI) -> str:
    """Procesa las llamadas a tools que el LLM decida hacer."""
    results = []
    for tool_call in response.choices[0].message.tool_calls:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        print(f"\n🔧 Ejecutando: {tool_name}({arguments})")
        result = run_tool(tool_name, arguments, api)
        print(f"   Resultado: {result}")
        results.append({
            "tool_call_id": tool_call.id,
            "tool_name": tool_name,
            "result": result,
        })
        # Registrar en log
        _log_entry(
            role="agent",
            message=f"Ejecutó tool: {tool_name}",
            tool_used=tool_name,
            tool_result=result,
        )
    return results


def build_messages(question: str) -> List[Dict[str, str]]:
    """Construye la lista de mensajes incluyendo el historial (memoria)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(MEMORY)
    messages.append({"role": "user", "content": question})
    return messages


def chat_loop():
    """Bucle principal interactivo del agente."""
    _init_log()
    api = InventoryAPI()

    # Registrar inicio de sesión
    _log_entry(role="system", message="Inicio de sesión del agente")

    print("\n" + "=" * 60)
    print("🤖 AGENTE DE GESTIÓN DE INVENTARIO")
    print("=" * 60)
    print("Escribe 'salir' o 'exit' para terminar.")
    print("Escribe 'help' para ver los comandos disponibles.")
    print("-" * 60 + "\n")

    while True:
        try:
            user_input = input("👤 Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 ¡Hasta luego!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("salir", "exit", "quit"):
            print("👋 ¡Hasta luego!")
            _log_entry(role="user", message="El usuario cerró la sesión")
            break

        if user_input.lower() == "help":
            print("\n📋 **Comandos disponibles:**")
            print("  • Pregunta en lenguaje natural lo que quieras hacer")
            print("  • 'salir' / 'exit' — Terminar la sesión")
            print("  • 'help' — Mostrar esta ayuda")
            print("\n**Ejemplos:**")
            print("  • 'Muéstrame el inventario'")
            print("  • 'Agrega 10 unidades de café'")
            print("  • 'Registra una salida de 5 kg de leche'")
            print("  • 'Qué productos tienen poco stock?'")
            print()
            continue

        # Registrar mensaje del usuario
        _log_entry(role="user", message=user_input)
        MEMORY.append({"role": "user", "content": user_input})

        # Llamar al LLM
        print("🧠 Pensando...", end="", flush=True)

        try:
            messages = build_messages(user_input)
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3,
            )
            print("\r" + " " * 20 + "\r", end="", flush=True)

            # Obtener el mensaje de respuesta
            assistant_msg = response.choices[0].message

            # Verificar si el LLM quiere ejecutar tools
            if assistant_msg.tool_calls:
                # Ejecutar las tools solicitadas
                tool_results = process_tool_calls(response, api)

                # Agregar la respuesta del asistente a la memoria
                MEMORY.append({
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in assistant_msg.tool_calls
                    ],
                })

                # Agregar resultados de tools a la memoria
                for tr in tool_results:
                    MEMORY.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_call_id"],
                        "content": tr["result"],
                    })

                # Hacer una segunda llamada al LLM para que genere respuesta en lenguaje natural
                second_messages = build_messages(user_input)
                # Reemplazar el último mensaje (user) con la cadena completa incluyendo tools
                second_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                second_messages.extend(MEMORY)

                second_response = client.chat.completions.create(
                    model=MODEL,
                    messages=second_messages,
                    temperature=0.3,
                )

                final_text = second_response.choices[0].message.content or ""
            else:
                final_text = assistant_msg.content or ""

            # Mostrar respuesta al usuario
            if final_text:
                print(f"🤖 Asistente:\n{final_text}\n")
                MEMORY.append({"role": "assistant", "content": final_text})
                _log_entry(role="assistant", message=final_text)

        except Exception as e:
            print(f"\n❌ Error al comunicarse con el LLM: {e}")
            _log_entry(role="error", message=str(e))

    api.close()


# ─── Punto de entrada ─────────────────────────────────────────────────────

if __name__ == "__main__":
    chat_loop()