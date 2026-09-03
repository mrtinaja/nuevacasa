"""Centroide (lat, lon) de cada barrio/partido/ciudad del dataset curado
de ubicaciones del frontend (`frontend/app.js`, `UBICACIONES`).

Se usa solo como aproximacion para los portales que no traen
coordenadas por aviso (MercadoLibre, Argenprop): en vez de la posicion
exacta de la propiedad, se usa el centroide de la zona buscada. Para
ZonaProp y RE/MAX no hace falta -- ya traen lat/lon real por aviso (ver
`app/geo.py`).

Geocodificado en vivo con Nominatim/OpenStreetMap (gratis, sin API key),
una sola vez por nombre -- no en cada busqueda. Las capitales de
provincia se geocodificaron con busqueda estructurada (city=/state=)
porque la busqueda de texto libre devolvia el centroide de la provincia
entera en vez de la ciudad (confirmado comparando contra coordenadas
conocidas de Mendoza y Santa Fe capital, que quedaban a >150km del
punto real con busqueda de texto libre).
"""

UBICACIONES_GEO: dict[str, tuple[float, float]] = {
    "agronomia": (-34.5953, -58.4860),
    "almagro": (-34.6100, -58.4222),
    "alta-gracia": (-31.6579, -64.4339),
    "avellaneda": (-34.6648, -58.3628),
    "balvanera": (-34.6092, -58.4031),
    "barracas": (-34.6453, -58.3876),
    "barrio-norte": (-34.5927, -58.4024),
    "belgrano": (-34.6130, -58.3776),
    "boedo": (-34.6255, -58.4161),
    "buenos-aires": (-36.3790, -60.3856),
    "caballito": (-34.6206, -58.4414),
    "capital-federal": (-34.6096, -58.3888),
    "chacarita": (-34.5872, -58.4552),
    "coghlan": (-34.5653, -58.4751),
    "colegiales": (-34.5730, -58.4482),
    "constitucion": (-34.6283, -58.3806),
    "cordoba": (-32.0222, -63.9699),
    "cordoba-capital": (-31.4167, -64.1834),
    "flores": (-34.6291, -58.4635),
    "floresta": (-34.6324, -58.4809),
    "godoy-cruz": (-32.9283, -68.9051),
    "ituzaingo": (-34.6583, -58.6671),
    "la-boca": (-34.6335, -58.3590),
    "la-paternal": (-34.5970, -58.4672),
    "la-plata": (-34.9207, -57.9538),
    "lanus": (-34.7074, -58.3906),
    "liniers": (-34.6389, -58.5263),
    "lomas-de-zamora": (-34.7573, -58.4027),
    "lujan-de-cuyo": (-33.1085, -69.0130),
    "maipu": (-32.9846, -68.7882),
    "mar-del-plata": (-37.9976, -57.5482),
    "mataderos": (-34.6579, -58.5018),
    "mendoza": (-34.5970, -68.7305),
    "mendoza-capital": (-32.8894, -68.8446),
    "merlo": (-34.6605, -58.7322),
    "monserrat": (-34.6116, -58.3841),
    "monte-castro": (-34.6188, -58.5059),
    "moreno": (-34.6397, -58.7898),
    "moron": (-34.6511, -58.6217),
    "nordelta": (-34.4144, -58.6495),
    "nueva-pompeya": (-34.6526, -58.4147),
    "nunez": (-34.5485, -58.4627),
    "palermo": (-34.5803, -58.4245),
    "parque-avellaneda": (-34.6451, -58.4797),
    "parque-chacabuco": (-34.6339, -58.4430),
    "parque-chas": (-34.5855, -58.4793),
    "parque-patricios": (-34.6385, -58.4063),
    "pilar": (-34.4571, -58.9142),
    "puerto-madero": (-34.6104, -58.3622),
    "quilmes": (-34.7244, -58.2588),
    "rafaela": (-31.2527, -61.4917),
    "recoleta": (-34.5874, -58.3916),
    "retiro": (-34.5912, -58.3747),
    "rio-cuarto": (-33.1238, -64.3490),
    "rosario": (-32.9594, -60.6617),
    "saavedra": (-34.5525, -58.4863),
    "san-cristobal": (-34.6241, -58.4024),
    "san-fernando": (-34.4472, -58.5702),
    "san-isidro": (-34.4740, -58.5265),
    "san-nicolas": (-34.6045, -58.3845),
    "san-rafael": (-34.6126, -68.3305),
    "san-telmo": (-34.6214, -58.3738),
    "santa-fe": (-30.3155, -61.1645),
    "santa-fe-capital": (-31.6475, -60.6429),
    "tigre": (-34.4235, -58.5818),
    "velez-sarsfield": (-34.6324, -58.4809),
    "venado-tuerto": (-33.7456, -61.9686),
    "versalles": (-34.6289, -58.5233),
    "vicente-lopez": (-34.5258, -58.4749),
    "villa-carlos-paz": (-31.4184, -64.4937),
    "villa-crespo": (-34.5933, -58.4480),
    "villa-del-parque": (-34.6014, -58.4941),
    "villa-devoto": (-34.6010, -58.5155),
    "villa-general-mitre": (-34.6103, -58.4693),
    "villa-lugano": (-34.6766, -58.4772),
    "villa-luro": (-34.6363, -58.5021),
    "villa-maria": (-32.4106, -63.2436),
    "villa-ortuzar": (-34.5813, -58.4682),
    "villa-pueyrredon": (-34.5794, -58.5041),
    "villa-real": (-34.6189, -58.5259),
    "villa-riachuelo": (-34.6912, -58.4714),
    "villa-santa-rita": (-34.6161, -58.4827),
    "villa-soldati": (-34.6623, -58.4411),
    "villa-urquiza": (-34.5732, -58.4915),
}


def centroide(ubicacion_slug: str) -> tuple[float, float] | None:
    return UBICACIONES_GEO.get((ubicacion_slug or "").strip("/").lower())
