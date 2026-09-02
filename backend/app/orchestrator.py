from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models import Filtros, PortalResultado, Propiedad, SearchResponse
from app.scrapers.argenprop import ArgenpropScraper
from app.scrapers.base import ScraperBloqueado, ScraperNoImplementado
from app.scrapers.mercadolibre import MercadoLibreScraper
from app.scrapers.properati import ProperatiScraper
from app.scrapers.remax import RemaxScraper
from app.scrapers.zonaprop import ZonapropScraper

SCRAPERS = {
    s.name: s
    for s in [
        ArgenpropScraper(),
        MercadoLibreScraper(),
        ZonapropScraper(),
        RemaxScraper(),
        ProperatiScraper(),
    ]
}


def _run_scraper(nombre: str, filtros: Filtros) -> tuple[list[Propiedad], PortalResultado]:
    scraper = SCRAPERS[nombre]
    try:
        propiedades = scraper.search(filtros)
        return propiedades, PortalResultado(portal=nombre, status="ok", cantidad=len(propiedades))
    except ScraperNoImplementado as exc:
        return [], PortalResultado(portal=nombre, status="not_implemented", detalle=str(exc))
    except ScraperBloqueado as exc:
        return [], PortalResultado(portal=nombre, status="blocked", detalle=str(exc))
    except Exception as exc:  # noqa: BLE001 - queremos capturar cualquier fallo de un portal sin tumbar el resto
        return [], PortalResultado(portal=nombre, status="error", detalle=str(exc))


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
