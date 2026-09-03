import re
import time

import requests
from bs4 import BeautifulSoup

from app.geo import distancia_general_paz_km
from app.models import Filtros, Propiedad
from app.scrapers.base import Scraper, ScraperBloqueado
from app.ubicaciones_geo import centroide
from app.zonas_cardinales import partidos_de_zona


def _parse_int(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _parse_float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


class ArgenpropScraper(Scraper):
    """
    Mitigacion de deuda tecnica (bloqueos anti-bot frecuentes): antes cada
    busqueda era un requests.get() suelto, sin cookies ni headers
    completos -- cualquier visitante real acumula cookies de sesion y
    manda mas headers que un navegador real envia por default. Ahora:

    - Se reutiliza una unica requests.Session() por instancia del
      scraper (persiste mientras el backend este corriendo), asi las
      cookies que Argenprop asigne sobreviven entre busquedas.
    - Antes de la primera busqueda de la sesion, se hace una visita
      "de calentamiento" al home (asi la primera cookie se consigue
      navegando como lo haria un browser, no pegandole directo a un
      listado).
    - Headers mas parecidos a un Chrome real (sec-ch-ua, sec-fetch-*,
      Accept completo), no solo User-Agent + Accept-Language.
    - Un reintento con backoff corto si la primera respuesta viene
      bloqueada, por si el bloqueo es de rafaga y no de ventana larga.

    Esto reduce pero NO elimina el riesgo de bloqueo: `requests` no
    puede imitar el fingerprint TLS real de un navegador (JA3), que es
    otra señal que los WAF mas sofisticados usan. Si Argenprop sigue
    bloqueando seguido, el siguiente paso seria migrar a un browser
    headless (Playwright), mucho mas pesado pero indistinguible a nivel
    de red.
    """

    name = "argenprop"
    BASE_URL = "https://www.argenprop.com"
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

    def _build_url(self, filtros: Filtros, ubicacion: str | None = None) -> str:
        ubicacion = (ubicacion if ubicacion is not None else filtros.ubicacion).strip("/").lower() or "capital-federal"
        return (
            f"{self.BASE_URL}/{filtros.tipo_propiedad.value}-"
            f"{filtros.operacion.value}-{ubicacion}"
        )

    def _extraer_features(self, item) -> tuple[float | None, int | None]:
        """Devuelve (superficie_m2, antiguedad_anios) leidos de card__main-features.
        Ese bloque no tiene claves fijas por posicion (varia segun el aviso),
        asi que se interpreta cada <li> por su texto."""
        superficie = None
        antiguedad = None
        for li in item.select(".card__main-features li"):
            texto = li.get_text(" ", strip=True)
            m_sup = re.search(r"([\d.,]+)\s*m", texto)
            if m_sup and superficie is None:
                crudo = m_sup.group(1).replace(".", "").replace(",", ".")
                superficie = _parse_float(crudo)
                continue
            m_anios = re.search(r"([\d]+)\s*a[\xf1n]os?", texto)
            if m_anios:
                antiguedad = _parse_int(m_anios.group(1))
            elif "estrenar" in texto.lower():
                antiguedad = 0
        return superficie, antiguedad

    def _extraer_expensas(self, item) -> float | None:
        el = item.select_one(".card__expenses")
        if el is None:
            return None
        match = re.search(r"([\d.,]+)", el.get_text(" ", strip=True))
        if not match:
            return None
        return _parse_float(match.group(1).replace(".", "").replace(",", "."))

    def _obtener(self, url: str) -> requests.Response:
        intentos = self.REINTENTOS + 1
        ultima_resp = None
        for intento in range(intentos):
            if intento > 0:
                time.sleep(self.ESPERA_REINTENTO_SEG)
            try:
                resp = self._session.get(url, timeout=15)
            except requests.RequestException as exc:
                raise ScraperBloqueado(f"error de red contactando Argenprop: {exc}") from exc
            if resp.status_code not in (403, 202, 429):
                return resp
            ultima_resp = resp
        raise ScraperBloqueado(
            f"Argenprop devolvio HTTP {ultima_resp.status_code} "
            f"(probable bloqueo anti-bot, reintentar mas tarde -- ya se reintento {self.REINTENTOS} vez/veces)"
        )

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
                f"Argenprop bloqueo los {len(errores)}/{len(partidos)} partidos de la zona: {errores[0]}"
            )
        return resultados

    def _buscar_una_ubicacion(self, filtros: Filtros, ubicacion: str) -> list[Propiedad]:
        self._calentar_sesion()
        url = self._build_url(filtros, ubicacion)
        resp = self._obtener(url)

        if resp.status_code != 200:
            raise ScraperBloqueado(f"Argenprop devolvio HTTP {resp.status_code} inesperado")

        soup = BeautifulSoup(resp.text, "html.parser")
        resultados: list[Propiedad] = []

        # Sin coordenadas por aviso: se aproxima con el centroide de la
        # zona buscada (ver comentario igual en mercadolibre.py).
        centro = centroide(ubicacion)
        distancia_gral_paz = distancia_general_paz_km(*centro) if centro else None

        for item in soup.select("div.listing__item"):
            a = item.select_one("a.card")
            if a is None:
                continue

            href = a.get("href", "")
            external_id = str(a.get("data-item-card") or href)
            precio = _parse_float(a.get("montonormalizado") or a.get("montooperacion"))
            dormitorios = _parse_int(a.get("dormitorios"))

            moneda_el = a.select_one(".card__currency")
            moneda = moneda_el.get_text(strip=True) if moneda_el else None

            direccion_el = a.select_one(".card__address")
            direccion = direccion_el.get_text(strip=True) if direccion_el else None

            imagen_url = None
            img_el = a.select_one(".card__photos img")
            if img_el is not None:
                imagen_url = img_el.get("src") or img_el.get("data-src")
                if imagen_url and "placeholder" in imagen_url:
                    imagen_url = None

            barrio_el = a.select_one(".card__title--primary")
            barrio = barrio_el.get_text(strip=True) if barrio_el else None

            titulo_el = a.select_one(".card__title")
            titulo = titulo_el.get_text(strip=True) if titulo_el else (barrio or "Sin titulo")

            superficie, antiguedad = self._extraer_features(a)
            expensas = self._extraer_expensas(a)

            # Filtros soportados con los datos que trae la tarjeta de listado.
            # con_cochera no se puede evaluar aca (esa info solo
            # esta en el detalle del aviso), asi que se ignoran en vez de
            # descartar avisos que podrian cumplirlos.
            if filtros.moneda and moneda and moneda != filtros.moneda.value:
                continue
            if filtros.precio_min and precio is not None and precio < filtros.precio_min:
                continue
            if filtros.precio_max and precio is not None and precio > filtros.precio_max:
                continue
            if filtros.ambientes_min and dormitorios is not None and dormitorios < filtros.ambientes_min:
                continue
            if filtros.ambientes_max and dormitorios is not None and dormitorios > filtros.ambientes_max:
                continue
            if filtros.dormitorios_min and dormitorios is not None and dormitorios < filtros.dormitorios_min:
                continue
            if filtros.dormitorios_max and dormitorios is not None and dormitorios > filtros.dormitorios_max:
                continue
            if filtros.superficie_min and superficie is not None and superficie < filtros.superficie_min:
                continue
            if filtros.superficie_max and superficie is not None and superficie > filtros.superficie_max:
                continue
            if filtros.antiguedad_max is not None and antiguedad is not None and antiguedad > filtros.antiguedad_max:
                continue
            if filtros.expensas_max and expensas is not None and expensas > filtros.expensas_max:
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
                    external_id=external_id,
                    titulo=titulo,
                    precio=precio,
                    moneda=moneda,
                    expensas=expensas,
                    direccion=direccion,
                    barrio=barrio,
                    ambientes=dormitorios,
                    dormitorios=dormitorios,
                    superficie_m2=superficie,
                    antiguedad_anios=antiguedad,
                    distancia_general_paz_km=distancia_gral_paz,
                    distancia_general_paz_aprox=True,
                    url=self.BASE_URL + href if href.startswith("/") else href,
                    imagen_url=imagen_url,
                )
            )

        return resultados
