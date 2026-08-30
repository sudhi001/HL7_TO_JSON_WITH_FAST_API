import logging
import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.models import ParseRequest
from app.api.v2 import router as v2_router
from app.render import legacy

logger = logging.getLogger("hl7")

BASE_DIR = Path(__file__).resolve().parent

# The legacy endpoint keeps working, unchanged, until this date. It is served by
# a frozen shim (app/render/legacy.py) that reproduces the old output including
# its defects, because that is the contract existing callers depend on.
LEGACY_SUNSET = date.today() + timedelta(days=400)

app = FastAPI(
    title="HL7 to JSON",
    version="2.0.0",
    description=(
        "Self-hosted HL7 v2 message parser. Message content is never stored, "
        "logged, or sent anywhere."
    ),
)
# Resolved from __file__, not the working directory, so the app starts from anywhere.
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_static_dir = BASE_DIR / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.include_router(v2_router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Baseline hardening headers.

    `no-store` matters most here: message content must not be cached by the
    browser or by any intermediary.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # No external origins at all: CSS and JS are self-hosted, and there is no
    # 'unsafe-inline' because nothing is inlined. A violation here means
    # something started reaching off-box, which this tool must never do.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the failure server-side; return a generic error to the client.

    The exception is not echoed to the client because it can contain fragments
    of the submitted message, which may be PHI. It *is* logged, with a
    correlation id the client also receives, so an operator can find the
    traceback without the user having to relay it. Swallowing it entirely --
    as this handler previously did -- makes a 500 impossible to diagnose.

    The request path is logged; the body never is.
    """
    error_id = uuid.uuid4().hex[:12]
    logger.exception(
        "Unhandled error %s handling %s %s", error_id, request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "Failed to process the request.",
            "errorId": error_id,
        },
    )


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post(
    "/convert/hl7/json",
    tags=["deprecated"],
    summary="Deprecated: use POST /api/v2/parse",
    description=(
        "Superseded by `/api/v2/parse`. This endpoint reproduces the original "
        "output shape, including known defects (repeated segments overwrite each "
        "other; `~` and `^` precedence is inverted), because changing it would "
        "break existing callers. It cannot represent a repeating segment "
        "correctly by construction."
    ),
    deprecated=True,
)
def convert_hl7_to_json(payload: ParseRequest, response: Response) -> dict:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = LEGACY_SUNSET.strftime("%a, %d %b %Y 00:00:00 GMT")
    response.headers["Link"] = '</api/v2/parse>; rel="successor-version"'

    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message is empty.")
    return legacy.render(payload.message)
