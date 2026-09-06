"""Riesgo sismico por zona, segun zonificacion oficial INPRES-CIRSOC 103.

Fuente: INPRES (Instituto Nacional de Prevencion Sismica),
https://www.argentina.gob.ar/inpres/ingenieria-sismorresistente/zonificacion-sismica
-- el pais se divide en 5 zonas de peligro sismico (0 a 4), de "muy
reducida" a "muy elevada", segun la maxima aceleracion del suelo
esperada para un sismo de diseno (recurrencia de 500 anios).

**Cobertura parcial, a proposito**: la zonificacion oficial completa
(Anexo A del reglamento INPRES-CIRSOC 103-2018) es por localidad/
departamento y varia DENTRO de una misma provincia (ej. Mendoza: Gran
Mendoza es zona 4, San Rafael es zona 3) -- no es un dato que se pueda
asumir parejo por provincia salvo donde la fuente lo confirma
explicitamente ("en su totalidad"). Solo se cargaron aca las
localidades para las que se encontro esa confirmacion explicita; el
resto queda sin dato (None) en vez de adivinar, mismo criterio que
`delitos.py` con "Rawson" o "Barrio Norte". Para cobertura completa
haria falta transcribir el Anexo A entero del reglamento.

Zonas confirmadas por fuente:
- Buenos Aires, Santa Fe, Entre Rios, Corrientes, Misiones: zona 0 en
  su totalidad (incluye CABA, geologicamente parte de la misma zona).
- Cordoba capital, Neuquen capital: zona 1.
- Tucuman y Catamarca: zona 2 en su totalidad. San Luis capital, La
  Rioja capital, San Carlos de Bariloche: zona 2.
- Salta capital, San Salvador de Jujuy: zona 3. San Rafael (Mendoza):
  zona 3.
- Gran Mendoza, Gran San Juan: zona 4 (la maxima).

**Zona 0, con una salvedad (confianza menor que las de arriba)**: Chaco,
Formosa, Santiago del Estero, La Pampa y Santa Cruz NO son "zona 0 en
su totalidad" -- son provincias donde el ESTE es zona 0 y el OESTE ya
pasa a zona 1 (fuente: Minuto Fueguino/CEPTM, citando el mapa INPRES
actualizado). Reciental (Chaco), Formosa capital y Clorinda (Formosa),
Santa Rosa y General Pico (La Pampa), Rio Gallegos y Caleta Olivia
(Santa Cruz) son todas localidades claramente del lado este/costero de
su provincia (rio Parana/Paraguay o costa atlantica), por eso se
cargan como zona 0 -- pero con menos certeza que Buenos Aires o Santa
Fe, que son zona 0 pareja en toda la provincia. Deliberadamente NO se
carga Tierra del Fuego: la misma fuente sugiere que la isla entera cae
en zona 1 (no zona 0) a pesar de ser la mas alejada de los Andes --
rompe el patron "lejos de los Andes = sin riesgo", asi que mejor
dejarla sin dato que asumir mal.
"""

_NIVEL_POR_ZONA = {
    0: "muy_reducida",
    1: "reducida",
    2: "moderada",
    3: "elevada",
    4: "muy_elevada",
}

# Buenos Aires + CABA + Santa Fe + Entre Rios + Corrientes + Misiones: zona 0.
_ZONA_0 = [
    # Buenos Aires (partidos + Costa Atlantica), igual set que delitos.py.
    "san-isidro", "vicente-lopez", "tigre", "san-fernando", "pilar", "nordelta",
    "moron", "ituzaingo", "merlo", "moreno", "quilmes", "avellaneda", "lanus",
    "lomas-de-zamora", "la-plata", "san-clemente-del-tuyu", "las-toninas",
    "santa-teresita", "mar-del-tuyu", "san-bernardo", "mar-de-ajo", "pinamar",
    "carilo", "valeria-del-mar", "ostende", "villa-gesell", "mar-de-las-pampas",
    "mar-del-plata", "miramar", "necochea", "monte-hermoso", "buenos-aires",
    # CABA: todos los barrios curados + el agregado.
    "agronomia", "almagro", "balvanera", "barracas", "belgrano", "boedo",
    "caballito", "chacarita", "coghlan", "colegiales", "constitucion", "flores",
    "floresta", "la-boca", "la-paternal", "liniers", "mataderos", "monserrat",
    "monte-castro", "nueva-pompeya", "nunez", "palermo", "parque-avellaneda",
    "parque-chacabuco", "parque-chas", "parque-patricios", "puerto-madero",
    "recoleta", "retiro", "saavedra", "san-cristobal", "san-nicolas",
    "san-telmo", "velez-sarsfield", "versalles", "villa-crespo",
    "villa-del-parque", "villa-devoto", "villa-general-mitre", "villa-lugano",
    "villa-luro", "villa-ortuzar", "villa-pueyrredon", "villa-real",
    "villa-riachuelo", "villa-santa-rita", "villa-soldati", "villa-urquiza",
    "capital-federal",
    # Santa Fe.
    "rosario", "santa-fe-capital", "rafaela", "venado-tuerto", "santa-fe",
    # Entre Rios.
    "parana", "concordia", "gualeguaychu", "concepcion-del-uruguay",
    "gualeguay", "entre-rios",
    # Corrientes.
    "corrientes-capital", "goya", "mercedes", "corrientes",
    # Misiones.
    "posadas", "obera", "eldorado", "puerto-iguazu", "misiones",
]

# Este/costa de Chaco, Formosa, La Pampa y Santa Cruz -- zona 0 con
# menos certeza que el bloque de arriba (ver docstring). Ninguna de
# estas 4 provincias se carga "en su totalidad": solo estas localidades
# puntuales, todas claramente del lado este/costero.
_ZONA_0_ESTE_PROVINCIA = [
    "resistencia",  # Chaco, sobre el Parana.
    "formosa-capital", "clorinda",  # Formosa, sobre el rio Paraguay.
    "santa-rosa", "general-pico",  # La Pampa, este de la provincia.
    "rio-gallegos", "caleta-olivia",  # Santa Cruz, costa atlantica.
]

_ZONA_1 = ["cordoba-capital", "neuquen-capital"]

_ZONA_2 = [
    # Tucuman y Catamarca "en su totalidad": provincia + localidades curadas.
    "tucuman", "san-miguel-de-tucuman", "yerba-buena", "tafi-viejo",
    "concepcion", "tafi-del-valle",
    "catamarca", "catamarca-capital",
    "san-luis-capital", "la-rioja-capital", "san-carlos-de-bariloche",
]

_ZONA_3 = ["salta-capital", "san-salvador-de-jujuy", "san-rafael"]

_ZONA_4 = [
    # Gran Mendoza y Gran San Juan.
    "mendoza-capital", "godoy-cruz", "lujan-de-cuyo", "maipu",
    "san-juan-capital", "rivadavia", "chimbas",
]

ZONA_SISMICA_POR_UBICACION: dict[str, int] = {
    **{slug: 0 for slug in _ZONA_0},
    **{slug: 0 for slug in _ZONA_0_ESTE_PROVINCIA},
    **{slug: 1 for slug in _ZONA_1},
    **{slug: 2 for slug in _ZONA_2},
    **{slug: 3 for slug in _ZONA_3},
    **{slug: 4 for slug in _ZONA_4},
}

# "Toda la provincia" (agregado): NO se puede asumir un nivel parejo en
# provincias donde solo confirmamos una localidad puntual (ej. la
# capital) -- por eso estas NO entran al dict de arriba. Pero esconder
# el dato en las provincias de mayor riesgo sismico del pais (Cuyo,
# NOA) es peor que mostrarlo con salvedad: un usuario buscando "toda
# Mendoza" no deberia ver "sin dato" en el mismo lugar donde alguien
# buscando Palermo ve "muy reducida". Se muestra el MAXIMO confirmado
# dentro de la provincia (criterio conservador: para uso en seguros es
# peor subestimar el riesgo que sobreestimarlo), con una nota explicita
# de que es un agregado, no una confirmacion pareja de toda la
# provincia -- mismo espiritu que `es_agregado_provincial` en
# delitos.py, pero con el maximo en vez de la suma.
#
# Deliberadamente NO se agrega Neuquen ni Cordoba aca: en ambas, la
# zona confirmada es la de la CAPITAL (este de la provincia, la mas
# tranquila), mientras que el oeste cordillerano (Neuquen: San Martin
# de los Andes, Villa La Angostura; Cordoba: sierras) es plausiblemente
# MAS riesgoso, no menos -- mostrar el valor de la capital ahi
# subestimaria el riesgo real, el error opuesto (y peor) que esconder
# el dato.
_AGREGADOS_PROVINCIALES: dict[str, tuple[int, str]] = {
    "mendoza": (4, "Confirmado: zona 3 en San Rafael, zona 4 en Gran Mendoza (la mas poblada). Se muestra el maximo."),
    "san-juan": (4, "Confirmado en Gran San Juan (la zona mas poblada). INPRES ubica a San Juan entre las provincias de mayor peligrosidad sismica del pais."),
    "salta": (3, "Confirmado en Salta capital. Resto de la provincia sin verificar localidad por localidad."),
    "jujuy": (3, "Confirmado en San Salvador de Jujuy. Resto de la provincia sin verificar localidad por localidad."),
    "san-luis": (2, "Confirmado en San Luis capital. Resto de la provincia sin verificar localidad por localidad."),
    "la-rioja": (2, "Confirmado en La Rioja capital. Resto de la provincia sin verificar localidad por localidad."),
}


def info_sismico(ubicacion_slug: str) -> dict | None:
    """Devuelve {zona, nivel, es_agregado_provincial, nota} para la
    ubicacion, o None si no hay zonificacion confirmada cargada para ese
    slug. `nota` solo viene cuando es_agregado_provincial=True."""
    slug = (ubicacion_slug or "").strip("/").lower()

    zona = ZONA_SISMICA_POR_UBICACION.get(slug)
    if zona is not None:
        return {"zona": zona, "nivel": _NIVEL_POR_ZONA[zona], "es_agregado_provincial": False, "nota": None}

    agregado = _AGREGADOS_PROVINCIALES.get(slug)
    if agregado is not None:
        zona, nota = agregado
        return {"zona": zona, "nivel": _NIVEL_POR_ZONA[zona], "es_agregado_provincial": True, "nota": nota}

    return None
