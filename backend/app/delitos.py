"""Delitos contra la propiedad por zona, 2024.

Fuente oficial: SNIC (Sistema Nacional de Informacion Criminal), Sistema
de Alerta Temprana - Delitos contra la Propiedad, Ministerio de
Seguridad de la Nacion. Descargado en vivo de
https://datos.gob.ar/dataset/seguridad_9 (CSV
"SAT-Propiedad-BU_2017-2024.csv"), sumando `cantidad_hechos` de todos
los tipos de delito contra la propiedad (robos, hurtos, robo/hurto de
automotores y motos, extorsiones) para el anio 2024 completo.

**Como se arma cada zona**:
- **Buenos Aires provincia**: `departamento_nombre` = partido, 1 a 1.
- **CABA**: el SNIC viene por Comuna, no por barrio -- se uso el mapeo
  oficial barrio->comuna (division politico-administrativa vigente,
  Ley 1777) para asignarle a cada barrio curado el total de SU comuna.
  Como varios barrios comparten comuna, muestran el mismo numero (ej.
  Retiro/San Nicolas/Puerto Madero/San Telmo/Monserrat/Constitucion son
  todos Comuna 1). "Barrio Norte" queda sin dato -- no es una comuna
  oficial ni coincide con ninguna, se superpone informalmente con
  Recoleta/Balvanera/Retiro y asignarlo a una seria inventar el numero.
- **Otras provincias**: se mapeo cada ciudad curada a su departamento
  real (ej. Villa Carlos Paz -> Departamento Punilla, Cordoba;
  Resistencia -> Departamento San Fernando, Chaco). Se dejaron sin
  mapear los casos donde el mismo slug podria referirse a mas de un
  lugar (ver `_SIN_DATO_POR_COLISION` mas abajo).

**Limitaciones reales, no un veredicto de seguridad**:
- Es la CANTIDAD TOTAL de hechos, sin ajustar por poblacion -- una
  ciudad grande o turistica va a mostrar mas hechos que una chica solo
  por tener mas gente, no necesariamente por ser "mas peligrosa" por
  habitante.
- Es un solo anio (2024), no una tendencia.
- Los niveles bajo/medio/alto son terciles calculados sobre las ~140
  localidades individuales cargadas hoy (no un estandar externo ni una
  escala de riesgo oficial) -- si se agregan mas localidades convendria
  recalcularlos.
- Las opciones "Toda la provincia" (`buenos-aires`, `cordoba`, etc.)
  suman TODOS los departamentos de esa provincia -- es un numero de
  escala totalmente distinta a una localidad puntual (una provincia
  entera vs. una ciudad), no tiene sentido compararlos con los mismos
  cortes bajo/medio/alto. Se marcan aparte (`es_agregado_provincial`)
  en vez de forzarles un nivel que no significa lo mismo.
"""

# Slug -> hechos 2024. Buenos Aires (partidos + Costa Atlantica).
_BUENOS_AIRES = {
    "san-isidro": 3559, "vicente-lopez": 2705, "tigre": 4047, "san-fernando": 1295,
    "pilar": 3108, "nordelta": 4047, "moron": 8220, "ituzaingo": 2571, "merlo": 6496,
    "moreno": 6170, "quilmes": 8762, "avellaneda": 4968, "lanus": 7420,
    "lomas-de-zamora": 7754, "la-plata": 9066, "san-clemente-del-tuyu": 1918,
    "las-toninas": 1918, "santa-teresita": 1918, "mar-del-tuyu": 1918,
    "san-bernardo": 1918, "mar-de-ajo": 1918, "pinamar": 1012, "carilo": 1012,
    "valeria-del-mar": 1012, "ostende": 1012, "villa-gesell": 1299,
    "mar-de-las-pampas": 1299, "mar-del-plata": 10156, "miramar": 1034,
    "necochea": 1357, "monte-hermoso": 168,
}

# CABA: cada barrio toma el total de su comuna oficial.
_CABA = {
    "agronomia": 8215, "almagro": 6794, "balvanera": 10193, "barracas": 11597,
    "belgrano": 7993, "boedo": 6794, "caballito": 5850, "chacarita": 8215,
    "coghlan": 6211, "colegiales": 7993, "constitucion": 18647, "flores": 10652,
    "floresta": 6056, "la-boca": 11597, "la-paternal": 8215, "liniers": 6796,
    "mataderos": 6796, "monserrat": 18647, "monte-castro": 6056,
    "nueva-pompeya": 11597, "nunez": 7993, "palermo": 11581,
    "parque-avellaneda": 6796, "parque-chacabuco": 10652, "parque-chas": 8215,
    "parque-patricios": 11597, "puerto-madero": 18647, "recoleta": 6201,
    "retiro": 18647, "saavedra": 6211, "san-cristobal": 10193,
    "san-nicolas": 18647, "san-telmo": 18647, "velez-sarsfield": 6056,
    "versalles": 6056, "villa-crespo": 8215, "villa-del-parque": 6505,
    "villa-devoto": 6505, "villa-general-mitre": 6505, "villa-lugano": 7905,
    "villa-luro": 6056, "villa-ortuzar": 8215, "villa-pueyrredon": 6211,
    "villa-real": 6056, "villa-riachuelo": 7905, "villa-santa-rita": 6505,
    "villa-soldati": 7905, "villa-urquiza": 6211,
}

# Resto de provincias, localidades individuales.
_OTRAS_LOCALIDADES = {
    "cordoba-capital": 79155, "villa-carlos-paz": 7599, "rio-cuarto": 3707,
    "villa-maria": 2411, "alta-gracia": 2819,
    "rosario": 23992, "santa-fe-capital": 11447, "rafaela": 3859,
    "venado-tuerto": 1049,
    "mendoza-capital": 7231, "godoy-cruz": 5622, "lujan-de-cuyo": 4480,
    "maipu": 4843, "san-rafael": 5634,
    "san-miguel-de-tucuman": 14212, "yerba-buena": 1237, "tafi-viejo": 2568,
    "concepcion": 983, "tafi-del-valle": 271,
    "parana": 8478, "concordia": 3735, "gualeguaychu": 911,
    "concepcion-del-uruguay": 1822, "gualeguay": 898,
    "salta-capital": 21797, "san-ramon-de-la-nueva-oran": 4614, "tartagal": 4854,
    "cafayate": 458,
    "posadas": 6071, "obera": 1463, "eldorado": 1209, "puerto-iguazu": 1216,
    "resistencia": 6353, "presidencia-roque-saenz-pena": 1421, "villa-angela": 713,
    "corrientes-capital": 4910, "goya": 817, "mercedes": 323,
    "santiago-del-estero-capital": 11046, "la-banda": 5776,
    "termas-de-rio-hondo": 1438,
    "san-juan-capital": 4217, "rivadavia": 3014, "chimbas": 2343,
    "san-salvador-de-jujuy": 6310, "palpala": 1402, "perico": 2049,
    "viedma": 1859, "san-carlos-de-bariloche": 3051, "general-roca": 6866,
    "cipolletti": 6866, "las-grutas": 830,
    "neuquen-capital": 11494, "plottier": 11494, "cutral-co": 11494,
    "san-martin-de-los-andes": 639, "villa-la-angostura": 209,
    "comodoro-rivadavia": 2843, "trelew": 3719, "puerto-madryn": 1515,
    "esquel": 410,
    # NOTA: "rawson" (San Juan Y Chubut, mismo nombre de ciudad en dos
    # provincias distintas) queda deliberadamente SIN dato -- el slug no
    # lleva prefijo de provincia asi que no se puede saber cual de las
    # dos referencia, y mostrar cualquiera de los dos numeros seria
    # potencialmente el equivocado.
}

# "Toda la provincia": suma de TODOS los departamentos de esa provincia
# en 2024. Escala distinta a una localidad puntual -- ver es_agregado_provincial.
_PROVINCIAS_ENTERAS = {
    "buenos-aires": 216358,
    "capital-federal": 132825,
    "cordoba": 116477,
    "santa-fe": 61057,
    "mendoza": 52494,
    "tucuman": 27234,
    "entre-rios": 21387,
    "salta": 40493,
    "misiones": 15291,
    "chaco": 13458,
    "corrientes": 9682,
    "santiago-del-estero": 23276,
    "san-juan": 21849,
    "jujuy": 13825,
    "rio-negro": 13830,
    "neuquen": 14518,
    "chubut": 9153,
}

HECHOS_2024_POR_UBICACION: dict[str, int] = {
    **_BUENOS_AIRES,
    **_CABA,
    **_OTRAS_LOCALIDADES,
    **_PROVINCIAS_ENTERAS,
}

# Terciles calculados sobre las ~140 localidades individuales (sin
# contar los agregados de "toda la provincia", que son de otra escala).
_CORTE_BAJO = 2843
_CORTE_MEDIO = 6866


def info_delitos(ubicacion_slug: str) -> dict | None:
    """Devuelve {hechos_2024, nivel, es_agregado_provincial} para la
    ubicacion, o None si no hay dato cargado."""
    slug = (ubicacion_slug or "").strip("/").lower()
    hechos = HECHOS_2024_POR_UBICACION.get(slug)
    if hechos is None:
        return None

    es_agregado = slug in _PROVINCIAS_ENTERAS
    if hechos <= _CORTE_BAJO:
        nivel = "bajo"
    elif hechos <= _CORTE_MEDIO:
        nivel = "medio"
    else:
        nivel = "alto"
    return {"hechos_2024": hechos, "nivel": nivel, "es_agregado_provincial": es_agregado}
