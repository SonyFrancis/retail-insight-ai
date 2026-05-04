import os
import math
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd

# Reproducibility
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# Partner → store mapping
# Each partner owns a subset of stores across regions
PARTNER_STORE_MAP = {
    "PARTNER_001": ["S001", "S002", "S003", "S004"],   # North-heavy
    "PARTNER_002": ["S005", "S006", "S007", "S008"],   # South-heavy
    "PARTNER_003": ["S009", "S010", "S011", "S012"],   # East-heavy
    "PARTNER_004": ["S013", "S014", "S015", "S016"],   # West-heavy
    "PARTNER_005": ["S017", "S018", "S019", "S020"],   # Mixed
    "PARTNER_006": ["S021", "S022", "S023", "S024"],   # Mixed
    "PARTNER_007": ["S025", "S026", "S027", "S028"],   # Mixed
    "PARTNER_008": ["S029", "S030", "S031", "S032"],   # Mixed
    "PARTNER_009": ["S033", "S034"],                   # Small partner
}

# Reverse map: store_id → partner_id
STORE_PARTNER_MAP = {
    store: partner
    for partner, stores in PARTNER_STORE_MAP.items()
    for store in stores
}


def ensure_dirs():
    os.makedirs("app/data/raw", exist_ok=True)


def make_calendar(start_weeks_ago=104, weeks=104):
    """
    Produce a weekly calendar ending last week (Sunday-based).
    Returns a DataFrame with 'date' (period end).
    """
    today = datetime.today()
    # Align to most recent Sunday (end of ISO week)
    end = today - relativedelta(days=today.weekday() + 1)  # Sunday
    start = end - relativedelta(weeks=weeks - 1)

    dates = pd.date_range(start=start, periods=weeks, freq="W-SUN")
    cal = pd.DataFrame({"date": dates})
    cal["year"] = cal["date"].dt.year
    cal["week"] = cal["date"].dt.isocalendar().week.astype(int)
    cal["month"] = cal["date"].dt.month
    cal["year_week"] = cal["date"].dt.strftime("%G-W%V")
    return cal


def sample_catalog():
    regions = ["North", "South", "East", "West"]
    stores_per_region = {"North": 8, "South": 10, "East": 7, "West": 9}

    categories = {
        "Electronics": ["Mobiles", "Laptops", "Accessories"],
        "Home": ["Furniture", "Kitchen", "Decor"],
        "Grocery": ["Beverages", "Snacks", "Dairy"],
        "Fashion": ["Menswear", "Womenswear", "Footwear"],
    }

    # Create product catalog
    rows = []
    pid = 1000
    for cat, subs in categories.items():
        for sub in subs:
            for i in range(30):  # ~30 SKUs per subcategory
                base_price = {
                    "Electronics": np.random.uniform(100, 800),
                    "Home": np.random.uniform(40, 300),
                    "Grocery": np.random.uniform(1, 10),
                    "Fashion": np.random.uniform(15, 120),
                }[cat]
                rows.append(
                    {
                        "product_id": f"P{pid}",
                        "category": cat,
                        "subcategory": sub,
                        "base_price": round(base_price, 2),
                    }
                )
                pid += 1
    catalog = pd.DataFrame(rows)

    # Stores
    stores = []
    sid = 1
    for r in regions:
        for _ in range(stores_per_region[r]):
            stores.append({"store_id": f"S{sid:03d}", "region": r})
            sid += 1
    stores = pd.DataFrame(stores)
    return catalog, stores


def weekly_seasonality(week):
    """
    Smooth yearly seasonality by week number.
    """
    # Map week 1..53 -> angle on a circle
    angle = 2 * math.pi * (week / 52.0)
    base = 1 + 0.18 * math.sin(angle - 0.6)  # general seasonality
    # Festive uplift
    festive_boost = 0.15 if week >= 46 or week <= 1 else 0.0
    # Early-year dip
    early_dip = -0.08 if 10 <= week <= 14 else 0.0
    return max(0.75, base + festive_boost + early_dip)


def monthly_effect(month, category):
    """
    Category-dependent monthly effects (e.g., fashion in Mar/Apr for weddings,
    electronics in Oct/Nov for festivals, home in May/Jun, grocery steady).
    """
    effects = 1.0
    if category == "Electronics" and month in (10, 11):  # Diwali season
        effects += 0.20
    if category == "Home" and month in (5, 6):
        effects += 0.10
    if category == "Fashion" and month in (3, 4):
        effects += 0.12
    if category == "Grocery" and month in (6, 7, 8):  # cool drinks/snacks
        effects += 0.08
    return effects


def promo_schedule(cal: pd.DataFrame, intensity=0.12, p_any=0.18):
    """
    Randomly mark some weeks as promo weeks with intensity factor.
    Returns dict date->promo_flag and date->promo_intensity.
    """
    flags = {}
    intensities = {}
    for d in cal["date"]:
        if np.random.rand() < p_any:
            flags[d] = 1
            # promo intensity between 8% and ~20%
            intensities[d] = np.random.uniform(0.08, intensity + 0.1)
        else:
            flags[d] = 0
            intensities[d] = 0.0
    return flags, intensities


def inject_anomalies(df, frac=0.002):
    """
    Random point anomalies: sudden spikes/drops in units for realism.
    """
    n = len(df)
    k = max(1, int(n * frac))
    idx = np.random.choice(df.index, size=k, replace=False)
    # +/- 40–80% perturbation
    shock = np.random.uniform(0.4, 0.8, size=k)
    signs = np.random.choice([-1, 1], size=k)
    df.loc[idx, "units"] = (df.loc[idx, "units"] * (1 + signs * shock)).clip(lower=0)
    return df


def generate_data():
    ensure_dirs()
    cal = make_calendar(weeks=104)  # 2 years weekly
    catalog, stores = sample_catalog()

    # print("Calendar sample ----\n", cal.head(3))
    # print("catalog sample ----\n", catalog.head(3))
    # print("stores sample ----\n", stores.head(3))

    promo_flag, promo_intensity = promo_schedule(cal)

    # Cross join calendar x (store x product-sample)
    # To keep dataset size reasonable, sample a subset of products per store
    products_per_store = 120  # adjust for size
    catalog_sampled = (
        catalog.sample(n=min(products_per_store, len(catalog)), random_state=RANDOM_SEED)
        .reset_index(drop=True)
    )

    store_prod = stores.assign(key=1).merge(
        catalog_sampled.assign(key=1), on="key", how="left"
    ).drop(columns="key")

    base_rows = cal.assign(key=1).merge(store_prod.assign(key=1), on="key").drop(columns="key")

    # Demand drivers
    # Base category demand scale (units)
    cat_base_units = {
        "Electronics": 4.0,
        "Home": 6.0,
        "Grocery": 25.0,
        "Fashion": 10.0,
    }

    rows = []
    for _, r in base_rows.iterrows():
        week = int(r["week"])
        month = int(r["month"])

        # Base demand per category with seasonality
        base_units = cat_base_units[r["category"]]
        seas = weekly_seasonality(week) * monthly_effect(month, r["category"])

        # Store/regional random effect
        region_factor = {
            "North": 1.05,
            "South": 1.10,
            "East": 0.95,
            "West": 1.00,
        }[r["region"]]
        store_noise = np.random.normal(1.0, 0.08)

        # Price around base with small drift
        price = r["base_price"] * np.random.uniform(0.95, 1.08)

        # Promo effect: higher units, slightly lower price
        pf = promo_flag[r["date"]]
        pint = promo_intensity[r["date"]]
        promo_uplift = 1.0 + (pint * np.random.uniform(0.8, 1.2)) if pf else 1.0
        promo_price_cut = (1.0 - min(0.15, pint * 0.6)) if pf else 1.0

        # Stockout chance slightly higher in promo weeks
        stockout = 1 if (np.random.rand() < (0.05 + 0.07 * pf)) else 0

        # Long-term growth trend by category
        weeks_since_start = (r["date"] - cal["date"].min()).days / 7

        category_growth = {
            "Electronics": 0.0015,  # ~15% annual growth
            "Fashion": -0.0008,     # slow decline
            "Home": 0.0005,         # mild growth
            "Grocery": 0.0          # stable
        }.get(r["category"], 0)

        growth_multiplier = 1 + (weeks_since_start * category_growth)


        # Units before stockout
        units_demand = base_units * seas * region_factor * store_noise * promo_uplift * growth_multiplier

        # Price elasticity: if price above base, slight reduction in demand (elasticity ~ -0.3)
        elasticity = -0.3
        price_ratio = price / r["base_price"]
        units_demand *= price_ratio ** elasticity

        # Add noise and floor
        units = max(0, np.random.normal(units_demand, max(0.5, units_demand * 0.15)))

        # Stockout effect: clamp to 40–75% of demand if stockout occurs
        if stockout:
            units *= np.random.uniform(0.4, 0.75)

        # Apply promo price cut at the end
        final_price = round(price * promo_price_cut, 2)

        # Revenue
        revenue = final_price * units

        # Returns: a small rate, slightly higher in Electronics/Fashion (fit/defects)
        base_ret_rate = 0.01
        cat_ret_bump = {"Electronics": 0.012, "Fashion": 0.006}.get(r["category"], 0.0)
        ret_rate = base_ret_rate + cat_ret_bump + np.random.uniform(-0.003, 0.003)
        returns_units = max(0, np.random.poisson(lam=max(0.0, units * ret_rate)))
        returns_revenue = returns_units * final_price

        rows.append(
            {
                "date": r["date"].date(),
                "partner_id": STORE_PARTNER_MAP.get(r["store_id"], "UNKNOWN"),  # ← ADD
                "store_id": r["store_id"],
                "region": r["region"],
                "category": r["category"],
                "subcategory": r["subcategory"],
                "product_id": r["product_id"],
                "price": round(final_price, 2),
                "units": round(units, 2),
                "revenue": round(revenue, 2),
                "promo_flag": pf,
                "promo_intensity": round(pint, 3),
                "stockouts": stockout,
                "returns_units": int(returns_units),
                "returns_revenue": round(returns_revenue, 2),
            }
        )

    df = pd.DataFrame(rows)

    # Inject random anomalies (spikes/drops)
    df = inject_anomalies(df, frac=0.002)

    # Basic sorting and types
    df = df.sort_values(["date", "partner_id", "store_id", "category", "subcategory", "product_id"]).reset_index(drop=True)

    # Validate no store fell through mapping
    unknown_count = (df["partner_id"] == "UNKNOWN").sum()
    if unknown_count > 0:
        print(f"⚠️  WARNING: {unknown_count} rows have no partner mapping")
    else:
        print("✅ All stores mapped to partners")
        
    # Save
    out_path = "app/data/raw/sales.csv"
    df.to_csv(out_path, index=False)
    print(f"✅ Generated dataset: {out_path}")
    print(f"Rows: {len(df):,} | Date range: {df['date'].min()} → {df['date'].max()}")
    print(f"Partners: {df['partner_id'].nunique()} | Stores: {df['store_id'].nunique()}")
    print(df.head(5))


if __name__ == "__main__":
    generate_data()
