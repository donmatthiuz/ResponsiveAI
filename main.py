import asyncio
import re
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Text Moderation API",
    description="API de moderación de texto con veredicto allowed/bloqued",
    version="1.0.0",
)

REQUEST_TIMEOUT_SECONDS = 5.0

# --- Lista de palabras/patrones de ejemplo para bloquear ---
# Reemplaza esto por tu modelo/servicio real de moderación (ML, API externa, etc.)
BLOCKED_PATTERNS = [
    r"\bpalabra_prohibida\b",
    r"\bejemplo_toxico\b",
]
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]

# Texto especial para forzar un error interno real (pruebas del manejador de 500)
FORCE_ERROR_TRIGGER = "__forzar_error500__"


# ---------- Modelos ----------

class ModerateRequest(BaseModel):
    text: str = Field(..., description="Texto a moderar")


class ModerateResponse(BaseModel):
    verdict: Literal["allowed", "bloqued"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., description="Explicación del veredicto")


# ---------- Lógica de moderación ----------

async def run_moderation(text: str) -> ModerateResponse:

    # Simula trabajo asíncrono (p.ej. llamada a un modelo/servicio externo)
    await asyncio.sleep(0)

    # Gatillo para probar el manejo de errores 500 (fallo interno real)
    if FORCE_ERROR_TRIGGER in text:
        raise RuntimeError("Fallo simulado en el servicio de moderación")

    matched_terms = [p.pattern for p in _COMPILED_PATTERNS if p.search(text)]

    if matched_terms:
        confidence = min(1.0, 0.7 + 0.1 * len(matched_terms))
        reason = f"Se detectaron patrones bloqueados: {', '.join(matched_terms)}"
        return ModerateResponse(
            verdict="bloqued", confidence=round(confidence, 2), reason=reason
        )

    # Sin coincidencias -> permitido, con confianza fija de ejemplo
    return ModerateResponse(
        verdict="allowed",
        confidence=0.95,
        reason="No se detectaron patrones bloqueados en el texto",
    )


# ---------- Endpoint ----------

@app.post("/moderate", response_model=ModerateResponse)
async def moderate(payload: ModerateRequest):
    if not payload.text or not payload.text.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "text is required"}
        )

    try:
        result = await asyncio.wait_for(
            run_moderation(payload.text), timeout=REQUEST_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout de moderación (5s) excedido")

    return result


# ---------- Manejo de errores ----------
# IMPORTANTE: cada tipo de error conserva su propio status code.
# El manejador genérico de Exception SOLO debe atrapar fallos
# realmente inesperados del servidor (ej. el gatillo de texto),
# no errores esperados como 400, 422 o 504.

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    # Deja pasar HTTPException (400, 404, 504, etc.) con su status code original
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    # Errores de validación de payload (ej. falta el campo 'text') -> 422, no 500
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Solo llega aquí un error verdaderamente no manejado -> 500
    return JSONResponse(
        status_code=500,
        content={"error": f"Error interno: {str(exc)}"},
    )

@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=500,
        content={
            "error":  f"{exc.errors()}"
        },
    )

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Servidor de moderación de texto")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="IP en la que escucha el servidor (default: 0.0.0.0, todas las interfaces)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Puerto en el que escucha el servidor (default: 8000)",
    )
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)