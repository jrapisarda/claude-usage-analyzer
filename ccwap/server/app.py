"""
FastAPI application factory for CCWAP web dashboard.

Creates the app with all routes, lifespan management, and static file serving.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ccwap.config.loader import load_config, get_database_path
from ccwap.models.schema import ensure_database, get_connection
from ccwap.server.websocket import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection lifecycle."""
    config = app.state.config if hasattr(app.state, "config") else load_config()
    app.state.config = config

    db_path = get_database_path(config)

    # Ensure schema is up to date using sync connection
    sync_conn = get_connection(db_path)
    ensure_database(sync_conn)
    sync_conn.close()

    # Open async connection
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row

    # Match PRAGMAs from ccwap/models/schema.py
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.execute("PRAGMA cache_size=-64000")
    await db.execute("PRAGMA temp_store=MEMORY")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA mmap_size=268435456")

    app.state.db = db

    # Start file watcher background task
    manager = ConnectionManager()
    app.state.ws_manager = manager
    stop_event = asyncio.Event()
    app.state.ws_stop_event = stop_event

    watcher_task = asyncio.create_task(_run_watcher_safe(manager, config, stop_event))
    app.state.watcher_task = watcher_task

    cost_task = asyncio.create_task(_run_cost_broadcaster_safe(manager, config, stop_event))
    app.state.cost_task = cost_task

    yield

    # Shutdown
    stop_event.set()
    watcher_task.cancel()
    cost_task.cancel()
    try:
        await watcher_task
    except asyncio.CancelledError:
        pass
    try:
        await cost_task
    except asyncio.CancelledError:
        pass
    await db.close()


async def _run_watcher_safe(manager, config, stop_event):
    """Wrapper that imports and runs file watcher, handling import errors gracefully."""
    try:
        from ccwap.server.file_watcher import run_file_watcher
        await run_file_watcher(manager, config=config, poll_interval=5, stop_event=stop_event)
    except Exception:
        pass  # Don't crash if watcher fails (e.g., missing files dir)


async def _run_cost_broadcaster_safe(manager, config, stop_event):
    """Wrapper that imports and runs daily cost broadcaster, handling errors gracefully."""
    try:
        from ccwap.server.file_watcher import run_daily_cost_broadcaster
        await run_daily_cost_broadcaster(manager, config=config, interval=30, stop_event=stop_event)
    except Exception:
        pass  # Don't crash if cost broadcaster fails


def create_app(config: dict = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="CCWAP Dashboard API",
        description="Claude Code Workflow Analytics Platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    if config:
        app.state.config = config

    # Global exception handler
    import logging
    logger = logging.getLogger("ccwap.server")

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)},
        )

    # WebSocket endpoint — BEFORE API routers, BEFORE static mount
    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket):
        manager = websocket.app.state.ws_manager
        await manager.connect(websocket)
        try:
            while True:
                # Keep connection alive, handle pings
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text('{"type":"pong"}')
        except WebSocketDisconnect:
            await manager.disconnect(websocket)
        except Exception:
            await manager.disconnect(websocket)

    # Include all API routers BEFORE mounting static files
    from ccwap.server.routes.health import router as health_router
    from ccwap.server.routes.dashboard import router as dashboard_router
    from ccwap.server.routes.projects import router as projects_router
    from ccwap.server.routes.sessions import router as sessions_router
    from ccwap.server.routes.cost import router as cost_router
    from ccwap.server.routes.productivity import router as productivity_router
    from ccwap.server.routes.analytics import router as analytics_router
    from ccwap.server.routes.experiments import router as experiments_router
    from ccwap.server.routes.settings import router as settings_router
    from ccwap.server.routes.search import router as search_router
    from ccwap.server.routes.heatmap import router as heatmap_router
    from ccwap.server.routes.models_route import router as models_router
    from ccwap.server.routes.workflows import router as workflows_router
    from ccwap.server.routes.explorer import router as explorer_router

    app.include_router(health_router)
    app.include_router(dashboard_router)
    app.include_router(projects_router)
    app.include_router(sessions_router)
    app.include_router(cost_router)
    app.include_router(productivity_router)
    app.include_router(analytics_router)
    app.include_router(experiments_router)
    app.include_router(settings_router)
    app.include_router(search_router)
    app.include_router(heatmap_router)
    app.include_router(models_router)
    app.include_router(workflows_router)
    app.include_router(explorer_router)

    # Serve static assets and SPA fallback
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        # Mount /assets for hashed JS/CSS bundles
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # SPA catch-all: serve index.html for any non-API, non-asset path
        index_html = static_dir / "index.html"

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            # Serve actual static files (e.g. vite.svg) if they exist
            file_path = static_dir / full_path
            if full_path and file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(index_html)

    return app
