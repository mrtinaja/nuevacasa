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
`frontend/app.js`). Las demas provincias listan los partidos/departamentos
mas conocidos de cada una (no exhaustivo). El slug que se manda es el
nombre pelado, sin prefijo de provincia (ej. `palermo`, `la-plata`),
confirmado en vivo:

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

Antes de esto el backend corria en la PC del usuario expuesto via
tunel (primero Cloudflare, despues ngrok), abandonado a proposito por
depender de que la PC este prendida 24hs. Queda documentado por si
hace falta volver a esa alternativa:
- La tarea programada de Windows ("NuevaCasa Backend", Programador de
  Tareas) que arrancaba el backend + tunel al iniciar sesion esta
  **deshabilitada** (no borrada -- se puede reactivar desde el
  Programador de Tareas si hiciera falta).
- El script `iniciar_backend.bat` sigue en el repo, sirve para correr
  el backend local a mano (desarrollo), ya no es necesario para que el
  sitio publico funcione.

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
- **IP compartida**: Render usa IPs de datacenter compartidas entre
  muchos servicios, lo que historicamente hizo que ZonaProp/MercadoLibre
  bloqueen mas seguido que con una IP residencial (la de una PC/hogar
  real, como la que se usaba con el tunel). Esto no se soluciono, solo
  se acepto como tradeoff a cambio de no depender de la PC -- si se
  vuelve un problema recurrente, la alternativa es sumar un proxy
  residencial pago solo para esos dos portales.

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
