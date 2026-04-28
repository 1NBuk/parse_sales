import os
import pandas as pd
import numpy as np
import psycopg2
from dotenv import load_dotenv
from xgboost import XGBRegressor
import joblib
load_dotenv()
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_CONFIG = {
    "host": os.getenv("PG_HOST"),
    "database": "prices_db",
    "user": "postgres",
    "password": os.getenv("PG_PASSWORD")
}

MODEL_PATH = "xgb_price_model.json"
TEST_DAYS = 7


def load_data():
    conn = psycopg2.connect(**DB_CONFIG)

    query = """
    SELECT
        ph.date,
        ph.price,
        ph.quantity,
        ph.unit,

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
    return df


def normalize(unit, qty):
    if unit == "pcs":
        return qty * 0.06
    elif unit == "g":
        return qty / 1000
    elif unit == "ml":
        return qty / 1000
    return np.nan


def build_features(df):
    df["date"] = pd.to_datetime(df["date"])

    df["kg"] = df.apply(lambda x: normalize(x["unit"], x["quantity"]), axis=1)
    df = df.dropna(subset=["kg", "price"])

    df["price_per_kg"] = df["price"] / df["kg"]

    df = df.sort_values(["product_id", "store_id", "date"])
    g = df.groupby(["product_id", "store_id"])

    df["price_lag_1"] = g["price_per_kg"].shift(1)
    df["price_lag_3"] = g["price_per_kg"].shift(3)
    df["price_lag_7"] = g["price_per_kg"].shift(7)
    df["price_lag_14"] = g["price_per_kg"].shift(14)

    df["price_mean_7"] = g["price_per_kg"].transform(lambda x: x.rolling(7).mean())
    df["price_std_7"] = g["price_per_kg"].transform(lambda x: x.rolling(7).std())

    df["price_diff_1"] = df["price_per_kg"] - df["price_lag_1"]

    df = df.dropna()
    return df


def split_data(df):
    split_date = df["date"].max() - pd.Timedelta(days=TEST_DAYS)

    train = df[df["date"] <= split_date]
    test = df[df["date"] > split_date]

    X_train = train.drop(columns=["price", "price_per_kg", "date", "unit", "quantity"])
    y_train = train["price_per_kg"]

    X_test = test.drop(columns=["price", "price_per_kg", "date", "unit", "quantity"])
    y_test = test["price_per_kg"]

    return X_train, y_train, X_test, y_test


def train_model(X_train, y_train, X_test, y_test):
    X_train = pd.get_dummies(X_train)
    X_test = pd.get_dummies(X_test)

    X_train, X_test = X_train.align(X_test, join="left", axis=1, fill_value=0)

    model = XGBRegressor(
        n_estimators=800,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )

    model.fit(X_train, y_train)

    preds = model.predict(X_test)

    rmse = np.sqrt(np.mean((preds - y_test) ** 2))
    mae = np.mean(np.abs(preds - y_test))
    mape = np.mean(np.abs((y_test - preds) / y_test)) * 100
    r2 = 1 - np.sum((y_test - preds) ** 2) / np.sum((y_test - np.mean(y_test)) ** 2)

    print("RMSE:", rmse)
    print("MAE:", mae)
    print("MAPE:", mape)
    print("R2:", r2)

    model.save_model(MODEL_PATH)
    feature_columns = X_train.columns.tolist()
    joblib.dump(feature_columns, os.path.join(BASE_DIR, "ml", "features.pkl"))
    return model


def main():
    df = load_data()
    df = build_features(df)
    X_train, y_train, X_test, y_test = split_data(df)
    train_model(X_train, y_train, X_test, y_test)


if __name__ == "__main__":
    main()