import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px

# -----------------------------
# Подключение к PostgreSQL
# -----------------------------
def load_data():

    conn = psycopg2.connect(
        host="localhost",
        database="prices_db",
        user="postgres",
        password="12345"
    )

    query = """
    SELECT store, product_clean, brand, price, quantity, date
    FROM prices
    """

    df = pd.read_sql(query, conn)

    conn.close()

    return df


# -----------------------------
# Streamlit UI
# -----------------------------

st.title("📊 Product Prices Dashboard")

df = load_data()

# -----------------------------
# Фильтры
# -----------------------------

stores = st.multiselect(
    "Выберите магазин",
    options=df["store"].unique(),
    default=df["store"].unique()
)

products = st.multiselect(
    "Выберите продукт",
    options=df["product_clean"].unique(),
    default=df["product_clean"].unique()
)

filtered = df[
    (df["store"].isin(stores)) &
    (df["product_clean"].isin(products))
]

# -----------------------------
# График цен
# -----------------------------

st.subheader("📈 Динамика цен")

fig = px.line(
    filtered,
    x="date",
    y="price",
    color="store",
    title="Price dynamics"
)

st.plotly_chart(fig)


# -----------------------------
# Средняя цена по магазинам
# -----------------------------

st.subheader("🏪 Средняя цена по магазинам")

avg_price = (
    filtered
    .groupby("store")["price"]
    .mean()
    .reset_index()
)

fig2 = px.bar(
    avg_price,
    x="store",
    y="price",
    title="Average price by store"
)

st.plotly_chart(fig2)


# -----------------------------
# Таблица
# -----------------------------

st.subheader("📋 Данные")

st.dataframe(filtered)