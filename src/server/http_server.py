from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

logger = logging.getLogger(__name__)

FALLBACK_HTML: str = (
    "<!DOCTYPE html><html><head><title>Monocranium Core Bridge</title></head>"
    "<body style='font-family:sans-serif;background:#0d1117;color:#e6edf3;padding:40px;'>"
    "<h1>Monocranium Core Bridge</h1>"
    "<p>Status: Online. Dashboard build pending. Connect via WebSocket on port 8765.</p>"
    "</body></html>"
)


class HttpServer:
    """Static file HTTP server serving dashboard SPA bundle with index fallback."""

    def __init__(
        self,
        static_dir: Path | str,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        """Initialise HTTP static server.

        Args:
            static_dir: Directory containing built static assets.
            host: Interface address to bind.
            port: Port to listen on.
        """
        self._static_dir = Path(static_dir)
        self._host = host
        self._port = port
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def _handle_request(self, request: web.Request) -> web.StreamResponse:
        """Serve requested static file, falling back to index.html for SPA routing."""
        tail = request.match_info.get("tail", "")
        file_path = (self._static_dir / tail).resolve()
        base_dir = str(self._static_dir.resolve())

        if tail and file_path.is_file() and str(file_path).startswith(base_dir):
            return web.FileResponse(file_path)

        index_path = self._static_dir / "index.html"
        if index_path.is_file():
            return web.FileResponse(index_path)

        return web.Response(text=FALLBACK_HTML, content_type="text/html")

    async def start(self) -> None:
        """Initialize application routes and start HTTP web server."""
        app = web.Application()
        app.router.add_get("/{tail:.*}", self._handle_request)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        logger.info("HTTP dashboard server listening on http://%s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Gracefully stop and clean up the HTTP web runner."""
        if self._runner is not None:
            await self._runner.cleanup()
            logger.info("HTTP dashboard server stopped")
