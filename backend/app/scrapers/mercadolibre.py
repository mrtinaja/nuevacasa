import json
import re
import time
from datetime import date

import requests

from app.geo import distancia_general_paz_km
from app.models import Filtros, Propiedad
from app.scrapers.base import Scraper, ScraperBloqueado
from app.ubicaciones_geo import centroide
from app.zonas_cardinales import partidos_de_zona


def _parse_float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _parse_int(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def _dias_desde(fecha_iso: str | None) -> int | None:
    if not fecha_iso:
        return None
    try:
        fecha = date.fromisoformat(fecha_iso[:10])
    except ValueError:
        return None
    return (date.today() - fecha).days


class MercadoLibreScraper(Scraper):
    """
    La API oficial (/sites/MLA/search) quedo descartada: incluso con un
    token OAuth valido (client_credentials), MercadoLibre la bloquea con
    403 "PA_UNAUTHORIZED_RESULT_FROM_POLICIES" para apps no certificadas
    -- es una restriccion de plataforma, no algo que se arregle con
    codigo (confirmado en vivo con credenciales reales).

    En cambio, la pagina publica de MercadoLibre Inmuebles
    (inmuebles.mercadolibre.com.ar) trae los resultados en un bloque
    JSON-LD estandar (schema.org RealEstateListing) embebido en el HTML,
    sin login ni token. Mismo patron que ZonaProp: leer el JSON embebido
    en vez de parsear tarjetas HTML.

    Limitaciones conocidas:
    - El JSON-LD trae menos campos que ZonaProp: no hay dormitorios,
      banos, superficie ni antiguedad, solo ambientes (numberOfRooms).
      Esos filtros simplemente no se aplican aca.
    - El tipo "ph" no se pudo confirmar: no aparecio como categoria
      propia en la muestra que revisamos. Se arma como "phs" siguiendo
      el mismo patron que "departamentos"/"casas", pero queda pendiente
      verificarlo.
    - Solo pagina 1 (no se reprodujo la paginacion todavia).

    Mismo endurecimiento anti-bloqueo que Argenprop/ZonaProp: sesion
    persistente, calentamiento, headers completos, reintento con
    espera. MercadoLibre redirige con HTTP 200 (no un 403 seco), lo que
    sugiere un sistema de bot-management mas sofisticado (huella TLS,
    fingerprinting) que `requests` no puede imitar del todo -- asi que
    esto probablemente no alcance, pero es la misma mitigacion
    legitima ya aplicada en los otros dos, sin costo de intentarla.
    """

    name = "mercadolibre"
    BASE_URL = "https://inmuebles.mercadolibre.com.ar"
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
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }
    REINTENTOS = 1
    ESPERA_REINTENTO_SEG = 2
    TIPO_SLUGS = {
        "departamento": "departamentos",
        "casa": "casas",
        "ph": "phs",
        "local": "locales",
    }
    OPERACION_SLUGS = {"venta": "venta", "alquiler": "alquiler"}

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)
        self._calentado = False

    def _calentar_sesion(self) -> None:
        if self._calentado:
            return
        try:
            self._session.get(f"{self.BASE_URL}/", timeout=15)
        except requests.RequestException:
            pass  # si falla el calentamiento seguimos igual con el request real
        self._calentado = True

    def _obtener(self, url: str) -> requests.Response:
        intentos = self.REINTENTOS + 1
        ultima_resp = None
        for intento in range(intentos):
            if intento > 0:
                time.sleep(self.ESPERA_REINTENTO_SEG)
            try:
                resp = self._session.get(url, timeout=15)
            except requests.RequestException as exc:
                raise ScraperBloqueado(f"error de red contactando MercadoLibre: {exc}") from exc
            bloqueado_por_status = resp.status_code in (403, 202, 429)
            bloqueado_por_redirect = "account-verification" in resp.url or "suspicious-traffic" in resp.text
            if not bloqueado_por_status and not bloqueado_por_redirect:
                return resp
            ultima_resp = resp
        if "account-verification" in ultima_resp.url or "suspicious-traffic" in ultima_resp.text:
            raise ScraperBloqueado(
                "MercadoLibre redirigio a una pagina de verificacion de trafico "
                f"sospechoso (bloqueo anti-bot con HTTP 200, sin ld+json real -- ya se reintento {self.REINTENTOS} vez/veces)"
            )
        raise ScraperBloqueado(
            f"MercadoLibre devolvio HTTP {ultima_resp.status_code} "
            f"(probable bloqueo anti-bot, reintentar mas tarde -- ya se reintento {self.REINTENTOS} vez/veces)"
        )

    # MercadoLibre no reconoce "buenos-aires" (el slug que usa el resto de
    # la app para "toda la provincia") como ubicacion propia -- devuelve su
    # pagina real de "no encontramos resultados" (200 OK, no es bloqueo).
    # Su slug real para la provincia entera es "provincia-de-buenos-aires"
    # (confirmado: trae listings reales via ld+json). Los partidos
    # individuales (ej. "tigre", "la-plata") SI funcionan porque ML les
    # hace un 301 a su URL canonica con prefijo de subregion
    # (bsas-gba-norte/tigre, buenos-aires-interior/la-plata) y `requests`
    # sigue redirects solo; este alias es la unica ubicacion que no tiene
    # ese redirect y necesita mapeo manual.
    #
    # Bug distinto y mas grave encontrado el 2026-09-06: para las
    # capitales de provincia cuyo nombre de ciudad es IGUAL al de la
    # provincia (Salta, Corrientes, Catamarca, Formosa, La Rioja, San
    # Luis), el slug "<provincia>-capital" que usa el resto de la app
    # NO es una ubicacion real de ML -- en vez de la pagina de "sin
    # resultados" (que si detectamos como bloqueo/vacio en otros casos),
    # ML lo interpreta como texto libre y devuelve avisos de temas no
    # relacionados (CABA en la calle "Salta", en la calle "Corrientes",
    # etc.) con HTTP 200 y ld+json valido -- se ve como un resultado
    # real pero es completamente erroneo, mas grave que devolver vacio.
    # La ubicacion real de ML para estas es una ruta anidada
    # "provincia/ciudad" (mismo patron que Buenos Aires con
    # "bsas-gba-norte/tigre", pero sin redirect automatico -- hay que
    # armar la ruta a mano). Confirmado en vivo con ld+json real
    # (addressLocality = la ciudad correcta) para las 6.
    # "San Fernando del Valle de Catamarca" no tiene este problema
    # porque su nombre real no es igual al de la provincia.
    UBICACION_SLUGS = {
        "buenos-aires": "provincia-de-buenos-aires",
        "salta-capital": "salta/salta",
        "corrientes-capital": "corrientes/corrientes",
        "catamarca-capital": "san-fernando-del-valle-de-catamarca",
        "formosa-capital": "formosa/formosa",
        "la-rioja-capital": "la-rioja/la-rioja",
        "san-luis-capital": "san-luis/san-luis",
    }

    def _build_url(self, filtros: Filtros, ubicacion: str | None = None) -> str:
        tipo = self.TIPO_SLUGS.get(filtros.tipo_propiedad.value, f"{filtros.tipo_propiedad.value}s")
        operacion = self.OPERACION_SLUGS.get(filtros.operacion.value, filtros.operacion.value)
        ubicacion = (ubicacion if ubicacion is not None else filtros.ubicacion).strip("/").lower() or "capital-federal"
        ubicacion = self.UBICACION_SLUGS.get(ubicacion, ubicacion)
        return f"{self.BASE_URL}/{tipo}/{operacion}/{ubicacion}/"

    def _extraer_listings(self, html: str) -> list[dict]:
        match = re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
        if match is None:
            return []
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
        return [item for item in data.get("@graph", []) if item.get("@type") == "RealEstateListing"]

    def search(self, filtros: Filtros) -> list[Propiedad]:
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
                f"MercadoLibre bloqueo los {len(errores)}/{len(partidos)} partidos de la zona: {errores[0]}"
            )
        return resultados

    def _buscar_una_ubicacion(self, filtros: Filtros, ubicacion: str) -> list[Propiedad]:
        self._calentar_sesion()
        url = self._build_url(filtros, ubicacion)
        resp = self._obtener(url)

        listings = self._extraer_listings(resp.text)
        resultados: list[Propiedad] = []

        # No hay coordenadas por aviso en el JSON-LD: se aproxima con el
        # centroide de la zona buscada (mismo valor para todos los avisos
        # de esta busqueda -- no es tan preciso como ZonaProp/RE-MAX, que
        # traen lat/lon real por aviso).
        centro = centroide(ubicacion)
        distancia_gral_paz = distancia_general_paz_km(*centro) if centro else None

        for item in listings:
            offer = item.get("offers") or {}
            precio = _parse_float(offer.get("price"))
            moneda = offer.get("priceCurrency")
            ambientes = _parse_int(item.get("numberOfRooms"))

            address = item.get("address") or {}
            barrio = address.get("addressLocality")
            dias_publicado = _dias_desde(item.get("datePosted"))

            if filtros.moneda and moneda and moneda != filtros.moneda.value:
                continue
            if filtros.precio_min and precio is not None and precio < filtros.precio_min:
                continue
            if filtros.precio_max and precio is not None and precio > filtros.precio_max:
                continue
            if filtros.ambientes_min and ambientes is not None and ambientes < filtros.ambientes_min:
                continue
            if filtros.ambientes_max and ambientes is not None and ambientes > filtros.ambientes_max:
                continue
            if filtros.publicado_max_dias is not None and dias_publicado is not None and dias_publicado > filtros.publicado_max_dias:
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
                    external_id=offer.get("url", item.get("name", "")),
                    titulo=item.get("name") or "Sin titulo",
                    precio=precio,
                    moneda=moneda,
                    barrio=barrio,
                    ambientes=ambientes,
                    dias_desde_publicacion=dias_publicado,
                    distancia_general_paz_km=distancia_gral_paz,
                    distancia_general_paz_aprox=True,
                    url=offer.get("url", ""),
                    imagen_url=item.get("image"),
                )
            )

        return resultados
