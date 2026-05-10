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
    "product_id", "store_id", "brand_id", "group_name",
    "day_of_week", "week_of_year", "month",
    "is_weekend", "is_holiday",
    "temperature",
    "quantity",

    "price_lag_1", "price_lag_3", "price_lag_7", "price_lag_14",
    "price_mean_7", "price_std_7", "price_median_7",

    "price_trend_3", "price_trend_7",
    "price_diff_1",
    "price_cv_7",

    "group_store_median",
    "price_vs_group",

    "store_mean",
    "price_vs_store",
]
BAD_TRIPLES = [
    (363, 170, 7),
    (329, 238, 13),
    (7941, 238, 5),
    (662, 57, 5),
    (7925, 170, 11),
    (36, 170, 5),
    (710, 170, 5),
    (7941, 251, 5),
]
# ==============================
# METRICS
# ==============================

def mape(y_true, y_pred):
    y_true = np.where(y_true < 10, 10, y_true)
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100


def evaluate(y_true, y_pred):
    return {
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "MAE": mean_absolute_error(y_true, y_pred),
        "MAPE": mape(y_true, y_pred),
        "R2": r2_score(y_true, y_pred),
    }


# ==============================
# LOAD DATA
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
        ef.temperature,
        pg.group_name
    FROM prices_history ph
    JOIN products p ON ph.product_id = p.id
    JOIN brands b ON p.brand_id = b.id
    JOIN stores s ON ph.store_id = s.id
    JOIN calendar c ON ph.date = c.date
    LEFT JOIN external_factors ef ON ph.date = ef.date
    LEFT JOIN product_groups pg ON ph.product_id = pg.product_id
    """

    df = pd.read_sql(query, conn)
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["product_id", "store_id", "date"]).reset_index(drop=True)
    df = df[df["group_name"] != "семена"]
    return df


# ==============================
# CLEAN DATA (КРИТИЧНО)
# ==============================

def clean_data(df):
    df = df.copy()

    # --- убираем мусорные цены ---
    df = df[df["price"] > 5]
    df = df[df["price"] < df["price"].quantile(0.99)]

    # --- заполняем quantity ---
    df["quantity"] = df.groupby("product_id")["quantity"].transform(
        lambda x: x.fillna(x.median())
    )

    # --- интерполяция цены ---
    df["price"] = df.groupby(["product_id", "store_id"])["price"].transform(
        lambda x: x.interpolate()
    )

    return df


# ==============================
# FEATURE ENGINEERING
# ==============================

def build_features(df):
    df = df.copy()

    g = df.groupby(["product_id", "store_id"])

    # --- лаги ---
    df["price_lag_1"] = g["price"].shift(1)
    df["price_lag_3"] = g["price"].shift(3)
    df["price_lag_7"] = g["price"].shift(7)
    df["price_lag_14"] = g["price"].shift(14)

    # --- rolling ---
    df["price_mean_7"] = g["price"].transform(lambda x: x.shift(1).rolling(7, min_periods=1).mean())
    df["price_std_7"] = g["price"].transform(lambda x: x.shift(1).rolling(7, min_periods=2).std())
    df["price_median_7"] = g["price"].transform(lambda x: x.shift(1).rolling(7, min_periods=1).median())

    # --- тренды ---
    df["price_trend_3"] = df["price_lag_1"] - df["price_lag_3"]
    df["price_trend_7"] = df["price_lag_1"] - df["price_lag_7"]

    # --- volatility ---
    df["price_cv_7"] = df["price_std_7"] / (df["price_mean_7"] + 1e-6)

    # --- diff ---
    df["price_diff_1"] = df["price_lag_1"] - g["price"].shift(2)

    # --- групповые фичи ---
    df["group_store_median"] = df.groupby(["group_name", "store_id"])["price"] \
        .transform(lambda x: x.shift(1).expanding().median())

    df["price_vs_group"] = df["price_lag_1"] / (df["group_store_median"] + 1e-6)

    df["store_mean"] = df.groupby(["store_id", "brand_id"])["price"] \
        .transform(lambda x: x.shift(1).expanding().mean())

    df["price_vs_store"] = df["price_lag_1"] / (df["store_mean"] + 1e-6)

    # --- лог таргет ---
    df["price_log"] = np.log1p(df["price"])

    # --- категории ---
    for col in CAT_FEATURES:
        df[col] = df[col].astype(str)

    df = df.dropna(subset=FEATURES + ["price_log"])

    return df


# ==============================
# SPLIT
# ==============================

def split_data(df):
    split_date = df["date"].max() - pd.Timedelta(days=TEST_DAYS)

    train = df[df["date"] <= split_date]
    test = df[df["date"] > split_date]

    return train, test


# ==============================
# TRAIN
# ==============================

def train_model(train, test):
    train = train.copy()

    train["weight"] = 1.0

    mask = train.set_index(["product_id", "store_id", "brand_id"]).index.isin(BAD_TRIPLES)

    train.loc[mask, "weight"] = 0.1
    X_train = train[FEATURES]
    y_train = train["price_log"]

    X_test = test[FEATURES]
    y_test = test["price_log"]

    cat_idx = [FEATURES.index(c) for c in CAT_FEATURES]

    weights = 1 / (np.expm1(y_train) + 1)

    model = CatBoostRegressor(
        iterations=800,
        depth=6,
        learning_rate=0.03,
        l2_leaf_reg=10,
        loss_function="RMSE",
        eval_metric="RMSE",
        early_stopping_rounds=50,
        verbose=100
    )

    model.fit(
        X_train, y_train,
        cat_features=cat_idx,
        eval_set=(X_test, y_test),
        sample_weight=train["weight"],
        use_best_model=True
    )

    preds_log = model.predict(X_test)

    preds = np.expm1(preds_log)
    y_true = np.expm1(y_test)

    return model, preds, y_true, X_test


# ==============================
# MAIN
# ==============================

def main():
    print("=== LOAD ===")
    df = load_data()

    print("=== CLEAN ===")
    df = clean_data(df)

    print("=== FEATURES ===")
    df = build_features(df)

    print("=== SPLIT ===")
    train, test = split_data(df)

    print("=== TRAIN ===")
    model, preds, y_true, X_test = train_model(train, test)

    print("=== METRICS ===")
    metrics = evaluate(y_true, preds)
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}")

    # --- анализ ошибок ---
    df_test = X_test.copy()
    df_test["true"] = y_true
    df_test["pred"] = preds
    df_test["error"] = abs(df_test["true"] - df_test["pred"])

    print("\nTOP ERRORS:")
    print(df_test.sort_values("error", ascending=False).head(20))

    model.save_model(MODEL_PATH)

    with open(FEATURES_PATH, "w") as f:
        json.dump({"features": FEATURES, "cat_features": CAT_FEATURES}, f)



if __name__ == "__main__":
    main()