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
      "Otras ciudades": ["Mar del Plata"],
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

const form = document.getElementById("filtros-form");
const estadoPortales = document.getElementById("estado-portales");
const resultadosEl = document.getElementById("resultados");
const paginacionEl = document.getElementById("paginacion");
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
    const resultado = await resp.json();
    renderPortales(resultado.portales);
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

function renderResultados(propiedades) {
  propiedadesActuales = propiedades;
  paginaActual = 1;
  renderPaginaActual();
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

function renderTarjetas(propiedades) {
  resultadosEl.innerHTML = propiedades
    .map((p, i) => {
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
    })
    .join("");
}
