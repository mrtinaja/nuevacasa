# NuevaCasa

Buscador agregado de propiedades. Un backend en FastAPI orquesta un
scraper por portal, normaliza los resultados a un esquema comun y un
frontend los muestra con filtros.

## Tipos de propiedad

Departamento, Casa, PH y Local (comercial). El slug de "Local" varia
mucho entre portales, no sigue el patron de los demas:
- **ZonaProp**: `locales-comerciales` (confirmado en vivo).
- **MercadoLibre**: `locales` (confirmado en vivo).
- **RE/MAX**: id de categoria `16` / valor `local` (confirmado en vivo,
  filtrado client-side como el resto de los tipos).
- **Argenprop**: `local` (mismo patron singular que departamento/casa/ph).
  Sin verificar en vivo -- Argenprop viene bloqueado por el anti-bot
  durante todo el desarrollo, no se pudo confirmar sin arriesgar
  extender el bloqueo.

## Estado de los portales

| Portal        | Estado                | Notas |
|---------------|------------------------|-------|
| Argenprop     | Funcionando            | HTML scraping. Tiene anti-bot: si se hacen muchos requests seguidos devuelve 403/202. Mitigado (no eliminado) con sesion persistente + cookies + headers mas realistas + 1 reintento con backoff -- ver docstring de `ArgenpropScraper`. Solo trae la primera pagina de resultados (paginacion no implementada, es via AJAX/POST a `/listing/searchbylisting`, todavia no reproducida). |
| MercadoLibre  | Funcionando            | No usa la API oficial (ver seccion abajo). Scraping de la pagina publica inmuebles.mercadolibre.com.ar, que trae un bloque JSON-LD (`schema.org/RealEstateListing`) sin login ni token. Menos campos que ZonaProp (solo ambientes, no dormitorios/banos/superficie/antiguedad). |
| ZonaProp      | Funcionando            | No es HTML scraping puro: la pagina trae un JSON completo embebido (`window.__PRELOADED_STATE__`) con precio, ambientes, dormitorios, banos, superficie, antiguedad, ubicacion e imagenes -- mas rico que Argenprop. Mismo riesgo de anti-bot (403/202/429) y misma limitacion de solo pagina 1. |
| RE/MAX        | Funcionando            | App Angular con SSR: se encontro su API publica real (`api-ar.redremax.com`) leyendo el TransferState (`ng-state`) embebido en el HTML. Sin anti-bot detectado. Operacion (venta/alquiler) es server-side; tipo de propiedad y ubicacion se filtran client-side (texto contra `geoLabel`/`displayAddress`, confirmado: 17/17 resultados reales en Capital Federal). Zona Norte/Oeste/Sur si distingue (matchea contra cualquier partido de la zona). |

## Portales descartados

- **Roomix**: el dominio que se tenia en mente (roomix.com.ar) esta
  caido; el real es roomix.ai, que resulto ser un agregador con IA que
  ya combina ZonaProp/Argenprop/MercadoLibre -- las mismas fuentes que
  ya scrapeamos directamente. Sumarlo hubiera sido mayormente
  duplicados.
- **Properati**: el sitio entero devuelve `401 Access Denied` para
  clientes no-browser (confirmado que el navegador normal del usuario
  entra perfecto -- no es un bloqueo de IP/reputacion como los otros
  portales, es especificamente contra clientes tipo `requests`/scripts).
  La unica forma de pasar eso seria imitar un browser real (Playwright)
  especificamente para evadir esa deteccion, y eso es bypassear
  bot-detection -- un limite que no se cruza aunque el usuario lo pida.
  Removido del proyecto a proposito, no queda pendiente.

## MercadoLibre: por que no usa la API oficial

Primero se implemento el camino "correcto": OAuth `client_credentials`
contra `/sites/MLA/search`. Se creo una app real en
developers.mercadolibre.com.ar y se probo en vivo con credenciales
reales -- el token se obtiene sin problema, pero la busqueda devuelve
`403 PA_UNAUTHORIZED_RESULT_FROM_POLICIES`. Es una restriccion de
plataforma: MercadoLibre bloquea ese endpoint a apps no certificadas,
certificacion que es un proceso de aprobacion manual, no algo que se
resuelva con codigo. Confirmado que no es un bug nuestro: hay reportes
de terceros con el mismo error.

Con ese camino cerrado, se pivoteo a scrapear
`inmuebles.mercadolibre.com.ar` (la web publica, no la API) -- misma
logica que ZonaProp: la pagina trae los resultados en un bloque
`<script type="application/ld+json">` con schema.org `RealEstateListing`,
sin login ni token. Confirmado funcionando en vivo.

Limitaciones conocidas:
- Bastante menos campos que ZonaProp: solo `ambientes` (numberOfRooms).
  No hay dormitorios, banos, superficie ni antiguedad en este JSON-LD,
  asi que esos filtros no se aplican a MercadoLibre (mismo patron que
  `banos_min` en Argenprop).
- El tipo "ph" no se pudo confirmar como categoria propia (no aparecio
  en la muestra revisada); se arma como `phs` seguiendo el patron de
  `departamentos`/`casas`, sin verificar.
- Solo pagina 1, igual que los otros portales.

## Paginacion

El frontend pagina los resultados ya combinados de todos los portales (12
por pagina, ver `RESULTADOS_POR_PAGINA` en `frontend/app.js`). Es
paginacion client-side sobre lo que ya se trajo en una sola consulta --
no dispara nuevos requests a los portales al cambiar de pagina.

## Ubicacion

El frontend arma el filtro `ubicacion` con dos selects en cascada
(Provincia -> Zona/Barrio, dataset curado en `frontend/app.js`,
`UBICACIONES`). Capital Federal trae los 48 barrios oficiales completos
mas "Barrio Norte" (no es oficial, pero es un slug real que usa
ZonaProp y es de los mas buscados). Buenos Aires agrupa sus partidos en
`<optgroup>` por punto cardinal (Zona Norte/Oeste/Sur) mas un grupo
aparte para ciudades importantes que no son GBA en sentido estricto.
Cada partido sigue mandando su propio slug real (no un "-zona-x"
inventado que no funciona en ningun portal), pero ademas cada grupo
cardinal tiene una opcion propia ("Toda la Zona Norte", etc,
value=`zona-norte`/`zona-oeste`/`zona-sur`) que busca en TODOS los
partidos de esa zona a la vez -- ver `backend/app/zonas_cardinales.py`
para la lista real de partidos por zona (sincronizada a mano con
`frontend/app.js`). Tambien tiene un grupo aparte **"Costa Atlantica"**
con las localidades del corredor de veraneo bonaerense (San Clemente
del Tuyu a Monte Hermoso, de norte a sur) -- sin fan-out de zona
cardinal (busca localidad por localidad, no hay "toda la costa" como
opcion).

Ademas de las 5 provincias originales (Capital Federal, Buenos Aires,
Cordoba, Santa Fe, Mendoza), se sumaron **Tucuman, Entre Rios, Salta,
Misiones, Chaco, Corrientes, Santiago del Estero, San Juan, Jujuy, Rio
Negro, Neuquen y Chubut** (17 en total) -- Rio Negro y Chubut incluyen
sus localidades costeras patagonicas (Las Grutas, Puerto Madryn,
Rawson). Cada una lista las ciudades/departamentos mas conocidos (no
exhaustivo). El slug que se manda es el nombre pelado, sin prefijo de
provincia (ej. `palermo`, `la-plata`), confirmado en vivo para
Capital Federal:

- **ZonaProp**: confirmado, barrio pelado funciona (usa esos mismos
  slugs en sus propios links de navegacion).
- **MercadoLibre**: confirmado en vivo -- comparamos los avisos que
  trae `capital-federal` vs `palermo` y son conjuntos distintos (94%
  no se superponen), asi que filtra de verdad.
- **RE/MAX**: no usa el slug para armar la URL (ver tabla de portales
  arriba), hace matching de texto contra `geoLabel`/`displayAddress`
  con el nombre de la zona -- funciona igual de bien con un barrio
  puntual que con la provincia entera.
- **Argenprop**: mismo patron de slug pelado que los demas, pero no se
  pudo confirmar en vivo (viene bloqueado por el anti-bot desde hace
  rato). Presumiblemente funciona igual, sin verificar.

**Busqueda por zona cardinal** (`zona-norte`/`zona-oeste`/`zona-sur`):
no hay un slug de portal que agrupe varios partidos en un solo pedido,
asi que cada portal lo resuelve distinto:
- **ZonaProp, MercadoLibre y Argenprop**: hacen un pedido HTTP por cada
  partido de la zona y juntan los resultados (confirmado en vivo con
  ZonaProp: 180 avisos de Zona Norte = 30 x 6 partidos, en ~8
  segundos). Mas pedidos por busqueda significa mas tiempo de espera y
  mas exposicion al anti-bot que buscar un solo partido -- si un
  partido puntual viene bloqueado pero los demas no, se devuelve lo
  que se pudo traer (solo se corta todo si TODOS los partidos de la
  zona fallan).
- **RE/MAX**: gratis en terminos de pedidos extra -- ya trae todo el
  pais en un unico pedido y filtra en memoria, asi que sumar mas
  partidos al matching de texto no cuesta nada mas.

## Filtros

El modelo `Filtros` acepta el set completo (precio, moneda, ambientes,
dormitorios, banos, superficie, antiguedad, cochera, expensas, orden). No
todos los portales pueden honrar todos los campos porque dependen de que
esa data este en la tarjeta de listado (no visitamos el detalle de cada
aviso, seria mucho mas lento):

- **Argenprop**: aplica precio, moneda, ambientes, dormitorios, superficie,
  antiguedad y expensas. `banos_min` y `con_cochera` se ignoran (no estan
  en la tarjeta de listado).
- **ZonaProp**: aplica todo lo de Argenprop y ademas `banos_min`,
  `con_cochera`, `con_patio`, `con_terraza` y `con_jardin`.
  Para las amenities, ZonaProp tiene sufijos de URL nativos y confirmados
  (`-con-patio`, `-con-terraza`, `-con-jardin`, `-mas-de-1-garage`) que
  filtran de verdad del lado del portal -- se usa **una sola** amenity por
  URL (probamos combinar dos, ej. `-con-patio-con-terraza`, y ZonaProp
  colapsa el filtro entero, lo pierde). Si se piden varias amenities a la
  vez, solo la primera (prioridad patio > terraza > jardin > cochera) usa
  el sufijo real; las demas caen al chequeo por `mainFeatures` (que en la
  pagina de listado suele venir vacio para estas amenities, asi que rara
  vez suman resultados extra en ese caso).
- Los filtros numericos (precio, ambientes, superficie, etc.) se aplican
  del lado del cliente sobre lo que ya se scrapeo (solo pagina 1 por
  ahora, salvo lo que ZonaProp ya filtra via URL). Reproducir el endpoint
  POST interno de Argenprop para filtrar server-side ahi tambien queda
  pendiente (ver Roadmap).
- **Superficie cubierta/descubierta**: las tarjetas muestran ambas por
  separado cuando el portal las expone asi. **ZonaProp** trae
  `CFT101` ("Superficie cubierta") y `CFT100` ("Superficie total")
  confirmadas por su propia label -- la descubierta es la resta de las
  dos (en depto suele ser balcon/terraza, en casa puede ser el patio o
  jardin entero, por eso el numero varia mucho segun el tipo). **RE/MAX**
  solo expone `dimensionCovered` (cubierta) de forma confiable;
  `dimensionLand` es el tamano del terreno, un concepto distinto al de
  "descubierta" en el sentido cubierta/descubierta argentino, asi que
  no se usa para no mostrar un numero enganoso. Argenprop y
  MercadoLibre no separan esto en absoluto -- ahi la tarjeta muestra
  solo el metraje generico, sin la etiqueta "cub."/"descub.".
- **`publicado_max_dias`** ("Publicado" en la fila principal del
  frontend): solo ZonaProp (`modified_date`, en rigor la ultima
  modificacion del aviso, no la fecha de alta original -- se usa como
  proxy) y MercadoLibre (`datePosted`, este si es la fecha real de
  publicacion) traen una fecha confiable. Argenprop no tiene ese dato
  en la tarjeta de listado y RE/MAX no lo expone en su API (aunque ya
  pide los avisos ordenados por `-createdAt`, asi que su orden interno
  ya es "mas recientes primero" aunque no se pueda filtrar por umbral
  de dias) -- en esos dos el filtro no descarta nada. El orden "Mas
  recientes" usa el mismo dato: los avisos sin fecha quedan al final,
  en el orden en que respondio el portal.
- **`distancia_general_paz_max_km`** ("Distancia max a Gral. Paz (km)"
  en "+ Filtros"): distancia minima real desde el aviso hasta la traza
  de la Av. General Paz (nube de ~250 puntos sacada en vivo de
  OpenStreetMap/Overpass, `backend/app/geo.py`, no inventada a mano).
  - **ZonaProp** y **RE/MAX** traen coordenadas reales por aviso
    (`postingLocation.postingGeolocation` y `location.coordinates`
    respectivamente, confirmado en vivo) -- la distancia es exacta.
  - **MercadoLibre** y **Argenprop** no traen coordenadas por aviso (el
    JSON-LD de MercadoLibre no incluye `geo`; el HTML de Argenprop no
    tiene lat/lon en ningun atributo). Para estos dos se aproxima con
    el centroide de la zona buscada (`backend/app/ubicaciones_geo.py`,
    geocodificado una sola vez con Nominatim/OpenStreetMap para cada
    barrio/partido del dataset curado del frontend -- no en cada
    busqueda). El campo `distancia_general_paz_aprox` en la respuesta
    marca esta diferencia; el frontend lo muestra con un `~` adelante.
  - Como siempre, dato faltante no descarta el aviso.

## Diferenciales del agregador

Dos cosas que ningun portal individual puede ofrecer porque no ve el
inventario de la competencia -- se calculan cruzando los resultados de
los 4 portales de cada busqueda:

- **"Buen precio"** (`backend/app/precio_justo.py`): calcula precio/m²
  de cada aviso y lo compara contra la mediana de precio/m² de esta
  misma busqueda (agrupado por moneda, USD y ARS no se mezclan). Si un
  aviso esta 15% o mas por debajo de esa mediana, se marca. No se marca
  nada si el grupo tiene menos de 5 avisos comparables (con poca
  muestra la mediana no dice mucho). No es una tasacion ni un "precio
  de mercado" objetivo -- es relativo a lo que trajo esa busqueda
  puntual.
- **Historial de precios / "Bajo de precio"** (`backend/app/historial.py`):
  cada busqueda registra el precio de cada aviso en un SQLite local
  (`backend/data/historial.db`, se crea solo, gitignored). Si en una
  busqueda posterior el mismo aviso (portal + id) aparece con un precio
  distinto, se marca como baja (o suba) de precio, con precio anterior
  y hace cuantos dias cambio. **No hay datos "de arranque"**: recien
  arma historial con el uso real a lo largo del tiempo -- si nadie
  vuelve a buscar lo mismo, no hay forma de detectar una baja que paso
  en el medio. No hay un cron corriendo re-scrapeando solo; el registro
  pasa cada vez que alguien busca.
- **Mejores precios de esta zona**: fila destacada de hasta 3 avisos
  (los de menor precio/m² entre los marcados "Buen precio") arriba de
  los resultados normales, en carrusel, calculada con el mismo cruce
  de portales.

## Delitos contra la propiedad por zona (`backend/app/delitos.py`)

Badge de color mostrado arriba de los resultados con la cantidad de
delitos contra la propiedad de 2024 en la zona buscada, fuente **SNIC
(Sistema Nacional de Informacion Criminal), Sistema de Alerta Temprana
-- Ministerio de Seguridad de la Nacion** (dato oficial, no scrapeado
de terceros, descargado de https://datos.gob.ar/dataset/seguridad_9).

**En el mapa se pinta la ZONA (poligono del partido), no la
propiedad**: pintar de rojo el marcador de un aviso puntual
estigmatizaria ese aviso especifico (y a quien lo publica) con un dato
que en realidad describe el partido entero, no esa direccion -- ademas
de ser mal negocio para el producto. La capa "Delitos por partido" en
el mapa (toggle abajo a la izquierda, se puede apagar) usa el limite
geografico real de cada partido, descargado del portal de datos
abiertos de la provincia de Buenos Aires
(`catalogo.datos.gba.gob.ar/dataset/partidos`, fuente ARBA) y
simplificado de ~22.700 a ~780 puntos (`frontend/partidos-delitos.geojson`,
33kb) para que cargue liviano. Los mismos umbrales bajo/medio/alto que
el badge, coloreando el partido entero con opacidad baja (no tapa el
mapa de calles/satelite de abajo).

**Cobertura real, no completa a proposito**: solo Buenos Aires
provincia (partidos + Costa Atlantica) tiene el cruce hecho hoy. CABA
necesitaria mapear barrio->comuna aparte (el SNIC viene por comuna, no
por barrio) y las 12 provincias sumadas mas recientemente todavia no
se cruzaron -- devuelven `delitos_zona: null` en vez de mostrar un
numero inventado o aproximado.

**Limitaciones reales, aclaradas tambien en la UI (tooltip)**:
- Es la cantidad TOTAL de hechos en 2024, sin ajustar por poblacion --
  una zona grande o turistica (Mar del Plata) va a mostrar mas hechos
  que una chica solo por tener mas gente, no necesariamente por ser
  "mas insegura" por habitante. No es una tasa ni un ranking de
  seguridad.
- Varias localidades curadas caen en el mismo partido SNIC y por eso
  muestran el mismo numero (ej. Cariló/Valeria del Mar/Ostende son
  todos el partido de Pinamar; San Clemente del Tuyú/Las Toninas/Santa
  Teresita/etc son todos el partido de La Costa).
- Los niveles bajo/medio/alto son terciles de las localidades ya
  cargadas (no un estandar externo) -- si se agregan mas localidades
  convendria recalcularlos.

## UI: mapa y vista de calles/satelite

Ademas de la grilla de tarjetas, los resultados se pueden ver en un
**mapa** (toggle "Lista"/"Mapa" arriba de los resultados, `frontend/app.js`,
usa Leaflet). Solo entran al mapa los avisos con coordenadas reales por
aviso (**ZonaProp** y **RE/MAX** -- ver seccion de distancia a Gral.
Paz arriba); el resto de los avisos siguen estando en la vista de
lista, el mapa no los oculta ni los descarta, solo no los puede ubicar.

Dos capas de mapa, ambas gratis y sin API key:
- **Calles**: tiles estandar de OpenStreetMap con un filtro CSS
  (`invert` + `hue-rotate`) para que se vea oscuro y combine con el
  resto del sitio -- los proveedores de tiles oscuros "gratis" (CARTO)
  pasaron a pedir API key, asi que no se uso ese camino.
- **Satelite**: Esri World Imagery (imagenes aereas reales, sin key),
  el equivalente funcional a pedir "una vista tipo Google Earth" sin
  meterse con las APIs pagas de Google.

**Bug real encontrado y arreglado en el camino**: el atributo HTML
`hidden` pierde contra cualquier clase que fije su propio `display`
(ej. `.resultados-grid { display: grid }`) porque tienen la misma
especificidad y la clase del autor gana por orden de cascada -- asi que
ocultar la grilla de resultados con `.hidden = true` no hacia nada.
Se arreglo con una regla global `[hidden] { display: none !important; }`
cerca del reset de estilos.

## Como correr

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend: abrir `frontend/index.html` directo en el navegador (usa `fetch`
contra `http://localhost:8000`), o deployarlo a un hosting estatico como
Netlify (ver seccion siguiente). Es responsive -- probado en viewport
mobile (375px): el formulario cae a 1 columna, la grilla de resultados
a 1 tarjeta por fila, sin scroll horizontal.

## Deploy del frontend (Netlify u otro hosting estatico)

El frontend es HTML/CSS/JS estatico (`frontend/`), se sube tal cual a
Netlify (drag & drop de la carpeta -- no esta conectado a GitHub, asi
que un push a este repo NO redeploya Netlify solo, hay que volver a
arrastrar la carpeta cada vez que cambia algo en `frontend/`). En
cualquier dominio que no sea `localhost` llama al backend real en
Render (ver seccion siguiente).

### Backend real: Render (siempre arriba, sin depender de ninguna PC)

El backend esta deployado en **Render** (`https://nuevacasa.onrender.com`,
blueprint en `render.yaml`, plan free) y se **autodeploya solo en cada
push a `main`** -- no hace falta gatillar nada a mano despues de un
`git push`.

**Limitaciones del plan free de Render a tener en cuenta**:
- **Se "duerme" tras ~15 min sin trafico**: la primera visita despues
  de un rato de inactividad tarda unos segundos de mas en responder
  (arranca el contenedor). Visitas siguientes son normales.
- **Disco no persistente**: el historial de precios (SQLite,
  `backend/data/historial.db`, ver seccion "Diferenciales del
  agregador") se resetea cada vez que Render reinicia el servicio
  (dormido por inactividad, redeploy, etc.) -- en un sitio de poco
  trafico esto pasa seguido, asi que "Bajo de precio" en la practica
  va a detectar menos bajas de las que detectaria con un disco
  persistente. Para que esto persista de verdad hace falta un plan
  pago de Render con disco, o una base de datos externa.
- **IP compartida (de datacenter)**: Render bloquea igual en TODAS sus
  regiones -- se probo en vivo levantando un segundo servicio de prueba
  en Frankfurt (en vez de la default Oregon) y ZonaProp/MercadoLibre
  bloquearon exactamente igual. Conclusion: no es reputacion de una
  region puntual, es que estos portales detectan "esto es una IP de
  datacenter" en general. Tambien se probo endurecer los scrapers
  (sesion persistente, cookies, headers completos, reintento -- mismo
  tratamiento que ya tenia Argenprop) para ZonaProp y MercadoLibre: no
  cambio nada en Render (mismo bloqueo, 12/12 intentos). MercadoLibre
  en particular redirige con HTTP 200 en vez de tirar un 403 seco, lo
  que sugiere un sistema de bot-management mas sofisticado
  (probablemente fingerprint TLS) que ninguna de estas mitigaciones
  legitimas puede resolver.

### Respaldo opcional: tunel de ngrok hacia la PC (invisible para quien busca)

Como Render bloquea ZonaProp/MercadoLibre segudio pero la IP
residencial de la PC del desarrollador no, el frontend (`app.js`,
`completarConTunel()`) intenta un segundo pedido contra un tunel de
ngrok hacia esa PC **solo cuando Render devuelve 2 o mas portales
bloqueados**, con un timeout corto (8s). Si la PC esta prendida y el
tunel andando, se usa para completar los portales que a Render le
fallaron (merge por portal, no se duplican avisos); si no responde a
tiempo (PC apagada, tunel caido), el intento simplemente se descarta y
se sigue con lo que ya trajo Render, sin mostrar ningun error -- es
invisible para quien busca, nunca es la fuente principal.

Esto significa que la PC **no es obligatoria** para que el sitio
funcione (Render solo ya alcanza), pero cuando esta prendida el sitio
trae mas resultados reales. Para que esto ande:
- La tarea programada de Windows ("NuevaCasa Backend", Programador de
  Tareas) arranca backend + tunel al iniciar sesion. Se puede
  deshabilitar desde el Programador de Tareas sin romper el sitio (el
  respaldo simplemente deja de estar disponible).
- El dominio del tunel es fijo (`celtic-lapel-smirk.ngrok-free.dev`,
  cuenta gratis de ngrok) -- no cambia entre reinicios, no hace falta
  tocar `app.js` por esto.
- El script `iniciar_backend.bat` sigue sirviendo para correr el
  backend local a mano.

## Legal

Los portales listados como pendientes no tienen API publica libre y sus
Terminos de Servicio en general prohiben el scraping automatizado. Este
proyecto es para uso personal/local; antes de escalarlo a produccion o
uso compartido conviene revisar los ToS de cada portal y evaluar
contactarlos por acceso a datos (feeds, partnerships) en vez de
scraping directo.

## Roadmap

1. Paginacion real en Argenprop y ZonaProp (hoy solo pagina 1).
2. Deduplicacion de propiedades repetidas entre portales.
