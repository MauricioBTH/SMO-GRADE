"""Anti-regressao: SELECT sobre smo.fracoes/smo.cabecalho deve usar `_atuais`.

Racional (Fase 6.5.b): toda query nova de leitura em `app/services/` ou
`app/routes/` deve usar as views `smo.fracoes_atuais` / `smo.cabecalho_atuais`
— elas ja filtram `deletado_em IS NULL`. Usar a tabela crua em uma query de
leitura expõe linhas soft-deletadas e quebra a fase 6.5.b silenciosamente
(sem erro de execucao — apenas dados fantasmas no analytics).

Exceções *legítimas* que listamos aqui, com racional:

- `upload_service.contar_linhas_upload` — conta TODAS as linhas (ativas +
  soft-deletadas) vinculadas a um upload específico. É exatamente esse o
  contrato: "quantas linhas tinha essa versao do upload?". Usa `WHERE
  upload_id = %s`, portanto não pode vazar linhas de outros uploads.

Qualquer nova excecao precisa ser adicionada aqui *com justificativa* — o
default é "use a view".
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DIRS_COBERTOS: tuple[Path, ...] = (
    REPO_ROOT / "app" / "services",
    REPO_ROOT / "app" / "routes",
)

# Padrao: FROM <schema>.<tabela> onde tabela e 'fracoes' ou 'cabecalho' sem o
# sufixo '_atuais'. `\b` na borda evita casar 'fracoes_atuais' ou 'fracao_*'.
PADRAO_LEAK = re.compile(
    r"FROM\s+smo\.(fracoes|cabecalho)\b(?!_atuais)",
    re.IGNORECASE,
)

# Arquivos autorizados a ler direto da tabela crua. Caminho relativo ao repo.
ARQUIVOS_PERMITIDOS: frozenset[str] = frozenset({
    # contar_linhas_upload precisa somar linhas soft-deletadas.
    "app/services/upload_service.py",
})


def _arquivos_python(dirs: tuple[Path, ...]) -> list[Path]:
    arquivos: list[Path] = []
    for d in dirs:
        arquivos.extend(d.rglob("*.py"))
    return sorted(arquivos)


def test_leitura_usa_views_atuais() -> None:
    """Falha se algum SELECT em app/ usa smo.fracoes/smo.cabecalho cruas."""
    ofensores: list[str] = []
    for arq in _arquivos_python(DIRS_COBERTOS):
        rel: str = arq.relative_to(REPO_ROOT).as_posix()
        if rel in ARQUIVOS_PERMITIDOS:
            continue
        texto: str = arq.read_text(encoding="utf-8")
        for n_linha, linha in enumerate(texto.splitlines(), start=1):
            if PADRAO_LEAK.search(linha):
                ofensores.append(f"{rel}:{n_linha}: {linha.strip()}")
    if ofensores:
        msg: str = (
            "Queries de leitura devem usar smo.fracoes_atuais / "
            "smo.cabecalho_atuais (veja tests/test_sem_leak_deletado.py). "
            "Se a leitura direto da tabela crua e intencional (ex.: "
            "contagem que precisa incluir soft-deletes), adicione o arquivo "
            "em ARQUIVOS_PERMITIDOS com justificativa.\n\nOfensores:\n  "
            + "\n  ".join(ofensores)
        )
        raise AssertionError(msg)
