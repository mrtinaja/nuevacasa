"""Perfil de riesgo geografico por zona, para uso de aseguradoras
(prototipo/demo -- ver memoria de proyecto "NuevaCasa: validacion de
mercado" para el contexto de negocio).

Cruza las fuentes oficiales ya integradas -- delitos contra la
propiedad (SNIC), homicidios dolosos (SNIC) y riesgo sismico (INPRES)
-- en una sola respuesta. Deliberadamente NO combina esto en un score
unico inventado: pesar "delito contra la propiedad" contra "homicidio"
contra "riesgo sismico" en un solo numero es una decision actuarial
real, no algo que corresponda decidir aca sin validarlo con quien lo
va a usar. Se devuelven las tres senales por separado -- para una
aseguradora de vida/saldo deudor, homicidios pesa directo en el riesgo
de mortalidad del asegurado; para una de hogar, pesa poco frente a
delitos contra la propiedad y riesgo sismico.

**Lo que falta para que esto sea un producto real** (no integrado
todavia):
- Precio real de mercado por zona, de fuente oficial (Colegio de
  Escribanos / data.buenosaires.gob.ar para CABA, IDECOR/Observatorio
  del Mercado Inmobiliario para Cordoba) -- deliberadamente NO se usa
  el precio scrapeado de los portales (`precio_justo.py`) aca, para
  que este perfil quede 100% independiente del scraping.
- Riesgo climatico (inundacion litoral/GBA, granizo Cordoba) -- fuente
  a confirmar (SMN / INA).
"""

from app.delitos import info_delitos
from app.direccion_a_zona import zona_mas_cercana
from app.homicidios import info_homicidios
from app.riesgo_sismico import info_sismico


def perfil_riesgo_zona(ubicacion_slug: str) -> dict:
    """Devuelve las senales de riesgo disponibles para la ubicacion.
    Cada senal es None si no hay dato cargado para ese slug -- un campo
    faltante nunca se completa con un supuesto."""
    return {
        "ubicacion": ubicacion_slug,
        "delitos_contra_la_propiedad": info_delitos(ubicacion_slug),
        "homicidios_dolosos": info_homicidios(ubicacion_slug),
        "riesgo_sismico": info_sismico(ubicacion_slug),
        "precio_mercado": None,  # TODO: Colegio de Escribanos / IDECOR, no integrado aun
        "riesgo_climatico": None,  # TODO: fuente a confirmar (SMN / INA)
    }


def perfil_riesgo_direccion(direccion: str, contexto: str | None = None) -> dict | None:
    """Mismo perfil que `perfil_riesgo_zona`, pero a partir de una
    direccion en texto libre (el caso real de uso de una aseguradora:
    tienen la direccion del asegurado, no un slug de NuevaCasa). Resuelve
    la direccion a la zona curada mas cercana (`direccion_a_zona.py`,
    aproximado por centroide) y devuelve el perfil de esa zona, mas los
    datos de la resolucion (`zona_resuelta`) para que quede claro que no
    es un match administrativo exacto. None si Nominatim no encontro
    nada para la direccion."""
    resuelta = zona_mas_cercana(direccion, contexto)
    if resuelta is None:
        return None

    perfil = perfil_riesgo_zona(resuelta["slug"])
    perfil["zona_resuelta"] = resuelta
    return perfil
