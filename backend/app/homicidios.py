"""Homicidios dolosos por zona, 2024 -- dimension separada de
`delitos.py` (que mide delitos CONTRA LA PROPIEDAD, robos/hurtos).

Un partido puede tener incidencia media en robos y a la vez estar entre
los mas violentos en homicidios -- son cosas distintas, mezclarlas en
un solo numero requeriria inventar una ponderacion arbitraria entre
"perdida de un bien" y "muerte violenta". Se muestran como dos
indicadores separados, cada uno con su propio dato y su propia fuente
(mismo criterio ya usado para sumar `riesgo_sismico.py` al lado de
`delitos.py`, en vez de mezclarlo).

Se armo esto porque, revisando el mapa, "Moreno: medio" (en delitos
contra la propiedad) llamaba la atencion por sentido comun -- Moreno
tiene fama de zona complicada. La razon real: Moreno es 4to de 78
partidos bonaerenses en homicidios dolosos 2024 (SNIC), pero queda a
mitad de tabla en delitos contra la propiedad -- son rankings
genuinamente distintos, no un error de carga.

Fuente oficial: SNIC (Sistema Nacional de Informacion Criminal),
dataset propio "Homicidios dolosos, Sistema de Alerta Temprana (HD)"
-- distinto del dataset "Delitos contra la Propiedad" que usa
`delitos.py`, mismo organismo (Direccion Nacional de Estadistica
Criminal, Ministerio de Seguridad de la Nacion). Descargado en vivo de
https://datos.gob.ar/dataset/homicidios-dolosos-sistema-de-alerta-temprana-estadisticas-criminales-en-la-republica-argentina
(CSV "SAT-HD-BU.csv"). Es microdato (una fila por victima Y una fila
por imputado de cada hecho) -- se cuenta `cant_vic` de las filas
"Victima" unicas por `id_hecho`, para no duplicar.

**Ojo, formato de codigo distinto al de `delitos.py`**: este archivo
usa `provincia_id`/`departamento_id` SIN cero a la izquierda (Buenos
Aires es "6", no "06"; CABA Comuna 4 es "2004", no "02004") -- mismo
organismo, pero un CSV con una convencion de codigo distinta. No se
puede cruzar por codigo directo contra `HECHOS_2024_POR_UBICACION` de
`delitos.py` sin normalizar primero.

**Cobertura, a proposito parcial**: por ahora solo Buenos Aires (31
partidos/localidades curados, mismo set que `_BUENOS_AIRES` en
delitos.py) y CABA (15 comunas, mismo mapeo Ley 1777 que `_CABA`) --
el resto de las provincias curadas todavia no se cargo. Se prioriza
cobertura donde nacio la pregunta (Moreno) antes de expandir al resto
del pais.

**Limitaciones reales, igual que en delitos.py**:
- Cantidad TOTAL de hechos en 2024, sin ajustar por poblacion.
- Un solo anio, no una tendencia.
- Los cortes bajo/medio/alto son terciles de las 46 localidades
  cargadas hoy (31 partidos de Buenos Aires + 15 comunas de CABA), no
  un estandar externo -- si se agregan mas localidades convendria
  recalcularlos (mismo criterio que delitos.py).
"""

# Slug -> homicidios dolosos 2024. Mismo set de partidos que
# _BUENOS_AIRES en delitos.py (localidades que comparten partido
# muestran el mismo numero, ej. las localidades de "La Costa").
_BUENOS_AIRES = {
    "san-isidro": 12, "vicente-lopez": 5, "tigre": 17, "san-fernando": 5,
    "pilar": 18, "nordelta": 17, "moron": 15, "ituzaingo": 4, "merlo": 35,
    "moreno": 40, "quilmes": 35, "avellaneda": 19, "lanus": 20,
    "lomas-de-zamora": 47, "la-plata": 26, "san-clemente-del-tuyu": 3,
    "las-toninas": 3, "santa-teresita": 3, "mar-del-tuyu": 3,
    "san-bernardo": 3, "mar-de-ajo": 3, "pinamar": 1, "carilo": 1,
    "valeria-del-mar": 1, "ostende": 1, "villa-gesell": 1,
    "mar-de-las-pampas": 1, "mar-del-plata": 41, "miramar": 0,
    "necochea": 2, "monte-hermoso": 0,
}

# CABA: cada barrio toma el total de su comuna oficial (Ley 1777),
# mismo agrupamiento que _CABA en delitos.py. Comuna por comuna (para
# no repetir el error de mezclar valores de comunas distintas):
# C1=12 C2=2 C3=5 C4=20 C5=4 C6=3 C7=6 C8=15 C9=3 C10=0 C11=2 C12=0
# C13=1 C14=1 C15=3.
_CABA = {
    # Comuna 1 (12): Retiro, San Nicolas, Puerto Madero, San Telmo,
    # Monserrat, Constitucion.
    "retiro": 12, "san-nicolas": 12, "puerto-madero": 12,
    "san-telmo": 12, "monserrat": 12, "constitucion": 12,
    # Comuna 2 (2): Recoleta.
    "recoleta": 2,
    # Comuna 3 (5): Balvanera, San Cristobal.
    "balvanera": 5, "san-cristobal": 5,
    # Comuna 4 (20): La Boca, Barracas, Parque Patricios, Nueva Pompeya.
    "la-boca": 20, "barracas": 20, "parque-patricios": 20,
    "nueva-pompeya": 20,
    # Comuna 5 (4): Almagro, Boedo.
    "almagro": 4, "boedo": 4,
    # Comuna 6 (3): Caballito.
    "caballito": 3,
    # Comuna 7 (6): Flores, Parque Chacabuco.
    "flores": 6, "parque-chacabuco": 6,
    # Comuna 8 (15): Villa Soldati, Villa Riachuelo, Villa Lugano.
    "villa-soldati": 15, "villa-riachuelo": 15, "villa-lugano": 15,
    # Comuna 9 (3): Liniers, Mataderos, Parque Avellaneda.
    "liniers": 3, "mataderos": 3, "parque-avellaneda": 3,
    # Comuna 10 (0, sin homicidios dolosos en 2024): Versalles, Monte
    # Castro, Villa Real, Floresta, Velez Sarsfield, Villa Luro.
    "versalles": 0, "monte-castro": 0, "villa-real": 0, "floresta": 0,
    "velez-sarsfield": 0, "villa-luro": 0,
    # Comuna 11 (2): Villa Gral. Mitre, Villa Devoto, Villa del Parque,
    # Villa Santa Rita.
    "villa-general-mitre": 2, "villa-devoto": 2, "villa-del-parque": 2,
    "villa-santa-rita": 2,
    # Comuna 12 (0, sin homicidios dolosos en 2024): Coghlan, Saavedra,
    # Villa Urquiza, Villa Pueyrredon.
    "coghlan": 0, "saavedra": 0, "villa-urquiza": 0, "villa-pueyrredon": 0,
    # Comuna 13 (1): Belgrano, Colegiales, Nunez.
    "belgrano": 1, "colegiales": 1, "nunez": 1,
    # Comuna 14 (1): Palermo.
    "palermo": 1,
    # Comuna 15 (3): Chacarita, Villa Crespo, La Paternal, Villa
    # Ortuzar, Agronomia, Parque Chas.
    "chacarita": 3, "villa-crespo": 3, "la-paternal": 3,
    "villa-ortuzar": 3, "agronomia": 3, "parque-chas": 3,
}

HECHOS_2024_POR_UBICACION: dict[str, int] = {**_BUENOS_AIRES, **_CABA}

# Terciles sobre las 46 localidades cargadas (31 partidos de Buenos
# Aires + 15 comunas de CABA) -- mismo metodo que delitos.py (ordenar y
# tomar los indices n//3 y 2*n//3).
_CORTE_BAJO = 3
_CORTE_MEDIO = 12


def info_homicidios(ubicacion_slug: str) -> dict | None:
    """Devuelve {hechos_2024, nivel} para la ubicacion, o None si no hay
    dato cargado (ver cobertura parcial en el docstring del modulo)."""
    slug = (ubicacion_slug or "").strip("/").lower()
    hechos = HECHOS_2024_POR_UBICACION.get(slug)
    if hechos is None:
        return None

    if hechos <= _CORTE_BAJO:
        nivel = "bajo"
    elif hechos <= _CORTE_MEDIO:
        nivel = "medio"
    else:
        nivel = "alto"
    return {"hechos_2024": hechos, "nivel": nivel}
