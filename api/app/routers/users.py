"""Usuários do bolão: CRUD. Criação aberta (cadastro de participante); edição e
exclusão exigem ser o próprio usuário ou um admin."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from api.app.auth import hash_password
from api.app.db import get_db
from api.app.models import Pool, PoolMember, Prediction, ScoringRule, User
from api.app.routers.auth import get_current_user, get_optional_user
from api.app.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "usuário não encontrado")
    return user


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    current: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Cria um usuário. `password` opcional (sem senha = participante sem login).
    `is_admin=True` só é aceito se quem chama for um admin autenticado."""
    uname = payload.username.strip()
    if not uname:
        raise HTTPException(400, "informe o nome de usuário")
    if db.scalar(select(User).where(User.username == uname)):
        raise HTTPException(400, "usuário já cadastrado")
    if payload.is_admin and not (current and current.is_admin):
        raise HTTPException(403, "só um admin pode criar outro admin")
    user = User(
        username=uname,
        name=(payload.name or uname),
        password_hash=hash_password(payload.password) if payload.password else None,
        is_admin=payload.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _can_manage(current: User, user_id: int) -> bool:
    return current.id == user_id or current.is_admin


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edita nome/e-mail. Só o próprio usuário ou um admin."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "usuário não encontrado")
    if not _can_manage(current, user_id):
        raise HTTPException(403, "sem permissão para editar este usuário")
    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = payload.email or None
    if payload.is_admin is not None:
        if not current.is_admin:
            raise HTTPException(403, "só um admin pode alterar o status de admin")
        user.is_admin = payload.is_admin
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exclui um usuário e seu histórico de palpites/participações.

    Bloqueia se o usuário for DONO de algum bolão (exclua/transfira antes). As
    regras de pontuação que ele criou viram globais (owner_id = NULL). Atenção:
    apagar um participante remove os palpites dele de TODOS os bolões — some do
    histórico e das estatísticas. Só o próprio usuário ou um admin.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "usuário não encontrado")
    if not _can_manage(current, user_id):
        raise HTTPException(403, "sem permissão para excluir este usuário")

    owns = db.scalar(select(Pool.id).where(Pool.owner_id == user_id))
    if owns is not None:
        raise HTTPException(400, "usuário é dono de bolões; exclua ou transfira antes")

    db.execute(delete(Prediction).where(Prediction.user_id == user_id))
    db.execute(delete(PoolMember).where(PoolMember.user_id == user_id))
    db.execute(update(ScoringRule).where(ScoringRule.owner_id == user_id).values(owner_id=None))
    db.delete(user)
    db.commit()
    return {"deleted": user_id}
