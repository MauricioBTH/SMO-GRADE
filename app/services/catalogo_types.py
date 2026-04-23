"""Tipos de dominio dos catalogos (CRPMs, municipios, missoes) + normalizador."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import TypedDict


@dataclass(frozen=True)
class Crpm:
    id: str
    sigla: str
    nome: str
    sede: str | None
    ordem: int
    ativo: bool


@dataclass(frozen=True)
class Municipio:
    id: str
    nome: str
    crpm_id: str
    crpm_sigla: str
    ativo: bool


@dataclass(frozen=True)
class Missao:
    id: str
    nome: str
    descricao: str | None
    ativo: bool


@dataclass(frozen=True)
class Bpm:
    """Batalhao de Policia Militar. Em POA (CPC) ha 6 BPMs; extensivel a
    outras regioes no futuro — o municipio_id vinculado faz o recorte."""
    id: str
    codigo: str       # "1 BPM", "20 BPM"
    numero: int       # 1, 20 — para ordenacao determinista
    municipio_id: str


@dataclass(frozen=True)
class Unidade:
    """Unidade operacional do CPChq (BPChq 1-6 + 4 RPMon). Fase 6.4.1:
    municipio_sede_id permite derivar municipio das missoes em quartel
    (Prontidao/Pernoite/Retorno) quando nao trazem municipio na linha.
    """
    id: str
    nome: str
    nome_normalizado: str
    municipio_sede_id: str
    ativo: bool


class MissaoCreate(TypedDict, total=False):
    nome: str
    descricao: str | None


class MissaoUpdate(TypedDict, total=False):
    nome: str
    descricao: str | None
    ativo: bool


class MunicipioCreate(TypedDict, total=False):
    nome: str
    crpm_id: str


class MunicipioUpdate(TypedDict, total=False):
    nome: str
    crpm_id: str
    ativo: bool


class CrpmCreate(TypedDict, total=False):
    sigla: str
    nome: str
    sede: str | None
    ordem: int


class CrpmUpdate(TypedDict, total=False):
    sigla: str
    nome: str
    sede: str | None
    ordem: int
    ativo: bool


def normalizar(texto: str) -> str:
    """Uppercase + sem acentos + trim + espacos colapsados. Usado em lookups."""
    if not texto:
        return ""
    sem_acento: str = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sem_acento.strip().upper().split())
