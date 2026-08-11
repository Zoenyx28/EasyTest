"""FastAPI application entry point for the Test Management Platform."""
from __future__ import annotations
import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Windows: must use ProactorEventLoop for subprocess support
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Ensure backend package is on path for imports
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import jwt

from app.api import discovery, report, ws
from app.api.common import ok, fail
from app.api import tasks as tasks_api
from app.api import executions as executions_api
from app.api import execution_cases as execution_cases_api
from app.api import projects as projects_api
from app.api import branches as branches_api
from app.api import auth as auth_api
from app.api import users as users_api
from app.api import project_members as project_members_api
from app.api import project_notes as project_notes_api
from app.api import ws
from app.api.defects import router as defects_router
from app.api.requirements import router as requirements_router
from app.api.requirement_layers import router as requirement_layers_router
from app.api.settings import router as settings_router
from app.config import JWT_SECRET, PROJECTS_DATA_DIR
from app.db import crud
from app.db.database import init_db

# ── Logging setup ──
# Log every interface call (URL / request / response / error stack) at INFO+.
_logger = logging.getLogger('easytest')
_access_logger = logging.getLogger('easytest.access')


def _configure_logging() -> None:
    """Configure root logging once (no-op if uvicorn already configured it)."""
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    )


_configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    from app.services.executor import set_discovery_cache
    from app.db import crud
    from app.api.discovery import _build_discovery_response

    # Ensure venvs directory exists
    from app.config import PROJECTS_VENV_DIR
    PROJECTS_VENV_DIR.mkdir(parents=True, exist_ok=True)
    try:
        items, _ = await crud.load_discovery_cache()
        if items:
            response = _build_discovery_response(items)
            set_discovery_cache(response)
    except Exception:
        _logger.exception('Failed to warm up discovery cache at startup')
    # Ensure all existing projects have at least a main branch
    try:
        projects = await crud.get_all_projects()
        for p in projects:
            await crud.ensure_main_branch(
                project_id=p['id'],
                source_path=p.get('server_path', ''),
                test_path=p.get('test_path', ''),
            )
    except Exception:
        _logger.exception('Failed to ensure main branches at startup')
    yield


app = FastAPI(
    title='Test Management Platform',
    description='Automated test management with real-time execution monitoring',
    version='1.0.0',
    lifespan=lifespan,
)

# ── Global exception handler ──
# Project convention: every API response — success or failure — uses HTTP 200
# and the unified envelope {code, msg, data}. The `code` mirrors HTTP-style
# semantics (200 ok / 401 permission / 404 not found / 50x server error),
# and `msg` carries a Chinese hint for the caller.
@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException | StarletteHTTPException):
    _logger.warning(
        'HTTP error %s: %s (url=%s)',
        exc.status_code, exc.detail, _request.url.path,
    )
    msg = exc.detail or str(exc)
    if not msg or msg == str(exc):
        msg = '请求失败'
    return JSONResponse(
        status_code=200,
        content={'code': exc.status_code, 'msg': msg, 'data': None},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, exc: Exception):
    # Record the full error stack before converting to the unified envelope.
    _logger.exception('Unhandled exception (url=%s)', _request.url.path)
    return JSONResponse(
        status_code=200,
        content={'code': 500, 'msg': '服务器内部错误', 'data': None},
    )


# ── Request logging middleware ──
# Log every interface call: method, URL, request body, response status/body,
# duration and (via the exception handlers above) the error stack.
@app.middleware('http')
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    request_body = None
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        try:
            raw = await request.body()
            if raw:
                request_body = raw.decode('utf-8', errors='replace')[:2048]
        except Exception:
            request_body = '<unreadable>'

    response = await call_next(request)

    # The middleware layer wraps responses as a stream, so consume the body
    # here (truncated for the log) and re-wrap it for the client.
    response_body = b''
    async for chunk in response.body_iterator:
        response_body += chunk

    response_text = None
    if response_body:
        response_text = response_body.decode('utf-8', errors='replace')[:2048]

    duration_ms = (time.perf_counter() - started) * 1000
    _access_logger.info(
        '%s %s -> %d (%.1fms) req=%s resp=%s',
        request.method,
        str(request.url.path) + (f'?{request.url.query}' if request.url.query else ''),
        response.status_code,
        duration_ms,
        request_body,
        response_text,
    )
    # Re-construct the response so the client still receives the original body.
    new_response = Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )
    return new_response

# ── JWT auth middleware ──
# Whitelist paths that don't require authentication
_AUTH_WHITELIST = {
    '/api/auth/register',
    '/api/auth/login',
    '/api/health',
}


@app.middleware('http')
async def jwt_auth_middleware(request: Request, call_next):
    path = request.url.path

    # Skip auth for whitelisted paths, static files, and GET attachment requests
    # (img/link tags in rendered HTML cannot carry an Authorization header)
    is_get_attachment = request.method == 'GET' and (
        path.startswith('/api/defects/attachments/temp/')
        or ('/attachments/' in path and path.endswith('/download'))
        or ('/images/' in path and path.startswith('/api/defects/'))
        or path.startswith('/api/requirements/sources/') and path.endswith('/download')
    )
    if path in _AUTH_WHITELIST or path.startswith('/api/static/') or is_get_attachment:
        return await call_next(request)

    # Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    token = ''
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    elif auth_header:
        token = auth_header

    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            user_id = payload.get('user_id')
            username = payload.get('username')
            if user_id:
                user_data = await crud.get_user_by_id(user_id)
                if user_data:
                    request.state.user = {
                        'id': user_data['id'],
                        'username': user_data['username'],
                        'nickname': user_data['nickname'],
                        'avatar_url': user_data.get('avatar_url', ''),
                    }
                else:
                    return JSONResponse(
                        status_code=200,
                        content={'code': 401, 'msg': '未登录或登录已过期', 'data': None},
                    )
            else:
                return JSONResponse(
                    status_code=200,
                    content={'code': 401, 'msg': '未登录或登录已过期', 'data': None},
                )
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=200,
                content={'code': 401, 'msg': '未登录或登录已过期', 'data': None},
            )
        except jwt.InvalidTokenError:
            return JSONResponse(
                status_code=200,
                content={'code': 401, 'msg': '未登录或登录已过期', 'data': None},
            )
    else:
        return JSONResponse(
            status_code=200,
            content={'code': 401, 'msg': '未登录或登录已过期', 'data': None},
        )

    response = await call_next(request)
    return response


# CORS - allow frontend origins from environment variable
_cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(',') if o.strip()],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Register routers
app.include_router(discovery.router)
app.include_router(tasks_api.router)
app.include_router(executions_api.router)
app.include_router(report.router)
app.include_router(projects_api.router)
app.include_router(execution_cases_api.router)
app.include_router(branches_api.router)
app.include_router(auth_api.router)
app.include_router(users_api.router)
app.include_router(project_notes_api.router)
app.include_router(project_members_api.router)
app.include_router(ws.router)
app.include_router(defects_router)
app.include_router(requirements_router)
app.include_router(requirement_layers_router)
app.include_router(settings_router)


@app.get('/api/health')
async def health():
    return ok({'status': 'ok', 'service': 'test-management-platform'})


# ── 头像静态文件服务 ──
_static_dir = PROJECTS_DATA_DIR / 'static'
_static_dir.mkdir(parents=True, exist_ok=True)
if _static_dir.is_dir():
    app.mount('/api/static', StaticFiles(directory=str(_static_dir)), name='static')
