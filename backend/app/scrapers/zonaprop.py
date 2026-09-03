import json
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from app.geo import distancia_general_paz_km
from app.models import Filtros, Propiedad
from app.scrapers.base import Scraper, ScraperBloqueado
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


def _dias_desde(fecha_iso: str | None) -> int | None:
    """`modified_date` es la ultima modificacion del aviso, no
    estrictamente la fecha de publicacion original -- no hay otro campo
    mas confiable en los datos que trae la pagina de listado, asi que se
    usa como proxy de "actividad reciente"."""
    if not fecha_iso:
        return None
    try:
        fecha = datetime.fromisoformat(fecha_iso).date()
    except ValueError:
        return None
    return (date.today() - fecha).days


def _extraer_preloaded_state(html: str) -> dict | None:
    """El listado de ZonaProp viene armado por React con los datos ya
    embebidos en <script id="preloadedData">window.__PRELOADED_STATE__ =
    {...};</script>. Ese script puede tener mas de una sentencia, asi que
    hay que recortar el objeto JSON con un scanner de llaves balanceadas
    (cortar por el ultimo ';' antes de </script> agarra de mas)."""
    marker = "window.__PRELOADED_STATE__ = "
    idx = html.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    if start >= len(html) or html[start] != "{":
        return None

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
        return None


def _feature_valor(features: dict, feature_id: str):
    feature = features.get(feature_id)
    return feature.get("value") if feature else None


def _ubicar_barrio(location: dict | None) -> str | None:
    """postingLocation.location puede ser una sub-zona (label ZONA); subimos
    la cadena de parents hasta encontrar el nivel BARRIO."""
    nodo = location
    while nodo is not None:
        if nodo.get("label") == "BARRIO":
            return nodo.get("name")
        nodo = nodo.get("parent")
    return location.get("name") if location else None


def _tiene_feature(features: dict, *palabras_clave: str) -> bool | None:
    """mainFeatures solo trae una clave cuando el aviso efectivamente tiene
    ese atributo (ej. "Cochera" no aparece si la propiedad no tiene
    cochera), asi que su ausencia se interpreta como que no lo tiene --
    a diferencia de los filtros numericos, donde dato faltante = desconocido
    y no se descarta el aviso."""
    for feat in features.values():
        label = (feat.get("label") or "").lower()
        if any(palabra in label for palabra in palabras_clave):
            return True
    return False


class ZonapropScraper(Scraper):
    name = "zonaprop"
    BASE_URL = "https://www.zonaprop.com.ar"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "es-AR,es;q=0.9",
        "Referer": "https://www.zonaprop.com.ar/",
    }

    TIPO_SLUGS = {
        "departamento": "departamentos",
        "casa": "casas",
        "ph": "ph",
        "local": "locales-comerciales",
    }

    def _build_url(self, filtros: Filtros, ubicacion: str | None = None) -> tuple[str, str | None]:
        """Devuelve (url, amenity_aplicada_en_url). Confirmamos en vivo que
        ZonaProp soporta sufijos "-con-patio", "-con-terraza", "-con-jardin",
        "-mas-de-1-garage" (cochera), "-con-apto-credito" (venta) y
        "-con-permite-mascotas" (alquiler) como filtro real del portal, pero
        NO permite combinar mas de uno a la vez -- probamos
        "-con-patio-con-terraza" y colapsa, pierde el filtro por completo.
        Por eso aplicamos como maximo una amenity en la URL (prioridad
        patio > terraza > jardin > cochera > apto credito/mascotas); si
        piden mas de una, las demas se intentan filtrar despues con los
        datos de mainFeatures (ver _tiene_feature, que hoy suele venir
        vacio para estas amenities en la pagina de listado).

        `ubicacion` permite pisar filtros.ubicacion -- lo usa la busqueda
        por zona cardinal (ver search()) para pedir un partido puntual a
        la vez sin tocar el resto del objeto Filtros."""
        tipo = self.TIPO_SLUGS.get(filtros.tipo_propiedad.value, f"{filtros.tipo_propiedad.value}s")
        ubicacion = (ubicacion if ubicacion is not None else filtros.ubicacion).strip("/").lower() or "capital-federal"
        url = f"{self.BASE_URL}/{tipo}-{filtros.operacion.value}-{ubicacion}"

        amenity_en_url = None
        if filtros.con_patio:
            url += "-con-patio"
            amenity_en_url = "patio"
        elif filtros.con_terraza:
            url += "-con-terraza"
            amenity_en_url = "terraza"
        elif filtros.con_jardin:
            url += "-con-jardin"
            amenity_en_url = "jardin"
        elif filtros.con_cochera:
            url += "-mas-de-1-garage"
            amenity_en_url = "cochera"
        elif filtros.apto_credito:
            url += "-con-apto-credito"
            amenity_en_url = "apto_credito"
        elif filtros.acepta_mascotas:
            url += "-con-permite-mascotas"
            amenity_en_url = "acepta_mascotas"

        return url + ".html", amenity_en_url

    def search(self, filtros: Filtros) -> list[Propiedad]:
        partidos = partidos_de_zona(filtros.ubicacion)
        if not partidos:
            return self._buscar_una_ubicacion(filtros, filtros.ubicacion)

        # Zona cardinal: no hay slug de portal que agrupe varios partidos
        # en un solo pedido, asi que se pide cada uno y se juntan los
        # resultados. Si algunos partidos vienen bloqueados pero otros no,
        # se devuelve lo que se pudo traer -- solo se levanta ScraperBloqueado
        # si TODOS fallaron (bloqueo sistemico, no puntual).
        resultados: list[Propiedad] = []
        errores: list[str] = []
        for partido in partidos:
            try:
                resultados.extend(self._buscar_una_ubicacion(filtros, partido))
            except ScraperBloqueado as exc:
                errores.append(str(exc))
        if not resultados and errores:
            raise ScraperBloqueado(
                f"ZonaProp bloqueo los {len(errores)}/{len(partidos)} partidos de la zona: {errores[0]}"
            )
        return resultados

    def _buscar_una_ubicacion(self, filtros: Filtros, ubicacion: str) -> list[Propiedad]:
        url, amenity_en_url = self._build_url(filtros, ubicacion)
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
        except requests.RequestException as exc:
            raise ScraperBloqueado(f"error de red contactando ZonaProp: {exc}") from exc

        if resp.status_code in (403, 202, 429):
            raise ScraperBloqueado(
                f"ZonaProp devolvio HTTP {resp.status_code} "
                "(probable bloqueo anti-bot, reintentar mas tarde)"
            )
        if resp.status_code != 200:
            raise ScraperBloqueado(f"ZonaProp devolvio HTTP {resp.status_code} inesperado")

        state = _extraer_preloaded_state(resp.text)
        if state is None:
            # La pagina puede devolver un interstitial/captcha con 200 pero
            # sin el bloque de datos esperado.
            raise ScraperBloqueado("ZonaProp no devolvio el bloque de datos esperado (posible captcha)")

        postings = state.get("listStore", {}).get("listPostings", [])
        resultados: list[Propiedad] = []

        for p in postings:
            features = p.get("mainFeatures", {})

            precio = None
            moneda = None
            price_ops = p.get("priceOperationTypes") or []
            if price_ops and price_ops[0].get("prices"):
                precio_info = price_ops[0]["prices"][0]
                precio = _parse_float(precio_info.get("amount"))
                moneda = precio_info.get("currency")

            expensas = None
            if p.get("expenses") and p["expenses"].get("currency") == "$":
                expensas = _parse_float(p["expenses"].get("amount"))

            ambientes = _parse_int(_feature_valor(features, "CFT1"))
            dormitorios = _parse_int(_feature_valor(features, "CFT2"))
            banos = _parse_int(_feature_valor(features, "CFT3"))
            antiguedad = _parse_int(_feature_valor(features, "CFT5"))
            # CFT101 = "Superficie cubierta", CFT100 = "Superficie total"
            # (confirmado en vivo con las labels que trae mainFeatures).
            # La descubierta se calcula por diferencia -- solo si ambas
            # estan y el total es mayor a la cubierta (si son iguales no
            # hay parte descubierta que valga la pena mostrar).
            superficie_cubierta = _parse_float(_feature_valor(features, "CFT101"))
            superficie_total = _parse_float(_feature_valor(features, "CFT100"))
            superficie = superficie_cubierta or superficie_total
            superficie_descubierta = None
            if superficie_cubierta is not None and superficie_total is not None and superficie_total > superficie_cubierta:
                superficie_descubierta = round(superficie_total - superficie_cubierta, 2)
            cochera = _tiene_feature(features, "cochera")
            patio = _tiene_feature(features, "patio")
            terraza = _tiene_feature(features, "terraza")
            jardin = _tiene_feature(features, "jardin", "jardín")
            apto_credito = _tiene_feature(features, "apto credito", "apto crédito")
            acepta_mascotas = _tiene_feature(features, "mascota")
            dias_publicado = _dias_desde(p.get("modified_date"))

            posting_location = p.get("postingLocation") or {}
            location = posting_location.get("location")
            barrio = _ubicar_barrio(location)
            direccion = (posting_location.get("address") or {}).get("name")

            geoloc = (posting_location.get("postingGeolocation") or {}).get("geolocation") or {}
            lat = _parse_float(geoloc.get("latitude"))
            lon = _parse_float(geoloc.get("longitude"))
            distancia_gral_paz = distancia_general_paz_km(lat, lon)

            imagen_url = None
            pics = (p.get("visiblePictures") or {}).get("pictures") or []
            if pics:
                imagen_url = pics[0].get("url360x266") or pics[0].get("url730x532")

            href = p.get("url", "")

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
            if filtros.antiguedad_max is not None and antiguedad is not None and antiguedad > filtros.antiguedad_max:
                continue
            if filtros.expensas_max and expensas is not None and expensas > filtros.expensas_max:
                continue
            # Si la amenity ya se filtro por URL (ver _build_url), confiamos
            # en el portal y no la re-chequeamos contra mainFeatures (que
            # para estas amenities suele venir vacio y descartaria todo).
            if filtros.con_cochera and amenity_en_url != "cochera" and not cochera:
                continue
            if filtros.con_patio and amenity_en_url != "patio" and not patio:
                continue
            if filtros.con_terraza and amenity_en_url != "terraza" and not terraza:
                continue
            if filtros.con_jardin and amenity_en_url != "jardin" and not jardin:
                continue
            if filtros.apto_credito and amenity_en_url != "apto_credito" and not apto_credito:
                continue
            if filtros.acepta_mascotas and amenity_en_url != "acepta_mascotas" and not acepta_mascotas:
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
                    external_id=str(p.get("postingId", href)),
                    titulo=p.get("title") or p.get("generatedTitle") or "Sin titulo",
                    precio=precio,
                    moneda=moneda,
                    expensas=expensas,
                    direccion=direccion,
                    barrio=barrio,
                    ambientes=ambientes,
                    dormitorios=dormitorios,
                    banos=banos,
                    superficie_m2=superficie,
                    superficie_cubierta_m2=superficie_cubierta,
                    superficie_descubierta_m2=superficie_descubierta,
                    antiguedad_anios=antiguedad,
                    cochera=cochera,
                    patio=patio,
                    terraza=terraza,
                    jardin=jardin,
                    apto_credito=apto_credito,
                    acepta_mascotas=acepta_mascotas,
                    dias_desde_publicacion=dias_publicado,
                    distancia_general_paz_km=distancia_gral_paz,
                    url=self.BASE_URL + href if href.startswith("/") else href,
                    imagen_url=imagen_url,
                )
            )

        return resultados
