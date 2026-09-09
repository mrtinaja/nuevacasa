import json
import re
import time

import requests
from bs4 import BeautifulSoup

from app.geo import distancia_general_paz_km
from app.models import Filtros, Propiedad
from app.scrapers.base import Scraper, ScraperBloqueado
from app.scrapers.zonaprop import PARTIDOS_BUENOS_AIRES_TODOS
from app.zonas_cardinales import partidos_de_zona


def _parse_int(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def _parse_float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _extraer_ga_listings(html: str) -> dict:
    """El precio/moneda/titulo de cada aviso NO esta en el HTML visible
    (se pinta client-side, ver docstring de la clase) -- viene en un
    <script>var gAListings = {...};</script> pensado para analytics
    (Google Tag Manager), pero es la unica fuente confiable de esos
    campos en la respuesta cruda. Escaneo de llaves balanceadas (no un
    regex greedy) porque item_name puede traer texto libre con
    caracteres raros, y un ";" o "}" suelto en un string no deberia
    cortar el objeto antes de tiempo."""
    marker = "var gAListings = "
    idx = html.find(marker)
    if idx == -1:
        return {}
    start = idx + len(marker)
    if start >= len(html) or html[start] != "{":
        return {}

    i = start
    depth = 0
    in_str = False
    str_char = ""
    escaped = False
    while i < len(html):
        c = html[i]
        if in_str:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == str_char:
                in_str = False
        else:
            if c in ('"', "'"):
                in_str = True
                str_char = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
        i += 1

    try:
        return json.loads(html[start:i])
    except json.JSONDecodeError:
        return {}


# "capital-federal" solo (el agregado "Todos los barrios") NO devuelve
# avisos directo -- confirmado en vivo: 200 OK, 48.607 en el <title>,
# pero el HTML es una pagina de "elegi un barrio" (class="items-list",
# sin ningun "li.serp-snippet" ni gAListings), no un listado real.
# Mismo problema que "toda la provincia de Buenos Aires" en otros
# portales -- se resuelve igual, con fan-out por barrio. Recortado a
# un subconjunto de 10 (no los 48 barrios reales) para no disparar una
# rafaga larga por busqueda, mismo criterio que
# PARTIDOS_BUENOS_AIRES_TODOS en zonaprop.py -- se priorizan los
# barrios de mayor volumen/busqueda real.
BARRIOS_CAPITAL_FEDERAL_TODOS = [
    "palermo", "belgrano", "recoleta", "caballito", "villa-urquiza",
    "flores", "almagro", "villa-crespo", "nunez", "puerto-madero",
]


def _texto_microdato(li, itemprop: str) -> str | None:
    el = li.find(attrs={"itemprop": itemprop})
    if el is None:
        return None
    return el.get("content") or el.get_text(strip=True) or None


class IcasasScraper(Scraper):
    """
    icasas.com.ar (grupo Proppit/LiFULL Connect) -- portal de avisos
    clasificados, mas parecido a un marketplace abierto (muchos
    publicadores individuales, no solo inmobiliarias grandes) que a
    ZonaProp/Argenprop. Investigado en vivo el 2026-09-09 buscando una
    quinta fuente independiente (Properati quedo descartado: bloquea
    esta red de raiz con 401 "Access Denied" hasta en /robots.txt, un
    bloqueo de infraestructura, no de comportamiento de bot -- no se
    investigo mas por eso).

    Sin bloqueo anti-bot detectado en ninguna prueba (headers realistas
    alcanzan, sin sesion/cookies especiales necesarias).

    **El precio/moneda/titulo NO estan en el HTML visible** de la
    respuesta cruda -- se pintan del lado del cliente. La unica fuente
    confiable es un bloque `<script>var gAListings = {...}` pensado
    para analytics (Google Tag Manager), indexado por el mismo `id`
    que trae cada `<li class="serp-snippet">` (ver _extraer_ga_listings).
    El resto (direccion, lat/lon, ambientes, banos, superficie) si esta
    en microdata schema.org normal en el HTML.

    **Trae lat/lon real por aviso** (microdata `geo`/`latitude`/
    `longitude`) -- a diferencia de Argenprop/MercadoLibre, queda a la
    altura de ZonaProp/RE-MAX en precision de mapa.

    **Filtro de precio soportado via URL** (confirmado en vivo):
    sufijo "/f_{min}-{max}-price" (o solo "/f_{min}-price" para "desde
    X" sin techo). Ambientes/dormitorios NO se encontro como filtro de
    URL ni de query string -- se trae sin ese filtro y se aplica
    despues del lado del cliente (mismo criterio que ya usa Argenprop
    para filtros que el portal no soporta).

    **Slugs de ubicacion propios, no siempre coinciden con los del
    resto de la app** (confirmado en vivo, ver UBICACION_SLUGS): p.ej.
    "cordoba" en icasas resuelve a Cordoba CAPITAL, no a toda la
    provincia (mismo tipo de trampa que ya paso con Rosario/Santa Fe
    en otros portales) -- por eso el agregado "toda la provincia" de
    Buenos Aires usa fan-out por partido (reutiliza el mismo subconjunto
    curado de ZonaProp, PARTIDOS_BUENOS_AIRES_TODOS) en vez de un pedido
    directo. Los barrios de Capital Federal necesitan el prefijo
    "capital-federal/" (confirmado: "palermo" solo, sin ese prefijo, da
    410 "Anuncio no encontrado"). El agregado "capital-federal" (Todos
    los barrios) tiene el MISMO problema que "toda la provincia de
    Buenos Aires": 200 OK pero es una pagina de "elegi un barrio", sin
    avisos reales -- mismo fan-out, ver BARRIOS_CAPITAL_FEDERAL_TODOS.

    **Sin paginar**: como el resto de los scrapers de este proyecto
    (ver argenprop.py), se trae solo la primera pagina de resultados
    por ubicacion.
    """

    name = "icasas"
    BASE_URL = "https://www.icasas.com.ar"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "es-AR,es;q=0.9",
    }
    REINTENTOS = 1
    ESPERA_REINTENTO_SEG = 2

    TIPO_SLUGS = {
        "departamento": "departamentos",
        "casa": "casas",
        "ph": "ph",
        "local": "locales",
    }

    # Los 48 barrios oficiales de CABA (Ley 1777, mismo set que
    # delitos.py) + Barrio Norte -- necesitan el prefijo
    # "capital-federal/" en la URL de icasas. El resto de las
    # ubicaciones (partidos de Buenos Aires, otras provincias/ciudades)
    # van solas, sin prefijo (confirmado en vivo con moron/quilmes/
    # rosario/cordoba).
    _CABA_BARRIOS = {
        "retiro", "san-nicolas", "puerto-madero", "san-telmo", "monserrat", "constitucion",
        "recoleta", "balvanera", "san-cristobal", "la-boca", "barracas", "parque-patricios",
        "nueva-pompeya", "almagro", "boedo", "caballito", "flores", "parque-chacabuco",
        "villa-soldati", "villa-riachuelo", "villa-lugano", "liniers", "mataderos",
        "parque-avellaneda", "versalles", "monte-castro", "villa-real", "floresta",
        "velez-sarsfield", "villa-luro", "villa-general-mitre", "villa-devoto",
        "villa-del-parque", "villa-santa-rita", "coghlan", "saavedra", "villa-urquiza",
        "villa-pueyrredon", "belgrano", "colegiales", "nunez", "palermo", "chacarita",
        "villa-crespo", "la-paternal", "villa-ortuzar", "agronomia", "parque-chas",
        "barrio-norte",
    }

    # Slug curado del proyecto -> slug real de icasas, solo para los
    # casos confirmados en vivo donde NO coinciden.
    _UBICACION_SLUGS = {
        "la-plata": "plata",
        "mar-del-plata": "mar-plata",
        "lomas-de-zamora": "lomas-zamora",
    }

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)

    def _obtener(self, url: str) -> requests.Response:
        intentos = self.REINTENTOS + 1
        ultima_resp = None
        for intento in range(intentos):
            if intento > 0:
                time.sleep(self.ESPERA_REINTENTO_SEG)
            try:
                resp = self._session.get(url, timeout=15)
            except requests.RequestException as exc:
                raise ScraperBloqueado(f"error de red contactando icasas: {exc}") from exc
            if resp.status_code not in (403, 202, 429):
                return resp
            ultima_resp = resp
        raise ScraperBloqueado(
            f"icasas devolvio HTTP {ultima_resp.status_code} "
            f"(probable bloqueo anti-bot, reintentar mas tarde -- ya se reintento {self.REINTENTOS} vez/veces)"
        )

    def _build_url(self, filtros: Filtros, ubicacion: str | None = None) -> str:
        ubicacion = (ubicacion if ubicacion is not None else filtros.ubicacion).strip("/").lower() or "capital-federal"
        ubicacion = self._UBICACION_SLUGS.get(ubicacion, ubicacion)
        if ubicacion in self._CABA_BARRIOS and ubicacion != "capital-federal":
            ubicacion = f"capital-federal/{ubicacion}"

        tipo = self.TIPO_SLUGS.get(filtros.tipo_propiedad.value, f"{filtros.tipo_propiedad.value}s")
        url = f"{self.BASE_URL}/{filtros.operacion.value}/{tipo}/{ubicacion}"

        # Filtro de precio via sufijo de URL -- reduce lo que hay que
        # traer y paginar, pero igual se re-chequea del lado del
        # cliente mas abajo (misma logica que el resto de los scrapers:
        # el filtro en la URL es una optimizacion, no la unica fuente
        # de verdad).
        if filtros.precio_min or filtros.precio_max:
            minimo = int(filtros.precio_min) if filtros.precio_min else 0
            if filtros.precio_max:
                url += f"/f_{minimo}-{int(filtros.precio_max)}-price"
            else:
                url += f"/f_{minimo}-price"

        return url

    def search(self, filtros: Filtros) -> list[Propiedad]:
        slug = (filtros.ubicacion or "").strip("/").lower()
        if slug == "buenos-aires":
            partidos = PARTIDOS_BUENOS_AIRES_TODOS
        elif slug == "capital-federal":
            partidos = BARRIOS_CAPITAL_FEDERAL_TODOS
        else:
            partidos = partidos_de_zona(filtros.ubicacion)
        if not partidos:
            return self._buscar_una_ubicacion(filtros, filtros.ubicacion)

        resultados: list[Propiedad] = []
        errores: list[str] = []
        for partido in partidos:
            try:
                resultados.extend(self._buscar_una_ubicacion(filtros, partido))
            except ScraperBloqueado as exc:
                errores.append(str(exc))
        if not resultados and errores:
            raise ScraperBloqueado(
                f"icasas bloqueo los {len(errores)}/{len(partidos)} partidos de la zona: {errores[0]}"
            )
        return resultados

    def _buscar_una_ubicacion(self, filtros: Filtros, ubicacion: str) -> list[Propiedad]:
        url = self._build_url(filtros, ubicacion)
        resp = self._obtener(url)

        # Ubicacion sin avisos o slug no reconocido por icasas (algunas
        # localidades curadas del resto de la app no tienen equivalente
        # exacto aca, ver docstring) -- 404/410 se trata como "sin
        # resultados", no como bloqueo.
        if resp.status_code in (404, 410):
            return []
        if resp.status_code != 200:
            raise ScraperBloqueado(f"icasas devolvio HTTP {resp.status_code} inesperado")

        soup = BeautifulSoup(resp.text, "html.parser")
        ga_listings = _extraer_ga_listings(resp.text)
        resultados: list[Propiedad] = []

        for li in soup.select("li.serp-snippet"):
            datos_ga = ga_listings.get(li.get("id") or "", {})

            precio = _parse_float(datos_ga.get("price"))
            # gAListings trae basura de precio de vez en cuando --
            # confirmado en vivo "price":1.0 (relleno de icasas para
            # avisos "Consultar precio": GA4 exige un numero, no null,
            # el sitio muestra "Consultar precio", no "USD 1") y
            # tambien "price":97.27 en un depto de 111 m2 (sin
            # explicacion clara, pero un departamento a la venta por
            # USD 97 no existe). En vez de perseguir cada caso puntual,
            # se descarta cualquier precio por debajo de un piso
            # imposible para una propiedad real -- ningun aviso real de
            # venta/alquiler de este proyecto (departamento/casa/ph/
            # local) baja de USD 1.000. Sin este chequeo, un precio
            # basura colaba como el mas bajo de la busqueda (marcaba
            # falso "Buen precio" y arruinaba la mediana de precio/m2
            # de TODOS los portales, no solo icasas).
            if precio is not None and precio < 1000:
                precio = None
            moneda = datos_ga.get("currency")
            titulo = datos_ga.get("item_name") or "Sin titulo"

            enlace = li.select_one("a.detail-redirection")
            href = enlace.get("href") if enlace else ""

            lat = _parse_float(_texto_microdato(li, "latitude"))
            lon = _parse_float(_texto_microdato(li, "longitude"))
            distancia_gral_paz = distancia_general_paz_km(lat, lon)

            direccion = _texto_microdato(li, "streetAddress") or None
            barrio = _texto_microdato(li, "addressLocality") or None

            # Un solo contador de "rooms" (icono de cama) -- igual que
            # Argenprop, se usa para ambientes Y dormitorios porque la
            # tarjeta de listado no distingue entre ambos.
            rooms_el = li.select_one(".rooms")
            habitaciones = _parse_int(rooms_el.get_text(strip=True)) if rooms_el else None
            banos_el = li.select_one(".bathrooms")
            banos = _parse_int(banos_el.get_text(strip=True)) if banos_el else None
            area_el = li.select_one(".areaBuilt")
            superficie = None
            if area_el:
                m = re.search(r"([\d.,]+)", area_el.get_text(strip=True))
                if m:
                    superficie = _parse_float(m.group(1).replace(".", "").replace(",", "."))

            img_el = li.select_one(".slider-ad img[data-lazy]") or li.select_one(".slider-ad img")
            imagen_url = (img_el.get("data-lazy") or img_el.get("src")) if img_el else None
            if imagen_url and "loading-image" in imagen_url:
                imagen_url = None

            if filtros.moneda and moneda and moneda != filtros.moneda.value:
                continue
            if filtros.precio_min and precio is not None and precio < filtros.precio_min:
                continue
            if filtros.precio_max and precio is not None and precio > filtros.precio_max:
                continue
            if filtros.ambientes_min and habitaciones is not None and habitaciones < filtros.ambientes_min:
                continue
            if filtros.ambientes_max and habitaciones is not None and habitaciones > filtros.ambientes_max:
                continue
            if filtros.dormitorios_min and habitaciones is not None and habitaciones < filtros.dormitorios_min:
                continue
            if filtros.dormitorios_max and habitaciones is not None and habitaciones > filtros.dormitorios_max:
                continue
            if filtros.superficie_min and superficie is not None and superficie < filtros.superficie_min:
                continue
            if filtros.superficie_max and superficie is not None and superficie > filtros.superficie_max:
                continue
            if (
                filtros.distancia_general_paz_max_km is not None
                and distancia_gral_paz is not None
                and distancia_gral_paz > filtros.distancia_general_paz_max_km
            ):
                continue

            resultados.append(
                Propiedad(
                    portal=self.name,
                    external_id=li.get("id") or href,
                    titulo=titulo,
                    precio=precio,
                    moneda=moneda,
                    direccion=direccion,
                    barrio=barrio,
                    ambientes=habitaciones,
                    dormitorios=habitaciones,
                    banos=banos,
                    superficie_m2=superficie,
                    distancia_general_paz_km=distancia_gral_paz,
                    lat=lat,
                    lon=lon,
                    url=self.BASE_URL + href if href.startswith("/") else href,
                    imagen_url=imagen_url,
                )
            )

        return resultados
