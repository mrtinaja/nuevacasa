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


# Orden de prioridad para la linea SECUNDARIA de cada sugerencia (ver
# `_partir_nombre`) -- de mas especifico a mas general. Nominatim no
# siempre trae todas estas claves; se usan las que esten presentes.
_CLAVES_SECUNDARIA = (
    "suburb", "neighbourhood", "quarter",
    "city_district", "town", "village", "municipality", "city",
    "state",
)


def _partir_nombre(item: dict) -> tuple[str, str]:
    """Separa un resultado de Nominatim en (principal, secundaria) para
    mostrar en el desplegable de sugerencias -- ej. principal="Avenida
    Cabildo 2000", secundaria="Belgrano, Ciudad Autonoma de Buenos
    Aires". Usa el `address` estructurado (`addressdetails=1`) en vez
    de cortar el `display_name` por comas: se probo eso primero y fallo
    con direcciones donde Nominatim antepone el nombre de un POI/edificio
    (ej. buscando "Av Cabildo 2000" devolvia display_name="Tribeca,
    2000, Avenida Cabildo, ..." -- cortar por comas mostraba "Tribeca,
    2000" como principal, perdiendo la calle real)."""
    address = item.get("address") or {}

    calle = address.get("road")
    numero = address.get("house_number")
    if calle:
        principal = f"{calle} {numero}" if numero else calle
    else:
        # Sin `road` estructurado (ej. una plaza, un barrio entero) --
        # el primer tramo del display_name es lo mejor que hay.
        principal = (item.get("display_name") or "").split(",")[0].strip()

    vistos = {principal}
    partes_secundaria = []
    for clave in _CLAVES_SECUNDARIA:
        valor = address.get(clave)
        if valor and valor not in vistos:
            partes_secundaria.append(valor)
            vistos.add(valor)
    return principal, ", ".join(partes_secundaria)


def _consultar(direccion: str, contexto: str | None, limite: int) -> list[dict]:
    direccion = (direccion or "").strip()
    if not direccion:
        return []

    consulta = f"{direccion}, {contexto}, Argentina" if contexto else f"{direccion}, Argentina"
    params = {
        "q": consulta,
        "format": "json",
        "limit": limite,
        "addressdetails": 1,
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        crudos = resp.json()
    except requests.RequestException:
        return []

    resultados = []
    for item in crudos:
        try:
            principal, secundaria = _partir_nombre(item)
            resultados.append({
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "nombre": item.get("display_name", direccion),
                "principal": principal or direccion,
                "secundaria": secundaria,
            })
        except (KeyError, ValueError, TypeError):
            continue
    return resultados


def geocodificar(direccion: str, contexto: str | None = None) -> dict | None:
    """Devuelve {lat, lon, nombre} para la direccion (el resultado mas
    relevante segun Nominatim), o None si no encontro nada o hubo un
    error de red. `contexto` (ej. el barrio/partido ya elegido en el
    buscador, en texto libre tipo "Palermo, Capital Federal") ayuda a
    desambiguar direcciones cortas como "Cabildo 2000" que sin esa
    pista podrian resolver a otra ciudad, o a un resultado mucho menos
    preciso."""
    resultados = _consultar(direccion, contexto, limite=1)
    return resultados[0] if resultados else None


def sugerir(direccion: str, contexto: str | None = None, limite: int = 5) -> list[dict]:
    """Devuelve hasta `limite` sugerencias {lat, lon, nombre} para
    autocompletar el campo de direccion mientras el usuario escribe
    (mismo estilo que un buscador tipo Google Maps) -- lista vacia si
    no hay nada o hubo un error, nunca None (mas facil de iterar del
    lado del frontend)."""
    return _consultar(direccion, contexto, limite=limite)
