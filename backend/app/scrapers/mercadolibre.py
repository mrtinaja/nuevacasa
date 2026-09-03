import json
import re
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
    """

    name = "mercadolibre"
    BASE_URL = "https://inmuebles.mercadolibre.com.ar"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "es-AR,es;q=0.9",
    }
    TIPO_SLUGS = {
        "departamento": "departamentos",
        "casa": "casas",
        "ph": "phs",
        "local": "locales",
    }
    OPERACION_SLUGS = {"venta": "venta", "alquiler": "alquiler"}

    def _build_url(self, filtros: Filtros, ubicacion: str | None = None) -> str:
        tipo = self.TIPO_SLUGS.get(filtros.tipo_propiedad.value, f"{filtros.tipo_propiedad.value}s")
        operacion = self.OPERACION_SLUGS.get(filtros.operacion.value, filtros.operacion.value)
        ubicacion = (ubicacion if ubicacion is not None else filtros.ubicacion).strip("/").lower() or "capital-federal"
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
        url = self._build_url(filtros, ubicacion)
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
        except requests.RequestException as exc:
            raise ScraperBloqueado(f"error de red contactando MercadoLibre: {exc}") from exc

        if resp.status_code in (403, 202, 429):
            raise ScraperBloqueado(
                f"MercadoLibre devolvio HTTP {resp.status_code} "
                "(probable bloqueo anti-bot, reintentar mas tarde)"
            )
        if resp.status_code != 200:
            raise ScraperBloqueado(f"MercadoLibre devolvio HTTP {resp.status_code} inesperado")

        if "account-verification" in resp.url or "suspicious-traffic" in resp.text:
            raise ScraperBloqueado(
                "MercadoLibre redirigio a una pagina de verificacion de trafico "
                "sospechoso (bloqueo anti-bot con HTTP 200, sin ld+json real)"
            )

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
