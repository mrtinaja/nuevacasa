"""Delitos contra la propiedad por partido (Buenos Aires provincia), 2024.

Fuente oficial: SNIC (Sistema Nacional de Informacion Criminal), Sistema
de Alerta Temprana - Delitos contra la Propiedad, Ministerio de
Seguridad de la Nacion. Descargado en vivo de
https://datos.gob.ar/dataset/seguridad_9 (CSV
"SAT-Propiedad-BU_2017-2024.csv"), sumando `cantidad_hechos` de todos
los tipos de delito contra la propiedad (robos, hurtos, robo/hurto de
automotores y motos, extorsiones) para el anio 2024 completo, por
`departamento_nombre` (que en Buenos Aires equivale al partido).

**Limitaciones reales, no un veredicto de seguridad**:
- Es la CANTIDAD TOTAL de hechos, sin ajustar por poblacion -- un
  partido grande y densamente poblado (ej. Mar del Plata / General
  Pueyrredon) va a mostrar mas hechos que uno chico solo por tener mas
  gente y mas turismo, no necesariamente por ser "mas peligroso" por
  habitante.
- Es un solo anio (2024), no una tendencia.
- Varias localidades curadas en el frontend caen dentro del MISMO
  partido SNIC (ej. Cariló/Valeria del Mar/Ostende son todos el
  partido de Pinamar; San Clemente del Tuyu/Las Toninas/Santa
  Teresita/etc son todos el partido de La Costa) -- muestran el mismo
  numero porque el SNIC no discrimina mas fino que partido.
- Solo cubre Buenos Aires provincia por ahora (partidos + Costa
  Atlantica). CABA necesitaria mapeo barrio->comuna aparte, y las 12
  provincias sumadas mas recientemente (Tucuman, Entre Rios, etc.)
  todavia no tienen este cruce hecho -- queda pendiente.

Los cortes de nivel (bajo/medio/alto) son terciles de las localidades
que hay cargadas hoy, no un estandar externo -- si se suman mas
localidades convendria recalcularlos.
"""

HECHOS_2024_POR_UBICACION: dict[str, int] = {
    "san-isidro": 3559,
    "vicente-lopez": 2705,
    "tigre": 4047,
    "san-fernando": 1295,
    "pilar": 3108,
    "nordelta": 4047,
    "moron": 8220,
    "ituzaingo": 2571,
    "merlo": 6496,
    "moreno": 6170,
    "quilmes": 8762,
    "avellaneda": 4968,
    "lanus": 7420,
    "lomas-de-zamora": 7754,
    "la-plata": 9066,
    "san-clemente-del-tuyu": 1918,
    "las-toninas": 1918,
    "santa-teresita": 1918,
    "mar-del-tuyu": 1918,
    "san-bernardo": 1918,
    "mar-de-ajo": 1918,
    "pinamar": 1012,
    "carilo": 1012,
    "valeria-del-mar": 1012,
    "ostende": 1012,
    "villa-gesell": 1299,
    "mar-de-las-pampas": 1299,
    "mar-del-plata": 10156,
    "miramar": 1034,
    "necochea": 1357,
    "monte-hermoso": 168,
    "buenos-aires": 216358,  # toda la provincia sumada, no comparable 1 a 1 con un partido
}

_CORTE_BAJO = 1918
_CORTE_MEDIO = 6170


def info_delitos(ubicacion_slug: str) -> dict | None:
    """Devuelve {hechos_2024, nivel} para la ubicacion, o None si no
    hay dato cargado (ubicacion fuera de Buenos Aires provincia, o una
    de las provincias/localidades sin este cruce todavia)."""
    hechos = HECHOS_2024_POR_UBICACION.get((ubicacion_slug or "").strip("/").lower())
    if hechos is None:
        return None
    if hechos <= _CORTE_BAJO:
        nivel = "bajo"
    elif hechos <= _CORTE_MEDIO:
        nivel = "medio"
    else:
        nivel = "alto"
    return {"hechos_2024": hechos, "nivel": nivel}
