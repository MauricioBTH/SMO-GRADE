"""Fase 4 — Analytics de cabecalho: media movel, tendencia, sazonalidade, indicadores."""

import pandas as pd
import numpy as np


def _build_dataframe(cabecalho: list[dict]) -> pd.DataFrame:
    """Converte lista de dicts do banco em DataFrame com data parseada."""
    if not cabecalho:
        return pd.DataFrame()

    df = pd.DataFrame(cabecalho)

    # Normalizar data: dd/mm/yyyy -> datetime
    if "data" in df.columns:
        df["data_dt"] = pd.to_datetime(
            df["data"], format="%d/%m/%Y", errors="coerce"
        )
        # Fallback yyyy-mm-dd
        mask_nat = df["data_dt"].isna()
        if mask_nat.any():
            df.loc[mask_nat, "data_dt"] = pd.to_datetime(
                df.loc[mask_nat, "data"], format="%Y-%m-%d", errors="coerce"
            )
        df = df.dropna(subset=["data_dt"])
        df = df.sort_values("data_dt")

    return df


CAMPOS_NUMERICOS: list[str] = [
    "efetivo_total", "oficiais", "sargentos", "soldados",
    "vtrs", "motos", "armas_ace", "armas_portateis", "armas_longas", "animais",
]


def calcular_media_movel(
    cabecalho: list[dict], janela: int = 7
) -> dict[str, list[dict]]:
    """Media movel por unidade para cada campo numerico.

    Retorna: { unidade: [ { data, campo1, campo1_mm, ... } ] }
    """
    df = _build_dataframe(cabecalho)
    if df.empty:
        return {}

    resultado: dict[str, list[dict]] = {}

    for unidade, grupo in df.groupby("unidade"):
        grupo = grupo.sort_values("data_dt").copy()
        registros: list[dict] = []

        for campo in CAMPOS_NUMERICOS:
            if campo in grupo.columns:
                grupo[campo] = pd.to_numeric(grupo[campo], errors="coerce").fillna(0)
                grupo[f"{campo}_mm"] = (
                    grupo[campo].rolling(window=janela, min_periods=1).mean().round(1)
                )

        for _, row in grupo.iterrows():
            registro: dict = {"data": row["data"]}
            for campo in CAMPOS_NUMERICOS:
                if campo in grupo.columns:
                    registro[campo] = int(row[campo])
                    registro[f"{campo}_mm"] = float(row[f"{campo}_mm"])
            registros.append(registro)

        resultado[str(unidade)] = registros

    return resultado


def calcular_tendencia(cabecalho: list[dict]) -> dict[str, dict[str, dict]]:
    """Tendencia linear (coeficiente angular) por unidade e campo.

    Retorna: { unidade: { campo: { coef, direcao } } }
    """
    df = _build_dataframe(cabecalho)
    if df.empty:
        return {}

    resultado: dict[str, dict[str, dict]] = {}

    for unidade, grupo in df.groupby("unidade"):
        grupo = grupo.sort_values("data_dt").copy()
        tendencias: dict[str, dict] = {}

        x = np.arange(len(grupo), dtype=np.float64)
        if len(x) < 2:
            resultado[str(unidade)] = {}
            continue

        for campo in CAMPOS_NUMERICOS:
            if campo not in grupo.columns:
                continue
            y = pd.to_numeric(grupo[campo], errors="coerce").fillna(0).values.astype(np.float64)
            coef = float(np.polyfit(x, y, 1)[0])
            direcao = "crescente" if coef > 0.1 else ("decrescente" if coef < -0.1 else "estavel")
            tendencias[campo] = {"coef": round(coef, 3), "direcao": direcao}

        resultado[str(unidade)] = tendencias

    return resultado


def calcular_sazonalidade(cabecalho: list[dict]) -> dict[str, list[dict]]:
    """Media por mes para cada unidade e campo.

    Retorna: { unidade: [ { mes, mes_label, campo1_media, ... } ] }
    """
    df = _build_dataframe(cabecalho)
    if df.empty:
        return {}

    MESES_LABEL = [
        "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez",
    ]

    resultado: dict[str, list[dict]] = {}

    for unidade, grupo in df.groupby("unidade"):
        grupo = grupo.copy()
        grupo["mes"] = grupo["data_dt"].dt.month

        for campo in CAMPOS_NUMERICOS:
            if campo in grupo.columns:
                grupo[campo] = pd.to_numeric(grupo[campo], errors="coerce").fillna(0)

        medias_mes = grupo.groupby("mes")[CAMPOS_NUMERICOS].mean().round(1)
        registros: list[dict] = []

        for mes_num in sorted(medias_mes.index):
            registro: dict = {
                "mes": int(mes_num),
                "mes_label": MESES_LABEL[int(mes_num)] if int(mes_num) < len(MESES_LABEL) else str(mes_num),
            }
            for campo in CAMPOS_NUMERICOS:
                registro[f"{campo}_media"] = float(medias_mes.loc[mes_num, campo])
            registros.append(registro)

        resultado[str(unidade)] = registros

    return resultado


def calcular_indicadores(cabecalho: list[dict]) -> dict[str, dict]:
    """Indicadores por unidade: media, ultimo valor, variacao percentual.

    Retorna: { unidade: { campo: { media, ultimo, variacao_pct } } }
    """
    df = _build_dataframe(cabecalho)
    if df.empty:
        return {}

    resultado: dict[str, dict] = {}

    for unidade, grupo in df.groupby("unidade"):
        grupo = grupo.sort_values("data_dt").copy()
        indicadores: dict[str, dict] = {}

        for campo in CAMPOS_NUMERICOS:
            if campo not in grupo.columns:
                continue
            valores = pd.to_numeric(grupo[campo], errors="coerce").fillna(0)
            media = float(valores.mean().round(1))
            ultimo = int(valores.iloc[-1]) if len(valores) > 0 else 0
            primeiro = int(valores.iloc[0]) if len(valores) > 0 else 0
            variacao_pct = (
                round(((ultimo - primeiro) / primeiro) * 100, 1)
                if primeiro != 0
                else 0.0
            )
            indicadores[campo] = {
                "media": media,
                "ultimo": ultimo,
                "variacao_pct": variacao_pct,
            }

        resultado[str(unidade)] = indicadores

    return resultado
