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

# Circuit breaker corto por portal: distinto del semaforo de arriba
# (que limita CUANTOS pedidos van en simultaneo), esto decide si vale
# la pena intentar pedir en absoluto. Si un portal nos bloqueo un par
# de veces seguidas hace poco, lo mas probable es que siga en mal
# momento -- insistirle en cada pedido nuevo (gastando los 2
# reintentos con backoff de cada scraper) es mas lento para quien
# busca y mas grosero con el portal que ya esta filtrando. Mientras el
# circuito esta "abierto" se devuelve blocked al toque, sin tocar la
# red, y se reintenta de nuevo pasado el cooldown (por si ya se le
# paso el mal momento).
_UMBRAL_BLOQUEOS_SEGUIDOS = 2      # bloqueos dentro de la ventana para abrir el circuito
_VENTANA_BLOQUEOS_SEG = 60         # ventana en la que cuentan como "seguidos"
_COOLDOWN_CIRCUITO_SEG = 45        # cuanto se deja de insistir una vez abierto

_lock_circuito = threading.Lock()
_bloqueos_recientes: dict[str, list[float]] = {}
_circuito_abierto_hasta: dict[str, float] = {}


def _circuito_abierto(nombre: str) -> bool:
    with _lock_circuito:
        return time.time() < _circuito_abierto_hasta.get(nombre, 0)


def _registrar_bloqueo(nombre: str) -> None:
    ahora = time.time()
    with _lock_circuito:
        eventos = [t for t in _bloqueos_recientes.get(nombre, []) if ahora - t < _VENTANA_BLOQUEOS_SEG]
        eventos.append(ahora)
        _bloqueos_recientes[nombre] = eventos
        if len(eventos) >= _UMBRAL_BLOQUEOS_SEGUIDOS:
            _circuito_abierto_hasta[nombre] = ahora + _COOLDOWN_CIRCUITO_SEG


def _registrar_ok(nombre: str) -> None:
    with _lock_circuito:
        _bloqueos_recientes.pop(nombre, None)
        _circuito_abierto_hasta.pop(nombre, None)


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
        if _circuito_abierto(nombre):
            propiedades, resultado = [], PortalResultado(
                portal=nombre,
                status="blocked",
                detalle=(
                    f"{nombre} bloqueo {_UMBRAL_BLOQUEOS_SEGUIDOS} veces seguidas hace poco -- "
                    f"en pausa {_COOLDOWN_CIRCUITO_SEG}s antes de reintentar, sin gastar reintentos de mas."
                ),
            )
        else:
            scraper = SCRAPERS[nombre]
            try:
                # El semaforo cubre la llamada COMPLETA a search() -- si
                # el scraper hace fan-out interno por varios partidos
                # (ej. ZonaProp/Argenprop/icasas con "toda la
                # provincia"), el permiso se retiene por todo ese
                # fan-out, no solo por un pedido HTTP suelto. Es
                # exactamente lo que se quiere: ese fan-out YA es una
                # rafaga en si mismo, no debería sumarse una segunda
                # busqueda en paralelo encima.
                with _semaforos_portal[nombre]:
                    propiedades = scraper.search(filtros)
                resultado = PortalResultado(portal=nombre, status="ok", cantidad=len(propiedades))
                _registrar_ok(nombre)
            except ScraperNoImplementado as exc:
                propiedades, resultado = [], PortalResultado(portal=nombre, status="not_implemented", detalle=str(exc))
            except ScraperBloqueado as exc:
                propiedades, resultado = [], PortalResultado(portal=nombre, status="blocked", detalle=str(exc))
                _registrar_bloqueo(nombre)
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
