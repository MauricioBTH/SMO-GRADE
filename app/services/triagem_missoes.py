"""Triagem humana dos textos de missao que o backfill fuzzy nao conseguiu
casar automaticamente.

Fase 6.3: fonte passou a ser `smo.fracao_missoes.missao_nome_raw` (N:N).
Nao lemos mais de `smo.fracoes.missao` — essa coluna permanece apenas como
espelho legado do 1o vertice. Agrupar/atualizar ocorre no vertice.

Contrato:
  - `agrupar_pendentes` deduplica os textos livres de smo.fracao_missoes
    ordenando por frequencia (maior impacto primeiro).
  - `sugerir_candidatos` usa rapidfuzz token_set_ratio (tolera nome curto
    dentro de texto longo — o inverso do token_sort_ratio usado no backfill).
  - `aplicar_mapeamento` e `criar_e_aplicar` fazem 1 UPDATE que resolve
    todos os vertices com aquele texto, idempotente por `missao_id IS NULL`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

import psycopg2

from app.models.database import get_connection
from app.services.catalogo_types import MissaoCreate, normalizar


_RE_PONTUACAO: re.Pattern[str] = re.compile(r"[^A-Z0-9 ]+")


def _preparar_fuzzy(texto: str) -> str:
    """Normaliza + remove pontuacao + colapsa espacos.

    Necessario porque `token_set_ratio` compara tokens inteiros: "PRONTIDAO,"
    nao casa com "PRONTIDAO". Virgulas/hifens/parenteses sao ruido no contexto.
    """
    base: str = normalizar(texto)
    if not base:
        return ""
    return " ".join(_RE_PONTUACAO.sub(" ", base).split())

try:
    from rapidfuzz import fuzz, process
except ImportError as exc:  # pragma: no cover - import validado no backfill
    raise RuntimeError(
        "rapidfuzz obrigatorio para triagem (pip install rapidfuzz)"
    ) from exc


__all__ = [
    "TextoPendente", "Candidato", "AplicacaoResult", "CriacaoResult",
    "DesfazerResult",
    "agrupar_pendentes", "contar_pendentes", "sugerir_candidatos",
    "aplicar_mapeamento", "criar_e_aplicar", "desfazer_aplicacao",
    "MAX_TEXTO_LEN", "MAX_NOME_LEN", "MAX_DESCRICAO_LEN",
]


MAX_TEXTO_LEN: int = 500
MAX_NOME_LEN: int = 120
MAX_DESCRICAO_LEN: int = 300
SCORE_MIN_DEFAULT: int = 50
TOP_N_DEFAULT: int = 3


@dataclass(frozen=True)
class TextoPendente:
    texto: str
    freq: int


@dataclass(frozen=True)
class Candidato:
    missao_id: str
    nome: str
    score: int


@dataclass(frozen=True)
class AplicacaoResult:
    missao_id: str
    missao_nome: str
    fracoes_atualizadas: int


@dataclass(frozen=True)
class CriacaoResult:
    missao_id: str
    missao_nome: str
    fracoes_atualizadas: int


@dataclass(frozen=True)
class DesfazerResult:
    texto: str
    missao_id: str
    fracoes_revertidas: int
    missao_removida: bool


# ---------------------------------------------------------------------------
# Leitura: textos pendentes agrupados
# ---------------------------------------------------------------------------


def agrupar_pendentes(limit: int = 20, offset: int = 0) -> list[TextoPendente]:
    """Lista textos DISTINTOS com `missao_id IS NULL`, ordenados por freq desc.

    Tiebreak estavel por texto asc para paginar sem embaralhar.
    """
    lim: int = max(1, min(int(limit), 200))
    off: int = max(0, int(offset))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT missao_nome_raw AS texto, COUNT(*) AS freq "
                "FROM smo.fracao_missoes "
                "WHERE missao_id IS NULL "
                "  AND missao_nome_raw IS NOT NULL "
                "  AND missao_nome_raw <> '' "
                "GROUP BY missao_nome_raw "
                "ORDER BY freq DESC, texto ASC "
                "LIMIT %s OFFSET %s",
                (lim, off),
            )
            return [
                TextoPendente(
                    texto=cast(str, r["texto"]), freq=int(r["freq"]),
                )
                for r in cur.fetchall()
            ]
    finally:
        conn.close()


def contar_pendentes() -> int:
    """Total de textos DISTINTOS pendentes (para paginacao)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT missao_nome_raw) AS n "
                "FROM smo.fracao_missoes "
                "WHERE missao_id IS NULL "
                "  AND missao_nome_raw IS NOT NULL "
                "  AND missao_nome_raw <> ''"
            )
            row = cur.fetchone()
            return int(row["n"]) if row else 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Sugestao de candidatos (rapidfuzz, sem banco)
# ---------------------------------------------------------------------------


def sugerir_candidatos(
    texto: str,
    catalogo: dict[str, str],
    n: int = TOP_N_DEFAULT,
    score_min: int = SCORE_MIN_DEFAULT,
) -> list[Candidato]:
    """Top-N candidatos com score >= score_min, desc por score.

    Args:
        texto: texto bruto (será normalizado internamente).
        catalogo: {nome_canonico: missao_id} — nomes ja normalizados ou nao,
                  normalizamos aqui para comparar.
        n: quantos retornar no maximo.
        score_min: corte inferior. O catalogo humano valida — 50 e suficiente
                   para ordenar a lista.

    Usa `token_set_ratio` (nao `token_sort_ratio`): tolera subconjunto, logo
    "PRONTIDAO RESERVA OCD INSTRUCAO ..." casa com "PRONTIDAO".
    Catalogo vazio -> [].
    """
    termo: str = _preparar_fuzzy(texto)
    if not termo or not catalogo:
        return []
    n_lim: int = max(1, min(int(n), 10))
    cutoff: int = max(0, min(int(score_min), 100))

    nomes_norm_para_id: dict[str, str] = {
        _preparar_fuzzy(nome): missao_id for nome, missao_id in catalogo.items()
    }
    nome_exibicao: dict[str, str] = {
        _preparar_fuzzy(nome): nome for nome in catalogo
    }

    resultado = process.extract(
        termo,
        list(nomes_norm_para_id.keys()),
        scorer=fuzz.token_set_ratio,
        limit=n_lim,
    )
    candidatos: list[Candidato] = []
    for nome_norm, score, _ in resultado:
        score_int: int = int(score)
        if score_int < cutoff:
            continue
        candidatos.append(Candidato(
            missao_id=nomes_norm_para_id[nome_norm],
            nome=nome_exibicao[nome_norm],
            score=score_int,
        ))
    return candidatos


# ---------------------------------------------------------------------------
# Escrita: aplicar mapeamento (UPDATE puro)
# ---------------------------------------------------------------------------


def _get_missao_nome(cur: psycopg2.extensions.cursor, missao_id: str) -> str:
    cur.execute(
        "SELECT nome FROM smo.missoes WHERE id = %s AND ativo = TRUE",
        (missao_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError("Missao inexistente ou inativa")
    return cast(str, row["nome"])


def aplicar_mapeamento(texto: str, missao_id: str) -> AplicacaoResult:
    """UPDATE em todas as fracoes com aquele texto e missao_id ainda nulo.

    Idempotente: re-executar nao afeta linhas ja vinculadas.
    Valida que a missao existe antes do UPDATE (erro amigavel em vez de 500
    da FK). O MAX_TEXTO_LEN limita input para proteger contra strings gigantes.
    """
    if not texto or len(texto) > MAX_TEXTO_LEN:
        raise ValueError("texto invalido")
    if not missao_id:
        raise ValueError("missao_id obrigatorio")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            missao_nome: str = _get_missao_nome(cur, missao_id)
            cur.execute(
                "UPDATE smo.fracao_missoes "
                "SET missao_id = %s "
                "WHERE missao_nome_raw = %s AND missao_id IS NULL "
                "RETURNING id",
                (missao_id, texto),
            )
            atualizadas: int = len(cur.fetchall())
        conn.commit()
        return AplicacaoResult(
            missao_id=missao_id,
            missao_nome=missao_nome,
            fracoes_atualizadas=atualizadas,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Escrita: criar missao nova + aplicar (transacao atomica)
# ---------------------------------------------------------------------------


def criar_e_aplicar(
    nome: str, descricao: str | None, texto: str,
) -> CriacaoResult:
    """Cria missao nova e ja aplica ao texto — 1 transacao.

    Rollback em qualquer erro garante que nao sobra missao orfa se o UPDATE
    falhar. O nome e normalizado (UPPER + sem acento) antes do insert,
    alinhado ao `catalogo_service.criar_missao`.
    """
    if not texto or len(texto) > MAX_TEXTO_LEN:
        raise ValueError("texto invalido")
    nome_limpo: str = (nome or "").strip()
    if not nome_limpo:
        raise ValueError("nome obrigatorio")
    if len(nome_limpo) > MAX_NOME_LEN:
        raise ValueError(f"nome excede {MAX_NOME_LEN} caracteres")
    nome_final: str = normalizar(nome_limpo)
    if not nome_final:
        raise ValueError("nome invalido apos normalizacao")

    descricao_final: str | None = None
    if descricao is not None:
        d: str = descricao.strip()
        if len(d) > MAX_DESCRICAO_LEN:
            raise ValueError(f"descricao excede {MAX_DESCRICAO_LEN} caracteres")
        descricao_final = d or None

    # Payload apenas para validacao estatica — o INSERT usa valores ja tratados.
    _payload: MissaoCreate = {"nome": nome_final, "descricao": descricao_final}
    _ = _payload

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO smo.missoes (nome, descricao) "
                    "VALUES (%s, %s) "
                    "RETURNING id, nome",
                    (nome_final, descricao_final),
                )
            except psycopg2.errors.UniqueViolation as exc:
                conn.rollback()
                raise ValueError(
                    f"Missao '{nome_final}' ja cadastrada"
                ) from exc
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                raise RuntimeError("Falha ao inserir missao")
            novo_id: str = str(row["id"])
            novo_nome: str = cast(str, row["nome"])

            cur.execute(
                "UPDATE smo.fracao_missoes "
                "SET missao_id = %s "
                "WHERE missao_nome_raw = %s AND missao_id IS NULL "
                "RETURNING id",
                (novo_id, texto),
            )
            atualizadas: int = len(cur.fetchall())
        conn.commit()
        return CriacaoResult(
            missao_id=novo_id,
            missao_nome=novo_nome,
            fracoes_atualizadas=atualizadas,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Desfazer: reversao cirurgica de aplicar / criar
# ---------------------------------------------------------------------------


def desfazer_aplicacao(
    texto: str, missao_id: str, remover_missao: bool = False,
) -> DesfazerResult:
    """Desfaz a acao cirurgicamente: zera `missao_id` apenas onde texto E id
    batem. Opcionalmente tenta remover a missao (util apos '+ Nova'); a
    remocao so ocorre se NAO houver outras fracoes ainda referenciando
    aquela missao (protecao contra apagar missao usada em outro contexto).
    """
    if not texto or len(texto) > MAX_TEXTO_LEN:
        raise ValueError("texto invalido")
    if not missao_id:
        raise ValueError("missao_id obrigatorio")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE smo.fracao_missoes "
                "SET missao_id = NULL "
                "WHERE missao_nome_raw = %s AND missao_id = %s "
                "RETURNING id",
                (texto, missao_id),
            )
            revertidas: int = len(cur.fetchall())

            missao_removida: bool = False
            if remover_missao:
                cur.execute(
                    "DELETE FROM smo.missoes "
                    "WHERE id = %s "
                    "  AND NOT EXISTS ("
                    "    SELECT 1 FROM smo.fracao_missoes WHERE missao_id = %s"
                    "  )",
                    (missao_id, missao_id),
                )
                missao_removida = bool(cur.rowcount)
        conn.commit()
        return DesfazerResult(
            texto=texto,
            missao_id=missao_id,
            fracoes_revertidas=revertidas,
            missao_removida=missao_removida,
        )
    finally:
        conn.close()
