"""Historial local de precios por aviso (SQLite, un archivo en
`backend/data/historial.db`, se crea solo).

No hay datos "de arranque": el historial se arma con el uso real, cada
vez que una busqueda trae un aviso se registra su precio. La primera
vez que se ve un aviso no hay nada para comparar (dias_en_mercado=0,
sin baja de precio). Recien de la segunda vez en adelante, si el
precio cambio respecto de lo guardado, se marca como baja (o suba) de
precio.

Es una funcionalidad que ningun portal individual ofrece con datos
cruzados de todos los demas -- pero tampoco es magia: si el usuario no
vuelve a buscar lo mismo, no hay forma de detectar que un precio bajo
en el medio.
"""

import os
import sqlite3
from datetime import date, datetime, timezone

from app.models import Propiedad

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "historial.db")


def _conectar() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS avisos_historial (
            portal TEXT NOT NULL,
            external_id TEXT NOT NULL,
            precio REAL,
            moneda TEXT,
            primera_vez TEXT NOT NULL,
            ultima_vez TEXT NOT NULL,
            precio_anterior REAL,
            fecha_cambio_precio TEXT,
            PRIMARY KEY (portal, external_id)
        )
        """
    )
    return conn


def _dias_desde(fecha_iso: str) -> int:
    fecha = datetime.fromisoformat(fecha_iso).date()
    return (date.today() - fecha).days


def registrar_y_enriquecer(propiedades: list[Propiedad]) -> None:
    """Para cada propiedad, compara contra lo guardado en el historial,
    actualiza el historial y completa en el propio objeto Propiedad
    (mutando in-place) los campos dias_en_mercado/precio_anterior/
    precio_bajado/dias_desde_baja_precio."""
    ahora = datetime.now(timezone.utc).isoformat()
    conn = _conectar()
    try:
        for p in propiedades:
            if not p.external_id:
                continue

            fila = conn.execute(
                "SELECT precio, primera_vez, precio_anterior, fecha_cambio_precio "
                "FROM avisos_historial WHERE portal = ? AND external_id = ?",
                (p.portal, p.external_id),
            ).fetchone()

            if fila is None:
                conn.execute(
                    "INSERT INTO avisos_historial "
                    "(portal, external_id, precio, moneda, primera_vez, ultima_vez, precio_anterior, fecha_cambio_precio) "
                    "VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
                    (p.portal, p.external_id, p.precio, p.moneda, ahora, ahora),
                )
                p.dias_en_mercado = 0
                continue

            precio_guardado, primera_vez, precio_anterior_guardado, fecha_cambio_guardada = fila
            p.dias_en_mercado = _dias_desde(primera_vez)

            precio_cambio = (
                p.precio is not None
                and precio_guardado is not None
                and p.precio != precio_guardado
            )
            if precio_cambio:
                conn.execute(
                    "UPDATE avisos_historial SET precio = ?, ultima_vez = ?, "
                    "precio_anterior = ?, fecha_cambio_precio = ? "
                    "WHERE portal = ? AND external_id = ?",
                    (p.precio, ahora, precio_guardado, ahora, p.portal, p.external_id),
                )
                p.precio_anterior = precio_guardado
                p.precio_bajado = p.precio < precio_guardado
                p.dias_desde_baja_precio = 0
            else:
                conn.execute(
                    "UPDATE avisos_historial SET ultima_vez = ? WHERE portal = ? AND external_id = ?",
                    (ahora, p.portal, p.external_id),
                )
                if precio_anterior_guardado is not None and p.precio is not None:
                    p.precio_anterior = precio_anterior_guardado
                    p.precio_bajado = p.precio < precio_anterior_guardado
                    if fecha_cambio_guardada:
                        p.dias_desde_baja_precio = _dias_desde(fecha_cambio_guardada)
        conn.commit()
    finally:
        conn.close()
