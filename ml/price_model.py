import os
import pandas as pd
import psycopg2
from catboost import CatBoostRegressor
from dotenv import load_dotenv
import os

load_dotenv()

PG_HOST = os.getenv("PG_HOST")
PG_PASSWORD = os.getenv("PG_PASSWORD")
DB_CONFIG = {
    "host": PG_HOST,
    "database": "prices_db",
    "user": "postgres",
    "password": PG_PASSWORD
}

MODEL_PATH = "catboost_price_model.cbm"
TEST_DAYS = 7


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
    return df


def build_features(df):
    df = df.sort_values(["product_id", "store_id", "date"])

    group = df.groupby(["product_id", "store_id"])

    df["price_lag_1"] = group["price"].shift(1)
    df["price_lag_3"] = group["price"].shift(3)
    df["price_lag_7"] = group["price"].shift(7)
    df["price_lag_14"] = group["price"].shift(14)

    df["price_mean_7"] = group["price"].transform(lambda x: x.rolling(7).mean())
    df["price_std_7"] = group["price"].transform(lambda x: x.rolling(7).std())

    df["price_diff_1"] = df["price"] - df["price_lag_1"]

    df = df.dropna()
    df = df.sort_values("date")

    return df


def split_data(df):
    split_date = df["date"].max() - pd.Timedelta(days=TEST_DAYS)

    train = df[df["date"] <= split_date]
    test = df[df["date"] > split_date]

    X_train = train.drop(columns=["price", "date"])
    y_train = train["price"]

    X_test = test.drop(columns=["price", "date"])
    y_test = test["price"]

    return X_train, y_train, X_test, y_test


def train_model(X_train, y_train, X_test, y_test):
    cat_features = [
        "product_id",
        "store_id",
        "brand_id",
        "is_weekend",
        "is_holiday"
    ]

    model = CatBoostRegressor(
        iterations=500,
        depth=6,
        learning_rate=0.03,
        l2_leaf_reg=10,
        random_strength=1,
        loss_function="RMSE",
        eval_metric="RMSE",
        random_seed=42,
        verbose=100
    )

    if os.path.exists(MODEL_PATH):
        print("Дообучение существующей модели")
        model.load_model(MODEL_PATH)

        model.fit(
            X_train,
            y_train,
            cat_features=cat_features,
            eval_set=(X_test, y_test),
            init_model=MODEL_PATH,
            use_best_model=False
        )
    else:
        print("Обучение с нуля")

        model.fit(
            X_train,
            y_train,
            cat_features=cat_features,
            eval_set=(X_test, y_test),
            use_best_model=True
        )

    model.save_model(MODEL_PATH)

    return model


def evaluate(model, X_test, y_test):
    preds = model.predict(X_test)
    rmse = ((preds - y_test) ** 2).mean() ** 0.5
    print(f"RMSE: {rmse:.4f}")


def main():
    print("Загрузка данных")
    df = load_data()

    print("Генерация фичей")
    df = build_features(df)

    print("Разделение данных")
    X_train, y_train, X_test, y_test = split_data(df)

    print("Обучение модели")
    model = train_model(X_train, y_train, X_test, y_test)

    print("Оценка")
    evaluate(model, X_test, y_test)

    print("Готово")


if __name__ == "__main__":
    main()