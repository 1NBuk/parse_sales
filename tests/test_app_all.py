import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

# импортируем функции из твоего app.py
from api.app import validate_csv, build_features, forecast_future, safe_decode, CAT_FEATURES


# -----------------------------
# FIXTURES
# -----------------------------
@pytest.fixture
def sample_df():
    dates = pd.date_range("2024-01-01", periods=20)
    return pd.DataFrame({
        "store": ["A"] * 20,
        "product_clean": ["p1"] * 20,
        "brand": ["b1"] * 20,
        "price": np.linspace(10, 30, 20),
        "quantity": np.linspace(1, 20, 20),
        "unit_normalized": ["kg"] * 20,
        "date": dates
    })


# -----------------------------
# validate_csv
# -----------------------------
def test_validate_csv_ok(sample_df):
    df = validate_csv(sample_df.copy())
    assert not df.isna().any().any()


def test_validate_csv_missing_columns():
    df = pd.DataFrame({"price": [1, 2]})
    with pytest.raises(ValueError):
        validate_csv(df)


def test_validate_csv_negative_price(sample_df):
    df = sample_df.copy()
    df.loc[0, "price"] = -10
    with pytest.raises(ValueError):
        validate_csv(df)


def test_validate_csv_nan_values(sample_df):
    df = sample_df.copy()
    df["price"] = df["price"].astype(object)
    df.loc[0, "price"] = "abc"
    with pytest.raises(ValueError):
        validate_csv(df)


# -----------------------------
# build_features
# -----------------------------
def test_build_features(sample_df):
    df = build_features(sample_df.copy())

    # после dropna должно стать меньше строк
    assert len(df) < len(sample_df)

    # проверяем наличие фичей
    assert "price_lag_1" in df.columns
    assert "price_mean_7" in df.columns


# -----------------------------
# forecast_future
# -----------------------------
class DummyModel:
    def predict(self, X):
        # возвращаем лог-предсказание
        return np.array([2.0])


def test_forecast_future(sample_df):
    df = sample_df.copy()

    model = DummyModel()
    features = df.columns.tolist()

    result = forecast_future(df, model, features, days=3)

    assert len(result) == 3
    assert "price" in result.columns
    assert not result["price"].isna().any()


# -----------------------------
# safe_decode
# -----------------------------
def test_safe_decode_utf8():
    assert safe_decode("hello".encode("utf-8")) == "hello"


def test_safe_decode_cp1251():
    text = "тест"
    encoded = text.encode("cp1251")
    assert safe_decode(encoded) == text


def test_safe_decode_fallback():
    bad = b"\xff\xfe\xfd"
    result = safe_decode(bad)
    assert isinstance(result, str)