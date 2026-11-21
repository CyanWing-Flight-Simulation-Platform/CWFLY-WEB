"""认证 / 权限 / CSRF / 上传安全冒烟测试。"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from app.deps import AuthFailure, CurrentUser, get_verified_user, require_permission
from app.db.session import get_db
from app.middleware.csrf import CSRFMiddleware
from app.routers import auth
from app.services.webauthn_service import b64url_decode, b64url_encode
from app.services.meetings_uploads import UnsupportedFileType, validate_upload
from app.services.profile_uploads import _image_dimensions, background_path_for_url


def _auth_app() -> TestClient:
    app = FastAPI()
    app.include_router(auth.router, prefix="/api")

    async def fake_db():
        yield object()

    app.dependency_overrides[get_db] = fake_db
    return TestClient(app)


def test_refresh_without_session_is_401() -> None:
    client = _auth_app()
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401


def _permission_app(rating: int, permissions: str) -> TestClient:
    app = FastAPI()

    @app.get("/admin-only", dependencies=[Depends(require_permission("admin"))])
    async def admin_only():
        return {"ok": True}

    async def fake_verified() -> CurrentUser:
        return CurrentUser(cid="9999", rating=rating, permissions=permissions)

    @app.exception_handler(AuthFailure)
    async def auth_failure_handler(_request, exc: AuthFailure):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"success": False, "message": exc.message},
            status_code=exc.status_code,
        )

    app.dependency_overrides[get_verified_user] = fake_verified
    return TestClient(app)


def test_permission_denied_on_backend() -> None:
    client = _permission_app(rating=1, permissions="")
    assert client.get("/admin-only").status_code == 403


def test_permission_allowed_for_admin_rating() -> None:
    client = _permission_app(rating=11, permissions="")
    assert client.get("/admin-only").status_code == 200


def test_csrf_rejects_cookie_write_without_matching_header() -> None:
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.post("/api/protected")
    async def protected():
        return {"ok": True}

    client = TestClient(app)
    client.cookies.set("cw_access", "session")
    client.cookies.set("cw_csrf", "csrf-token")

    assert client.post("/api/protected").status_code == 403
    response = client.post("/api/protected", headers={"X-CSRF-Token": "csrf-token"})
    assert response.status_code == 200


def test_webauthn_b64url_roundtrip() -> None:
    raw = b"\x00\x01passkey-test\xff"
    encoded = b64url_encode(raw)
    assert "=" not in encoded
    assert b64url_decode(encoded) == raw


def test_upload_magic_and_extension_validation() -> None:
    assert validate_upload("manual.pdf", b"%PDF-1.7 test") == ".pdf"
    with pytest.raises(UnsupportedFileType):
        validate_upload("evil.pdf", b"<html>not a pdf</html>")
    with pytest.raises(UnsupportedFileType):
        validate_upload("evil.exe", b"MZ")


def test_background_path_is_bound_to_current_cid() -> None:
    assert background_path_for_url("/uploads/backgrounds/bg_1234_1700000000000.jpg", "1234") is not None
    assert background_path_for_url("/uploads/backgrounds/bg_9999_1700000000000.jpg", "1234") is None
    assert background_path_for_url("/uploads/avatars/victim.jpg", "1234") is None
    assert background_path_for_url("/uploads/backgrounds/../avatars/victim.jpg", "1234") is None


def test_png_dimensions_are_parsed() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (320).to_bytes(4, "big") + (180).to_bytes(4, "big")
    assert _image_dimensions(png) == (320, 180)
