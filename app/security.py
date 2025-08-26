import hmac, hashlib, time
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, Response
from .config import APP_API_KEY, UI_REMEMBER_DAYS, TZ, COOKIE_NAME

def check_api_key(req: Request):
    key = req.headers.get("x-api-key") or req.query_params.get("key")
    if key != APP_API_KEY:
        raise HTTPException(401, "invalid api key")

def sign_token(ts: str) -> str:
    sig = hmac.new(APP_API_KEY.encode(), ts.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{ts}.{sig}"

def verify_token(token: str) -> bool:
    try:
        ts, _sig = token.split(".")
        if sign_token(ts) != token:
            return False
        created = datetime.fromtimestamp(int(ts), tz=TZ)
        return (datetime.now(TZ) - created) < timedelta(days=UI_REMEMBER_DAYS)
    except:
        return False

def require_ui_auth(request: Request) -> bool:
    if (request.headers.get("x-api-key") or request.query_params.get("key")) == APP_API_KEY:
        return True
    tok = request.cookies.get(COOKIE_NAME)
    return bool(tok and verify_token(tok))

def issue_cookie(resp: Response):
    ts = str(int(time.time()))
    token = sign_token(ts)
    resp.set_cookie(
        key=COOKIE_NAME, value=token,
        max_age=UI_REMEMBER_DAYS * 24 * 3600,
        httponly=True, secure=True, samesite="lax", path="/"
    )

def ui_auth_state(request: Request, pass_: str | None, remember: bool) -> tuple[bool, bool]:
    from .config import UI_PASS  # avoid cycle
    if require_ui_auth(request): return True, False
    if pass_ is not None and pass_ == UI_PASS: return True, bool(remember)
    return False, False
