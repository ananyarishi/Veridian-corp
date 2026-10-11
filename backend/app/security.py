from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .config import settings

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(subject: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expires}, settings.jwt_secret_key, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate":"Bearer"})
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise error
    except JWTError:
        raise error
    from .database import get_db
    db = get_db()
    user = await db.users.find_one({"username": username}, {"_id": 0, "password_hash": 0})
    if not user or not user.get("is_active", True):
        raise error
    return user
