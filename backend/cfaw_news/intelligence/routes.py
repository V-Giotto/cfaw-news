"""Strict opt-in local API; domain transactions and computation remain in service/store."""

from datetime import datetime

from fastapi import APIRouter, Query, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from evals.intelligence_g3.budget_contracts import CoverageDiagnostics

from .boundary import BoundaryError, error_response
from .checkpoint import PersistenceError
from .persistence_contracts import (
    ArchiveView,
    BriefingView,
    BriefingWrite,
    CancelWrite,
    EventDetailView,
    InteractionView,
    InteractionWrite,
    MutationView,
    PersonaView,
    PersonaWrite,
    RunView,
    StatusView,
)


def install_routes(app, service):
    router = APIRouter(prefix="/api/intelligence", tags=["intelligence"], responses={
        code: {"model": BoundaryError} for code in (400, 403, 404, 409, 413, 415, 422, 429, 503)})

    @app.exception_handler(PersistenceError)
    async def persistence_error(request, error):
        return error_response(error.code, error.status, error.database_state)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        if request.url.path.startswith("/api/intelligence/"):
            codes = {getattr(e.get("ctx", {}).get("error"), "code", "G4_SCHEMA_INVALID") for e in error.errors()}
            return error_response(next(iter(codes)) if len(codes) == 1 else "G4_SCHEMA_INVALID", 422)
        return await request_validation_exception_handler(request, error)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        if request.url.path.startswith("/api/intelligence/"):
            return error_response("G4_NOT_FOUND" if error.status_code == 404 else "G4_HTTP_REJECTED", error.status_code)
        return await http_exception_handler(request, error)

    @router.get("/status", response_model=StatusView)
    def status():
        return service.status()

    write_headers = {"parameters": [{"name": "Origin", "in": "header", "required": True,
        "schema": {"type": "string", "enum": list(service.settings.intelligence_origins)},
        "description": "Explicit allowed local Origin; this is a browser write boundary, not authentication."}]}

    @router.post("/persona", response_model=MutationView, status_code=201, openapi_extra=write_headers)
    def save_persona(body: PersonaWrite):
        return service.persona_write(body)

    @router.get("/persona", response_model=PersonaView)
    def persona(as_of: datetime | None = None):
        return service.persona(as_of)

    @router.get("/persona/versions", response_model=list[PersonaView])
    def persona_versions(as_of: datetime | None = None, limit: int = Query(default=200, ge=1, le=500),
                         offset: int = Query(default=0, ge=0, le=20000)):
        return service.persona(as_of, all_versions=True, limit=limit, offset=offset)

    @router.post("/briefings", response_model=MutationView, status_code=202, openapi_extra=write_headers)
    def generate(body: BriefingWrite):
        return service.start_run(body)

    @router.get("/briefings/latest", response_model=BriefingView, responses={304: {"description": "Same immutable ETag"}})
    def latest(request: Request):
        result = service.briefing()
        if request.headers.get("if-none-match") == result.etag:
            return Response(status_code=304, headers={"ETag": result.etag, "Cache-Control": "no-cache"})
        return Response(result.model_dump_json(), media_type="application/json",
                        headers={"ETag": result.etag, "Cache-Control": "no-cache"})

    @router.get("/briefings/{identifier}", response_model=BriefingView)
    def briefing(identifier: str):
        result = service.briefing(identifier)
        return Response(result.model_dump_json(), media_type="application/json", headers={"ETag": result.etag})

    @router.get("/runs/{identifier}", response_model=RunView)
    def get_run(identifier: str):
        return service.get_run(identifier)

    @router.post("/runs/{identifier}/cancel", response_model=MutationView, openapi_extra=write_headers)
    def cancel(identifier: str, body: CancelWrite):
        return service.cancel(identifier, body)

    @router.get("/events/detail", response_model=EventDetailView)
    def detail(briefing_id: str = Query(min_length=1, max_length=512),
               event_snapshot_id: str = Query(min_length=1, max_length=512)):
        return service.detail(briefing_id, event_snapshot_id)

    @router.get("/archive", response_model=list[ArchiveView])
    def archive(briefing_id: str | None = Query(default=None, min_length=1, max_length=512)):
        return service.briefing(briefing_id).archive

    @router.get("/coverage", response_model=CoverageDiagnostics)
    def coverage(briefing_id: str | None = Query(default=None, min_length=1, max_length=512)):
        return service.briefing(briefing_id).coverage

    @router.post("/interactions", response_model=MutationView, status_code=201, openapi_extra=write_headers)
    def interaction(body: InteractionWrite):
        return service.interaction(body)

    @router.get("/interactions", response_model=list[InteractionView])
    def interactions(as_of: datetime | None = None, limit: int = Query(default=200, ge=1, le=500),
                     offset: int = Query(default=0, ge=0, le=20000)):
        return service.interactions(as_of, limit=limit, offset=offset)

    app.include_router(router)
