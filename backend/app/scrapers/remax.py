import re
import unicodedata

import requests

from app.geo import distancia_general_paz_km
from app.models import Filtros, Propiedad
from app.scrapers.base import Scraper, ScraperBloqueado


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


def _categoria(tipo_valor: str) -> str | None:
    if not tipo_valor:
        return None
    if tipo_valor.startswith("departamento"):
        return "departamento"
    if tipo_valor.startswith("casa"):
        return "casa"
    if tipo_valor == "ph":
        return "ph"
    if tipo_valor == "local":
        return "local"
    return None


def _normalizar(texto: str) -> str:
    if not texto:
        return ""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return sin_acentos.lower()


# Texto legible por provincia/ciudad para matchear contra geoLabel/displayAddress.
# El sufijo "-zona-<cardinal>" (ver frontend UBICACIONES) se ignora aca: no hay
# forma confiable de mapear cada partido del GBA a su zona sin una lista curada
# mucho mas grande, asi que se filtra por la provincia entera nomas.
UBICACION_DISPLAY = {
    "capital-federal": "Capital Federal",
    "buenos-aires": "Buenos Aires",
    "cordoba": "Cordoba",
    "santa-fe": "Santa Fe",
    "mendoza": "Mendoza",
}
_ZONA_SUFIJO = re.compile(r"-zona-(norte|sur|este|oeste)$")


class RemaxScraper(Scraper):
    """
    RE/MAX Argentina es una app Angular con SSR: el HTML trae un bloque
    `<script id="ng-state">` (TransferState de Angular) con las respuestas
    de API ya cacheadas, ahi se encontro el endpoint real
    api-ar.redremax.com/remaxweb-ar/api/listings/findAllWithEntrepreneurships
    -- es publico, no requiere auth, y no tiene anti-bot detectado.

    Confirmado en vivo que el filtro `in=operationId:{1|2}` funciona
    server-side (solo trae venta o solo alquiler). El filtro de tipo de
    propiedad NO se manda al servidor (no se pudo confirmar la sintaxis
    para combinar varios typeId), se aplica del lado del cliente sobre
    el campo `type.value` de cada resultado.

    Ubicacion: el filtro nativo del sitio se vio poco confiable en las
    pruebas (buscando "Capital Federal" aparecian avisos de Mendoza), asi
    que en vez de replicarlo se arma un filtro de texto client-side
    contra `geoLabel` + `displayAddress` de cada resultado (ver
    UBICACION_DISPLAY). No distingue Zona Norte/Sur/Este/Oeste dentro de
    Buenos Aires -- filtra por la provincia entera, no hay una lista
    curada de que partido cae en cada zona.
    """

    name = "remax"
    API_URL = "https://api-ar.redremax.com/remaxweb-ar/api/listings/findAllWithEntrepreneurships"
    SITE_URL = "https://www.remax.com.ar"
    IMG_BASE = "https://d1acdg20u0pmxj.cloudfront.net"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "es-AR,es;q=0.9",
    }
    OPERACION_IDS = {"venta": 1, "alquiler": 2}

    def _imagen_url(self, item: dict) -> str | None:
        fotos = item.get("photos") or []
        if not fotos:
            return None
        raw = fotos[0].get("rawValue", "")
        partes = raw.split("/")
        if len(partes) != 3:
            return None
        carpeta, entidad, archivo = partes
        return f"{self.IMG_BASE}/{carpeta}/{entidad}/360x200/{archivo}.webp"

    def _ubicacion_buscada(self, filtros: Filtros) -> str:
        slug = (filtros.ubicacion or "").strip("/").lower()
        slug_base = _ZONA_SUFIJO.sub("", slug)
        texto = UBICACION_DISPLAY.get(slug_base, slug_base.replace("-", " "))
        return _normalizar(texto)

    def search(self, filtros: Filtros) -> list[Propiedad]:
        operation_id = self.OPERACION_IDS.get(filtros.operacion.value, 1)
        # pageSize mas grande que el resto de los portales: al filtrar
        # ubicacion del lado del cliente sobre resultados de todo el pais,
        # con pageSize chico casi no quedan avisos de una provincia puntual.
        params = {
            "page": 0,
            "pageSize": 100,
            "sort": "-createdAt",
            "in": f"operationId:{operation_id}",
        }
        ubicacion_buscada = self._ubicacion_buscada(filtros)

        try:
            resp = requests.get(self.API_URL, params=params, headers=self.HEADERS, timeout=15)
        except requests.RequestException as exc:
            raise ScraperBloqueado(f"error de red contactando RE/MAX: {exc}") from exc

        if resp.status_code in (403, 202, 429):
            raise ScraperBloqueado(
                f"RE/MAX devolvio HTTP {resp.status_code} (probable bloqueo anti-bot, reintentar mas tarde)"
            )
        if resp.status_code != 200:
            raise ScraperBloqueado(f"RE/MAX devolvio HTTP {resp.status_code} inesperado")

        try:
            data = resp.json()
        except ValueError as exc:
            raise ScraperBloqueado(f"RE/MAX no devolvio JSON valido: {exc}") from exc

        items = (data.get("data") or {}).get("data") or []
        resultados: list[Propiedad] = []

        for item in items:
            if _categoria(item.get("type", {}).get("value")) != filtros.tipo_propiedad.value:
                continue

            if ubicacion_buscada:
                texto_item = _normalizar(f"{item.get('geoLabel', '')} {item.get('displayAddress', '')}")
                if ubicacion_buscada not in texto_item:
                    continue

            precio = _parse_float(item.get("price"))
            moneda = item.get("currency", {}).get("value")
            expensas = _parse_float(item.get("expensesPrice"))
            ambientes = _parse_int(item.get("totalRooms"))
            dormitorios = _parse_int(item.get("bedrooms"))
            banos = _parse_int(item.get("bathrooms"))
            superficie_cubierta = _parse_float(item.get("dimensionCovered")) or None
            superficie = superficie_cubierta or _parse_float(item.get("dimensionTotalBuilt"))
            # dimensionLand es el tamano del terreno (relevante en casas/
            # lotes), no el equivalente a "superficie descubierta" del
            # sentido cubierta/descubierta argentino (patio, balcon, etc):
            # incluye jardin, playon, todo lo que no este construido.
            # Restarla de la cubierta daria un numero que no representa
            # lo mismo que en ZonaProp, asi que no se expone aca.

            # GeoJSON Point: coordinates viene como [longitud, latitud].
            coords = (item.get("location") or {}).get("coordinates") or []
            lon = _parse_float(coords[0]) if len(coords) == 2 else None
            lat = _parse_float(coords[1]) if len(coords) == 2 else None
            distancia_gral_paz = distancia_general_paz_km(lat, lon)

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
            if filtros.dormitorios_min and dormitorios is not None and dormitorios < filtros.dormitorios_min:
                continue
            if filtros.dormitorios_max and dormitorios is not None and dormitorios > filtros.dormitorios_max:
                continue
            if filtros.superficie_min and superficie is not None and superficie < filtros.superficie_min:
                continue
            if filtros.superficie_max and superficie is not None and superficie > filtros.superficie_max:
                continue
            if filtros.expensas_max and expensas is not None and expensas > filtros.expensas_max:
                continue
            if (
                filtros.distancia_general_paz_max_km is not None
                and distancia_gral_paz is not None
                and distancia_gral_paz > filtros.distancia_general_paz_max_km
            ):
                continue

            slug = item.get("slug", "")

            resultados.append(
                Propiedad(
                    portal=self.name,
                    external_id=str(item.get("id", slug)),
                    titulo=item.get("title") or "Sin titulo",
                    precio=precio,
                    moneda=moneda,
                    expensas=expensas,
                    direccion=item.get("displayAddress"),
                    barrio=item.get("geoLabel"),
                    ambientes=ambientes,
                    dormitorios=dormitorios,
                    banos=banos,
                    superficie_m2=superficie,
                    superficie_cubierta_m2=superficie_cubierta,
                    distancia_general_paz_km=distancia_gral_paz,
                    url=f"{self.SITE_URL}/listings/{slug}",
                    imagen_url=self._imagen_url(item),
                )
            )

        return resultados
