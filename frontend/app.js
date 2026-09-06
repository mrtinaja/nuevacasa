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
  "Catamarca": {
    todas: "catamarca",
    todasLabel: "Toda la provincia",
    zonas: ["Catamarca Capital"],
  },
  "Formosa": {
    todas: "formosa",
    todasLabel: "Toda la provincia",
    zonas: ["Formosa Capital", "Clorinda"],
  },
  "La Pampa": {
    todas: "la-pampa",
    todasLabel: "Toda la provincia",
    zonas: ["Santa Rosa", "General Pico"],
  },
  "La Rioja": {
    todas: "la-rioja",
    todasLabel: "Toda la provincia",
    zonas: ["La Rioja Capital", "Chilecito"],
  },
  "San Luis": {
    todas: "san-luis",
    todasLabel: "Toda la provincia",
    zonas: ["San Luis Capital", "Villa Mercedes"],
  },
  "Santa Cruz": {
    todas: "santa-cruz",
    todasLabel: "Toda la provincia",
    zonas: ["Rio Gallegos", "Caleta Olivia"],
  },
  "Tierra del Fuego": {
    todas: "tierra-del-fuego",
    todasLabel: "Toda la provincia",
    zonas: ["Ushuaia", "Rio Grande"],
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

// El nivel bajo/medio/alto de cada partido/comuna viene HORNEADO en el
// geojson mismo (properties.nivel, properties.hechos) -- no como una
// tabla aparte en este archivo. Eso evita el bug que tuvimos una vez
// (esta tabla quedo con cortes viejos, desincronizada de
// backend/app/delitos.py, y coloreo mal 3 partidos). Los geojson se
// generan con un script one-off que usa los mismos cortes
// _CORTE_BAJO/_CORTE_MEDIO que ese archivo -- ver README para el
// detalle de generacion (fuente ARBA para partidos, data.buenosaires
// para comunas de CABA).
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

// Reemplaza un <select> nativo por un trigger + listbox propios --
// el resaltado de la lista abierta de un <select> es dibujado por el
// sistema operativo (en Windows/Chrome ignora accent-color), no hay
// forma de pintarlo turquesa via CSS. El <select> original se queda en
// el DOM (oculto, invisible y sin pointer-events) para no tocar nada
// del resto del codigo: sigue viajando en el FormData del form, sigue
// recibiendo `.value =`, `.innerHTML =` y `.addEventListener("change")`
// como si el reemplazo no existiera.
function crearSelectPersonalizado(select) {
  const wrapper = document.createElement("div");
  wrapper.className = "select-custom";
  select.parentNode.insertBefore(wrapper, select);
  wrapper.appendChild(select);
  select.tabIndex = -1;

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "select-trigger";
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  wrapper.appendChild(trigger);

  const listbox = document.createElement("ul");
  listbox.className = "select-listbox";
  listbox.setAttribute("role", "listbox");
  listbox.hidden = true;
  wrapper.appendChild(listbox);

  let opciones = [];
  let indiceResaltado = -1;

  function actualizarTrigger() {
    const opt = select.options[select.selectedIndex];
    trigger.textContent = opt ? opt.textContent : "";
  }

  function agregarOpcion(opt) {
    // El indice se captura ACA, antes del push -- si se lee
    // opciones.length recien adentro del listener de click, para ese
    // entonces ya termino de construirse toda la lista y siempre da el
    // indice del ULTIMO elemento (mismo indice para todas las
    // opciones, ninguna selecciona lo que corresponde).
    const indice = opciones.length;
    const li = document.createElement("li");
    li.className = "select-option";
    li.textContent = opt.textContent;
    li.setAttribute("role", "option");
    if (opt.value === select.value) li.classList.add("seleccionada");
    li.addEventListener("click", () => seleccionar(indice));
    listbox.appendChild(li);
    opciones.push(opt);
  }

  function construirListbox() {
    listbox.innerHTML = "";
    opciones = [];
    for (const nodo of select.children) {
      if (nodo.tagName === "OPTGROUP") {
        const etiqueta = document.createElement("li");
        etiqueta.className = "select-optgroup-label";
        etiqueta.textContent = nodo.label;
        listbox.appendChild(etiqueta);
        for (const opt of nodo.children) agregarOpcion(opt);
      } else if (nodo.tagName === "OPTION") {
        agregarOpcion(nodo);
      }
    }
  }

  function resaltar(indice) {
    indiceResaltado = indice;
    listbox.querySelectorAll(".select-option").forEach((li, i) => li.classList.toggle("resaltada", i === indice));
    const li = listbox.querySelectorAll(".select-option")[indice];
    if (li) li.scrollIntoView({ block: "nearest" });
  }

  function seleccionar(indice) {
    const opt = opciones[indice];
    if (!opt) return;
    if (select.value !== opt.value) {
      select.value = opt.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    actualizarTrigger();
    cerrar();
  }

  function abrir() {
    construirListbox();
    listbox.hidden = false;
    wrapper.classList.add("abierto");
    trigger.setAttribute("aria-expanded", "true");
    resaltar(Math.max(opciones.indexOf(select.options[select.selectedIndex]), 0));
  }

  function cerrar() {
    listbox.hidden = true;
    wrapper.classList.remove("abierto");
    trigger.setAttribute("aria-expanded", "false");
    indiceResaltado = -1;
  }

  trigger.addEventListener("click", () => (listbox.hidden ? abrir() : cerrar()));

  // Clickear la <label for="..."> de un control enfoca el control real
  // (el <select> oculto, no el trigger) -- se reenvia el foco visible
  // al trigger para que se vea el estado activo donde corresponde.
  select.addEventListener("focus", () => trigger.focus());

  trigger.addEventListener("keydown", (ev) => {
    if (listbox.hidden) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(ev.key)) {
        ev.preventDefault();
        abrir();
      }
      return;
    }
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      resaltar(Math.min(indiceResaltado + 1, opciones.length - 1));
    } else if (ev.key === "ArrowUp") {
      ev.preventDefault();
      resaltar(Math.max(indiceResaltado - 1, 0));
    } else if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      if (indiceResaltado >= 0) seleccionar(indiceResaltado);
    } else if (ev.key === "Escape") {
      cerrar();
    } else if (ev.key.length === 1) {
      // Salto por letra (tipo "escribir para buscar" de un <select>
      // nativo) -- util en listas largas como Zona (barrios de CABA).
      const letra = ev.key.toLowerCase();
      const desde = (indiceResaltado + 1) % opciones.length;
      const orden = [...opciones.keys()].map((i) => (desde + i) % opciones.length);
      const encontrado = orden.find((i) => opciones[i].textContent.toLowerCase().startsWith(letra));
      if (encontrado !== undefined) resaltar(encontrado);
    }
  });

  document.addEventListener("click", (ev) => {
    if (!wrapper.contains(ev.target)) cerrar();
  });

  actualizarTrigger();
  select.addEventListener("change", actualizarTrigger);
  return { refrescar: actualizarTrigger };
}

document.querySelectorAll("select").forEach((select) => {
  select._controlSelect = crearSelectPersonalizado(select);
});

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
  provinciaSelect._controlSelect?.refrescar();
  poblarZonas(provinciaSelect.value);
}

function opcionZona(zona) {
  const slug = slugify(zona);
  return `<option value="${slug}">${escapeHtml(zona)}</option>`;
}

function poblarZonas(nombreProvincia) {
  const provincia = UBICACIONES[nombreProvincia];
  let html = "";

  if (provincia) {
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
      html = todas + optgroups;
    } else {
      html = todas + provincia.zonas.map(opcionZona).join("");
    }
  }

  ubicacionSelect.innerHTML = html;
  ubicacionSelect._controlSelect?.refrescar();
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

// Precio/expensas usan "." como separador de miles (145.000 = ciento
// cuarenta y cinco mil, uso de Argentina) -- por eso son type="text" y
// no type="number" (un <input type="number"> interpreta el punto como
// separador DECIMAL, no de miles: "145.000" ahi se leeria como 145).
function precioOrNull(valorFormateado) {
  const soloDigitos = valorFormateado.replace(/\./g, "");
  return soloDigitos === "" ? null : Number(soloDigitos);
}

function formatearMiles(valorCrudo) {
  const soloDigitos = valorCrudo.replace(/\D/g, "");
  return soloDigitos === "" ? "" : Number(soloDigitos).toLocaleString("es-AR");
}

document.querySelectorAll(".input-precio").forEach((input) => {
  input.addEventListener("input", () => {
    const cursorAlFinal = input.selectionStart === input.value.length;
    input.value = formatearMiles(input.value);
    if (cursorAlFinal) input.setSelectionRange(input.value.length, input.value.length);
  });
});

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
    precio_min: precioOrNull(formData.get("precio_min")),
    precio_max: precioOrNull(formData.get("precio_max")),
    moneda: stringOrNull(formData.get("moneda")),
    ambientes_min: numeroOrNull(formData.get("ambientes_min")),
    ambientes_max: numeroOrNull(formData.get("ambientes_max")),
    dormitorios_min: numeroOrNull(formData.get("dormitorios_min")),
    dormitorios_max: numeroOrNull(formData.get("dormitorios_max")),
    superficie_min: numeroOrNull(formData.get("superficie_min")),
    superficie_max: numeroOrNull(formData.get("superficie_max")),
    antiguedad_max: numeroOrNull(formData.get("antiguedad_max")),
    expensas_max: precioOrNull(formData.get("expensas_max")),
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

const NIVEL_LABEL = { bajo: "Baja", medio: "Media", alto: "Alta" };

// Paneo general, sin numeros: a alguien buscando para comprar/alquilar le
// sirve mas un pantallazo rapido (bajo/medio/alto) que la cantidad cruda
// de hechos -- el detalle metodologico completo queda en el tooltip, no
// en pantalla.
const NIVEL_TOOLTIP = {
  bajo: "Incidencia baja de delitos contra la propiedad en esta zona respecto al resto del pais. Fuente: SNIC, Ministerio de Seguridad de la Nacion (2024). No es un veredicto de seguridad: no ajusta por poblacion ni es una tendencia.",
  medio: "Incidencia media de delitos contra la propiedad en esta zona respecto al resto del pais. Fuente: SNIC, Ministerio de Seguridad de la Nacion (2024). No es un veredicto de seguridad: no ajusta por poblacion ni es una tendencia.",
  alto: "Incidencia alta de delitos contra la propiedad en esta zona respecto al resto del pais. Fuente: SNIC, Ministerio de Seguridad de la Nacion (2024). No es un veredicto de seguridad: no ajusta por poblacion ni es una tendencia.",
};
const TOOLTIP_AGREGADO_PROVINCIAL =
  "Dato de toda la provincia, no de esta localidad puntual -- a escala provincial no es comparable con una ciudad. Fuente: SNIC, Ministerio de Seguridad de la Nacion (2024).";

function renderDelitosZona(delitos) {
  if (!delitos) {
    delitosZonaEl.hidden = true;
    return;
  }
  delitosZonaEl.hidden = false;
  delitosZonaEl.className = `delitos-zona nivel-${delitos.nivel}`;
  const tooltip = delitos.es_agregado_provincial ? TOOLTIP_AGREGADO_PROVINCIAL : NIVEL_TOOLTIP[delitos.nivel];
  const texto = delitos.es_agregado_provincial
    ? "Incidencia de inseguridad (toda la provincia)"
    : `Incidencia de inseguridad: <strong>${NIVEL_LABEL[delitos.nivel]}</strong>`;
  delitosZonaEl.title = tooltip;
  delitosZonaEl.innerHTML = `
    <span class="punto" aria-hidden="true"></span>
    <span>${texto}</span>
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

// Estilo y tooltip identicos para cualquier capa de zonas (partidos o
// comunas): el nivel ya viene calculado en el geojson (properties.nivel),
// asi que esta funcion no necesita saber que tipo de zona es.
function estiloZonaDelito(feature) {
  const color = COLOR_NIVEL[feature.properties.nivel] || "#64748b";
  return { color, weight: 1, fillColor: color, fillOpacity: 0.22 };
}

function tooltipZonaDelito(nombreZona) {
  return (feature, layer) => {
    if (!feature.properties.nivel) return;
    layer.bindTooltip(
      `${nombreZona(feature)}: incidencia de inseguridad <strong>${NIVEL_LABEL[feature.properties.nivel]}</strong>`,
      { sticky: true }
    );
  };
}

// Carga una capa de zonas desde un geojson que ya trae el nivel
// horneado en cada feature (properties.nivel/hechos) -- no como una
// tabla aparte en este archivo. Eso evita el bug que tuvimos una vez
// (una tabla separada quedo con cortes viejos, desincronizada de
// backend/app/delitos.py, y coloreo mal 3 partidos). Los geojson se
// generan con un script one-off que usa los mismos cortes
// _CORTE_BAJO/_CORTE_MEDIO que ese archivo -- ver README para el
// detalle de generacion (fuente ARBA para partidos, data.buenosaires
// para comunas de CABA). Cada capa se carga con su propio try/catch:
// si un archivo no esta (ej. recien agregado y todavia no deployado a
// Netlify), la otra capa igual se muestra en vez de perderse las dos.
async function cargarCapaZona(archivo, nombreZona) {
  try {
    const resp = await fetch(archivo);
    const geojson = await resp.json();
    return L.geoJSON(geojson, { style: estiloZonaDelito, onEachFeature: tooltipZonaDelito(nombreZona) });
  } catch (err) {
    return null;
  }
}

async function cargarCapaDelitos() {
  // Color por ZONA (el partido/comuna/departamento entero), no por
  // propiedad -- pintar una propiedad puntual de rojo estigmatizaria ese
  // aviso especifico, que no es lo que dicen los datos (son delitos de
  // la zona entera, no de esa direccion). Ver backend/app/delitos.py
  // para las limitaciones reales (cantidad total sin ajustar por
  // poblacion).
  //
  // Tres fuentes de limites geograficos porque cada nivel administrativo
  // se llama distinto: CABA por Comuna (15, Ley 1777), Buenos Aires por
  // partido, el resto del pais por departamento (capa nacional del IGN)
  // -- se cargan como capas separadas pero se agrupan en un unico
  // capaDelitos para que el toggle "Delitos por partido" las
  // prenda/apague juntas.
  const [capaPartidos, capaComunas, capaDepartamentos] = await Promise.all([
    cargarCapaZona("partidos-delitos.geojson", (f) => f.properties.partido),
    cargarCapaZona("comunas-delitos.geojson", (f) => `Comuna ${f.properties.comuna} (CABA)`),
    cargarCapaZona("departamentos-delitos.geojson", (f) => `${f.properties.departamento} (${f.properties.provincia})`),
  ]);

  const capas = [capaPartidos, capaComunas, capaDepartamentos].filter(Boolean);
  if (capas.length === 0) return;

  capaDelitos = L.layerGroup(capas);
  if (capaDelitosVisible) capaDelitos.addTo(mapaLeaflet);
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
    // Paleta a proposito distinta de COLOR_NIVEL (verde/amarillo/rojo
    // de la capa de delitos) -- "buen precio" usaba el mismo amarillo
    // que "nivel medio" de delitos (#fbbf24, el mismo hex), confundia
    // dos leyendas distintas en el mismo mapa. Precio y delito son
    // datos independientes, no deberian compartir ningun color.
    const color = p.buen_precio ? "#2dd4bf" : "#94a3b8";
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
