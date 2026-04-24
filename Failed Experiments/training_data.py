import pandas as pd
import numpy as np
from negative_pertubration import snap_md_eligibility

############################################
# 1. Eligibility calculator (port of snap_md_eligibility)
############################################
def snap_md_eligibility(df: pd.DataFrame) -> pd.DataFrame:
    # 1. fill missing numerics with 0
    vars_zero_if_na = [
        "FSDEPDED", "FSMEDDED", "FSCSDED",
        "FSSLTEXP", "FSEARN", "FSUNEARN", "FSBENSUPP"
    ]
    for v in vars_zero_if_na:
        if v in df.columns:
            df[v] = df[v].fillna(0)

    # 2. constants by fiscal year
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

    # map YRMONTH (yyyyMM) -> fiscal year
    def fy_from_ym(ym):
        ym = int(ym)
        yr = ym // 100
        mo = ym % 100
        if mo >= 10:  # Oct-Dec counts as next FY
            yr += 1
        return str(yr)

    fy = fy_from_ym(df.iloc[0]["YRMONTH"])
    const = FY_CONST[fy]

    fpl100      = const["fpl100"]
    fpl200      = 2 * fpl100
    std_table   = const["std"]
    shelter_cap = const["shelter_cap"]
    max_allot   = const["max_allot"]
    min_benefit = 23

    # helper: standard deduction by HH size
    # std_table is [193,193,193,225,258,258] etc
    # R version did a weird bracket mapping; this is equivalent to "cap at 6"
    def std_from_size(size_arr):
        idx = np.minimum(size_arr, 6) - 1  # 0-based index
        idx = np.clip(idx, 0, len(std_table)-1)
        return std_table[idx]

    # household size, clipped to 6 for table lookups
    hhsize = df["CERTHHSZ"].clip(upper=6).astype(int)

    gross = df["FSEARN"] + df["FSUNEARN"]
    earned_ded = np.floor(0.20 * df["FSEARN"])
    std_ded_v = std_from_size(hhsize)

    adj_income = np.floor(
        gross
        - earned_ded
        - std_ded_v
        - df["FSDEPDED"]
        - df["FSMEDDED"]
    )

    # apply HCSUA and shelter cap logic
    HCSUA_FY23 = 557  # this is MD-specific constant in your R code
    FSSLTEXP_eff = np.minimum(df["FSSLTEXP"] + HCSUA_FY23, 2000)

    excess_shelter = np.maximum(0, FSSLTEXP_eff - np.floor(0.5 * adj_income))
    excess_shelter = np.floor(np.minimum(excess_shelter, shelter_cap))

    net_income = adj_income - excess_shelter

    # eligibility flags
    # index into fpl arrays by hh size
    # fpl100[i] is for household size i+1
    gross_limit = fpl200[hhsize.values - 1]
    net_limit   = fpl100[hhsize.values - 1]

    pass_gross = gross <= gross_limit
    pass_net   = net_income <= net_limit

    # BBCE simplification from your code:
    eligible = pass_gross

    # benefit calculation
    thirty_pct = np.floor(0.30 * net_income)
    allot = max_allot[hhsize.values - 1]
    prelim_ben = allot - thirty_pct

    benefit = np.where(
        hhsize <= 2,
        np.maximum(prelim_ben, min_benefit),
        np.maximum(prelim_ben, 0)
    )
    benefit = np.ceil(benefit)
    benefit[~eligible] = 0

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


############################################
# 2. Load CSV and filter by state + time
############################################
# path: update to your server path
raw = pd.read_csv("/home/dev/Masters_Thesis/Neuro_Symbolic/qc_pub_fy2023_2.csv")

# keep only the columns you used in R
keep_cols = [
    "YRMONTH", "STATENAME", "CERTHHSZ",
    "FSDEPDED", "FSMEDDED", "FSSLTEXP", "FSEARN",
    "FSUNEARN", "FSDIS", "FSELDER", "HHLDNO",
    "HOMELESS_DED", "FSBENSUPP", "FSBEN",
    "MED_DED_DEMO", "FSCSDED"
]
df = raw[keep_cols].copy()

# Maryland version:
md = df[(df["STATENAME"] == "Maryland") & (df["YRMONTH"] > 202212)].copy()

# basic cleaning 
for col in ["FSELDER", "FSDIS"]:
    if col in md.columns:
        md[col] = md[col].fillna(0).astype(int)  # R used factor; int is fine here

md = md.fillna(0)


############################################
# 3. Evaluate eligibility for the filtered data
############################################
pos = snap_md_eligibility(md)
pos["DENIAL_CODE"] = "NA"
pos["IS_APPROVED"] = 1  # all real QC records are approved


############################################
# 4. Generate synthetic ineligible cases by perturbing rules
############################################
def generate_negatives(df_pos, neg_ratio=3, seed=42):
    """
    Rough Python port of generate_negatives_2023():
    - sample approved cases
    - push one or more key variables so they break a rule
    - re-check eligibility
    - keep only those now ineligible
    """
    rng = np.random.default_rng(seed)

    # FY23 constants (Maryland-style); keep aligned with the R version
    fpl_100     = np.array([13590,18310,23030,27750,32470,37190]) / 12
    fpl_200     = 2 * fpl_100
    shelter_cap = 624

    neg_rows = []

    # iterate by household size like you did in R
    for hhsize_val in [1,2,3,4,5,6]:
        subset = df_pos[df_pos["CERTHHSZ"] == hhsize_val]
        if subset.empty:
            continue

        target_n = len(subset) * neg_ratio
        made = 0

        while made < target_n:
            base = subset.sample(n=1, replace=True, random_state=rng.integers(1e9)).copy()
            base = base.reset_index(drop=True)

            # compute baseline metrics
            base_eval = snap_md_eligibility(base.copy())
            gross0 = float(base_eval.loc[0, "gross"])
            net0   = float(base_eval.loc[0, "net_income"])
            exc0   = float(base_eval.loc[0, "excess_shelter"])

            # determine which rules are still passable and thus breakable
            applicable = []
            # break gross income test
            if gross0 <= fpl_200[min(hhsize_val,6)-1]:
                applicable.append("EXCESS_GROSS")
            # break net income test
            if net0 <= fpl_100[min(hhsize_val,6)-1]:
                applicable.append("EXCESS_NET")
            # break shelter cap-related part
            if exc0 < shelter_cap:
                applicable.append("SHELTER_CAP")

            if not applicable:
                continue

            # pick 1+ rules to break
            n_muts = rng.integers(low=1, high=len(applicable)+1)
            chosen = list(rng.choice(applicable, size=n_muts, replace=False))

            cand = base.copy()

            # apply chosen mutators, similar to R code
            if "EXCESS_GROSS" in chosen:
                # push earned income up past 200% FPL gross threshold
                gap = fpl_200[min(hhsize_val,6)-1] - gross0
                if not np.isnan(gap) and gap > 0:
                    cand["FSEARN"] = cand["FSEARN"].astype(float)
                    cand.loc[0, "FSEARN"] = int(round(cand.loc[0, "FSEARN"] + gap + rng.integers(50,100)))

            if "EXCESS_NET" in chosen:
                gap = fpl_100[min(hhsize_val,6)-1] - net0
                if not np.isnan(gap) and gap > 0:
                    cand["FSUNEARN"] = cand["FSUNEARN"].astype(float)
                    cand.loc[0, "FSUNEARN"] = int(round(cand.loc[0, "FSUNEARN"] + gap + rng.integers(50,100)))

            if "SHELTER_CAP" in chosen:
                gap = shelter_cap - exc0
                if not np.isnan(gap) and gap > 0:
                    cand["FSSLTEXP"] = cand["FSSLTEXP"].astype(float)
                    cand.loc[0, "FSSLTEXP"] = int(round(cand.loc[0, "FSSLTEXP"] + gap + rng.integers(50,100)))

            # mild random jitter to other deductions just like your 0.8–1.2 idea
            for col in ["FSDEPDED", "FSMEDDED"]:
                if col in cand.columns:
                    cand.loc[0, col] = cand.loc[0, col] * rng.uniform(0.8, 1.2)

            # evaluate the mutated row with the real eligibility rules
            out_eval = snap_md_eligibility(cand.copy())

            if not bool(out_eval.loc[0, "eligible"]):
                # mark denial reason
                fails = []
                if not bool(out_eval.loc[0, "pass_gross"]):
                    fails.append("EXCESS_GROSS")
                if not bool(out_eval.loc[0, "pass_net"]):
                    fails.append("EXCESS_NET")
                # only add shelter_cap if shelter actually contributed
                if float(out_eval.loc[0, "excess_shelter"]) >= shelter_cap and (not bool(out_eval.loc[0, "pass_net"])):
                    fails.append("SHELTER_CAP")

                cand["DENIAL_CODE"] = "+".join(sorted(set(fails))) if fails else "UNKNOWN"
                cand["IS_APPROVED"] = 0
                neg_rows.append(cand.iloc[0].to_dict())
                made += 1

    neg_df = pd.DataFrame(neg_rows)
    return neg_df


############################################
# 5. Build negatives and merge
############################################
neg_df = generate_negatives(pos)

# pos are all approved cases
pos_for_train = pos.copy()
pos_for_train["IS_APPROVED"] = 1
pos_for_train["DENIAL_CODE"] = "NA"

# stack positives + negatives
train_df = pd.concat([pos_for_train, neg_df], ignore_index=True)

# optional: drop obvious NAs
train_df = train_df.fillna(0)

############################################
# 6. train_df is now ready for:
#    - modeling,
#    - LLM explanation,
#    - audit.
############################################

print(train_df.head())
print(train_df[["IS_APPROVED", "DENIAL_CODE"]].value_counts())