from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Operacion(str, Enum):
    venta = "venta"
    alquiler = "alquiler"


class TipoPropiedad(str, Enum):
    departamento = "departamento"
    casa = "casa"
    ph = "ph"
    local = "local"


class Moneda(str, Enum):
    USD = "USD"
    ARS = "ARS"


class Orden(str, Enum):
    relevancia = "relevancia"
    precio_asc = "precio_asc"
    precio_desc = "precio_desc"
    mas_recientes = "mas_recientes"


class Filtros(BaseModel):
    operacion: Operacion = Operacion.venta
    tipo_propiedad: TipoPropiedad = TipoPropiedad.departamento
    # Slug de ubicacion tal como lo usa cada portal, ej "capital-federal".
    # En v1 el usuario lo escribe directo; mas adelante conviene traducirlo
    # desde un selector de barrios/localidades comun a todos los portales.
    ubicacion: str = "capital-federal"

    precio_min: Optional[float] = None
    precio_max: Optional[float] = None
    moneda: Optional[Moneda] = None

    ambientes_min: Optional[int] = None
    ambientes_max: Optional[int] = None
    dormitorios_min: Optional[int] = None
    dormitorios_max: Optional[int] = None

    superficie_min: Optional[float] = None
    superficie_max: Optional[float] = None

    antiguedad_max: Optional[int] = None  # anios; 0 = a estrenar
    con_cochera: Optional[bool] = None
    con_patio: Optional[bool] = None
    con_terraza: Optional[bool] = None
    con_jardin: Optional[bool] = None
    apto_credito: Optional[bool] = None  # solo tiene sentido para operacion=venta
    acepta_mascotas: Optional[bool] = None  # solo tiene sentido para operacion=alquiler
    expensas_max: Optional[float] = None

    publicado_max_dias: Optional[int] = None  # 1, 7, 30... solo se aplica donde hay fecha real
    distancia_general_paz_max_km: Optional[float] = None  # solo se aplica donde hay lat/lon real

    orden: Orden = Orden.relevancia
    portales: Optional[list[str]] = None  # None = todos los habilitados


class Propiedad(BaseModel):
    portal: str
    external_id: str
    titulo: str
    precio: Optional[float] = None
    moneda: Optional[str] = None
    expensas: Optional[float] = None
    direccion: Optional[str] = None
    barrio: Optional[str] = None
    ambientes: Optional[int] = None
    dormitorios: Optional[int] = None
    banos: Optional[int] = None
    superficie_m2: Optional[float] = None
    antiguedad_anios: Optional[int] = None
    cochera: Optional[bool] = None
    patio: Optional[bool] = None
    terraza: Optional[bool] = None
    jardin: Optional[bool] = None
    apto_credito: Optional[bool] = None
    acepta_mascotas: Optional[bool] = None
    dias_desde_publicacion: Optional[int] = None
    distancia_general_paz_km: Optional[float] = None
    distancia_general_paz_aprox: bool = False  # True = centroide del barrio, no del aviso puntual
    url: str
    imagen_url: Optional[str] = None


class PortalResultado(BaseModel):
    portal: str
    status: str  # "ok" | "blocked" | "not_implemented" | "error"
    detalle: Optional[str] = None
    cantidad: int = 0


class SearchResponse(BaseModel):
    propiedades: list[Propiedad]
    portales: list[PortalResultado]
