"""Loopback-only synthetic integration harness, never a replacement Campus runtime."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/api/src'))
sys.path.insert(0, str(ROOT / 'services/worker/src'))

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse, Response

from campus247.application.identity.session_service import SessionService
from campus247.bootstrap.learning import load_local_learning
from campus247.presentation.identity import IdentityMiddleware, get_current_identity
from campus247.presentation.learning import create_learning_router


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


def create_test_app(config: Path, frontend_port: int):
    service, adapter = load_local_learning(config, workspace=ROOT, tenant_id='huce-local-public')

    @asynccontextmanager
    async def lifespan(app):
        async def worker():
            while True:
                await service.tick()
                await asyncio.sleep(1)
        task = asyncio.create_task(worker())
        ocr_task = asyncio.create_task(service.serve_accessible_text()) if service.accessible_text_pipeline else None
        try:
            yield
        finally:
            if ocr_task is not None:
                ocr_task.cancel()
                await asyncio.gather(ocr_task, return_exceptions=True)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
    sessions = SessionService()
    app.add_middleware(IdentityMiddleware, adapter=adapter, session_service=sessions)
    app.include_router(create_learning_router(service))

    @app.get('/health/learning-test')
    def health():
        return {'synthetic_only': True, 'campus_main_runtime': False, 'learning': True}

    @app.post('/v1/knowledge/platform/session')
    async def login(body: Login, request: Request):
        if request.headers.get('origin', str(request.base_url).rstrip('/')).rstrip('/') != str(request.base_url).rstrip('/'):
            raise HTTPException(403)
        try:
            token = adapter.authenticate(body.username, body.password)
            actor = adapter.resolve_token(token)
        except ValueError:
            raise HTTPException(401, 'Tài khoản không hợp lệ.') from None
        response = JSONResponse({'user_id': actor.subject_id, 'roles': [role.value for role in actor.roles], 'synthetic_only': True}, headers={'Cache-Control': 'no-store'})
        response.set_cookie('auth_token', token, httponly=True, samesite='strict', max_age=3600)
        return response

    @app.get('/v1/users/me')
    async def me(request: Request):
        actor = get_current_identity(request)
        return JSONResponse({'user_id': actor.subject_id, 'display_name': actor.display_name, 'roles': [role.value for role in actor.roles], 'is_synthetic': True}, headers={'Cache-Control': 'no-store'})

    @app.post('/v1/auth/logout')
    async def logout(request: Request):
        get_current_identity(request)
        sessions.revoke_session(request.cookies.get('auth_token', ''))
        response = JSONResponse({'status': 'logged_out'})
        response.delete_cookie('auth_token')
        return response

    @app.get('/{page_path:path}')
    async def frontend(page_path: str, request: Request):
        if ('..' in page_path or '\\' in page_path or not (page_path in {'learning', 'login'} or page_path.startswith(('learning/', '_next/', 'images/', 'fonts/')))):
            raise HTTPException(404)
        import httpx
        async with httpx.AsyncClient(trust_env=False, timeout=60) as client:
            response = await client.get(f'http://127.0.0.1:{frontend_port}/{page_path}', params=request.query_params)
        return Response(response.content, status_code=response.status_code, media_type=response.headers.get('content-type'))

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8025)
    parser.add_argument('--frontend-port', type=int, default=3025)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_test_app(args.config, args.frontend_port), host='127.0.0.1', port=args.port, access_log=False)
