from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.models import Filtros, SearchResponse
from app.orchestrator import SCRAPERS, buscar

app = FastAPI(title="compraTuCasa API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototipo local; restringir en produccion
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def permitir_red_privada(request: Request, call_next):
    """Sin este header, Chrome bloquea con "Failed to fetch" (sin mas
    detalle) cualquier pedido desde una pagina publica -- ej. el
    frontend deployado en Netlify -- hacia localhost/127.0.0.1: es la
    politica "Private Network Access", que exige que el propio backend
    autorice explicitamente ese acceso desde una red publica."""
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.get("/api/portales")
def listar_portales():
    return {"portales": list(SCRAPERS.keys())}


@app.get("/api/debug/meli")
def debug_meli():
    """Endpoint temporal para diagnosticar por que MercadoLibre devuelve 0
    resultados desde Render (funciona bien en otros entornos) -- sacar
    despues de diagnosticar."""
    import requests

    resp = requests.get(
        "https://inmuebles.mercadolibre.com.ar/departamentos/venta/capital-federal/",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "es-AR,es;q=0.9",
        },
        timeout=15,
    )
    return {
        "status_code": resp.status_code,
        "final_url": resp.url,
        "size": len(resp.text),
        "tiene_ld_json": "application/ld+json" in resp.text,
        "tiene_realestate": "RealEstateListing" in resp.text,
        "primeros_500": resp.text[:500],
    }


@app.post("/api/search", response_model=SearchResponse)
def search(filtros: Filtros) -> SearchResponse:
    return buscar(filtros)
