"""Fase 4 — Analytics de fracoes: missoes, fracoes, cobertura horaria, padroes."""

import pandas as pd
import numpy as np


def _build_dataframe(fracoes: list[dict]) -> pd.DataFrame:
    """Converte lista de dicts do banco em DataFrame com data parseada."""
    if not fracoes:
        return pd.DataFrame()

    df = pd.DataFrame(fracoes)

    if "data" in df.columns:
        df["data_dt"] = pd.to_datetime(
            df["data"], format="%d/%m/%Y", errors="coerce"
        )
        mask_nat = df["data_dt"].isna()
        if mask_nat.any():
            df.loc[mask_nat, "data_dt"] = pd.to_datetime(
                df.loc[mask_nat, "data"], format="%Y-%m-%d", errors="coerce"
            )
        df = df.dropna(subset=["data_dt"])
        df = df.sort_values("data_dt")

    for col in ["equipes", "pms"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return df


def _parse_horario(h: str) -> float:
    """Converte 'HH:MM' em horas decimais. Retorna NaN se invalido."""
    if not h or not isinstance(h, str):
        return float("nan")
    partes = h.strip().split(":")
    if len(partes) < 2:
        return float("nan")
    try:
        return int(partes[0]) + int(partes[1]) / 60.0
    except (ValueError, TypeError):
        return float("nan")


def analisar_missoes(fracoes: list[dict]) -> dict:
    """Frequencia de missoes: quais se repetem, cresceram ou diminuiram.

    Retorna: {
        ranking: [ { missao, total, pms_total, equipes_total } ],
        evolucao: { missao: [ { data, count, pms } ] }
    }
    """
    df = _build_dataframe(fracoes)
    if df.empty:
        return {"ranking": [], "evolucao": {}}

    df["missao_norm"] = df["missao"].fillna("").str.strip().str.upper()
    df = df[df["missao_norm"] != ""]

    # Ranking geral
    ranking_df = (
        df.groupby("missao_norm")
        .agg(total=("missao_norm", "size"), pms_total=("pms", "sum"), equipes_total=("equipes", "sum"))
        .sort_values("total", ascending=False)
        .head(20)
        .reset_index()
    )
    ranking = [
        {
            "missao": str(row["missao_norm"]),
            "total": int(row["total"]),
            "pms_total": int(row["pms_total"]),
            "equipes_total": int(row["equipes_total"]),
        }
        for _, row in ranking_df.iterrows()
    ]

    # Evolucao por data (top 10 missoes)
    top_missoes = [r["missao"] for r in ranking[:10]]
    evolucao: dict[str, list[dict]] = {}

    for missao in top_missoes:
        sub = df[df["missao_norm"] == missao]
        por_data = (
            sub.groupby("data")
            .agg(count=("missao_norm", "size"), pms=("pms", "sum"))
            .reset_index()
        )
        evolucao[missao] = [
            {"data": str(row["data"]), "count": int(row["count"]), "pms": int(row["pms"])}
            for _, row in por_data.iterrows()
        ]

    return {"ranking": ranking, "evolucao": evolucao}


def analisar_fracoes_freq(fracoes: list[dict]) -> dict:
    """Frequencia de fracoes por unidade.

    Retorna: {
        por_unidade: { unidade: [ { fracao, total, pms_total } ] },
        geral: [ { fracao, total, pms_total } ]
    }
    """
    df = _build_dataframe(fracoes)
    if df.empty:
        return {"por_unidade": {}, "geral": []}

    df["fracao_norm"] = df["fracao"].fillna("").str.strip()
    df = df[df["fracao_norm"] != ""]

    # Por unidade
    por_unidade: dict[str, list[dict]] = {}
    for unidade, grupo in df.groupby("unidade"):
        freq = (
            grupo.groupby("fracao_norm")
            .agg(total=("fracao_norm", "size"), pms_total=("pms", "sum"))
            .sort_values("total", ascending=False)
            .reset_index()
        )
        por_unidade[str(unidade)] = [
            {"fracao": str(row["fracao_norm"]), "total": int(row["total"]), "pms_total": int(row["pms_total"])}
            for _, row in freq.iterrows()
        ]

    # Geral
    freq_geral = (
        df.groupby("fracao_norm")
        .agg(total=("fracao_norm", "size"), pms_total=("pms", "sum"))
        .sort_values("total", ascending=False)
        .head(20)
        .reset_index()
    )
    geral = [
        {"fracao": str(row["fracao_norm"]), "total": int(row["total"]), "pms_total": int(row["pms_total"])}
        for _, row in freq_geral.iterrows()
    ]

    return {"por_unidade": por_unidade, "geral": geral}


def analisar_cobertura_horaria(fracoes: list[dict]) -> dict:
    """Distribuicao de emprego por faixa horaria (turno).

    Retorna: {
        por_turno: [ { turno, total_fracoes, pms_total, equipes_total } ],
        por_unidade_turno: { unidade: [ { turno, total, pms } ] },
        horas_cobertura: [ { hora (0-23), pms_medio } ]
    }
    """
    df = _build_dataframe(fracoes)
    if df.empty:
        return {"por_turno": [], "por_unidade_turno": {}, "horas_cobertura": []}

    # Classificar turno a partir do horario_inicio
    df["hora_inicio"] = df["horario_inicio"].apply(_parse_horario)
    df["hora_fim"] = df["horario_fim"].apply(_parse_horario)

    def _classificar_turno(hora: float) -> str:
        if pd.isna(hora):
            return "indefinido"
        if hora < 12:
            return "manha"
        if hora < 18:
            return "tarde"
        return "noite"

    df["turno_calc"] = df["hora_inicio"].apply(_classificar_turno)

    # Por turno (geral)
    por_turno_df = (
        df.groupby("turno_calc")
        .agg(total_fracoes=("turno_calc", "size"), pms_total=("pms", "sum"), equipes_total=("equipes", "sum"))
        .sort_index()
        .reset_index()
    )
    por_turno = [
        {
            "turno": str(row["turno_calc"]),
            "total_fracoes": int(row["total_fracoes"]),
            "pms_total": int(row["pms_total"]),
            "equipes_total": int(row["equipes_total"]),
        }
        for _, row in por_turno_df.iterrows()
    ]

    # Por unidade/turno
    por_unidade_turno: dict[str, list[dict]] = {}
    for unidade, grupo in df.groupby("unidade"):
        turno_grupo = (
            grupo.groupby("turno_calc")
            .agg(total=("turno_calc", "size"), pms=("pms", "sum"))
            .reset_index()
        )
        por_unidade_turno[str(unidade)] = [
            {"turno": str(row["turno_calc"]), "total": int(row["total"]), "pms": int(row["pms"])}
            for _, row in turno_grupo.iterrows()
        ]

    # Cobertura por hora (0-23): PMs medio empregados naquela hora
    dias_unicos = df["data_dt"].nunique() if "data_dt" in df.columns else 1
    horas_cobertura: list[dict] = []

    for hora in range(24):
        mask = (df["hora_inicio"] <= hora) & (df["hora_fim"] > hora)
        pms_na_hora = df.loc[mask, "pms"].sum()
        pms_medio = round(pms_na_hora / max(dias_unicos, 1), 1)
        horas_cobertura.append({"hora": hora, "pms_medio": pms_medio})

    return {
        "por_turno": por_turno,
        "por_unidade_turno": por_unidade_turno,
        "horas_cobertura": horas_cobertura,
    }


def analisar_padroes_diarios(fracoes: list[dict]) -> dict:
    """Padroes por dia da semana: emprego medio.

    Retorna: {
        por_dia_semana: [ { dia (0=seg..6=dom), dia_label, fracoes_media, pms_medio } ]
    }
    """
    df = _build_dataframe(fracoes)
    if df.empty:
        return {"por_dia_semana": []}

    DIAS_LABEL = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]

    df["dia_semana"] = df["data_dt"].dt.dayofweek  # 0=Monday

    # Agrupar por data primeiro, depois media por dia da semana
    por_data = (
        df.groupby(["data_dt", "dia_semana"])
        .agg(fracoes_count=("dia_semana", "size"), pms_total=("pms", "sum"))
        .reset_index()
    )

    por_dia = (
        por_data.groupby("dia_semana")
        .agg(fracoes_media=("fracoes_count", "mean"), pms_medio=("pms_total", "mean"))
        .round(1)
        .reset_index()
    )

    resultado = [
        {
            "dia": int(row["dia_semana"]),
            "dia_label": DIAS_LABEL[int(row["dia_semana"])] if int(row["dia_semana"]) < 7 else "?",
            "fracoes_media": float(row["fracoes_media"]),
            "pms_medio": float(row["pms_medio"]),
        }
        for _, row in por_dia.iterrows()
    ]

    return {"por_dia_semana": resultado}


def analisar_concentracao(fracoes: list[dict]) -> dict:
    """Concentracao de PMs e equipes por missao e fracao ao longo do tempo.

    Retorna: {
        por_missao: [ { missao, pms_medio_dia, equipes_medio_dia } ],
        por_fracao: [ { fracao, pms_medio_dia, equipes_medio_dia } ]
    }
    """
    df = _build_dataframe(fracoes)
    if df.empty:
        return {"por_missao": [], "por_fracao": []}

    dias_unicos = df["data_dt"].nunique() if "data_dt" in df.columns else 1

    # Por missao
    df["missao_norm"] = df["missao"].fillna("").str.strip().str.upper()
    missao_agg = (
        df[df["missao_norm"] != ""]
        .groupby("missao_norm")
        .agg(pms_soma=("pms", "sum"), equipes_soma=("equipes", "sum"))
        .reset_index()
    )
    missao_agg["pms_medio_dia"] = (missao_agg["pms_soma"] / max(dias_unicos, 1)).round(1)
    missao_agg["equipes_medio_dia"] = (missao_agg["equipes_soma"] / max(dias_unicos, 1)).round(1)
    missao_agg = missao_agg.sort_values("pms_medio_dia", ascending=False).head(15)

    por_missao = [
        {
            "missao": str(row["missao_norm"]),
            "pms_medio_dia": float(row["pms_medio_dia"]),
            "equipes_medio_dia": float(row["equipes_medio_dia"]),
        }
        for _, row in missao_agg.iterrows()
    ]

    # Por fracao
    df["fracao_norm"] = df["fracao"].fillna("").str.strip()
    fracao_agg = (
        df[df["fracao_norm"] != ""]
        .groupby("fracao_norm")
        .agg(pms_soma=("pms", "sum"), equipes_soma=("equipes", "sum"))
        .reset_index()
    )
    fracao_agg["pms_medio_dia"] = (fracao_agg["pms_soma"] / max(dias_unicos, 1)).round(1)
    fracao_agg["equipes_medio_dia"] = (fracao_agg["equipes_soma"] / max(dias_unicos, 1)).round(1)
    fracao_agg = fracao_agg.sort_values("pms_medio_dia", ascending=False).head(15)

    por_fracao = [
        {
            "fracao": str(row["fracao_norm"]),
            "pms_medio_dia": float(row["pms_medio_dia"]),
            "equipes_medio_dia": float(row["equipes_medio_dia"]),
        }
        for _, row in fracao_agg.iterrows()
    ]

    return {"por_missao": por_missao, "por_fracao": por_fracao}
