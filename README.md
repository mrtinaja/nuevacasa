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
| RE/MAX        | Funcionando            | App Angular con SSR: se encontro su API publica real (`api-ar.redremax.com`) leyendo el TransferState (`ng-state`) embebido en el HTML. Sin anti-bot detectado. Operacion (venta/alquiler) es server-side; tipo de propiedad y ubicacion se filtran client-side (texto contra `geoLabel`/`displayAddress`, confirmado: 17/17 resultados reales en Capital Federal). No distingue Zona Norte/Sur/Este/Oeste, cae a la provincia entera. |

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
aparte para ciudades importantes que no son GBA en sentido estricto --
la agrupacion es solo visual, cada opcion sigue mandando el slug real
del partido, no un "-zona-x" inventado que no funciona en ningun
portal. Las demas provincias listan los partidos/departamentos mas
conocidos de cada una (no exhaustivo). El slug que se manda es el
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

El frontend es HTML/CSS/JS estatico (`frontend/`), se puede subir tal
cual a Netlify (drag & drop de la carpeta, o `netlify deploy`). Pero
sigue llamando a `http://localhost:8000` -- funciona solo si el
backend esta corriendo en la MISMA maquina donde se abre la pagina
deployada, no sirve para que otras personas lo usen.

**Importante**: si abris la version deployada (HTTPS) y te tira
"Failed to fetch" al buscar, es la politica de navegador "Private
Network Access" -- una pagina publica (Netlify) no puede pedirle datos
a `localhost` (red privada) a menos que el backend lo autorice
explicitamente con un header. Ya esta resuelto en
`backend/app/main.py` (middleware `permitir_red_privada`), pero
necesitas el backend corriendo con ese codigo actualizado.

### Backend real: PC local + tunel de ngrok (dominio fijo)

Para que la version de Netlify funcione para cualquiera (no solo en tu
maquina), el backend corre en tu PC expuesto via **ngrok**, con un
**dominio estatico gratis** de la cuenta (`celtic-lapel-smirk.ngrok-free.dev`)
-- a diferencia del tunel de Cloudflare que se uso al principio (un
"quick tunnel" sin cuenta, con URL aleatoria que cambiaba en cada
reinicio), este dominio no cambia nunca, asi que `frontend/app.js` no
necesita tocarse de nuevo por esto.

- **Arranque automatico**: hay una tarea programada de Windows
  ("NuevaCasa Backend", `schtasks`/Task Scheduler) que corre
  `iniciar_backend.bat` al iniciar sesion en Windows -- no hace falta
  tocar nada al prender la PC, siempre que inicies sesion en tu
  usuario. Para verla o borrarla: Programador de Tareas de Windows,
  buscar "NuevaCasa Backend" en la raiz.
- **Manual**: doble clic en **`iniciar_backend.bat`** (en la raiz del
  proyecto) reinicia backend + tunel juntos.
- **ngrok free**: las visitas de navegador sin el header
  `ngrok-skip-browser-warning` ven una pagina de advertencia HTML en
  vez de la respuesta real -- por eso el `fetch` en `app.js` manda ese
  header en todo pedido que no sea a `localhost`.

**Limitaciones a tener en cuenta**:
- Si la PC se apaga o entra en reposo, el backend y el tunel se caen
  igual -- necesitas que la PC este prendida (y con la sesion
  iniciada) para que el sitio funcione. La tarea programada resuelve
  el "hay que tocar algo a mano" pero no el "la PC tiene que estar
  prendida".
- Windows esta configurado para no entrar en reposo mientras la PC
  esta enchufada (`powercfg /change standby-timeout-ac 0`) -- si es
  una notebook, conviene activar algun limite de carga de bateria del
  fabricante para no tenerla siempre al 100%.
- El authtoken de ngrok esta guardado localmente
  (`%LOCALAPPDATA%\ngrok\ngrok.yml`), no en el repo.

## Legal

Los portales listados como pendientes no tienen API publica libre y sus
Terminos de Servicio en general prohiben el scraping automatizado. Este
proyecto es para uso personal/local; antes de escalarlo a produccion o
uso compartido conviene revisar los ToS de cada portal y evaluar
contactarlos por acceso a datos (feeds, partnerships) en vez de
scraping directo.

## Roadmap

1. Paginacion real en Argenprop y ZonaProp (hoy solo pagina 1).
2. Filtro de ubicacion real para Argenprop/ZonaProp/MercadoLibre (RE/MAX
   ya lo tiene -- ver seccion Ubicacion).
3. Zona Norte/Sur/Este/Oeste con lista curada de partidos reales, en vez
   de caer a "toda la provincia" (RE/MAX) o un slug sin verificar
   (Argenprop/ZonaProp).
4. Deduplicacion de propiedades repetidas entre portales.
5. Cache de resultados para no re-pegarle a los portales en cada busqueda.
