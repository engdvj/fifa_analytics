"""Autenticação: register, login, /me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.auth import create_access_token, hash_password, verify_password
from api.app.db import get_db
from api.app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
optional_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


class RegisterIn(BaseModel):
    username: str
    password: str
    name: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: int
    username: str
    name: str


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    uname = payload.username.strip()
    if not uname:
        raise HTTPException(400, "usuário inválido")
    if db.scalar(select(User).where(User.username == uname)):
        raise HTTPException(400, "usuário já cadastrado")
    user = User(
        username=uname,
        name=(payload.name or uname).strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id, user.username))


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not user.password_hash or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=create_access_token(user.id, user.username))


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dependency: retorna o usuário autenticado ou 401."""
    try:
        from api.app.auth import decode_token
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="usuário não encontrado")
    return user


def get_optional_user(
    token: str | None = Depends(optional_oauth2), db: Session = Depends(get_db)
) -> User | None:
    """Como get_current_user, mas devolve None (em vez de 401) quando não há token
    válido. Para endpoints abertos que dão tratamento extra a quem está logado."""
    if not token:
        return None
    try:
        from api.app.auth import decode_token
        payload = decode_token(token)
        return db.get(User, int(payload["sub"]))
    except (JWTError, KeyError, ValueError):
        return None


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency: exige usuário autenticado E admin. 403 caso contrário."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="acesso restrito a administradores",
        )
    return user


class MeOutAdmin(MeOut):
    is_admin: bool


@router.get("/me", response_model=MeOutAdmin)
def me(user: User = Depends(get_current_user)):
    return MeOutAdmin(id=user.id, username=user.username, name=user.name, is_admin=user.is_admin)


class UpdateMeIn(BaseModel):
    name: str | None = None
    password: str | None = None


@router.patch("/me", response_model=MeOutAdmin)
def update_me(
    payload: UpdateMeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualiza o próprio perfil: nome de exibição e/ou senha."""
    if payload.name is not None and payload.name.strip():
        user.name = payload.name.strip()
    if payload.password:
        if len(payload.password) < 4:
            raise HTTPException(400, "senha muito curta")
        user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return MeOutAdmin(id=user.id, username=user.username, name=user.name, is_admin=user.is_admin)
