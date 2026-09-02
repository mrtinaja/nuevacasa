from abc import ABC, abstractmethod

from app.models import Filtros, Propiedad


class ScraperNoImplementado(Exception):
    """El portal todavia no tiene scraper funcional."""


class ScraperBloqueado(Exception):
    """El portal devolvio una respuesta de bloqueo/anti-bot (403, captcha, etc)."""


class Scraper(ABC):
    name: str

    @abstractmethod
    def search(self, filtros: Filtros) -> list[Propiedad]:
        ...
