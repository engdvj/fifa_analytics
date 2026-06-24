"""Bolões flexíveis: criação (com escopo, regra inline, aninhamento por fase),
listagem em árvore, detalhe, jogos do escopo e ranking (com agregação de grupo).
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from api.app.db import get_db
from api.app.models import Match, Pool, PoolMember, Prediction, ScoringRule, User
from api.app.routers.auth import get_current_user, require_admin
from api.app.scoring.engine import score_prediction
from api.app.scoring.recompute import match_in_scope, matches_in_scope, recompute_pool_points
from api.app.scoring.rules import available_keys
from api.app.schemas import (
    AdminPoolOut,
    ChildRanking,
    GridParticipant,
    GridPrediction,
    GroupRankingOut,
    PoolGridOut,
    PoolCreate,
    PoolDetailOut,
    PoolMatchOut,
    PoolMemberOut,
    MemberIn,
    MoveIn,
    PoolOut,
    PoolTreeOut,
    PoolUpdate,
    PredictionOut,
    RankingRow,
    RegistroBatch,
    RegistroResult,
    RuleOut,
    SalaCreate,
    TransferIn,
)

router = APIRouter(prefix="/pools", tags=["pools"])


# ── Helpers de serialização ──────────────────────────────────────────────────

def _to_tree(pool: Pool) -> PoolTreeOut:
    """Bolão → árvore com filhos aninhados."""
    return PoolTreeOut(
        id=pool.id,
        name=pool.name,
        owner_id=pool.owner_id,
        rule_id=pool.rule_id,
        parent_id=pool.parent_id,
        scope=pool.scope,
        is_group=pool.is_group,
        children=[_to_tree(c) for c in sorted(pool.children, key=lambda p: p.id)],
    )


def _pool_scope_matches(pool: Pool, all_matches: list) -> list:
    """Jogos do bolão: união dos jogos dos filhos (grupo) ou do próprio escopo."""
    if pool.children:
        seen: set[str] = set()
        out: list = []
        for child in pool.children:
            for m in _pool_scope_matches(child, all_matches):
                if m.match_id not in seen:
                    seen.add(m.match_id)
                    out.append(m)
        return out
    return [m for m in all_matches if match_in_scope(m, pool.scope)]


def _pool_status(pool: Pool, all_matches: list) -> str:
    """a_iniciar (nenhum jogo finalizado) | em_andamento | finalizado (todos)."""
    in_scope = _pool_scope_matches(pool, all_matches)
    if not in_scope:
        return "a_iniciar"
    fin = sum(1 for m in in_scope if m.status == "finalizado")
    if fin == 0:
        return "a_iniciar"
    if fin == len(in_scope):
        return "finalizado"
    return "em_andamento"


def _pool_winners(db: Session, pool: Pool, names: dict) -> list[str]:
    """Nome(s) do(s) vencedor(es): maior pontuação (empate → vários)."""
    if pool.children:
        agg: dict[int, int] = defaultdict(int)
        for child in pool.children:
            for r in _ranking_for_pool(db, child, names):
                agg[r.user_id] += r.total_points
        rows = [(names.get(uid, str(uid)), pts) for uid, pts in agg.items()]
    else:
        rows = [(r.name, r.total_points) for r in _ranking_for_pool(db, pool, names)]
    if not rows:
        return []
    top = max(pts for _, pts in rows)
    if top <= 0:
        return []
    return sorted(name for name, pts in rows if pts == top)


def _to_tree_rich(pool: Pool, member_counts: dict, all_matches: list, rule_names: dict,
                  db: Session, names: dict) -> PoolTreeOut:
    """Como _to_tree, mas com nº de participantes, nº de jogos, nome da regra,
    status e vencedor(es) — usado nos cards da listagem."""
    status = _pool_status(pool, all_matches)
    winners = _pool_winners(db, pool, names) if status == "finalizado" else []
    return PoolTreeOut(
        id=pool.id,
        name=pool.name,
        owner_id=pool.owner_id,
        rule_id=pool.rule_id,
        parent_id=pool.parent_id,
        scope=pool.scope,
        is_group=pool.is_group,
        n_members=int(member_counts.get(pool.id, 0)),
        n_matches=sum(1 for m in all_matches if match_in_scope(m, pool.scope)),
        rule_name=rule_names.get(pool.rule_id),
        status=status,
        winners=winners,
        children=[_to_tree_rich(c, member_counts, all_matches, rule_names, db, names)
                  for c in sorted(pool.children, key=lambda p: p.id)],
    )


# ── Regras (compat: /pools/rules continua existindo) ──────────────────────────

@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regras builtin + as do usuário + as usadas pelos bolões dele (ver scoring)."""
    pool_ids = {m.pool_id for m in db.scalars(select(PoolMember).where(PoolMember.user_id == user.id))}
    pool_ids |= set(db.scalars(select(Pool.id).where(Pool.owner_id == user.id)))
    used_rule_ids = set(db.scalars(select(Pool.rule_id).where(Pool.id.in_(pool_ids)))) if pool_ids else set()
    stmt = (
        select(ScoringRule)
        .where(or_(
            ScoringRule.owner_id.is_(None),
            ScoringRule.owner_id == user.id,
            ScoringRule.id.in_(used_rule_ids),
        ))
        .order_by(ScoringRule.id)
    )
    return db.scalars(stmt).all()


# ── Listagem / detalhe ────────────────────────────────────────────────────────

@router.get("", response_model=list[PoolTreeOut])
def list_pools(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bolões do usuário (dono ou membro), como árvore (só raízes no topo).

    Admin vê TODOS os bolões da plataforma, mesmo sem participar — ele administra.
    """
    member_counts = dict(db.execute(select(PoolMember.pool_id, func.count()).group_by(PoolMember.pool_id)).all())
    all_matches = db.scalars(select(Match)).all()
    rule_names = {r.id: r.name for r in db.scalars(select(ScoringRule)).all()}
    names = {u.id: u.name for u in db.scalars(select(User)).all()}

    def rich(p: Pool) -> PoolTreeOut:
        return _to_tree_rich(p, member_counts, all_matches, rule_names, db, names)

    if user.is_admin:
        pools = db.scalars(select(Pool).order_by(Pool.id)).all()
        return [rich(p) for p in pools if p.parent_id is None]

    member_ids = {
        m.pool_id
        for m in db.scalars(select(PoolMember).where(PoolMember.user_id == user.id)).all()
    }
    owned = db.scalars(select(Pool).where(Pool.owner_id == user.id)).all()
    pool_ids = member_ids | {p.id for p in owned}
    if not pool_ids:
        return []
    pools = db.scalars(
        select(Pool).where(Pool.id.in_(pool_ids)).order_by(Pool.id)
    ).all()
    # Só raízes no topo; filhos vêm aninhados. Um filho cujo pai está na lista
    # não aparece solto.
    roots = [p for p in pools if p.parent_id is None or p.parent_id not in pool_ids]
    return [rich(p) for p in roots]


@router.get("/mine", response_model=list[PoolTreeOut])
def list_my_pools(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compat: mesmo que GET /pools (bolões do usuário, em árvore)."""
    return list_pools(user=user, db=db)


@router.get("/{pool_id}", response_model=PoolDetailOut)
def get_pool(
    pool_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    names = {u.id: u.name for u in db.scalars(select(User)).all()}
    members = [
        PoolMemberOut(user_id=m.user_id, name=names.get(m.user_id, str(m.user_id)))
        for m in pool.members
    ]
    return PoolDetailOut(
        id=pool.id,
        name=pool.name,
        owner_id=pool.owner_id,
        rule_id=pool.rule_id,
        parent_id=pool.parent_id,
        scope=pool.scope,
        is_group=pool.is_group,
        rule=RuleOut.model_validate(pool.rule) if pool.rule else None,
        members=members,
        children=[_to_tree(c) for c in sorted(pool.children, key=lambda p: p.id)],
    )


# ── Criação ───────────────────────────────────────────────────────────────────

def _resolve_rule(payload: PoolCreate, user: User, db: Session) -> ScoringRule:
    """Resolve a regra do bolão: inline_spec (cria na hora) ou rule_id."""
    if payload.inline_spec is not None:
        known = set(available_keys())
        criterios = [k for k in payload.inline_spec if not k.startswith("_")]
        if not criterios or any(k not in known for k in criterios):
            raise HTTPException(400, "inline_spec com critérios inválidos")
        rule = ScoringRule(
            name=f"{payload.name} (regra de {user.name})",
            description="Regra inline do bolão",
            spec=payload.inline_spec,
            owner_id=user.id,
        )
        db.add(rule)
        db.flush()
        return rule
    if payload.rule_id is None:
        raise HTTPException(400, "informe rule_id ou inline_spec")
    rule = db.get(ScoringRule, payload.rule_id)
    if rule is None:
        raise HTTPException(404, "regra não encontrada")
    return rule


@router.post("", response_model=PoolTreeOut, status_code=201)
def create_pool(
    payload: PoolCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria um bolão flexível.

    - `scope`: define os jogos (default = todos).
    - `rule_id` OU `inline_spec`: regra de pontuação.
    - `parent_id`: aninha sob um bolão-grupo existente.
    - `nest_by_stage`: cria um grupo + um filho por fase distinta do escopo.
    """
    parent = db.get(Pool, payload.parent_id) if payload.parent_id is not None else None
    if payload.parent_id is not None and parent is None:
        raise HTTPException(404, "bolão pai não encontrado")

    # Sub-bolão dentro de uma SALA herda a regra padrão da sala (se nenhuma vier).
    in_sala = parent is not None and parent.is_group
    if in_sala and payload.rule_id is None and payload.inline_spec is None:
        rule = parent.rule
    else:
        rule = _resolve_rule(payload, user, db)
    scope = payload.scope.model_dump() if payload.scope else {"type": "all"}

    if payload.nest_by_stage:
        return _create_nested_by_stage(payload, scope, rule, user, db)

    pool = Pool(
        name=payload.name,
        owner_id=user.id,
        rule_id=rule.id,
        scope=scope,
        parent_id=payload.parent_id,
        is_group=False,
    )
    db.add(pool)
    db.flush()
    # Dentro de uma sala: herda os PARTICIPANTES da sala. Senão: o criador entra
    # como membro (admin apenas administra, não joga).
    if in_sala and parent.members:
        for m in parent.members:
            db.add(PoolMember(pool_id=pool.id, user_id=m.user_id))
    elif not user.is_admin:
        db.add(PoolMember(pool_id=pool.id, user_id=user.id))
    db.commit()
    db.refresh(pool)
    return _to_tree(pool)


def _create_nested_by_stage(
    payload: PoolCreate, scope: dict, rule: ScoringRule, user: User, db: Session
) -> PoolTreeOut:
    """Cria um bolão-grupo e um filho por fase distinta presente no escopo."""
    in_scope = matches_in_scope(db, scope)
    stages: list[str] = []
    for m in in_scope:
        if m.stage and m.stage not in stages:
            stages.append(m.stage)
    if not stages:
        raise HTTPException(400, "nenhuma fase encontrada no escopo para aninhar")

    parent = Pool(
        name=payload.name,
        owner_id=user.id,
        rule_id=rule.id,
        scope=scope,
        parent_id=payload.parent_id,
        is_group=True,
    )
    db.add(parent)
    db.flush()
    add_member = not user.is_admin  # admin só administra, não joga
    if add_member:
        db.add(PoolMember(pool_id=parent.id, user_id=user.id))

    for stage in stages:
        child = Pool(
            name=f"{payload.name} — {stage}",
            owner_id=user.id,
            rule_id=rule.id,
            scope={"type": "stage", "stages": [stage]},
            parent_id=parent.id,
            is_group=False,
        )
        db.add(child)
        db.flush()
        if add_member:
            db.add(PoolMember(pool_id=child.id, user_id=user.id))

    db.commit()
    db.refresh(parent)
    return _to_tree(parent)


# ── Salas (ligas): grupo com participantes + regra padrão ────────────────────

@router.post("/sala", response_model=PoolTreeOut, status_code=201)
def create_sala(
    payload: SalaCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cria uma SALA (liga) — bolão-grupo com participantes e regra padrão.
    Os sub-bolões criados dentro herdam os participantes e a regra."""
    if payload.rule_id is not None:
        rule = db.get(ScoringRule, payload.rule_id)
        if rule is None:
            raise HTTPException(404, "regra não encontrada")
    elif payload.inline_spec is not None:
        rule = ScoringRule(name=f"{payload.name} (regra)", spec=payload.inline_spec, owner_id=user.id)
        db.add(rule)
        db.flush()
    else:
        raise HTTPException(400, "informe rule_id ou inline_spec")

    sala = Pool(
        name=payload.name, owner_id=user.id, rule_id=rule.id,
        scope={"type": "all"}, parent_id=None, is_group=True,
    )
    db.add(sala)
    db.flush()
    seen: set[int] = set()
    for uid in payload.member_ids:
        if uid in seen or db.get(User, uid) is None:
            continue
        db.add(PoolMember(pool_id=sala.id, user_id=uid))
        seen.add(uid)
    db.commit()
    db.refresh(sala)
    return _to_tree(sala)


@router.post("/{pool_id}/members", status_code=201)
def add_member(
    pool_id: int,
    payload: MemberIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Adiciona um participante à sala (e aos sub-bolões dela)."""
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    if pool.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "só o dono pode gerenciar participantes")
    if db.get(User, payload.user_id) is None:
        raise HTTPException(404, "usuário não encontrado")
    for p in [pool, *pool.children]:
        existing = db.scalar(
            select(PoolMember).where(PoolMember.pool_id == p.id, PoolMember.user_id == payload.user_id)
        )
        if existing is None:
            db.add(PoolMember(pool_id=p.id, user_id=payload.user_id))
    db.commit()
    return {"ok": True}


@router.delete("/{pool_id}/members/{member_user_id}")
def remove_member(
    pool_id: int,
    member_user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove um participante da sala (e dos sub-bolões dela)."""
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    if pool.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "só o dono pode gerenciar participantes")
    target_ids = [pool.id, *[c.id for c in pool.children]]
    db.execute(
        delete(PoolMember).where(
            PoolMember.pool_id.in_(target_ids), PoolMember.user_id == member_user_id
        )
    )
    db.commit()
    return {"ok": True}


@router.post("/{pool_id}/move", response_model=PoolOut)
def move_pool(
    pool_id: int,
    payload: MoveIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move um bolão para dentro de uma sala (parent_id) ou para a raiz (None)."""
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    if pool.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "só o dono pode mover")
    if payload.parent_id is not None:
        parent = db.get(Pool, payload.parent_id)
        if parent is None:
            raise HTTPException(404, "sala não encontrada")
        if not parent.is_group:
            raise HTTPException(400, "o destino precisa ser uma sala")
        # evita ciclo: o destino não pode ser o próprio bolão nem um descendente dele
        anc: Pool | None = parent
        while anc is not None:
            if anc.id == pool.id:
                raise HTTPException(400, "movimento criaria um ciclo")
            anc = db.get(Pool, anc.parent_id) if anc.parent_id else None
        pool.parent_id = parent.id
    else:
        pool.parent_id = None
    db.commit()
    db.refresh(pool)
    return pool


@router.post("/{pool_id}/join", response_model=PoolOut)
def join_pool(
    pool_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Entra num bolão pelo ID. Idempotente: retorna 200 se já for membro."""
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    existing = db.scalar(
        select(PoolMember).where(
            PoolMember.pool_id == pool_id, PoolMember.user_id == user.id
        )
    )
    if existing is None:
        db.add(PoolMember(pool_id=pool_id, user_id=user.id))
        db.commit()
    return pool


@router.patch("/{pool_id}", response_model=PoolDetailOut)
def update_pool(
    pool_id: int,
    payload: PoolUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edita um bolão (nome, regra e/ou escopo). Só o dono ou admin.

    Mudar a regra ou o escopo recalcula os pontos dos palpites afetados.
    """
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    if pool.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "só o dono do bolão pode editá-lo")

    rescore = False
    if payload.name is not None:
        pool.name = payload.name
    if payload.rule_id is not None and payload.rule_id != pool.rule_id:
        if db.get(ScoringRule, payload.rule_id) is None:
            raise HTTPException(404, "regra não encontrada")
        pool.rule_id = payload.rule_id
        rescore = True
    if payload.scope is not None:
        pool.scope = payload.scope.model_dump()
        rescore = True

    db.flush()
    if rescore:
        recompute_pool_points(db)
    db.commit()
    return get_pool(pool_id, user, db)


def _subtree_ids(pool: Pool) -> list[int]:
    """IDs do bolão e de todos os descendentes (pai antes dos filhos)."""
    ids = [pool.id]
    stack = list(pool.children)
    while stack:
        c = stack.pop()
        ids.append(c.id)
        stack.extend(c.children)
    return ids


@router.delete("/{pool_id}")
def delete_pool(
    pool_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exclui o bolão (e os sub-bolões, se for grupo). Só o dono ou admin.

    Apaga junto os palpites e as participações; a regra de pontuação (mesmo a
    inline) é preservada — pode estar em uso por outro bolão.
    """
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    if pool.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "só o dono do bolão pode excluí-lo")

    ids = _subtree_ids(pool)
    db.execute(delete(Prediction).where(Prediction.pool_id.in_(ids)))
    db.execute(delete(PoolMember).where(PoolMember.pool_id.in_(ids)))
    db.delete(pool)  # cascade (delete-orphan) remove os sub-bolões
    db.commit()
    return {"deleted": len(ids)}


@router.post("/{pool_id}/transfer", response_model=PoolDetailOut)
def transfer_pool(
    pool_id: int,
    payload: TransferIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transfere a posse do bolão (e dos sub-bolões) para outro usuário.

    Só o dono atual ou um admin. O novo dono vira membro (passa a jogar), a não
    ser que seja admin — admin só administra.
    """
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    if pool.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "só o dono ou um admin pode transferir o bolão")
    new_owner = db.get(User, payload.user_id)
    if new_owner is None:
        raise HTTPException(404, "usuário de destino não encontrado")

    ids = _subtree_ids(pool)
    db.execute(update(Pool).where(Pool.id.in_(ids)).values(owner_id=new_owner.id))
    if not new_owner.is_admin:
        already = {
            m.pool_id for m in db.scalars(
                select(PoolMember).where(
                    PoolMember.user_id == new_owner.id, PoolMember.pool_id.in_(ids)
                )
            )
        }
        for pid in ids:
            if pid not in already:
                db.add(PoolMember(pool_id=pid, user_id=new_owner.id))
    db.commit()
    return get_pool(pool_id, user, db)


@router.get("/admin/all", response_model=list[AdminPoolOut])
def admin_list_pools(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Todos os bolões da plataforma, com dono e nº de jogadores (gestão admin)."""
    pools = db.scalars(select(Pool).order_by(Pool.id)).all()
    names = {u.id: u.name for u in db.scalars(select(User)).all()}
    rules = {r.id: r.name for r in db.scalars(select(ScoringRule)).all()}
    counts = dict(
        db.execute(
            select(PoolMember.pool_id, func.count()).group_by(PoolMember.pool_id)
        ).all()
    )
    return [
        AdminPoolOut(
            id=p.id,
            name=p.name,
            owner_id=p.owner_id,
            owner_name=names.get(p.owner_id, "?"),
            is_group=p.is_group,
            parent_id=p.parent_id,
            members=int(counts.get(p.id, 0)),
            rule_name=rules.get(p.rule_id),
            scope=p.scope,
        )
        for p in pools
    ]


# ── Registro de bolão já encerrado ────────────────────────────────────────────

@router.post("/{pool_id}/registro", response_model=RegistroResult)
def registro_bolao(
    pool_id: int,
    payload: RegistroBatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registra um bolão JÁ ENCERRADO: grava os palpites em nome de cada
    participante e pontua na hora (o resultado vem da tabela `matches`).

    Diferente de POST .../predictions, este endpoint:
    - é restrito ao DONO do bolão (ou admin) — ele lança o palpite de todo mundo;
    - aceita jogos já FINALIZADOS (é exatamente o caso de uso do registro);
    - recebe `user_id` por item e vira membro automático quem ainda não for.
    """
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    if pool.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "só o dono do bolão pode registrar palpites")
    if pool.is_group:
        raise HTTPException(400, "bolão de grupo não recebe palpites diretos")

    matches = {m.match_id: m for m in db.scalars(select(Match)).all()}
    members = {
        m.user_id
        for m in db.scalars(select(PoolMember).where(PoolMember.pool_id == pool_id)).all()
    }
    known_users = {u.id for u in db.scalars(select(User)).all()}
    spec = pool.rule.spec if pool.rule else {}

    registered = scored = 0
    for item in payload.items:
        if item.user_id not in known_users:
            raise HTTPException(404, f"usuário {item.user_id} não encontrado")
        match = matches.get(item.match_id)
        if match is None:
            raise HTTPException(404, f"jogo {item.match_id} não encontrado")
        if not match_in_scope(match, pool.scope):
            raise HTTPException(400, f"jogo {item.match_id} fora do escopo do bolão")

        if item.user_id not in members:
            db.add(PoolMember(pool_id=pool_id, user_id=item.user_id))
            members.add(item.user_id)

        pred = db.scalar(
            select(Prediction).where(
                Prediction.pool_id == pool_id,
                Prediction.user_id == item.user_id,
                Prediction.match_id == item.match_id,
            )
        )
        if pred is None:
            pred = Prediction(
                pool_id=pool_id,
                user_id=item.user_id,
                match_id=item.match_id,
                home_score=item.home_score,
                away_score=item.away_score,
            )
            db.add(pred)
        else:
            pred.home_score = item.home_score
            pred.away_score = item.away_score

        if (
            match.status == "finalizado"
            and match.home_score is not None
            and match.away_score is not None
        ):
            pred.points = score_prediction(
                spec, (item.home_score, item.away_score), (match.home_score, match.away_score)
            )
            scored += 1
        else:
            pred.points = None
        registered += 1

    db.commit()
    names = {u.id: u.name for u in db.scalars(select(User)).all()}
    return RegistroResult(
        registered=registered,
        scored=scored,
        ranking=_ranking_for_pool(db, pool, names),
    )


@router.get("/{pool_id}/grid", response_model=PoolGridOut)
def pool_grid(
    pool_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grade de palpites de TODOS os participantes do bolão. Só dono ou admin.

    Usada para o dono/admin ver e editar os palpites de cada um (salva via
    POST .../registro). Jogos do escopo + participantes (não-admins) + palpites.
    """
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    if pool.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "só o dono ou um admin pode gerenciar os palpites")
    if pool.is_group:
        raise HTTPException(400, "bolão de grupo não tem grade — use os sub-bolões")

    matches = matches_in_scope(db, pool.scope)
    preds = db.scalars(select(Prediction).where(Prediction.pool_id == pool_id)).all()
    users = {u.id: u for u in db.scalars(select(User)).all()}

    member_ids = {m.user_id for m in db.scalars(select(PoolMember).where(PoolMember.pool_id == pool_id)).all()}
    participant_ids = (member_ids | {p.user_id for p in preds})
    participant_ids = sorted(uid for uid in participant_ids if not (users.get(uid) and users[uid].is_admin))

    participants = [GridParticipant(user_id=uid, name=users[uid].name if uid in users else str(uid)) for uid in participant_ids]
    grid_preds = [
        GridPrediction(user_id=p.user_id, match_id=p.match_id, home_score=p.home_score, away_score=p.away_score, points=p.points)
        for p in preds
    ]
    match_out = [
        PoolMatchOut(
            match_id=m.match_id, match_number=m.match_number,
            home_team=m.home_team, away_team=m.away_team,
            home_team_code=m.home_team_code, away_team_code=m.away_team_code,
            stage=m.stage, group=m.group, date_utc=m.date_utc, status=m.status,
            home_score=m.home_score, away_score=m.away_score, prediction=None,
        )
        for m in matches
    ]
    return PoolGridOut(matches=match_out, participants=participants, predictions=grid_preds)


# ── Jogos do escopo ───────────────────────────────────────────────────────────

@router.get("/{pool_id}/matches", response_model=list[PoolMatchOut])
def pool_matches(
    pool_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Jogos no escopo do bolão (ordem por match_number) + palpite do caller."""
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    matches = matches_in_scope(db, pool.scope)
    preds = {
        p.match_id: p
        for p in db.scalars(
            select(Prediction).where(
                Prediction.pool_id == pool_id, Prediction.user_id == user.id
            )
        ).all()
    }
    out: list[PoolMatchOut] = []
    for m in matches:
        pred = preds.get(m.match_id)
        out.append(
            PoolMatchOut(
                match_id=m.match_id,
                match_number=m.match_number,
                home_team=m.home_team,
                away_team=m.away_team,
                home_team_code=m.home_team_code,
                away_team_code=m.away_team_code,
                stage=m.stage,
                group=m.group,
                date_utc=m.date_utc,
                status=m.status,
                home_score=m.home_score,
                away_score=m.away_score,
                prediction=PredictionOut.model_validate(pred) if pred else None,
            )
        )
    return out


# ── Ranking ───────────────────────────────────────────────────────────────────

def _ranking_for_pool(db: Session, pool: Pool, names: dict[int, str]) -> list[RankingRow]:
    """Ranking de um bolão-folha: soma points dos palpites no escopo."""
    preds = db.scalars(select(Prediction).where(Prediction.pool_id == pool.id)).all()
    matches = {m.match_id: m for m in db.scalars(select(Match)).all()}
    points: dict[int, int] = defaultdict(int)
    counts: dict[int, int] = defaultdict(int)
    for p in preds:
        m = matches.get(p.match_id)
        if m is None or not match_in_scope(m, pool.scope):
            continue
        points[p.user_id] += p.points or 0
        counts[p.user_id] += 1
    rows = [
        RankingRow(
            user_id=uid,
            name=names.get(uid, str(uid)),
            total_points=points[uid],
            predictions=counts[uid],
        )
        for uid in counts
    ]
    rows.sort(key=lambda r: (-r.total_points, r.name))
    return rows


@router.get("/{pool_id}/ranking", response_model=GroupRankingOut)
def pool_ranking(
    pool_id: int,
    db: Session = Depends(get_db),
):
    """Ranking do bolão.

    Bolão-folha: ranking direto. Bolão-grupo: ranking agregado de todos os
    filhos + quebra por filho (`children`)."""
    pool = db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(404, "bolão não encontrado")
    names = {u.id: u.name for u in db.scalars(select(User)).all()}

    if not pool.children:
        return GroupRankingOut(ranking=_ranking_for_pool(db, pool, names), children=[])

    # Grupo: agrega os filhos.
    agg_points: dict[int, int] = defaultdict(int)
    agg_counts: dict[int, int] = defaultdict(int)
    children_out: list[ChildRanking] = []
    for child in sorted(pool.children, key=lambda p: p.id):
        child_ranking = _ranking_for_pool(db, child, names)
        for row in child_ranking:
            agg_points[row.user_id] += row.total_points
            agg_counts[row.user_id] += row.predictions
        stage = None
        if child.scope and child.scope.get("type") == "stage":
            stages = child.scope.get("stages") or []
            stage = stages[0] if stages else None
        children_out.append(
            ChildRanking(
                child_id=child.id, child_name=child.name, stage=stage, ranking=child_ranking
            )
        )

    overall = [
        RankingRow(
            user_id=uid,
            name=names.get(uid, str(uid)),
            total_points=agg_points[uid],
            predictions=agg_counts[uid],
        )
        for uid in agg_counts
    ]
    overall.sort(key=lambda r: (-r.total_points, r.name))
    return GroupRankingOut(ranking=overall, children=children_out)
