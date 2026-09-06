"""Perfil de riesgo geografico por zona, para uso de aseguradoras
(prototipo/demo -- ver memoria de proyecto "NuevaCasa: validacion de
mercado" para el contexto de negocio).

Cruza las fuentes oficiales ya integradas -- delitos contra la
propiedad (SNIC) y riesgo sismico (INPRES) -- en una sola respuesta.
Deliberadamente NO combina esto en un score unico inventado: pesar
"delito" contra "riesgo sismico" en un solo numero es una decision
actuarial real, no algo que corresponda decidir aca sin validarlo con
quien lo va a usar. Se devuelven las dos senales por separado.

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
from app.riesgo_sismico import info_sismico


def perfil_riesgo_zona(ubicacion_slug: str) -> dict:
    """Devuelve las senales de riesgo disponibles para la ubicacion.
    Cada senal es None si no hay dato cargado para ese slug -- un campo
    faltante nunca se completa con un supuesto."""
    return {
        "ubicacion": ubicacion_slug,
        "delitos_contra_la_propiedad": info_delitos(ubicacion_slug),
        "riesgo_sismico": info_sismico(ubicacion_slug),
        "precio_mercado": None,  # TODO: Colegio de Escribanos / IDECOR, no integrado aun
        "riesgo_climatico": None,  # TODO: fuente a confirmar (SMN / INA)
    }
