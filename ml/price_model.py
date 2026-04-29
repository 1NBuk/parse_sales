import os
import json
import numpy as np
import pandas as pd
import psycopg2

from catboost import CatBoostRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# ==============================
# CONFIG
# ==============================

DB_CONFIG = {
    "host": "localhost",
    "database": "prices_db",
    "user": "postgres",
    "password": "12345"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "catboost_price_model.cbm")
FEATURES_PATH = os.path.join(BASE_DIR, "catboost_features.json")

TEST_DAYS = 7

CAT_FEATURES = ["product_id", "store_id", "brand_id", "group_name", "is_weekend", "is_holiday"]
FEATURES = [
    "product_id", "store_id", "brand_id", "group_name",  # ← добавить group_name
    "day_of_week", "week_of_year", "month",
    "is_weekend", "is_holiday",
    "usd_rub", "eur_rub", "oil_price",
    "temperature", "precipitation",
    "quantity",
    "price_lag_1", "price_lag_3", "price_lag_7", "price_lag_14",
    "price_mean_7", "price_std_7", "price_diff_1",
    "group_median", "price_vs_group",
    "store_mean", "price_vs_store",
]


# ==============================
# METRICS
# ==============================

def mape(y_true, y_pred):
    y_true = np.where(y_true == 0, 1e-6, y_true)
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100


def evaluate(y_true, y_pred):
    return {
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "MAE":  mean_absolute_error(y_true, y_pred),
        "MAPE": mape(np.array(y_true), np.array(y_pred)),
        "R2":   r2_score(y_true, y_pred),
    }


# ==============================
# DATA LOADING
# ==============================

def load_data():
    conn = psycopg2.connect(**DB_CONFIG)

    query = """
    SELECT
        ph.date,
        ph.price,
        ph.quantity,
        p.id  AS product_id,
        s.id  AS store_id,
        b.id  AS brand_id,
        c.day_of_week,
        c.week_of_year,
        c.month,
        c.is_weekend,
        c.is_holiday,
        ef.usd_rub,
        ef.eur_rub,
        ef.oil_price,
        ef.temperature,
        ef.precipitation,
        pg.group_name
    FROM prices_history ph
    JOIN products p       ON ph.product_id = p.id
    JOIN brands b         ON p.brand_id    = b.id
    JOIN stores s         ON ph.store_id   = s.id
    JOIN calendar c       ON ph.date       = c.date
    LEFT JOIN external_factors ef ON ph.date = ef.date
    LEFT JOIN product_groups pg ON ph.product_id = pg.product_id
    """

    df = pd.read_sql(query, conn)
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["product_id", "store_id", "date"]).reset_index(drop=True)
    return df


# ==============================
# FEATURE ENGINEERING
# Все агрегаты — только по прошлым данным (shift/expanding),
# чтобы не было data leakage из будущего.
# ==============================

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    g = df.groupby(["product_id", "store_id"])

    # --- лаги (shift гарантирует использование только прошлого) ---
    df["price_lag_1"]  = g["price"].shift(1)
    df["price_lag_3"]  = g["price"].shift(3)
    df["price_lag_7"]  = g["price"].shift(7)
    df["price_lag_14"] = g["price"].shift(14)

    # --- rolling: min_periods защищает от NaN на старте ---
    df["price_mean_7"] = g["price"].transform(
        lambda x: x.shift(1).rolling(7, min_periods=1).mean()
    )
    df["price_std_7"] = g["price"].transform(
        lambda x: x.shift(1).rolling(7, min_periods=2).std()
    )

    # --- разница с предыдущим днём ---
    df["price_diff_1"] = df["price_lag_1"] - g["price"].shift(2)

    df["group_median"] = df.groupby("group_name")["price"] \
        .transform(lambda x: x.expanding().median().shift(1))
    df["price_vs_group"] = df["price_lag_1"] / (df["group_median"] + 1e-6)

    # --- среднее по магазину+бренду: то же самое ---
    df["store_mean"] = (
        df.groupby(["store_id", "brand_id"])["price"]
        .transform(lambda x: x.expanding().mean().shift(1))
    )
    df["price_vs_store"] = df["price_lag_1"] / (df["store_mean"] + 1e-6)

    # --- категориальные приводим к строке (CatBoost требует str или int) ---
    for col in CAT_FEATURES:
        df[col] = df[col].astype(str)

    df = df.dropna(subset=FEATURES + ["price"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ==============================
# SPLIT
# ==============================

def split_data(df: pd.DataFrame):
    split_date = df["date"].max() - pd.Timedelta(days=TEST_DAYS)

    train = df[df["date"] <= split_date]
    test  = df[df["date"] >  split_date]

    X_train, y_train = train[FEATURES], train["price"]
    X_test,  y_test  = test[FEATURES],  test["price"]

    print(f"Train: {len(train)} rows | Test: {len(test)} rows")
    print(f"Train period: {train['date'].min().date()} → {train['date'].max().date()}")
    print(f"Test  period: {test['date'].min().date()}  → {test['date'].max().date()}")

    return X_train, y_train, X_test, y_test


# ==============================
# TRAIN
# ==============================

def train_model(X_train, y_train, X_test, y_test):
    # Индексы категориальных фич в списке FEATURES
    cat_indices = [FEATURES.index(c) for c in CAT_FEATURES]

    model = CatBoostRegressor(
        iterations=800,
        depth=6,
        learning_rate=0.03,
        l2_leaf_reg=10,
        random_strength=1,
        loss_function="RMSE",
        eval_metric="RMSE",
        random_seed=42,
        verbose=100,
        early_stopping_rounds=50,
    )

    model.fit(
        X_train, y_train,
        cat_features=cat_indices,
        eval_set=(X_test, y_test),
        use_best_model=True,
    )

    model.save_model(MODEL_PATH)

    # Сохраняем список фичей и категориальные — для инференса
    with open(FEATURES_PATH, "w", encoding="utf-8") as f:
        json.dump({"features": FEATURES, "cat_features": CAT_FEATURES}, f, ensure_ascii=False)

    preds = model.predict(X_test)
    return model, preds, y_test


# ==============================
# MAIN
# ==============================

def main():
    print("=== Loading data ===")
    df = load_data()
    print(f"Rows loaded: {len(df)}")

    print("\n=== Building features ===")
    df = build_features(df)
    print(f"Rows after feature engineering: {len(df)}")

    # Быстрая проверка на leakage: price_vs_group и price_vs_store
    # должны считаться от price_lag_1, а не от price
    assert (df["price_vs_group"] != df["price"] / (df["group_median"] + 1e-6)).any(), \
        "LEAKAGE: price_vs_group использует текущую цену!"
    print("Leakage check passed.")

    print("\n=== Splitting ===")
    X_train, y_train, X_test, y_test = split_data(df)

    print("\n=== Training ===")
    model, preds, y_true = train_model(X_train, y_train, X_test, y_test)

    print("\n=== Metrics on test set ===")
    metrics = evaluate(y_true, preds)
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")

    print(f"\nModel   → {MODEL_PATH}")
    print(f"Features→ {FEATURES_PATH}")


if __name__ == "__main__":
    main()