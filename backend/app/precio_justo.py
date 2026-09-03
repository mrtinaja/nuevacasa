"""
"Precio justo": compara el precio/m2 de cada aviso contra la mediana
de precio/m2 de esta misma busqueda (ya viene acotada a una zona, un
tipo de propiedad y una operacion). Es una comparacion posible solo
porque se junta el inventario de varios portales a la vez -- ningun
portal individual puede compararse contra la competencia.

No es un valor de mercado "real" ni tasado -- es relativo a lo que
trajo esta busqueda puntual. Con pocos avisos comparables la mediana
no dice mucho, asi que no se marca nada si la muestra es chica.
"""

import statistics

from app.models import Propiedad

_MUESTRA_MINIMA = 5
_UMBRAL_BUEN_PRECIO = 0.85  # 15% o mas por debajo de la mediana


def marcar_buen_precio(propiedades: list[Propiedad]) -> None:
    """Muta in-place: completa precio_m2 en todas las que se pueda, y
    marca buen_precio=True en las que estan notablemente por debajo de
    la mediana de precio/m2 de su grupo (agrupado por moneda, ya que
    comparar USD contra ARS no tiene sentido)."""
    for p in propiedades:
        if p.precio is not None and p.superficie_m2:
            p.precio_m2 = round(p.precio / p.superficie_m2, 2)

    por_moneda: dict[str, list[Propiedad]] = {}
    for p in propiedades:
        if p.precio_m2 is not None and p.moneda:
            por_moneda.setdefault(p.moneda, []).append(p)

    for grupo in por_moneda.values():
        if len(grupo) < _MUESTRA_MINIMA:
            continue
        mediana = statistics.median(p.precio_m2 for p in grupo)
        umbral = mediana * _UMBRAL_BUEN_PRECIO
        for p in grupo:
            if p.precio_m2 <= umbral:
                p.buen_precio = True
