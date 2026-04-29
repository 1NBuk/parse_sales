import os
import numpy as np
import pandas as pd
import psycopg2

from xgboost import XGBRegressor

from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

DB_CONFIG = {
    "host": "localhost",
    "database": "prices_db",
    "user": "postgres",
    "password": "12345"
}

MODEL_PATH = "xgb_price_model.json"
TEST_DAYS = 7


def mape(y_true, y_pred):
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100


def evaluate(y_true, y_pred):
    return {
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "MAE": mean_absolute_error(y_true, y_pred),
        "MAPE": mape(y_true, y_pred),
        "R2": r2_score(y_true, y_pred)
    }


def load_data():
    conn = psycopg2.connect(**DB_CONFIG)

    query = """
    SELECT
        ph.date,
        ph.price,
        ph.quantity,
        p.id as product_id,
        s.id as store_id,
        b.id as brand_id,
        c.day_of_week,
        c.week_of_year,
        c.month,
        c.is_weekend,
        c.is_holiday,
        ef.usd_rub,
        ef.eur_rub,
        ef.oil_price,
        ef.temperature,
        ef.precipitation
    FROM prices_history ph
    JOIN products p ON ph.product_id = p.id
    JOIN brands b ON p.brand_id = b.id
    JOIN stores s ON ph.store_id = s.id
    JOIN calendar c ON ph.date = c.date
    LEFT JOIN external_factors ef ON ph.date = ef.date
    """

    df = pd.read_sql(query, conn)
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["product_id", "store_id", "date"])

    return df


def build_features(df):
    g = df.groupby(["product_id", "store_id"])

    df["price_lag_7"] = g["price"].shift(7)

    df["price_mean_7"] = g["price"].transform(lambda x: x.rolling(7).mean())
    df["price_std_7"] = g["price"].transform(lambda x: x.rolling(7).std())

    df["price_diff"] = df["price"] - df["price_lag_7"]

    df["group_median"] = df.groupby("brand_id")["price"].transform(lambda x: x.expanding().median().shift(1))

    df["price_vs_group"] = df["price"] / df["group_median"]

    df["store_mean"] = df.groupby(["store_id", "brand_id"])["price"].transform(lambda x: x.expanding().mean().shift(1))

    df["price_vs_store"] = df["price"] / df["store_mean"]

    df = df.dropna()

    return df


def split_data(df):
    split_date = df["date"].max() - pd.Timedelta(days=TEST_DAYS)

    train = df[df["date"] <= split_date]
    test = df[df["date"] > split_date]

    features = [
        "product_id",
        "store_id",
        "brand_id",
        "day_of_week",
        "week_of_year",
        "month",
        "is_weekend",
        "is_holiday",
        "usd_rub",
        "eur_rub",
        "oil_price",
        "temperature",
        "precipitation",
        "price_lag_7",
        "price_mean_7",
        "price_std_7",
        "group_median",
        "price_vs_group",
        "store_mean",
        "price_vs_store"
    ]

    X_train = train[features]
    y_train = train["price"]

    X_test = test[features]
    y_test = test["price"]

    return X_train, y_train, X_test, y_test


def train_model(X_train, y_train, X_test, y_test):

    X_train = pd.get_dummies(X_train)
    X_test = pd.get_dummies(X_test)

    X_train, X_test = X_train.align(X_test, join="left", axis=1, fill_value=0)

    model = XGBRegressor(
        n_estimators=800,
        learning_rate=0.03,
        max_depth=7,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1,
        random_state=42
    )

    model.fit(X_train, y_train)

    preds = model.predict(X_test)

    model.save_model(MODEL_PATH)

    return model, preds, y_test


def main():
    df = load_data()
    df = build_features(df)

    X_train, y_train, X_test, y_test = split_data(df)

    model, preds, y_true = train_model(X_train, y_train, X_test, y_test)

    metrics = evaluate(y_true, preds)

    for k, v in metrics.items():
        print(f"{k}: {v:.4f}")


if __name__ == "__main__":
    main()