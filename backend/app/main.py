from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.models import Filtros, SearchResponse
from app.orchestrator import SCRAPERS, buscar

app = FastAPI(title="NuevaCasa API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # uso personal/local; restringir si se comparte
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


@app.post("/api/search", response_model=SearchResponse)
def search(filtros: Filtros) -> SearchResponse:
    return buscar(filtros)
