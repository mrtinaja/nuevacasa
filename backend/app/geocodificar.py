"""Geocodificacion EN VIVO de una direccion escrita a mano por el
usuario (buscador por direccion) -- distinto de `ubicaciones_geo.py`,
que es una tabla precalculada de centroides de zonas curadas, geocodeada
una sola vez. Una direccion puntual ("Av. Cabildo 2000") no se puede
precargar de antemano, hay que resolverla en el momento.

Fuente: Nominatim (OpenStreetMap), gratis y sin API key -- mismo
proveedor que ya se usa para el resto de la geocodificacion del
proyecto. Nominatim pide un User-Agent identificable en su politica de
uso (https://operations.osmfoundation.org/policies/nominatim/); sin
eso puede empezar a devolver 403. No apto para volumen alto (limite
informal de 1 req/seg) -- aceptable para un buscador personal, no para
tráfico de produccion real.
"""

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "NuevaCasa/1.0 (buscador de propiedades, uso personal)"}


def geocodificar(direccion: str, contexto: str | None = None) -> dict | None:
    """Devuelve {lat, lon, nombre} para la direccion, o None si
    Nominatim no encontro nada o hubo un error de red. `contexto` (ej.
    el barrio/partido ya elegido en el buscador, en texto libre tipo
    "Palermo, Capital Federal") ayuda a desambiguar direcciones cortas
    como "Cabildo 2000" que sin esa pista podrian resolver a otra
    ciudad, o a un resultado mucho menos preciso."""
    direccion = (direccion or "").strip()
    if not direccion:
        return None

    consulta = f"{direccion}, {contexto}, Argentina" if contexto else f"{direccion}, Argentina"
    params = {
        "q": consulta,
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        resultados = resp.json()
    except requests.RequestException:
        return None

    if not resultados:
        return None

    primero = resultados[0]
    try:
        return {
            "lat": float(primero["lat"]),
            "lon": float(primero["lon"]),
            "nombre": primero.get("display_name", direccion),
        }
    except (KeyError, ValueError, TypeError):
        return None
