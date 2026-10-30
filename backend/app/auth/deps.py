from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import User
from app.auth.utils import SECRET_KEY, ALGORITHM
from jose import JWTError, jwt

security = HTTPBearer(auto_error=False)
optional_security = HTTPBearer(auto_error=False)


def _user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.email == email).first()


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Return the authenticated user, or None for anonymous requests."""
    if credentials is None:
        return None
    return _user_from_token(credentials.credentials, db)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_exception
    user = _user_from_token(credentials.credentials, db)
    if user is None:
        raise credentials_exception
    return user
