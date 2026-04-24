import pandas as pd
import numpy as np

def snap_md_eligibility(df: pd.DataFrame) -> pd.DataFrame:
    """Replicates SNAP eligibility logic for Maryland / California FY23–25."""

    # ---- 1. Fill missing numerics with 0
    vars_zero_if_na = [
        "FSDEPDED", "FSMEDDED", "FSCSDED",
        "FSSLTEXP", "FSEARN", "FSUNEARN", "FSBENSUPP"
    ]
    for v in vars_zero_if_na:
        if v in df.columns:
            df[v] = df[v].fillna(0)

    # ---- 2. Constants FY23–25
    FY_CONST = {
        "2023": dict(
            fpl100=np.array([13590,18310,23030,27750,32470,37190]) / 12,
            std=np.array([193,193,193,225,258,258]),
            shelter_cap=624,
            max_allot=np.array([281,516,740,939,1116,1339])
        ),
        "2024": dict(
            fpl100=np.array([14680,19860,25040,30220,35400,40580]) / 12,
            std=np.array([198,198,198,208,244,279]),
            shelter_cap=672,
            max_allot=np.array([291,535,766,973,1155,1386])
        ),
        "2025": dict(
            fpl100=np.array([15650,21150,26650,32150,37650,43150]) / 12,
            std=np.array([204,204,204,219,255,291]),
            shelter_cap=712,
            max_allot=np.array([291,535,766,975,1155,1386])
        ),
    }

    # ---- 3. Map YRMONTH → FY
    def fy_from_ym(ym):
        yr, mo = divmod(int(ym), 100)
        if mo >= 10: yr += 1
        return str(yr)

    fy = fy_from_ym(df.iloc[0]["YRMONTH"])
    const = FY_CONST[fy]

    fpl100, std_table, shelter_cap, max_allot = (
        const["fpl100"], const["std"], const["shelter_cap"], const["max_allot"]
    )
    fpl200 = 2 * fpl100
    min_benefit = 23

    # ---- 4. Core computation
    hhsize = df["CERTHHSZ"].clip(upper=6).astype(int)
    gross = df["FSEARN"] + df["FSUNEARN"]
    earned_ded = np.floor(0.20 * df["FSEARN"])
    std_ded_v = np.take(std_table, np.minimum(hhsize, 6) - 1)

    adj_income = np.floor(
        gross - earned_ded - std_ded_v
        - df["FSDEPDED"] - df["FSMEDDED"]
    )

    HCSUA_FY23 = 557
    FSSLTEXP = np.minimum(df["FSSLTEXP"] + HCSUA_FY23, 2000)
    excess_shelter = np.floor(np.minimum(
        np.maximum(0, FSSLTEXP - np.floor(0.5 * adj_income)),
        shelter_cap
    ))
    net_income = adj_income - excess_shelter

    # ---- 5. Eligibility checks
    pass_gross = gross <= np.take(fpl200, hhsize - 1)
    pass_net = net_income <= np.take(fpl100, hhsize - 1)
    eligible = pass_gross  # BBCE simplification

    # ---- 6. Benefit computation
    thirty_pct = np.floor(0.30 * net_income)
    prelim_ben = np.take(max_allot, hhsize - 1) - thirty_pct
    benefit = np.where(
        hhsize <= 2,
        np.maximum(prelim_ben, min_benefit),
        np.maximum(prelim_ben, 0)
    )
    benefit = np.ceil(benefit)
    benefit[~eligible] = 0

    # ---- 7. Return augmented DataFrame
    out = df.copy()
    out["gross"] = gross
    out["earned_ded"] = earned_ded
    out["std_ded"] = std_ded_v
    out["adj_income"] = adj_income
    out["excess_shelter"] = excess_shelter
    out["net_income"] = net_income
    out["pass_gross"] = pass_gross
    out["pass_net"] = pass_net
    out["eligible"] = eligible
    out["benefit_calc"] = benefit

    return out
