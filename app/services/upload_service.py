"""Serviço de uploads versionados (Fase 6.5.b).

Cada chamada de save_fracoes/save_cabecalho cria um Upload por (unidade,
data). Substituições não apagam — marcam o upload anterior como
`cancelado_em` e as linhas vinculadas como `deletado_em` (soft-delete). Pra
reverter, basta chamar `restaurar_upload` — o ativo atual cancela e o alvo
vira ativo novamente com as linhas undelete.

Invariantes:
  - UNIQUE constraint em uploads(unidade, data) WHERE cancelado_em IS NULL
    garante 1 upload ativo por dia. Violação dispara `IntegrityError`, que
    o `save_fracoes` usa como detecção de race.
  - `cancelar_upload` é idempotente (no-op se já cancelado).
  - `restaurar_upload` exige que o alvo NÃO esteja já ativo (erro amigável).

Queries 100% parametrizadas; toda escrita em transação; decoradores de role
ficam nos endpoints (camada HTTP).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast

import psycopg2
import psycopg2.extensions

from app.models.database import get_connection

OrigemUpload = str
ORIGENS_VALIDAS: frozenset[str] = frozenset(
    ("whatsapp", "xlsx", "edicao", "backfill")
)


@dataclass(frozen=True)
class Upload:
    id: str
    usuario_id: str
    unidade: str
    data: str
    criado_em: datetime
    origem: OrigemUpload
    texto_original: str | None
    substitui_id: str | None
    cancelado_em: datetime | None
    cancelado_por: str | None
    observacao: str | None


_COLUNAS_UPLOAD: str = (
    "id, usuario_id, unidade, data, criado_em, origem, texto_original, "
    "substitui_id, cancelado_em, cancelado_por, observacao"
)


def _row_to_upload(row: dict) -> Upload:
    origem_raw: str = cast(str, row["origem"])
    if origem_raw not in ORIGENS_VALIDAS:
        raise ValueError(f"Origem invalida no banco: {origem_raw}")
    return Upload(
        id=str(row["id"]),
        usuario_id=str(row["usuario_id"]),
        unidade=cast(str, row["unidade"]),
        data=cast(str, row["data"]),
        criado_em=cast(datetime, row["criado_em"]),
        origem=origem_raw,
        texto_original=cast("str | None", row["texto_original"]),
        substitui_id=str(row["substitui_id"]) if row["substitui_id"] else None,
        cancelado_em=cast("datetime | None", row["cancelado_em"]),
        cancelado_por=(
            str(row["cancelado_por"]) if row["cancelado_por"] else None
        ),
        observacao=cast("str | None", row["observacao"]),
    )


def upload_ativo_por_dia(unidade: str, data: str) -> Upload | None:
    """Upload mais recente *e* não-cancelado — o que está "valendo"."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUNAS_UPLOAD} FROM smo.uploads "
                "WHERE unidade = %s AND data = %s AND cancelado_em IS NULL "
                "ORDER BY criado_em DESC LIMIT 1",
                (unidade, data),
            )
            row = cur.fetchone()
            return _row_to_upload(dict(row)) if row else None
    finally:
        conn.close()


def upload_ativo_com_metadata(
    unidade: str, data: str
) -> "UploadHistorico | None":
    """Ativo do dia + nome do autor + contagens — 1 query.

    Usado por GET /api/uploads/existente (modal de confirmacao). Evita o
    caminho geral via listar_historico (6 queries) para manter o modal
    responsivo — ver AUDITORIA_6_5 secao 12 (UX).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            colunas_up: str = ", ".join(
                f"up.{c.strip()}" for c in _COLUNAS_UPLOAD.split(",")
            )
            cur.execute(
                f"SELECT {colunas_up}, u.nome AS usuario_nome, "
                "       (SELECT COUNT(*) FROM smo.fracoes     f "
                "         WHERE f.upload_id = up.id) AS qtde_fracoes, "
                "       (SELECT COUNT(*) FROM smo.cabecalho   c "
                "         WHERE c.upload_id = up.id) AS qtde_cabecalho "
                "FROM smo.uploads up "
                "JOIN smo.usuarios u ON u.id = up.usuario_id "
                "WHERE up.unidade = %s AND up.data = %s "
                "  AND up.cancelado_em IS NULL "
                "ORDER BY up.criado_em DESC LIMIT 1",
                (unidade, data),
            )
            row = cur.fetchone()
            if row is None:
                return None
            d = dict(row)
            return UploadHistorico(
                upload=_row_to_upload(d),
                usuario_nome=str(d["usuario_nome"]),
                cancelado_por_nome=None,
                qtde_fracoes=int(d["qtde_fracoes"]),
                qtde_cabecalho=int(d["qtde_cabecalho"]),
            )
    finally:
        conn.close()


def listar_uploads_por_dia(unidade: str, data: str) -> list[Upload]:
    """Histórico completo do dia (inclui cancelados), desc por criado_em."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUNAS_UPLOAD} FROM smo.uploads "
                "WHERE unidade = %s AND data = %s "
                "ORDER BY criado_em DESC",
                (unidade, data),
            )
            return [_row_to_upload(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()


def get_upload(upload_id: str) -> Upload | None:
    if not upload_id:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUNAS_UPLOAD} FROM smo.uploads WHERE id = %s",
                (upload_id,),
            )
            row = cur.fetchone()
            return _row_to_upload(dict(row)) if row else None
    finally:
        conn.close()


# ---------- Helpers transacionais (recebem cursor já em transação) ----------

def _cur_upload_ativo(
    cur: psycopg2.extensions.cursor, unidade: str, data: str
) -> Upload | None:
    """Idem `upload_ativo_por_dia` mas usando um cursor ja aberto com SELECT
    FOR UPDATE — impede race no ciclo cancelar-anterior -> inserir-novo."""
    cur.execute(
        f"SELECT {_COLUNAS_UPLOAD} FROM smo.uploads "
        "WHERE unidade = %s AND data = %s AND cancelado_em IS NULL "
        "ORDER BY criado_em DESC LIMIT 1 FOR UPDATE",
        (unidade, data),
    )
    row = cur.fetchone()
    return _row_to_upload(dict(row)) if row else None


def _cancelar_upload_na_transacao(
    cur: psycopg2.extensions.cursor, upload_id: str, usuario_id: str
) -> None:
    """Marca cancelado_em + soft-deleta fracoes/cabecalho vinculados."""
    cur.execute(
        "UPDATE smo.uploads "
        "SET cancelado_em = NOW(), cancelado_por = %s "
        "WHERE id = %s AND cancelado_em IS NULL",
        (usuario_id, upload_id),
    )
    cur.execute(
        "UPDATE smo.fracoes "
        "SET deletado_em = NOW(), deletado_por = %s "
        "WHERE upload_id = %s AND deletado_em IS NULL",
        (usuario_id, upload_id),
    )
    cur.execute(
        "UPDATE smo.cabecalho "
        "SET deletado_em = NOW(), deletado_por = %s "
        "WHERE upload_id = %s AND deletado_em IS NULL",
        (usuario_id, upload_id),
    )


def _criar_upload_na_transacao(
    cur: psycopg2.extensions.cursor,
    *,
    usuario_id: str,
    unidade: str,
    data: str,
    texto_original: str | None,
    substitui_id: str | None,
    origem: OrigemUpload,
) -> str:
    if origem not in ORIGENS_VALIDAS:
        raise ValueError(f"Origem invalida: {origem}")
    cur.execute(
        "INSERT INTO smo.uploads "
        "(usuario_id, unidade, data, texto_original, substitui_id, origem) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (usuario_id, unidade, data, texto_original, substitui_id, origem),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("INSERT smo.uploads nao retornou id")
    return str(row["id"])


def preparar_uploads_para_pares(
    cur: psycopg2.extensions.cursor,
    *,
    pares: set[tuple[str, str]],
    usuario_id: str,
    texto_original: str | None,
    origem: OrigemUpload,
) -> dict[tuple[str, str], str]:
    """Para cada (unidade, data): cancela o ativo anterior e cria novo upload.

    Retorna dict {(unidade, data): upload_id_novo}. Deve ser chamado dentro
    da mesma transação do save_fracoes/save_cabecalho.
    """
    upload_ids: dict[tuple[str, str], str] = {}
    for unidade, data in pares:
        anterior = _cur_upload_ativo(cur, unidade, data)
        if anterior is not None:
            _cancelar_upload_na_transacao(cur, anterior.id, usuario_id)
        novo_id = _criar_upload_na_transacao(
            cur,
            usuario_id=usuario_id,
            unidade=unidade,
            data=data,
            texto_original=texto_original,
            substitui_id=anterior.id if anterior else None,
            origem=origem,
        )
        upload_ids[(unidade, data)] = novo_id
    return upload_ids


# ---------- Operações públicas autônomas (abrem própria transação) ----------

def cancelar_upload(upload_id: str, usuario_id: str) -> None:
    """Cancela um upload e soft-deleta linhas. Idempotente."""
    if not upload_id:
        raise ValueError("upload_id vazio")
    if not usuario_id:
        raise ValueError("usuario_id vazio")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _cancelar_upload_na_transacao(cur, upload_id, usuario_id)
        conn.commit()
    except psycopg2.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def restaurar_upload(upload_id: str, usuario_id: str) -> Upload:
    """Cancela o upload ativo atual (se houver) e "undelete" as linhas do alvo.

    Regras:
      - Se o alvo já está ativo -> erro amigável.
      - Se o alvo não existe -> erro amigável.
      - Transacional: ou tudo ou nada.
    """
    if not upload_id:
        raise ValueError("upload_id vazio")
    if not usuario_id:
        raise ValueError("usuario_id vazio")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Lock o upload alvo pra ler unidade/data + validar estado.
            cur.execute(
                f"SELECT {_COLUNAS_UPLOAD} FROM smo.uploads "
                "WHERE id = %s FOR UPDATE",
                (upload_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError("Upload nao encontrado")
            alvo = _row_to_upload(dict(row))
            if alvo.cancelado_em is None:
                raise ValueError(
                    "Este upload ja e o ativo desse dia — nada a restaurar"
                )

            # Cancela o ativo corrente (se houver).
            ativo = _cur_upload_ativo(cur, alvo.unidade, alvo.data)
            if ativo is not None:
                if ativo.id == alvo.id:
                    # Inconsistente (alvo.cancelado_em != NULL mas ativo.id == alvo.id)
                    # — defesa: não tem o que fazer.
                    raise RuntimeError(
                        "Estado inconsistente: alvo listado como ativo e como "
                        "cancelado. Abortando."
                    )
                _cancelar_upload_na_transacao(cur, ativo.id, usuario_id)

            # Undelete as linhas vinculadas ao alvo e limpa cancelado_em.
            cur.execute(
                "UPDATE smo.uploads "
                "SET cancelado_em = NULL, cancelado_por = NULL "
                "WHERE id = %s",
                (alvo.id,),
            )
            cur.execute(
                "UPDATE smo.fracoes "
                "SET deletado_em = NULL, deletado_por = NULL "
                "WHERE upload_id = %s",
                (alvo.id,),
            )
            cur.execute(
                "UPDATE smo.cabecalho "
                "SET deletado_em = NULL, deletado_por = NULL "
                "WHERE upload_id = %s",
                (alvo.id,),
            )

            # Le o alvo atualizado.
            cur.execute(
                f"SELECT {_COLUNAS_UPLOAD} FROM smo.uploads WHERE id = %s",
                (alvo.id,),
            )
            row2 = cur.fetchone()
            if row2 is None:
                raise RuntimeError("Alvo desapareceu apos UPDATE — bug")
            restaurado = _row_to_upload(dict(row2))
        conn.commit()
        return restaurado
    except psycopg2.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def contar_linhas_upload(upload_id: str) -> tuple[int, int]:
    """Retorna (qtde_fracoes, qtde_cabecalhos) vinculadas ao upload.

    Usado pelo listagem de histórico para mostrar quantas frações tem cada
    versão. Considera TODAS as linhas — ativas e soft-deletadas — já que o
    upload só tem o seu conjunto próprio.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM smo.fracoes WHERE upload_id = %s",
                (upload_id,),
            )
            row_f = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) AS n FROM smo.cabecalho WHERE upload_id = %s",
                (upload_id,),
            )
            row_c = cur.fetchone()
            qf = int(row_f["n"]) if row_f else 0
            qc = int(row_c["n"]) if row_c else 0
            return qf, qc
    finally:
        conn.close()


@dataclass(frozen=True)
class UploadHistorico:
    """Upload + nomes resolvidos + contagem de linhas — payload de histórico.

    Usado pela UI de histórico (listar) e pelo modal de confirmação (existente).
    Evita round-trip N+1 (1 query join usuarios; 2 queries de count por upload).
    """
    upload: Upload
    usuario_nome: str
    cancelado_por_nome: str | None
    qtde_fracoes: int
    qtde_cabecalho: int


def listar_historico(unidade: str, data: str) -> list[UploadHistorico]:
    """Histórico completo do dia com nomes + contagem (ordem desc por criado_em).

    Projetado para alimentar /api/uploads?unidade=X&data=Y — em um único
    round-trip busca todos os uploads, nomes dos usuários (autor e quem
    cancelou, via LEFT JOIN) e as contagens de linhas."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            colunas_up: str = ", ".join(
                f"up.{c.strip()}" for c in _COLUNAS_UPLOAD.split(",")
            )
            cur.execute(
                f"SELECT {colunas_up}, "
                "       u.nome  AS usuario_nome, "
                "       uc.nome AS cancelado_por_nome "
                "FROM smo.uploads up "
                "JOIN      smo.usuarios u  ON u.id  = up.usuario_id "
                "LEFT JOIN smo.usuarios uc ON uc.id = up.cancelado_por "
                "WHERE up.unidade = %s AND up.data = %s "
                "ORDER BY up.criado_em DESC",
                (unidade, data),
            )
            rows = cur.fetchall()

            resultado: list[UploadHistorico] = []
            for row in rows:
                d = dict(row)
                up = _row_to_upload(d)
                cur.execute(
                    "SELECT COUNT(*) AS n FROM smo.fracoes "
                    "WHERE upload_id = %s",
                    (up.id,),
                )
                row_f = cur.fetchone()
                cur.execute(
                    "SELECT COUNT(*) AS n FROM smo.cabecalho "
                    "WHERE upload_id = %s",
                    (up.id,),
                )
                row_c = cur.fetchone()
                resultado.append(
                    UploadHistorico(
                        upload=up,
                        usuario_nome=str(d["usuario_nome"]),
                        cancelado_por_nome=(
                            str(d["cancelado_por_nome"])
                            if d["cancelado_por_nome"] is not None
                            else None
                        ),
                        qtde_fracoes=int(row_f["n"]) if row_f else 0,
                        qtde_cabecalho=int(row_c["n"]) if row_c else 0,
                    )
                )
            return resultado
    finally:
        conn.close()
