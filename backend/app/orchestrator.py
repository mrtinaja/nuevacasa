import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from app.delitos import info_delitos
from app.historial import registrar_y_enriquecer
from app.homicidios import info_homicidios
from app.models import CentroZona, Filtros, InfoDelitos, InfoHomicidios, InfoSismico, PortalResultado, Propiedad, SearchResponse
from app.precio_justo import marcar_buen_precio
from app.riesgo_sismico import info_sismico
from app.scrapers.argenprop import ArgenpropScraper
from app.scrapers.base import ScraperBloqueado, ScraperNoImplementado
from app.scrapers.icasas import IcasasScraper
from app.scrapers.mercadolibre import MercadoLibreScraper
from app.scrapers.remax import RemaxScraper
from app.scrapers.zonaprop import ZonapropScraper
from app.ubicaciones_geo import centroide

SCRAPERS = {
    s.name: s
    for s in [
        ArgenpropScraper(),
        MercadoLibreScraper(),
        ZonapropScraper(),
        RemaxScraper(),
        IcasasScraper(),
    ]
}

# Techo de pedidos EN VUELO por portal, compartido por todas las
# busquedas del backend (no por busqueda individual). El coalescing de
# mas abajo evita pedidos REPETIDOS en simultaneo, pero no dice nada
# si 5 usuarios buscan 5 zonas DISTINTAS al mismo tiempo -- eso son 5
# pedidos reales en paralelo contra el mismo portal, la misma rafaga
# que ya confirmamos que dispara bloqueos (22 pedidos seguidos a
# ZonaProp = bloqueo). Con el semaforo, el pedido 3ro en adelante
# espera su turno en cola en vez de sumarse a la rafaga -- mitigacion
# legitima (pedir de a poco), no evasion; sigue pudiendo bloquear
# igual si el bloqueo es por reputacion de IP y no por volumen.
_MAX_PEDIDOS_CONCURRENTES_POR_PORTAL = 2
_semaforos_portal = {nombre: threading.Semaphore(_MAX_PEDIDOS_CONCURRENTES_POR_PORTAL) for nombre in SCRAPERS}


# Cache muy simple en memoria: si dos busquedas piden lo mismo a un
# portal dentro de la ventana de tiempo, la segunda no vuelve a
# scrapear -- devuelve lo que ya se trajo. Esto no "extiende" un
# bloqueo anti-bot que ya paso, pero evita gatillar uno nuevo por
# pegarle al portal de mas cuando el usuario repite o casi repite una
# busqueda (ej. toca "Buscar" de nuevo, cambia un filtro que ni se
# aplica a este portal, etc.). Se pierde al reiniciar el backend.
#
# Subido de 10 a 30 min pensando en picos de trafico concurrente (ej.
# un post en LinkedIn): varias visitas casi al mismo tiempo buscando
# zonas populares (Capital Federal, Palermo, etc.) pegan todas contra
# el mismo backend/IP de Render -- exactamente el patron que ya
# confirmamos que dispara bloqueos con UN solo usuario de prueba.
# Una ventana mas larga absorbe busquedas repetidas de zonas populares
# entre visitantes distintos, no solo del mismo usuario reintentando.
_CACHE_TTL_SEGUNDOS = 30 * 60
_cache: dict[str, tuple[float, list[Propiedad], PortalResultado]] = {}

# Coalescing de pedidos ("single-flight"): si dos usuarios buscan lo
# mismo casi al mismo tiempo (ej. varios entrando desde un link
# compartido y buscando "Palermo" en la misma ventana de un par de
# segundos), el cache de arriba NO alcanza a evitar el segundo scrapeo
# real -- el primero todavia no termino, asi que todavia no hay nada
# en _cache para reusar. Sin esto, una rafaga de N pedidos identicos
# simultaneos dispara N scrapeos reales contra el mismo portal en vez
# de 1, justo el patron que confirmamos que gatilla bloqueos.
#
# _en_progreso guarda, por clave, el Future del pedido que ya esta en
# vuelo -- el primer thread que llega para una clave se vuelve "lider"
# (crea el Future y de verdad scrapea), cualquier otro que llegue
# mientras tanto para la MISMA clave se vuelve "espectador" y solo
# espera el resultado del lider (future.result() bloquea el thread,
# no ocupa CPU). _lock_en_progreso protege el dict en si -- la seccion
# critica es solo "leer o crear la entrada", microscopica, no el
# scrapeo entero.
_lock_en_progreso = threading.Lock()
_en_progreso: dict[str, "Future[tuple[list[Propiedad], PortalResultado]]"] = {}


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

    with _lock_en_progreso:
        future = _en_progreso.get(clave)
        soy_lider = future is None
        if soy_lider:
            future = _en_progreso[clave] = Future()

    if not soy_lider:
        return future.result()

    try:
        scraper = SCRAPERS[nombre]
        try:
            # El semaforo cubre la llamada COMPLETA a search() -- si el
            # scraper hace fan-out interno por varios partidos (ej.
            # ZonaProp/Argenprop/icasas con "toda la provincia"), el
            # permiso se retiene por todo ese fan-out, no solo por un
            # pedido HTTP suelto. Es exactamente lo que se quiere: ese
            # fan-out YA es una rafaga en si mismo, no debería sumarse
            # una segunda busqueda en paralelo encima.
            with _semaforos_portal[nombre]:
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
        future.set_result((propiedades, resultado))
        return propiedades, resultado
    except BaseException as exc:  # noqa: BLE001 - un espectador esperando no debe quedar colgado si el lider explota
        future.set_exception(exc)
        raise
    finally:
        with _lock_en_progreso:
            _en_progreso.pop(clave, None)


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

    # Estas dos solo tienen sentido con el inventario de todos los
    # portales ya junto -- por eso se calculan aca y no en cada scraper.
    marcar_buen_precio(propiedades)
    registrar_y_enriquecer(propiedades)

    if filtros.orden == "precio_asc":
        propiedades.sort(key=lambda p: (p.precio is None, p.precio))
    elif filtros.orden == "precio_desc":
        propiedades.sort(key=lambda p: (p.precio is None, -(p.precio or 0)))
    elif filtros.orden == "mas_recientes":
        # Solo ZonaProp y MercadoLibre traen fecha real; Argenprop y
        # RE/MAX quedan sin ese dato (None) y van al final, en el orden
        # en que respondio cada portal.
        propiedades.sort(key=lambda p: (p.dias_desde_publicacion is None, p.dias_desde_publicacion))
    # "relevancia" queda en el orden en que respondio cada portal.

    resultados_portal.sort(key=lambda r: r.portal)

    datos_delitos = info_delitos(filtros.ubicacion)
    delitos_zona = InfoDelitos(**datos_delitos) if datos_delitos else None

    datos_sismico = info_sismico(filtros.ubicacion)
    riesgo_sismico = InfoSismico(**datos_sismico) if datos_sismico else None

    datos_homicidios = info_homicidios(filtros.ubicacion)
    homicidios_zona = InfoHomicidios(**datos_homicidios) if datos_homicidios else None

    punto_zona = centroide(filtros.ubicacion)
    centro_zona = CentroZona(lat=punto_zona[0], lon=punto_zona[1]) if punto_zona else None

    return SearchResponse(
        propiedades=propiedades,
        portales=resultados_portal,
        delitos_zona=delitos_zona,
        riesgo_sismico=riesgo_sismico,
        homicidios_zona=homicidios_zona,
        centro_zona=centro_zona,
    )
