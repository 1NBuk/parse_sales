"""
ml/retrain.py

Ежедневное дообучение CatBoost.
Запускается из Airflow DAG или напрямую: python -m ml.retrain

Что делает:
  1. Загружает данные из PostgreSQL (весь накопленный датасет)
  2. Чистит, строит признаки — аналогично оригинальному price_model.py
  3. Обучает CatBoost, используя последние TEST_DAYS как валидацию
  4. Сохраняет метрики в таблицу model_metrics
  5. Если MAPE > порога — отправляет алерт в Telegram
  6. Сохраняет модель с версионированием (дата + время)
  7. Обновляет симлинк catboost_latest.cbm
"""

import os
import json
import logging
import shutil
from datetime import datetime

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
import requests
from catboost import CatBoostRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "prices_db"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR  = os.path.join(BASE_DIR, "models")
LATEST_LINK = os.path.join(MODELS_DIR, "catboost_latest.cbm")

MAPE_THRESHOLD = float(os.getenv("MAPE_THRESHOLD", 15.0))   # % — порог алерта
TEST_DAYS      = 7

CAT_FEATURES = ["product_id", "store_id", "brand_id", "group_name", "is_weekend", "is_holiday"]

FEATURES = [
    "product_id", "store_id", "brand_id", "group_name",
    "day_of_week", "week_of_year", "month",
    "is_weekend", "is_holiday",
    "temperature", "quantity",
    "price_lag_1", "price_lag_3", "price_lag_7", "price_lag_14",
    "price_mean_7", "price_std_7", "price_median_7",
    "price_trend_3", "price_trend_7",
    "price_diff_1", "price_cv_7",
    "group_store_median", "price_vs_group",
    "store_mean", "price_vs_store",
]

# Проблемные тройки (product_id, store_id, brand_id) с пониженным весом
BAD_TRIPLES = [
    (363, 170, 7), (329, 238, 13), (7941, 238, 5),
    (662, 57, 5),  (7925, 170, 11), (36, 170, 5),
    (710, 170, 5), (7941, 251, 5),
]

os.makedirs(MODELS_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def mape(y_true, y_pred):
    y_true = np.where(y_true < 10, 10, y_true)
    return float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)


def evaluate(y_true, y_pred) -> dict:
    return {
        "mae":  float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mape": mape(y_true, y_pred),
        "r2":   float(r2_score(y_true, y_pred)),
    }


def send_telegram_alert(message: str):
    token   = os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        log.warning("TELEGRAM_TOKEN или TELEGRAM_CHAT_ID не заданы — алерт пропущен")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        log.info("Telegram алерт отправлен")
    except Exception as e:
        log.error(f"Ошибка отправки Telegram алерта: {e}")


# ──────────────────────────────────────────────
# LOAD
# ──────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    log.info("Загрузка данных из PostgreSQL...")
    query = """
        SELECT
            ph.date,
            ph.price,
            ph.quantity,
            p.id   AS product_id,
            s.id   AS store_id,
            b.id   AS brand_id,
            c.day_of_week,
            c.week_of_year,
            c.month,
            c.is_weekend,
            c.is_holiday,
            ef.temperature,
            pg.group_name
        FROM prices_history ph
        JOIN products p       ON ph.product_id = p.id
        JOIN brands b         ON p.brand_id = b.id
        JOIN stores s         ON ph.store_id = s.id
        JOIN calendar c       ON ph.date = c.date
        LEFT JOIN external_factors ef ON ph.date = ef.date
        LEFT JOIN product_groups pg   ON ph.product_id = pg.product_id
    """
    with get_conn() as conn:
        df = pd.read_sql(query, conn)

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["product_id", "store_id", "date"]).reset_index(drop=True)
    df = df[df["group_name"] != "семена"]
    log.info(f"Загружено строк: {len(df)}")
    return df


# ──────────────────────────────────────────────
# CLEAN
# ──────────────────────────────────────────────

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["price"] > 5]
    df = df[df["price"] < df["price"].quantile(0.99)]
    df["quantity"] = df.groupby("product_id")["quantity"].transform(
        lambda x: x.fillna(x.median())
    )
    df["price"] = df.groupby(["product_id", "store_id"])["price"].transform(
        lambda x: x.interpolate()
    )
    log.info(f"После очистки: {len(df)} строк")
    return df


# ──────────────────────────────────────────────
# FEATURES
# ──────────────────────────────────────────────

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    g = df.groupby(["product_id", "store_id"])

    df["price_lag_1"]  = g["price"].shift(1)
    df["price_lag_3"]  = g["price"].shift(3)
    df["price_lag_7"]  = g["price"].shift(7)
    df["price_lag_14"] = g["price"].shift(14)

    df["price_mean_7"]   = g["price"].transform(lambda x: x.shift(1).rolling(7, min_periods=1).mean())
    df["price_std_7"]    = g["price"].transform(lambda x: x.shift(1).rolling(7, min_periods=2).std())
    df["price_median_7"] = g["price"].transform(lambda x: x.shift(1).rolling(7, min_periods=1).median())

    df["price_trend_3"] = df["price_lag_1"] - df["price_lag_3"]
    df["price_trend_7"] = df["price_lag_1"] - df["price_lag_7"]
    df["price_cv_7"]    = df["price_std_7"] / (df["price_mean_7"] + 1e-6)
    df["price_diff_1"]  = df["price_lag_1"] - g["price"].shift(2)

    df["group_store_median"] = df.groupby(["group_name", "store_id"])["price"].transform(
        lambda x: x.shift(1).expanding().median()
    )
    df["price_vs_group"] = df["price_lag_1"] / (df["group_store_median"] + 1e-6)

    df["store_mean"]    = df.groupby(["store_id", "brand_id"])["price"].transform(
        lambda x: x.shift(1).expanding().mean()
    )
    df["price_vs_store"] = df["price_lag_1"] / (df["store_mean"] + 1e-6)

    df["price_log"] = np.log1p(df["price"])

    for col in CAT_FEATURES:
        df[col] = df[col].astype(str)

    df = df.dropna(subset=FEATURES + ["price_log"])
    log.info(f"После feature engineering: {len(df)} строк")
    return df


# ──────────────────────────────────────────────
# SPLIT
# ──────────────────────────────────────────────

def split_data(df: pd.DataFrame):
    split_date = df["date"].max() - pd.Timedelta(days=TEST_DAYS)
    train = df[df["date"] <= split_date]
    test  = df[df["date"] > split_date]
    log.info(f"Train: {len(train)}, Test: {len(test)}")
    return train, test


# ──────────────────────────────────────────────
# TRAIN
# ──────────────────────────────────────────────

def train_model(train: pd.DataFrame, test: pd.DataFrame):
    train = train.copy()
    idx   = train.set_index(["product_id", "store_id", "brand_id"]).index
    mask  = idx.isin(BAD_TRIPLES)
    train.loc[mask, "weight"] = 0.1
    train["weight"] = train.get("weight", 1.0).fillna(1.0)

    X_train, y_train = train[FEATURES], train["price_log"]
    X_test,  y_test  = test[FEATURES],  test["price_log"]
    cat_idx  = [FEATURES.index(c) for c in CAT_FEATURES]

    # Проверяем: есть ли уже обученная модель для warm-start
    init_model = None
    if os.path.exists(LATEST_LINK):
        try:
            init_model = CatBoostRegressor()
            init_model.load_model(LATEST_LINK)
            log.info("Warm-start: загружена предыдущая модель")
        except Exception as e:
            log.warning(f"Не удалось загрузить предыдущую модель: {e}")
            init_model = None

    model = CatBoostRegressor(
        iterations=800,
        depth=6,
        learning_rate=0.03,
        l2_leaf_reg=10,
        loss_function="RMSE",
        eval_metric="RMSE",
        early_stopping_rounds=50,
        verbose=100,
        # если есть предыдущая модель — дообучаем поверх неё
        **({"init_model": init_model} if init_model else {}),
    )

    model.fit(
        X_train, y_train,
        cat_features=cat_idx,
        eval_set=(X_test, y_test),
        sample_weight=train["weight"],
        use_best_model=True,
    )

    preds  = np.expm1(model.predict(X_test))
    y_true = np.expm1(y_test)
    return model, preds, y_true


# ──────────────────────────────────────────────
# SAVE METRICS
# ──────────────────────────────────────────────

def save_metrics(metrics: dict, version: str, train_size: int, test_size: int,
                 iterations_used: int, degraded: bool):
    query = """
        INSERT INTO model_metrics
            (model_version, mae, rmse, mape, r2, train_size, test_size, iterations_used, degraded)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (
                version,
                metrics["mae"],
                metrics["rmse"],
                metrics["mape"],
                metrics["r2"],
                train_size,
                test_size,
                iterations_used,
                degraded,
            ))
        conn.commit()
    log.info("Метрики сохранены в model_metrics")


# ──────────────────────────────────────────────
# VERSIONING
# ──────────────────────────────────────────────

def save_model(model: CatBoostRegressor) -> tuple[str, str]:
    version   = datetime.now().strftime("%Y-%m-%d_%H-%M")
    model_path = os.path.join(MODELS_DIR, f"catboost_{version}.cbm")
    model.save_model(model_path)

    # обновляем "latest" — просто копируем (симлинки ненадёжны в Docker volumes)
    shutil.copy2(model_path, LATEST_LINK)

    # оставляем только последние 7 версий
    _cleanup_old_models(keep=7)

    log.info(f"Модель сохранена: {model_path}")
    log.info(f"Симлинк обновлён: {LATEST_LINK}")
    return model_path, version


def _cleanup_old_models(keep: int = 7):
    files = sorted(
        [f for f in os.listdir(MODELS_DIR) if f.startswith("catboost_") and f != "catboost_latest.cbm"],
        reverse=True,
    )
    for old_file in files[keep:]:
        os.remove(os.path.join(MODELS_DIR, old_file))
        log.info(f"Удалена старая модель: {old_file}")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    log.info("=== RETRAIN START ===")

    df    = load_data()
    df    = clean_data(df)
    df    = build_features(df)
    train, test = split_data(df)

    model, preds, y_true = train_model(train, test)
    metrics = evaluate(y_true, preds)

    for k, v in metrics.items():
        log.info(f"{k.upper()}: {v:.4f}")

    model_path, version = save_model(model)
    degraded = metrics["mape"] > MAPE_THRESHOLD

    save_metrics(
        metrics    = metrics,
        version    = version,
        train_size = len(train),
        test_size  = len(test),
        iterations_used = model.best_iteration_ or 0,
        degraded   = degraded,
    )

    if degraded:
        msg = (
            f"⚠️ Деградация модели!\n"
            f"Версия: {version}\n"
            f"MAPE: {metrics['mape']:.2f}% (порог: {MAPE_THRESHOLD}%)\n"
            f"MAE:  {metrics['mae']:.2f}\n"
            f"RMSE: {metrics['rmse']:.2f}"
        )
        log.warning(msg)
        send_telegram_alert(msg)
    else:
        log.info(f"Качество в норме. MAPE={metrics['mape']:.2f}%")

    log.info("=== RETRAIN DONE ===")
    return metrics


if __name__ == "__main__":
    main()