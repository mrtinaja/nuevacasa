"""Zonas cardinales de Buenos Aires (Norte/Oeste/Sur): mismos grupos y
partidos que `UBICACIONES["Buenos Aires"].grupos` en `frontend/app.js`
-- se mantienen sincronizados a mano, documentado en el README.

Buscar por zona cardinal significa buscar en TODOS los partidos de esa
zona a la vez (no hay un slug de portal que agrupe varios partidos en
un solo pedido). Cada scraper que soporta esto hace un pedido por
partido y junta los resultados.
"""

ZONAS_CARDINALES: dict[str, list[str]] = {
    "zona-norte": ["san-isidro", "vicente-lopez", "tigre", "san-fernando", "pilar", "nordelta"],
    "zona-oeste": ["moron", "ituzaingo", "merlo", "moreno"],
    "zona-sur": ["quilmes", "avellaneda", "lanus", "lomas-de-zamora", "la-plata"],
}


def partidos_de_zona(ubicacion_slug: str) -> list[str] | None:
    return ZONAS_CARDINALES.get((ubicacion_slug or "").strip("/").lower())
