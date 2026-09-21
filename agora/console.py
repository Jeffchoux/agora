from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse

from agora.inspection import WIDTHS
from agora.missions import PROFILES, Missions
from agora.store import Denied

STATIC = Path(__file__).parent / "static"


def install(app, store):
    missions = Missions(store)

    @app.get("/")
    def index():
        return FileResponse(
            STATIC / "index.html",
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                "Referrer-Policy": "no-referrer",
            },
        )

    @app.get("/ui.css")
    def css():
        return FileResponse(STATIC / "ui.css", headers={"Cache-Control": "no-store"})

    @app.get("/capture.css")
    def capture_css():
        return FileResponse(STATIC / "capture.css", headers={"Cache-Control": "no-store"})

    @app.get("/ui.js")
    def js():
        return FileResponse(
            STATIC / "ui.js",
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/v1/console")
    def overview(request: Request):
        target = request.query_params.get("target")
        return {
            "missions": missions.list(target),
            "agents": [
                {
                    "id": k,
                    "label": v["label"],
                    "type": "Local" if v["provider"] == "ollama" else "Abonnement",
                }
                for k, v in PROFILES.items()
            ],
            "targets": missions.projects(),
            "api_budget_usd": 0,
        }

    @app.get("/v1/console/projects")
    def projects():
        return missions.projects()

    @app.post("/v1/console/projects")
    async def create_project(request: Request):
        try:
            d = await request.json()
            if not isinstance(d, dict):
                raise TypeError("Objet requis")
            return missions.create_project(
                d.get("label"), d.get("repository"), d.get("website"), d.get("notes", "")
            )
        except (ValueError, TypeError, Denied) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.get("/v1/console/{mid}")
    def detail(mid: str):
        try:
            return missions.detail(mid)
        except Denied as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)

    @app.get("/v1/console/{mid}/evidence/{width}")
    def screenshot(mid: str, width: int):
        try:
            if width not in WIDTHS:
                raise Denied("Capture introuvable")
            detail = missions.detail(mid)
            if not detail["evidence"] or not any(
                item.get("viewport") == width and item.get("screenshot") == f"{width}.png"
                for item in detail["evidence"].get("browser", [])
            ):
                raise Denied("Capture introuvable")
            path = Path(store.path).parent / "evidence" / mid / f"{width}.png"
            if not path.is_file():
                raise Denied("Capture introuvable")
            return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
        except Denied as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)

    @app.post("/v1/console")
    async def create(request: Request):
        try:
            d = await request.json()
            if not isinstance(d, dict):
                raise TypeError("Objet requis")
            mid = missions.create(
                **{
                    k: d.get(k)
                    for k in [
                        "title",
                        "brief",
                        "agents",
                        "max_calls",
                        "seconds",
                        "request_key",
                        "target",
                    ]
                }
            )
            return {"id": mid}
        except (ValueError, TypeError, Denied) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/v1/console/{mid}/{action}")
    def action(mid: str, action: str):
        try:
            missions.action(mid, action)
            return missions.detail(mid)
        except (ValueError, Denied) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
