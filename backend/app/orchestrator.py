import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models import Filtros, PortalResultado, Propiedad, SearchResponse
from app.scrapers.argenprop import ArgenpropScraper
from app.scrapers.base import ScraperBloqueado, ScraperNoImplementado
from app.scrapers.mercadolibre import MercadoLibreScraper
from app.scrapers.remax import RemaxScraper
from app.scrapers.zonaprop import ZonapropScraper

SCRAPERS = {
    s.name: s
    for s in [
        ArgenpropScraper(),
        MercadoLibreScraper(),
        ZonapropScraper(),
        RemaxScraper(),
    ]
}


# Cache muy simple en memoria: si dos busquedas piden lo mismo a un
# portal dentro de la ventana de tiempo, la segunda no vuelve a
# scrapear -- devuelve lo que ya se trajo. Esto no "extiende" un
# bloqueo anti-bot que ya paso, pero evita gatillar uno nuevo por
# pegarle al portal de mas cuando el usuario repite o casi repite una
# busqueda (ej. toca "Buscar" de nuevo, cambia un filtro que ni se
# aplica a este portal, etc.). Se pierde al reiniciar el backend --
# no hace falta mas que eso para este prototipo.
_CACHE_TTL_SEGUNDOS = 10 * 60
_cache: dict[str, tuple[float, list[Propiedad], PortalResultado]] = {}


def _clave_cache(nombre: str, filtros: Filtros) -> str:
    datos = filtros.model_dump(mode="json")
    datos.pop("portales", None)  # no cambia el resultado de ESTE portal
    return f"{nombre}:{json.dumps(datos, sort_keys=True)}"


def _run_scraper(nombre: str, filtros: Filtros) -> tuple[list[Propiedad], PortalResultado]:
    clave = _clave_cache(nombre, filtros)
    en_cache = _cache.get(clave)
    ahora = time.time()
    if en_cache is not None and ahora - en_cache[0] < _CACHE_TTL_SEGUNDOS:
        return en_cache[1], en_cache[2]

    scraper = SCRAPERS[nombre]
    try:
        propiedades = scraper.search(filtros)
        resultado = PortalResultado(portal=nombre, status="ok", cantidad=len(propiedades))
    except ScraperNoImplementado as exc:
        propiedades, resultado = [], PortalResultado(portal=nombre, status="not_implemented", detalle=str(exc))
    except ScraperBloqueado as exc:
        propiedades, resultado = [], PortalResultado(portal=nombre, status="blocked", detalle=str(exc))
    except Exception as exc:  # noqa: BLE001 - queremos capturar cualquier fallo de un portal sin tumbar el resto
        propiedades, resultado = [], PortalResultado(portal=nombre, status="error", detalle=str(exc))

    if resultado.status == "ok":
        _cache[clave] = (ahora, propiedades, resultado)
    return propiedades, resultado


def buscar(filtros: Filtros) -> SearchResponse:
    portales = filtros.portales or list(SCRAPERS.keys())
    portales = [p for p in portales if p in SCRAPERS]

    propiedades: list[Propiedad] = []
    resultados_portal: list[PortalResultado] = []

    with ThreadPoolExecutor(max_workers=len(portales) or 1) as executor:
        futuros = {executor.submit(_run_scraper, nombre, filtros): nombre for nombre in portales}
        for futuro in as_completed(futuros):
            props, resultado = futuro.result()
            propiedades.extend(props)
            resultados_portal.append(resultado)

    if filtros.orden == "precio_asc":
        propiedades.sort(key=lambda p: (p.precio is None, p.precio))
    elif filtros.orden == "precio_desc":
        propiedades.sort(key=lambda p: (p.precio is None, -(p.precio or 0)))
    # "relevancia" y "mas_recientes" quedan en el orden en que respondio cada
    # portal -- todavia no tenemos fecha de publicacion para ordenar por eso.

    resultados_portal.sort(key=lambda r: r.portal)

    return SearchResponse(propiedades=propiedades, portales=resultados_portal)
