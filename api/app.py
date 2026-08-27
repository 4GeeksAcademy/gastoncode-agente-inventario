"""
FastAPI - Gestión de Inventario de Productos
Almacena los productos localmente en products.csv
"""

import csv
import os
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional

# --- Configuración ---
CSV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "products.csv")
CSV_HEADERS = ["product_id", "name", "quantity", "unit"]
DEFAULT_ALERT_THRESHOLD = 10

app = FastAPI(
    title="API de Inventario",
    description="API para gestionar el inventario de productos de una tienda.",
    version="1.0.0",
)


# --- Modelos Pydantic ---

class Product(BaseModel):
    """Representa un producto del inventario."""
    product_id: int = Field(..., description="Identificador único del producto")
    name: str = Field(..., description="Nombre del producto")
    quantity: int = Field(..., ge=0, description="Cantidad en stock (no negativa)")
    unit: str = Field(..., description="Unidad de medida (ej: kg, unidades, litros)")


class ProductCreate(BaseModel):
    """Datos necesarios para crear un nuevo producto."""
    name: str = Field(..., min_length=1, description="Nombre del producto")
    quantity: int = Field(..., ge=0, description="Cantidad inicial en stock")
    unit: str = Field(..., min_length=1, description="Unidad de medida (ej: kg, unidades, litros)")


class ProductUpdate(BaseModel):
    """Delta de stock para actualizar un producto (positivo = entrada, negativo = salida)."""
    delta: int = Field(..., description="Variación de stock: positivo para entrada, negativo para salida")


# --- Funciones auxiliares de CSV ---

def _read_csv() -> List[dict]:
    """Lee el archivo CSV y devuelve una lista de diccionarios."""
    if not os.path.exists(CSV_FILE):
        # Si no existe, crear con encabezados
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
        return []

    with open(CSV_FILE, "r", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def _write_csv(products: List[dict]):
    """Escribe la lista completa de productos en el CSV."""
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(products)


def _next_id(products: List[dict]) -> int:
    """Retorna el siguiente ID disponible."""
    if not products:
        return 1
    return max(int(p["product_id"]) for p in products) + 1


def _find_product(products: List[dict], product_id: int) -> Optional[dict]:
    """Busca un producto por su ID. Retorna None si no existe."""
    for p in products:
        if int(p["product_id"]) == product_id:
            return p
    return None


def _to_product_response(product: dict) -> Product:
    """Convierte un diccionario del CSV a un modelo Product."""
    return Product(
        product_id=int(product["product_id"]),
        name=product["name"],
        quantity=int(product["quantity"]),
        unit=product["unit"],
    )


# --- Endpoints ---

@app.get("/inventory", response_model=List[Product], status_code=200)
def get_inventory():
    """
    Devuelve la lista completa de productos del inventario.
    """
    try:
        products = _read_csv()
        return [_to_product_response(p) for p in products]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer el inventario: {str(e)}")


@app.post("/inventory", response_model=Product, status_code=201)
def add_product(product_data: ProductCreate):
    """
    Añade un nuevo producto al inventario.
    - **name**: Nombre del producto
    - **quantity**: Cantidad inicial en stock
    - **unit**: Unidad de medida (ej: kg, unidades, litros)
    """
    try:
        products = _read_csv()

        new_product = {
            "product_id": str(_next_id(products)),
            "name": product_data.name,
            "quantity": str(product_data.quantity),
            "unit": product_data.unit,
        }

        products.append(new_product)
        _write_csv(products)

        return _to_product_response(new_product)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al añadir producto: {str(e)}")


@app.patch("/inventory/{product_id}", response_model=Product, status_code=200)
def update_stock(product_id: int, update_data: ProductUpdate):
    """
    Actualiza el stock de un producto existente.
    - **product_id**: ID del producto a actualizar
    - **delta**: Variación de stock (positivo para entrada, negativo para salida)
    """
    try:
        products = _read_csv()
        product = _find_product(products, product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail=f"Producto con ID {product_id} no encontrado",
            )

        current_qty = int(product["quantity"])
        new_qty = current_qty + update_data.delta

        if new_qty < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente. Cantidad actual: {current_qty}, "
                       f"intento de salida: {abs(update_data.delta)}",
            )

        product["quantity"] = str(new_qty)
        _write_csv(products)

        return _to_product_response(product)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar stock: {str(e)}")


@app.get("/inventory/alerts", response_model=List[Product], status_code=200)
def get_alerts(threshold: int = Query(DEFAULT_ALERT_THRESHOLD, ge=0, description="Umbral mínimo de stock para generar alerta")):
    """
    Devuelve todos los productos cuya cantidad esté por debajo del umbral especificado.
    - **threshold**: Cantidad mínima de stock (por defecto 10). Solo se muestran productos con quantity < threshold.
    """
    try:
        products = _read_csv()
        alert_products = [
            _to_product_response(p)
            for p in products
            if int(p["quantity"]) < threshold
        ]
        return alert_products
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar alertas: {str(e)}")


@app.get("/", status_code=200)
def root():
    """Endpoint raíz con información de la API."""
    return {
        "message": "API de Inventario",
        "documentation": "/docs",
        "endpoints": [
            "GET  /inventory",
            "POST /inventory",
            "PATCH /inventory/{product_id}",
            "GET  /inventory/alerts?threshold=10",
        ],
    }