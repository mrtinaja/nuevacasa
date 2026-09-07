"""Resuelve una direccion en texto libre a la zona curada (slug) mas
cercana -- el paso que le falta al perfil de riesgo por zona
(riesgo_seguros.py) para aceptar una direccion puntual en vez de un
slug de zona elegido a mano. Pensado para el caso real de uso de una
aseguradora: tienen una direccion (la del asegurado), no un slug de
NuevaCasa.

No hay poligonos reales de barrio/partido para hacer un point-in-polygon
correcto (serian ~135 partidos + 48 barrios + el resto del pais
curado) -- se aproxima con la zona cuya CENTROIDE esta mas cerca de la
direccion geocodificada (`ubicaciones_geo.py`, mismo dataset que ya usa
el resto del proyecto para aproximar distancias cuando no hay
coordenadas reales por aviso). Es una aproximacion, no una resolucion
administrativa exacta -- una direccion cerca del limite entre dos
barrios puede resolver al vecino en vez de al propio. Se devuelve
`distancia_km` siempre, para que quien llame pueda decidir si confiar
en el match (una distancia grande, ej. >15km en CABA, es señal de que
la direccion cae fuera de las zonas curadas) -- esta funcion no
descarta nada sola.

Se excluyen del match los agregados "toda la provincia/ciudad" (ej.
"buenos-aires", "capital-federal", "cordoba") -- son el centroide de
una region enorme, nunca deberian "ganar" como zona mas cercana a una
direccion puntual.
"""

import math

from app.geocodificar import geocodificar
from app.ubicaciones_geo import UBICACIONES_GEO

_AGREGADOS_PROVINCIALES = {
    "capital-federal", "buenos-aires", "cordoba", "santa-fe", "mendoza",
    "tucuman", "entre-rios", "salta", "misiones", "chaco", "corrientes",
    "santiago-del-estero", "san-juan", "jujuy", "rio-negro", "neuquen",
    "chubut", "catamarca", "formosa", "la-pampa", "la-rioja", "san-luis",
    "santa-cruz", "tierra-del-fuego",
}

_CANDIDATOS = {slug: c for slug, c in UBICACIONES_GEO.items() if slug not in _AGREGADOS_PROVINCIALES}

_RADIO_TIERRA_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * _RADIO_TIERRA_KM * math.asin(math.sqrt(a))


def zona_mas_cercana(direccion: str, contexto: str | None = None) -> dict | None:
    """Geocodifica `direccion` (Nominatim, ver geocodificar.py) y
    devuelve {slug, nombre_geocodificado, distancia_km} de la zona
    curada mas cercana, o None si Nominatim no encontro nada."""
    geo = geocodificar(direccion, contexto)
    if geo is None:
        return None

    slug_mas_cercano = min(
        _CANDIDATOS,
        key=lambda slug: _haversine_km(geo["lat"], geo["lon"], *_CANDIDATOS[slug]),
    )
    distancia = _haversine_km(geo["lat"], geo["lon"], *_CANDIDATOS[slug_mas_cercano])

    return {
        "slug": slug_mas_cercano,
        "nombre_geocodificado": geo["nombre"],
        "distancia_km": round(distancia, 2),
    }
