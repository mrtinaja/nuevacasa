import requests

from app.models import Filtros, Propiedad
from app.scrapers.base import Scraper, ScraperBloqueado, ScraperNoImplementado


class ProperatiScraper(Scraper):
    """
    El sitio entero (hasta el homepage) devolvio "401 Access Denied" en
    las pruebas -- con curl y con navegador real, mismo resultado --
    parece un bloqueo de IP/WAF al entorno donde corremos esto, no algo
    que se arregle con headers ni con mas codigo. No hay API publica
    documentada; Properati solo publica datasets historicos
    ("Properati Data") via BigQuery, que no sirven para busqueda en
    vivo con filtros del usuario.

    A diferencia de un scraper "no implementado" de verdad, este SI
    intenta la conexion en cada busqueda -- si el bloqueo alguna vez se
    levanta, el estado va a reflejarlo solo (va a pasar a "not_implemented"
    con un mensaje distinto en vez de "blocked", indicando que ya se
    puede conectar pero todavia falta escribir el parser del HTML real).
    """

    name = "properati"
    URL = "https://www.properati.com.ar/"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "es-AR,es;q=0.9",
    }

    def search(self, filtros: Filtros) -> list[Propiedad]:
        try:
            resp = requests.get(self.URL, headers=self.HEADERS, timeout=15)
        except requests.RequestException as exc:
            raise ScraperBloqueado(f"error de red contactando Properati: {exc}") from exc

        if resp.status_code != 200:
            raise ScraperBloqueado(
                f"Properati devolvio HTTP {resp.status_code} incluso en el homepage "
                "(bloqueo de IP/WAF al entorno, no es un problema de codigo)"
            )

        raise ScraperNoImplementado(
            "El bloqueo de IP parece haberse levantado (el homepage respondio 200), "
            "pero todavia falta inspeccionar la estructura real de la pagina de "
            "resultados y escribir el parser"
        )
