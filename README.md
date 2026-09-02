# compraTuCasa

Buscador agregado de propiedades. Prototipo local: un backend en FastAPI
orquesta un scraper por portal, normaliza los resultados a un esquema
comun y un frontend simple los muestra con filtros.

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
| Properati     | Bloqueado (infra)      | El sitio entero devuelve `401 Access Denied` (probado con curl y con navegador real, en dos intentos separados), incluso en el homepage -- parece un bloqueo de IP/WAF al entorno donde corremos, no algo que se arregle con headers. No hay API publica documentada, solo datasets historicos ("Properati Data") en BigQuery, que no sirven para busqueda en vivo. **No se puede implementar el scraper sin poder inspeccionar la pagina real** -- si alguien puede acceder al sitio desde otra red y compartir el HTML de una busqueda, se puede retomar. El badge en la UI muestra `blocked` (no `not_implemented`): el scraper intenta la conexion real en cada busqueda, asi que si el bloqueo se levanta algun dia el estado lo va a reflejar solo. |

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
(Provincia -> Zona: Norte/Sur/Este/Oeste, dataset curado en
`frontend/app.js`, `UBICACIONES`). El slug que se manda es
`<provincia>-zona-<punto-cardinal>` (ej. `buenos-aires-zona-norte`); es una
convencion razonable pero todavia no esta verificada 1:1 contra la
taxonomia real de Argenprop, asi que puede no traer resultados para
algunas combinaciones hasta confirmarla. RE/MAX es la excepcion: no usa
ese slug tal cual, hace matching de texto (ver tabla de portales arriba),
asi que "toda la provincia" y "Capital Federal" andan bien pero el
sufijo `-zona-x` se ignora ahi.

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

## Legal

Los portales listados como pendientes no tienen API publica libre y sus
Terminos de Servicio en general prohiben el scraping automatizado. Este
proyecto es un prototipo para uso personal/local; antes de escalarlo a
produccion o uso compartido conviene revisar los ToS de cada portal y
evaluar contactarlos por acceso a datos (feeds, partnerships) en vez de
scraping directo.

## Roadmap

1. Properati: retomar si se consigue inspeccionar el sitio desde una red
   que no este bloqueada.
2. Paginacion real en Argenprop y ZonaProp (hoy solo pagina 1).
3. Filtro de ubicacion real para Argenprop/ZonaProp/MercadoLibre (RE/MAX
   ya lo tiene -- ver seccion Ubicacion).
4. Zona Norte/Sur/Este/Oeste con lista curada de partidos reales, en vez
   de caer a "toda la provincia" (RE/MAX) o un slug sin verificar
   (Argenprop/ZonaProp).
5. Deduplicacion de propiedades repetidas entre portales.
6. Cache de resultados para no re-pegarle a los portales en cada busqueda.
