// En localhost usa el backend local directo (para desarrollar mas rapido).
// En cualquier otro dominio (ej. el deploy en Netlify) usa el backend
// deployado en Render -- NO depende de que ninguna PC este prendida, el
// servicio esta siempre arriba (aunque en el plan gratis puede tardar
// unos segundos en "despertar" si nadie lo uso en un rato). Se
// autodeploya solo con cada push a GitHub (blueprint `render.yaml`).
const ES_LOCAL = location.hostname === "localhost" || location.hostname === "127.0.0.1";
const API_URL = ES_LOCAL
  ? "http://localhost:8000/api/search"
  : "https://nuevacasa.onrender.com/api/search";

// Respaldo opcional: la IP de Render es de datacenter y ZonaProp/
// MercadoLibre la bloquean seguido (confirmado: el mismo bloqueo pasa
// en cualquier region de Render, no es cuestion de reputacion de una
// region puntual -- ver README). La IP residencial de la PC del
// desarrollador no tiene ese problema. Si Render devuelve 2 o mas
// portales bloqueados, se intenta el mismo pedido contra ese tunel con
// un timeout corto -- si la PC esta prendida y el tunel andando,
// se usa lo que traiga; si no, el intento falla rapido y se sigue con
// lo que ya trajo Render, sin mostrar ningun error (respaldo invisible
// para quien busca).
const TUNEL_URL = "https://celtic-lapel-smirk.ngrok-free.dev/api/search";
const TUNEL_TIMEOUT_MS = 8000;
const UMBRAL_PORTALES_BLOQUEADOS_PARA_RESPALDO = 2;

// Dataset curado de ubicaciones (no es exhaustivo, hay muchos mas barrios
// y partidos/departamentos reales que los listados aca). El slug de "Zona"
// es lo que efectivamente se manda al backend como filtros.ubicacion --
// va PELADO (ej. "palermo", "la-plata"), sin prefijo de provincia.
// Confirmado en vivo que ZonaProp y MercadoLibre aceptan barrios pelados
// para Capital Federal; Argenprop y los partidos/departamentos de otras
// provincias siguen el mismo patron pero no se verificaron todos
// individualmente.
const UBICACIONES = {
  "Capital Federal": {
    todas: "capital-federal",
    todasLabel: "Todos los barrios",
    // Los 48 barrios oficiales de CABA + "Barrio Norte" (no es oficial,
    // pero es un slug real que confirmamos que usa ZonaProp y es de los
    // mas buscados en venta/alquiler).
    zonas: [
      "Agronomia", "Almagro", "Balvanera", "Barracas", "Barrio Norte",
      "Belgrano", "Boedo", "Caballito", "Chacarita", "Coghlan",
      "Colegiales", "Constitucion", "Flores", "Floresta", "La Boca",
      "La Paternal", "Liniers", "Mataderos", "Monserrat", "Monte Castro",
      "Nueva Pompeya", "Nuñez", "Palermo", "Parque Avellaneda",
      "Parque Chacabuco", "Parque Chas", "Parque Patricios",
      "Puerto Madero", "Recoleta", "Retiro", "Saavedra", "San Cristobal",
      "San Nicolas", "San Telmo", "Velez Sarsfield", "Versalles",
      "Villa Crespo", "Villa del Parque", "Villa Devoto",
      "Villa General Mitre", "Villa Lugano", "Villa Luro",
      "Villa Ortuzar", "Villa Pueyrredon", "Villa Real", "Villa Riachuelo",
      "Villa Santa Rita", "Villa Soldati", "Villa Urquiza",
    ],
  },
  "Buenos Aires": {
    todas: "buenos-aires",
    todasLabel: "Toda la provincia",
    // Partidos del GBA agrupados por zona cardinal (asi se buscan en la
    // vida real), mas un grupo aparte para ciudades importantes que no
    // son "GBA" en sentido estricto. El value que se manda sigue siendo
    // el slug real del partido -- la agrupacion es solo visual
    // (<optgroup>), no inventamos un slug "-zona-x" que no funciona en
    // ningun portal.
    grupos: {
      "Zona Norte": ["San Isidro", "Vicente Lopez", "Tigre", "San Fernando", "Pilar", "Nordelta"],
      "Zona Oeste": ["Moron", "Ituzaingo", "Merlo", "Moreno"],
      "Zona Sur": ["Quilmes", "Avellaneda", "Lanus", "Lomas de Zamora", "La Plata"],
      // Costa Atlantica bonaerense -- el corredor de veraneo clasico,
      // de norte a sur.
      "Costa Atlantica": [
        "San Clemente del Tuyu", "Las Toninas", "Santa Teresita",
        "Mar del Tuyu", "San Bernardo", "Mar de Ajo", "Pinamar",
        "Cariló", "Valeria del Mar", "Ostende", "Villa Gesell",
        "Mar de las Pampas", "Mar del Plata", "Miramar", "Necochea",
        "Monte Hermoso",
      ],
    },
  },
  "Cordoba": {
    todas: "cordoba",
    todasLabel: "Toda la provincia",
    zonas: ["Cordoba Capital", "Villa Carlos Paz", "Rio Cuarto", "Villa Maria", "Alta Gracia"],
  },
  "Santa Fe": {
    todas: "santa-fe",
    todasLabel: "Toda la provincia",
    zonas: ["Rosario", "Santa Fe Capital", "Rafaela", "Venado Tuerto"],
  },
  "Mendoza": {
    todas: "mendoza",
    todasLabel: "Toda la provincia",
    zonas: ["Mendoza Capital", "Godoy Cruz", "Lujan de Cuyo", "Maipu", "San Rafael"],
  },
  "Tucuman": {
    todas: "tucuman",
    todasLabel: "Toda la provincia",
    zonas: ["San Miguel de Tucuman", "Yerba Buena", "Tafi Viejo", "Concepcion", "Tafi del Valle"],
  },
  "Entre Rios": {
    todas: "entre-rios",
    todasLabel: "Toda la provincia",
    zonas: ["Parana", "Concordia", "Gualeguaychu", "Concepcion del Uruguay", "Gualeguay"],
  },
  "Salta": {
    todas: "salta",
    todasLabel: "Toda la provincia",
    zonas: ["Salta Capital", "San Ramon de la Nueva Oran", "Tartagal", "Cafayate"],
  },
  "Misiones": {
    todas: "misiones",
    todasLabel: "Toda la provincia",
    zonas: ["Posadas", "Obera", "Eldorado", "Puerto Iguazu"],
  },
  "Chaco": {
    todas: "chaco",
    todasLabel: "Toda la provincia",
    zonas: ["Resistencia", "Presidencia Roque Saenz Peña", "Villa Angela"],
  },
  "Corrientes": {
    todas: "corrientes",
    todasLabel: "Toda la provincia",
    zonas: ["Corrientes Capital", "Goya", "Mercedes"],
  },
  "Santiago del Estero": {
    todas: "santiago-del-estero",
    todasLabel: "Toda la provincia",
    zonas: ["Santiago del Estero Capital", "La Banda", "Termas de Rio Hondo"],
  },
  "San Juan": {
    todas: "san-juan",
    todasLabel: "Toda la provincia",
    zonas: ["San Juan Capital", "Rivadavia", "Chimbas", "Rawson"],
  },
  "Jujuy": {
    todas: "jujuy",
    todasLabel: "Toda la provincia",
    zonas: ["San Salvador de Jujuy", "Palpala", "Perico"],
  },
  "Rio Negro": {
    todas: "rio-negro",
    todasLabel: "Toda la provincia",
    // Incluye costa atlantica rionegrina (Las Grutas).
    zonas: ["Viedma", "San Carlos de Bariloche", "General Roca", "Cipolletti", "Las Grutas"],
  },
  "Neuquen": {
    todas: "neuquen",
    todasLabel: "Toda la provincia",
    zonas: ["Neuquen Capital", "Plottier", "Cutral Co", "San Martin de los Andes", "Villa La Angostura"],
  },
  "Chubut": {
    todas: "chubut",
    todasLabel: "Toda la provincia",
    // Incluye costa atlantica chubutense (Puerto Madryn, Rawson).
    zonas: ["Comodoro Rivadavia", "Trelew", "Puerto Madryn", "Rawson", "Esquel"],
  },
};

function slugify(texto) {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

const RESULTADOS_POR_PAGINA = 12;
let propiedadesActuales = [];
let paginaActual = 1;
let vistaActual = "lista";
let mapaLeaflet = null;
let marcadoresLayer = null;
let capaCalles = null;
let capaSatelite = null;
let capaDelitos = null;
let capaDelitosVisible = true;

// Mismos totales 2024 y niveles que backend/app/delitos.py (SNIC,
// Ministerio de Seguridad), pero indexados por nombre de partido tal
// como viene en partidos-delitos.geojson en vez de por slug de
// ubicacion -- es la misma fuente, solo la llave de busqueda cambia
// porque el poligono no sabe que slug elegiste, solo su propio nombre.
const PARTIDOS_NIVEL_DELITOS = {
  "Avellaneda": { hechos: 4968, nivel: "medio" },
  "Lanús": { hechos: 7420, nivel: "alto" },
  "General Alvarado": { hechos: 1034, nivel: "bajo" },
  "General Pueyrredón": { hechos: 10156, nivel: "alto" },
  "La Plata": { hechos: 9066, nivel: "alto" },
  "Tigre": { hechos: 4047, nivel: "medio" },
  "Lomas de Zamora": { hechos: 7754, nivel: "alto" },
  "Merlo": { hechos: 6496, nivel: "alto" },
  "Moreno": { hechos: 6170, nivel: "medio" },
  "Necochea": { hechos: 1357, nivel: "bajo" },
  "Pilar": { hechos: 3108, nivel: "medio" },
  "Quilmes": { hechos: 8762, nivel: "alto" },
  "San Fernando": { hechos: 1295, nivel: "bajo" },
  "San Isidro": { hechos: 3559, nivel: "medio" },
  "Morón": { hechos: 8220, nivel: "alto" },
  "Vicente López": { hechos: 2705, nivel: "medio" },
  "La Costa": { hechos: 1918, nivel: "bajo" },
  "Pinamar": { hechos: 1012, nivel: "bajo" },
  "Villa Gesell": { hechos: 1299, nivel: "bajo" },
  "Monte Hermoso": { hechos: 168, nivel: "bajo" },
  "Ituzaingó": { hechos: 2571, nivel: "medio" },
};
const COLOR_NIVEL = { bajo: "#34d399", medio: "#fbbf24", alto: "#fb7185" };

const form = document.getElementById("filtros-form");
const estadoPortales = document.getElementById("estado-portales");
const resultadosEl = document.getElementById("resultados");
const paginacionEl = document.getElementById("paginacion");
const delitosZonaEl = document.getElementById("delitos-zona");
const destacadosWrapEl = document.getElementById("destacados-wrap");
const destacadosEl = document.getElementById("destacados");
const toggleVistaEl = document.getElementById("toggle-vista");
const mapaEl = document.getElementById("mapa");
const mapaWrapEl = document.getElementById("mapa-wrap");
const mapaNotaEl = document.getElementById("mapa-nota");
const toggleMasFiltros = document.getElementById("toggle-mas-filtros");
const masFiltros = document.getElementById("mas-filtros");
const provinciaSelect = document.getElementById("provincia");
const ubicacionSelect = document.getElementById("ubicacion");
const operacionSelect = document.getElementById("operacion");
const filtroEspecialInput = document.getElementById("filtro-especial-operacion");
const filtroEspecialLabel = document.getElementById("filtro-especial-operacion-label");

// "Apto credito" solo tiene sentido para venta y "Acepta mascotas" solo
// para alquiler -- en vez de mostrar los dos siempre, un unico switch
// cambia de significado segun la Operacion elegida.
function actualizarFiltroEspecial() {
  const esAlquiler = operacionSelect.value === "alquiler";
  filtroEspecialLabel.textContent = esAlquiler ? "Acepta mascotas" : "Apto credito";
  filtroEspecialInput.checked = false;
}

operacionSelect.addEventListener("change", actualizarFiltroEspecial);
actualizarFiltroEspecial();

function poblarProvincias() {
  provinciaSelect.innerHTML = Object.keys(UBICACIONES)
    .map((nombre) => `<option value="${escapeHtml(nombre)}">${escapeHtml(nombre)}</option>`)
    .join("");
  poblarZonas(provinciaSelect.value);
}

function opcionZona(zona) {
  const slug = slugify(zona);
  return `<option value="${slug}">${escapeHtml(zona)}</option>`;
}

function poblarZonas(nombreProvincia) {
  const provincia = UBICACIONES[nombreProvincia];
  if (!provincia) {
    ubicacionSelect.innerHTML = "";
    return;
  }
  const todas = `<option value="${provincia.todas}">${escapeHtml(provincia.todasLabel)}</option>`;

  if (provincia.grupos) {
    const optgroups = Object.entries(provincia.grupos)
      .map(([nombreGrupo, zonas]) => {
        // "Toda la Zona X" busca en TODOS los partidos de esa zona a la
        // vez (el backend hace el fan-out) -- solo tiene sentido para
        // las zonas cardinales de verdad, no para el grupo "Otras
        // ciudades" (que no es una zona geografica, es un cajon de
        // sastre de ciudades importantes sueltas).
        const opcionToda = nombreGrupo.startsWith("Zona ")
          ? `<option value="${slugify(nombreGrupo)}">Toda la ${escapeHtml(nombreGrupo)}</option>`
          : "";
        const opciones = zonas.map(opcionZona).join("");
        return `<optgroup label="${escapeHtml(nombreGrupo)}">${opcionToda}${opciones}</optgroup>`;
      })
      .join("");
    ubicacionSelect.innerHTML = todas + optgroups;
    return;
  }

  const opciones = provincia.zonas.map(opcionZona).join("");
  ubicacionSelect.innerHTML = todas + opciones;
}

provinciaSelect.addEventListener("change", () => poblarZonas(provinciaSelect.value));
poblarProvincias();

toggleMasFiltros.setAttribute("aria-expanded", "false");
toggleMasFiltros.addEventListener("click", () => {
  const abrir = masFiltros.hidden;
  masFiltros.hidden = !abrir;
  toggleMasFiltros.setAttribute("aria-expanded", String(abrir));
  toggleMasFiltros.querySelector(".link-btn-icon").textContent = abrir ? "−" : "+";
  toggleMasFiltros.querySelector(".link-btn-label").textContent = abrir ? "Menos filtros" : "Mas filtros";
});

async function completarConTunel(resultadoRender, filtros) {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TUNEL_TIMEOUT_MS);
    const resp = await fetch(TUNEL_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true" },
      body: JSON.stringify(filtros),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!resp.ok) return resultadoRender;
    const resultadoTunel = await resp.json();

    const propiedades = resultadoRender.propiedades.slice();
    const portales = resultadoRender.portales.map((p) => {
      if (p.status === "ok") return p;
      const delTunel = resultadoTunel.portales.find((t) => t.portal === p.portal);
      if (!delTunel || delTunel.status !== "ok") return p;
      propiedades.push(...resultadoTunel.propiedades.filter((prop) => prop.portal === p.portal));
      return delTunel;
    });

    return { propiedades, portales, delitos_zona: resultadoRender.delitos_zona };
  } catch (err) {
    // Tunel no disponible (PC apagada, ngrok caido, timeout) -- se sigue
    // con lo que ya trajo Render, sin mostrar ningun error.
    return resultadoRender;
  }
}

function numeroOrNull(valor) {
  return valor === "" ? null : Number(valor);
}

function stringOrNull(valor) {
  return valor === "" ? null : valor;
}

function escapeHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto ?? "";
  return div.innerHTML;
}

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const formData = new FormData(form);

  const filtros = {
    operacion: formData.get("operacion"),
    tipo_propiedad: formData.get("tipo_propiedad"),
    ubicacion: formData.get("ubicacion"),
    precio_min: numeroOrNull(formData.get("precio_min")),
    precio_max: numeroOrNull(formData.get("precio_max")),
    moneda: stringOrNull(formData.get("moneda")),
    ambientes_min: numeroOrNull(formData.get("ambientes_min")),
    ambientes_max: numeroOrNull(formData.get("ambientes_max")),
    dormitorios_min: numeroOrNull(formData.get("dormitorios_min")),
    dormitorios_max: numeroOrNull(formData.get("dormitorios_max")),
    superficie_min: numeroOrNull(formData.get("superficie_min")),
    superficie_max: numeroOrNull(formData.get("superficie_max")),
    antiguedad_max: numeroOrNull(formData.get("antiguedad_max")),
    expensas_max: numeroOrNull(formData.get("expensas_max")),
    con_cochera: formData.get("con_cochera") === "on" ? true : null,
    con_patio: formData.get("con_patio") === "on" ? true : null,
    con_terraza: formData.get("con_terraza") === "on" ? true : null,
    con_jardin: formData.get("con_jardin") === "on" ? true : null,
    apto_credito: operacionSelect.value !== "alquiler" && filtroEspecialInput.checked ? true : null,
    acepta_mascotas: operacionSelect.value === "alquiler" && filtroEspecialInput.checked ? true : null,
    publicado_max_dias: numeroOrNull(formData.get("publicado_max_dias")),
    distancia_general_paz_max_km: numeroOrNull(formData.get("distancia_general_paz_max_km")),
    orden: formData.get("orden") || "relevancia",
  };

  estadoPortales.innerHTML = `<span class="estado-cargando"><span class="spinner"></span> Consultando portales...</span>`;
  renderSkeletons();

  try {
    const resp = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(filtros),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    let resultado = await resp.json();

    const bloqueados = resultado.portales.filter((p) => p.status !== "ok").length;
    if (!ES_LOCAL && bloqueados >= UMBRAL_PORTALES_BLOQUEADOS_PARA_RESPALDO) {
      resultado = await completarConTunel(resultado, filtros);
    }

    renderPortales(resultado.portales);
    renderDelitosZona(resultado.delitos_zona);
    renderResultados(resultado.propiedades);
  } catch (err) {
    estadoPortales.innerHTML = `<span class="badge badge-error">Error: ${escapeHtml(err.message)}</span>`;
  }
});

function renderSkeletons(cantidad = 6) {
  resultadosEl.innerHTML = Array.from({ length: cantidad })
    .map(
      (_, i) => `
    <div class="skeleton-card" style="--stagger-delay: ${i * 60}ms">
      <div class="skeleton-thumb"></div>
      <div class="skeleton-body">
        <div class="skeleton-line w-40"></div>
        <div class="skeleton-line w-80"></div>
        <div class="skeleton-line w-60"></div>
      </div>
    </div>`
    )
    .join("");
}

function renderPortales(portales) {
  estadoPortales.innerHTML = portales
    .map((p, i) => {
      const label = `${escapeHtml(p.portal)}: ${escapeHtml(p.status)}${p.status === "ok" ? ` (${p.cantidad})` : ""}`;
      return `<span class="badge badge-${escapeHtml(p.status)}" style="--stagger-delay: ${i * 50}ms" title="${escapeHtml(p.detalle ?? "")}">${label}</span>`;
    })
    .join("");
}

const NIVEL_LABEL = { bajo: "Bajo", medio: "Medio", alto: "Alto" };

function renderDelitosZona(delitos) {
  if (!delitos) {
    delitosZonaEl.hidden = true;
    return;
  }
  delitosZonaEl.hidden = false;
  delitosZonaEl.className = `delitos-zona nivel-${delitos.nivel}`;
  const nivelTexto = delitos.es_agregado_provincial
    ? `<strong>toda la provincia</strong> -- no comparable 1 a 1 con una localidad puntual`
    : `nivel relativo <strong>${NIVEL_LABEL[delitos.nivel]}</strong>`;
  delitosZonaEl.innerHTML = `
    <span class="punto" aria-hidden="true"></span>
    <span>
      Delitos contra la propiedad en esta zona (2024): <strong>${delitos.hechos_2024.toLocaleString("es-AR")} hechos</strong>
      &middot; ${nivelTexto}
      <span title="Total anual sin ajustar por poblacion -- una zona grande o turistica va a mostrar mas hechos solo por tener mas gente, no necesariamente por ser menos segura por habitante. Fuente: SNIC, Ministerio de Seguridad de la Nacion.">(?)</span>
    </span>
  `;
}

function renderResultados(propiedades) {
  propiedadesActuales = propiedades;
  paginaActual = 1;
  renderDestacados(propiedades);
  actualizarVista();
}

function actualizarVista() {
  const enMapa = vistaActual === "mapa";
  resultadosEl.hidden = enMapa;
  if (enMapa) paginacionEl.hidden = true;
  mapaWrapEl.hidden = !enMapa;
  mapaNotaEl.hidden = !enMapa;

  if (enMapa) {
    // El contenedor recien se destapo (hidden=false) -- esperar a que el
    // layout se aplique de verdad antes de que Leaflet mida el tamano,
    // sino puede inicializar con 0x0 y quedar roto. setTimeout (no
    // requestAnimationFrame) porque rAF se suspende del todo en pestañas
    // en segundo plano y el mapa nunca llegaria a inicializarse ahi.
    setTimeout(() => renderMapa(propiedadesActuales), 0);
  } else {
    renderPaginaActual();
  }
}

toggleVistaEl.addEventListener("click", (ev) => {
  const boton = ev.target.closest(".toggle-vista-btn");
  if (!boton || boton.dataset.vista === vistaActual) return;
  vistaActual = boton.dataset.vista;
  toggleVistaEl.querySelectorAll(".toggle-vista-btn").forEach((b) => {
    b.classList.toggle("is-activo", b === boton);
  });
  actualizarVista();
});

document.querySelector(".toggle-capa").addEventListener("click", (ev) => {
  const boton = ev.target.closest(".toggle-capa-btn");
  if (!boton || !mapaLeaflet) return;
  document.querySelectorAll(".toggle-capa-btn").forEach((b) => b.classList.toggle("is-activo", b === boton));
  if (boton.dataset.capa === "satelite") {
    mapaLeaflet.removeLayer(capaCalles);
    capaSatelite.addTo(mapaLeaflet);
  } else {
    mapaLeaflet.removeLayer(capaSatelite);
    capaCalles.addTo(mapaLeaflet);
  }
});

async function cargarCapaDelitos() {
  try {
    const resp = await fetch("partidos-delitos.geojson");
    const geojson = await resp.json();
    // Color por ZONA (el partido entero), no por propiedad -- pintar
    // una propiedad puntual de rojo estigmatizaria ese aviso especifico,
    // que no es lo que dicen los datos (son delitos del partido entero,
    // no de esa direccion). Ver backend/app/delitos.py para las
    // limitaciones reales (cantidad total sin ajustar por poblacion).
    capaDelitos = L.geoJSON(geojson, {
      style: (feature) => {
        const info = PARTIDOS_NIVEL_DELITOS[feature.properties.partido];
        const color = info ? COLOR_NIVEL[info.nivel] : "#64748b";
        return { color, weight: 1, fillColor: color, fillOpacity: 0.22 };
      },
      onEachFeature: (feature, layer) => {
        const info = PARTIDOS_NIVEL_DELITOS[feature.properties.partido];
        if (!info) return;
        layer.bindTooltip(
          `${feature.properties.partido}: ${info.hechos.toLocaleString("es-AR")} delitos contra la propiedad (2024, SNIC) -- nivel ${NIVEL_LABEL[info.nivel]}`,
          { sticky: true }
        );
      },
    });
    if (capaDelitosVisible) capaDelitos.addTo(mapaLeaflet);
  } catch (err) {
    // Si el geojson no carga (red, etc.) el mapa sigue andando sin esta
    // capa -- no es critico para poder ver los avisos.
  }
}

document.getElementById("toggle-delitos").addEventListener("click", () => {
  capaDelitosVisible = !capaDelitosVisible;
  document.getElementById("toggle-delitos").classList.toggle("apagado", !capaDelitosVisible);
  if (!capaDelitos) return;
  if (capaDelitosVisible) capaDelitos.addTo(mapaLeaflet);
  else mapaLeaflet.removeLayer(capaDelitos);
});

function renderMapa(propiedades) {
  const conUbicacion = propiedades.filter((p) => typeof p.lat === "number" && typeof p.lon === "number");

  mapaNotaEl.textContent = `El mapa muestra ${conUbicacion.length} de ${propiedades.length} avisos -- solo ZonaProp y RE/MAX traen ubicacion exacta.`;

  if (!mapaLeaflet) {
    mapaLeaflet = L.map(mapaEl);

    // Calles: OpenStreetMap estandar (gratis, sin API key) con un filtro
    // CSS para que se vea oscuro y combine con el resto del sitio -- los
    // proveedores de tiles oscuros "gratis" (CARTO) ahora piden API key.
    capaCalles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
      className: "tiles-oscuros",
    });

    // Satelital: Esri World Imagery, gratis y sin API key -- el
    // equivalente real y disponible a "vista Google Earth".
    capaSatelite = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "&copy; Esri", maxZoom: 19 }
    );

    capaCalles.addTo(mapaLeaflet);
    marcadoresLayer = L.layerGroup().addTo(mapaLeaflet);
    cargarCapaDelitos();
  }

  marcadoresLayer.clearLayers();

  if (conUbicacion.length === 0) {
    mapaLeaflet.setView([-34.6037, -58.3816], 12);
    return;
  }

  conUbicacion.forEach((p) => {
    const color = p.buen_precio ? "#fbbf24" : "#5eead4";
    const marcador = L.circleMarker([p.lat, p.lon], {
      radius: 7,
      color,
      weight: 2,
      fillColor: color,
      fillOpacity: 0.6,
    });
    const precio = p.precio != null ? `${escapeHtml(p.moneda ?? "")} ${p.precio.toLocaleString("es-AR")}` : "Consultar";
    marcador.bindPopup(`
      <div class="popup-mapa">
        <span class="portal-tag">${escapeHtml(p.portal)}</span>
        <h4>${escapeHtml(p.titulo)}</h4>
        <p class="precio">${precio}</p>
        <a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">Ver aviso &rarr;</a>
      </div>
    `);
    marcadoresLayer.addLayer(marcador);
  });

  mapaLeaflet.fitBounds(conUbicacion.map((p) => [p.lat, p.lon]), { padding: [30, 30], maxZoom: 15 });
  setTimeout(() => mapaLeaflet.invalidateSize(), 50);
}

function renderPaginaActual() {
  const total = propiedadesActuales.length;

  if (total === 0) {
    resultadosEl.innerHTML = `<div class="sin-resultados">Sin resultados para estos filtros. Probá ampliarlos o revisá el estado de los portales arriba.</div>`;
    paginacionEl.hidden = true;
    paginacionEl.innerHTML = "";
    return;
  }

  const totalPaginas = Math.max(1, Math.ceil(total / RESULTADOS_POR_PAGINA));
  paginaActual = Math.min(Math.max(1, paginaActual), totalPaginas);

  const desde = (paginaActual - 1) * RESULTADOS_POR_PAGINA;
  const pagina = propiedadesActuales.slice(desde, desde + RESULTADOS_POR_PAGINA);

  renderTarjetas(pagina);
  renderPaginacion(total, totalPaginas);
  resultadosEl.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderPaginacion(total, totalPaginas) {
  if (totalPaginas <= 1) {
    paginacionEl.hidden = true;
    paginacionEl.innerHTML = "";
    return;
  }

  paginacionEl.hidden = false;
  paginacionEl.innerHTML = `
    <button type="button" class="pag-btn" id="pag-prev" ${paginaActual === 1 ? "disabled" : ""}>&larr; Anterior</button>
    <span class="pag-info">Página ${paginaActual} de ${totalPaginas} &middot; ${total} propiedades</span>
    <button type="button" class="pag-btn" id="pag-next" ${paginaActual === totalPaginas ? "disabled" : ""}>Siguiente &rarr;</button>
  `;

  document.getElementById("pag-prev").addEventListener("click", () => {
    paginaActual -= 1;
    renderPaginaActual();
  });
  document.getElementById("pag-next").addEventListener("click", () => {
    paginaActual += 1;
    renderPaginaActual();
  });
}

function pillsSuperficie(p) {
  // Cubierta + descubierta solo cuando el portal realmente expone las
  // dos por separado (hoy: ZonaProp). Si solo hay cubierta (RE/MAX) o
  // solo el total generico (Argenprop), se muestra nada mas eso.
  if (p.superficie_cubierta_m2 && p.superficie_descubierta_m2) {
    return [
      `<span>${p.superficie_cubierta_m2} m&sup2; cub.</span>`,
      `<span>${p.superficie_descubierta_m2} m&sup2; descub.</span>`,
    ];
  }
  if (p.superficie_cubierta_m2) {
    return [`<span>${p.superficie_cubierta_m2} m&sup2; cub.</span>`];
  }
  if (p.superficie_m2) {
    return [`<span>${p.superficie_m2} m&sup2;</span>`];
  }
  return [];
}

function tarjetaHTML(p, i) {
      const retraso = Math.min(i, 10) * 40;
      const features = [
        p.ambientes ? `<span>${p.ambientes} amb.</span>` : "",
        ...pillsSuperficie(p),
        p.antiguedad_anios !== null && p.antiguedad_anios !== undefined
          ? `<span>${p.antiguedad_anios === 0 ? "A estrenar" : p.antiguedad_anios + " años"}</span>`
          : "",
        p.cochera ? `<span>Cochera</span>` : "",
        p.patio ? `<span>Patio</span>` : "",
        p.terraza ? `<span>Terraza</span>` : "",
        p.jardin ? `<span>Jardin</span>` : "",
        p.apto_credito ? `<span>Apto credito</span>` : "",
        p.acepta_mascotas ? `<span>Acepta mascotas</span>` : "",
        p.dias_desde_publicacion !== null && p.dias_desde_publicacion !== undefined
          ? `<span>${p.dias_desde_publicacion === 0 ? "Publicado hoy" : "Hace " + p.dias_desde_publicacion + " dias"}</span>`
          : "",
        p.distancia_general_paz_km !== null && p.distancia_general_paz_km !== undefined
          ? `<span title="${p.distancia_general_paz_aprox ? "Aproximado por barrio, no por aviso puntual" : "Distancia real del aviso"}">${p.distancia_general_paz_aprox ? "~" : ""}${p.distancia_general_paz_km.toFixed(1)} km de Gral. Paz</span>`
          : "",
      ]
        .filter(Boolean)
        .join("");

      const destacados = [
        p.buen_precio ? `<span class="destacado-buen-precio" title="Precio/m² notablemente por debajo de la mediana de esta busqueda">Buen precio</span>` : "",
        p.precio_bajado
          ? `<span class="destacado-bajo-precio" title="${p.precio_anterior ? "Antes " + p.moneda + " " + p.precio_anterior.toLocaleString("es-AR") : "Bajo de precio"}">${p.dias_desde_baja_precio === 0 ? "Bajo de precio hoy" : "Bajo de precio hace " + p.dias_desde_baja_precio + " dias"}</span>`
          : "",
      ]
        .filter(Boolean)
        .join("");

      const thumb = p.imagen_url
        ? `<img class="thumb" src="${escapeHtml(p.imagen_url)}" alt="" loading="lazy" onerror="this.parentElement.classList.add('thumb-fallback')" />`
        : "";

      return `
    <a class="card-propiedad" style="--stagger-delay: ${retraso}ms" href="${escapeHtml(p.url)}" target="_blank" rel="noopener">
      <div class="thumb-box${p.imagen_url ? "" : " thumb-fallback"}">
        ${thumb}
      </div>
      <div class="card-body">
        <span class="portal-tag">${escapeHtml(p.portal)}</span>
        <h3>${escapeHtml(p.titulo)}</h3>
        <p class="precio">${escapeHtml(p.moneda ?? "")} ${p.precio?.toLocaleString("es-AR") ?? "Consultar"}</p>
        <p class="direccion">${escapeHtml(p.direccion ?? p.barrio ?? "")}</p>
        ${destacados ? `<div class="destacados">${destacados}</div>` : ""}
        <div class="features">${features}</div>
      </div>
    </a>`;
}

function renderTarjetas(propiedades) {
  resultadosEl.innerHTML = propiedades.map(tarjetaHTML).join("");
}

function renderDestacados(propiedades) {
  const top3 = propiedades
    .filter((p) => p.buen_precio && p.precio_m2 != null)
    .sort((a, b) => a.precio_m2 - b.precio_m2)
    .slice(0, 3);

  destacadosWrapEl.hidden = top3.length === 0;
  destacadosEl.innerHTML = top3.map(tarjetaHTML).join("");
  destacadosEl.scrollTo({ left: 0 });
}

document.querySelector(".destacados-flecha-izq").addEventListener("click", () => {
  destacadosEl.scrollBy({ left: -300, behavior: "smooth" });
});
document.querySelector(".destacados-flecha-der").addEventListener("click", () => {
  destacadosEl.scrollBy({ left: 300, behavior: "smooth" });
});
