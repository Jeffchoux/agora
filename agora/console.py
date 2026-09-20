from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse

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
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                "Referrer-Policy": "no-referrer",
            },
        )

    @app.get("/ui.css")
    def css():
        return FileResponse(STATIC / "ui.css")

    @app.get("/ui.js")
    def js():
        return FileResponse(STATIC / "ui.js", media_type="application/javascript")

    @app.get("/v1/console")
    def overview():
        return {
            "missions": missions.list(),
            "agents": [
                {
                    "id": k,
                    "label": v["label"],
                    "type": "Local" if v["provider"] == "ollama" else "Abonnement",
                }
                for k, v in PROFILES.items()
            ],
            "api_budget_usd": 0,
        }

    @app.get("/v1/console/{mid}")
    def detail(mid: str):
        try:
            return missions.detail(mid)
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
