import pandas as pd
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path("app/data/raw/sales.csv")

@lru_cache(maxsize=1)
def load_sales_data() -> pd.DataFrame:
    """
    Load sales CSV once and cache in memory.
    lru_cache means the CSV is read once per process lifetime.
    """
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    print(f"✅ Sales data loaded: {len(df):,} rows")
    return df

def get_partner_data(partner_id: str, metric: str = "revenue") -> pd.DataFrame:
    """Filter sales data for a specific partner."""
    df = load_sales_data()
    partner_df = df[df["partner_id"] == partner_id].copy()
    if partner_df.empty:
        raise ValueError(f"No data found for partner_id: {partner_id}")
    return partner_df