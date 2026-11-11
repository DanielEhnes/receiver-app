"""HTTP Basic auth with a single user from settings."""
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import settings

security = HTTPBasic(realm="receiver-app")


def require_user(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    user_ok = secrets.compare_digest(
        credentials.username.encode(), settings.app_username.encode()
    )
    pass_ok = secrets.compare_digest(
        credentials.password.encode(), settings.app_password.encode()
    )
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="receiver-app"'},
        )
    return credentials.username
