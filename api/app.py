import streamlit as st
import pandas as pd
import subprocess
import psycopg2
from catboost import CatBoostRegressor
import os
import sys

DB_CONFIG = {
    "host": "localhost",
    "database": "prices_db",
    "user": "postgres",
    "password": "12345"
}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_PATH = os.path.join(BASE_DIR, "ml", "catboost_price_model.cbm")

conn = psycopg2.connect(**DB_CONFIG)
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
    return df

def forecast_future(df, model, days=14):
    df = df.copy()

    future_rows = []

    for i in range(days):
        df_feat = build_features(df.copy())

        last_row = df_feat.iloc[-1:].copy()

        X = last_row.drop(columns=["price", "date"])

        pred = model.predict(X)[0]

        new_row = df.iloc[-1:].copy()
        new_row["date"] = new_row["date"] + pd.Timedelta(days=1)
        new_row["price"] = pred

        df = pd.concat([df, new_row], ignore_index=True)

        future_rows.append(new_row)

    future_df = pd.concat(future_rows, ignore_index=True)
    return future_df

st.set_page_config(page_title="Price Forecast App", layout="wide")

st.title("Прогнозирование цен на продукты")
st.markdown("Проект создан: **Ваше Имя**")

# Навигация между страницами
page = st.sidebar.selectbox(
    "Выберите страницу",
    ["Главная", "Таблицы", "Графики", "Просмотр предсказаний", "Добавление данных", "Запуск парсингов"]
)

# ====================== Главная ======================
if page == "Главная":
    st.header("Добро пожаловать!")
    st.write("""
    Это Streamlit приложение для анализа и прогнозирования цен на продукты.
    Здесь вы можете:
    - Просматривать таблицы данных
    - Строить графики
    - Просматривать прогнозы модели
    - Добавлять свои данные
    - Запускать процесс ETL и парсинга
    """)

elif page == "Таблицы":
    st.header("Просмотр таблиц")

    tables = [
        "brands",
        "calendar",
        "external_factors",
        "prices_history",
        "prices_raw",
        "products",
        "stores"
    ]

    selected_table = st.selectbox("Выберите таблицу", tables)

    # Получаем данные
    query = f"SELECT * FROM {selected_table} LIMIT 1000"
    df = pd.read_sql(query, conn)

    # Выбор колонок
    columns = st.multiselect(
        "Выберите колонки",
        df.columns.tolist(),
        default=df.columns.tolist()
    )

    df = df[columns]

    # ===== ФИЛЬТРЫ =====
    st.subheader("Фильтры")

    for col in df.columns:
        if df[col].dtype == "object":
            values = st.multiselect(f"{col}", df[col].unique())
            if values:
                df = df[df[col].isin(values)]

        elif "int" in str(df[col].dtype) or "float" in str(df[col].dtype):
            min_val = float(df[col].min())
            max_val = float(df[col].max())

            selected_range = st.slider(
                f"{col}",
                min_val,
                max_val,
                (min_val, max_val)
            )
            df = df[df[col].between(*selected_range)]

        elif "date" in str(df[col].dtype):
            date_range = st.date_input(f"{col}", [])
            if len(date_range) == 2:
                df = df[
                    (df[col] >= pd.to_datetime(date_range[0])) &
                    (df[col] <= pd.to_datetime(date_range[1]))
                ]

    # Лимит строк
    limit = st.slider("Количество строк", 10, 1000, 100)
    st.dataframe(df.head(limit))

elif page == "Графики":
    st.header("Графики")

    query = """
    SELECT 
        ph.date,
        ph.price,
        ph.quantity,
        p.name as product_name,
        b.name as brand_name,
        s.name as store_name
    FROM prices_history ph
    JOIN products p ON ph.product_id = p.id
    JOIN brands b ON p.brand_id = b.id
    JOIN stores s ON ph.store_id = s.id
    """

    df = pd.read_sql(query, conn)

    # ===== ФИЛЬТРЫ =====
    st.sidebar.header("Фильтры")

    # Продукт по названию
    products = df["product_name"].unique()
    selected_product = st.sidebar.selectbox("Продукт", products)

    # Бренд
    brands = df["brand_name"].unique()
    selected_brand = st.sidebar.multiselect("Бренд", brands)

    # Магазин
    stores = df["store_name"].unique()
    selected_store = st.sidebar.multiselect("Магазин", stores)

    # Дата
    date_range = st.sidebar.date_input("Период", [])

    # Метрика
    metric = st.selectbox("Метрика", ["price", "quantity"])

    # ===== ПРИМЕНЕНИЕ ФИЛЬТРОВ =====
    df_filtered = df[df["product_name"] == selected_product]

    if selected_brand:
        df_filtered = df_filtered[df_filtered["brand_name"].isin(selected_brand)]

    if selected_store:
        df_filtered = df_filtered[df_filtered["store_name"].isin(selected_store)]

    if len(date_range) == 2:
        df_filtered = df_filtered[
            (df_filtered["date"] >= pd.to_datetime(date_range[0])) &
            (df_filtered["date"] <= pd.to_datetime(date_range[1]))
        ]

    # ===== ГРУППИРОВКА =====
    group_by = st.selectbox("Группировка", ["По дням", "По месяцам"])

    if group_by == "По месяцам":
        df_filtered["date"] = pd.to_datetime(df_filtered["date"])
        df_filtered["month"] = df_filtered["date"].dt.to_period("M")
        df_plot = df_filtered.groupby("month")[metric].mean().reset_index()
        df_plot["month"] = df_plot["month"].astype(str)
        st.line_chart(df_plot.set_index("month"))

    else:
        df_plot = df_filtered.groupby("date")[metric].mean().reset_index()
        st.line_chart(df_plot.set_index("date"))

    # ===== ТАБЛИЦА =====
    st.subheader("Данные")
    st.dataframe(df_filtered.head(100))

elif page == "Просмотр предсказаний":
    st.header("Прогноз цен (будущее)")

    model = CatBoostRegressor()
    model.load_model(MODEL_PATH)

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

    # фильтр как в графиках
    products = df["product_id"].unique()
    selected_product = st.selectbox("Продукт", products)

    df = df[df["product_id"] == selected_product]

    df = df.sort_values("date")

    st.subheader("Исторические данные")
    st.line_chart(df.set_index("date")["price"])

    # горизонт прогноза
    days = st.slider("Прогноз на дней", 1, 30, 7)

    if st.button("Спрогнозировать"):
        future_df = forecast_future(df, model, days)

        # объединяем
        df["type"] = "history"
        future_df["type"] = "forecast"

        full_df = pd.concat([df, future_df])

        st.subheader("Факт + Прогноз")

        st.line_chart(full_df.set_index("date")["price"])

        st.subheader("Таблица прогноза")
        st.dataframe(future_df[["date", "price"]])

# ====================== Добавление данных ======================
elif page == "Добавление данных":
    st.header("Добавление своих данных")
    uploaded_file = st.file_uploader("Выберите CSV файл", type=["csv"])
    if uploaded_file:
        df_new = pd.read_csv(uploaded_file)
        st.write("Предпросмотр данных:")
        st.dataframe(df_new.head())
        if st.button("Сохранить в БД"):
            df_new.to_sql("prices_history", conn, if_exists="append", index=False)
            st.success("Данные успешно добавлены!")

elif page == "Запуск парсингов":

    import os

    st.header("Запуск парсингов")

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    PRODUCTS_FILE = os.path.join(BASE_DIR, "products")  # теперь это файл!
    PARSERS_DIR = os.path.join(BASE_DIR, "etl", "parsers")
    TRANSFORM_SCRIPT = os.path.join(BASE_DIR, "etl", "transformer", "transform.py")
    EXTERNAL_SCRIPT = os.path.join(BASE_DIR, "etl", "load_external_factors.py")

    # =========================
    # Проверки
    # =========================
    if not os.path.exists(PARSERS_DIR):
        st.error(f"Нет папки парсеров: {PARSERS_DIR}")
        st.stop()

    if not os.path.exists(PRODUCTS_FILE):
        st.error(f"Нет файла продуктов: {PRODUCTS_FILE}")
        st.stop()

    if not os.path.isfile(PRODUCTS_FILE):
        st.error(f"products должен быть файлом: {PRODUCTS_FILE}")
        st.stop()

    # =========================
    # Чтение продуктов из файла
    # =========================
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        products = [
            line.strip().replace('"', '').replace(',', '')
            for line in f.readlines()
            if line.strip()
        ]

    # =========================
    # Выбор парсера (магазина)
    # =========================
    parsers = [f for f in os.listdir(PARSERS_DIR) if f.endswith(".py")]

    selected_parser = st.selectbox(
        "Выберите магазин (парсер)",
        parsers
    )

    # =========================
    # Выбор продуктов
    # =========================
    product_mode = st.radio(
        "Выбор продуктов",
        ["Все продукты", "Выбрать вручную"]
    )

    if product_mode == "Выбрать вручную":
        selected_products = st.multiselect("Выберите продукты", products)
    else:
        selected_products = products

    # =========================
    # Режим
    # =========================
    mode = st.radio(
        "Режим работы",
        ["Только посмотреть", "Добавить в БД"]
    )

    # =========================
    # Запуск парсинга
    # =========================
    if st.button("Запустить парсинг"):
        parser_path = os.path.join(PARSERS_DIR, selected_parser)

        all_data = []

        for product in selected_products:

            # 👉 теперь передаем СТРОКУ продукта, а не путь
            result = subprocess.run(
                [sys.executable, parser_path, product],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                st.error(f"Ошибка при парсинге: {product}")
                st.text(result.stderr)
                continue

            try:
                df = pd.read_json(result.stdout)
                all_data.append(df)
            except:
                st.warning(f"Не удалось прочитать JSON для: {product}")

        if not all_data:
            st.error("Нет данных после парсинга")
        else:
            final_df = pd.concat(all_data, ignore_index=True)

            st.subheader("Результат парсинга")
            st.dataframe(final_df.head())

            # =========================
            # Только просмотр
            # =========================
            if mode == "Только посмотреть":
                st.success("Режим просмотра завершен")

            # =========================
            # Добавление в БД
            # =========================
            else:
                st.info("Запуск трансформации...")

                transform_result = subprocess.run(
                    [sys.executable, TRANSFORM_SCRIPT],
                    capture_output=True,
                    text=True
                )

                if transform_result.returncode != 0:
                    st.error("Ошибка трансформации")
                    st.text(transform_result.stderr)
                    st.stop()

                st.success("Трансформация выполнена")

                # =========================
                # Проверка дублей
                # =========================
                st.info("Проверка на дубликаты...")

                existing = pd.read_sql(
                    "SELECT date, product_id, store_id FROM prices_history",
                    conn
                )

                merged = final_df.merge(
                    existing,
                    on=["date", "product_id", "store_id"],
                    how="left",
                    indicator=True
                )

                new_data = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])

                st.write(f"Новых записей: {len(new_data)}")

                if len(new_data) > 0:
                    new_data.to_sql("prices_history", conn, if_exists="append", index=False)
                    st.success("Данные добавлены в БД")
                else:
                    st.warning("Все данные уже есть в БД")

    # =========================
    # EXTERNAL FACTORS
    # =========================
    st.markdown("---")
    st.subheader("External factors")

    ext_mode = st.radio(
        "Режим external factors",
        ["Только посмотреть", "Добавить в БД"]
    )

    if st.button("Запустить загрузку external factors"):
        result = subprocess.run(
            [sys.executable, EXTERNAL_SCRIPT],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            st.error("Ошибка загрузки external factors")
            st.text(result.stderr)
        else:
            try:
                df_ext = pd.read_json(result.stdout)
                st.dataframe(df_ext.head())

                if ext_mode == "Добавить в БД":
                    existing = pd.read_sql(
                        "SELECT date FROM external_factors",
                        conn
                    )

                    merged = df_ext.merge(
                        existing,
                        on="date",
                        how="left",
                        indicator=True
                    )

                    new_data = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])

                    if len(new_data) > 0:
                        new_data.to_sql("external_factors", conn, if_exists="append", index=False)
                        st.success("External factors добавлены")
                    else:
                        st.warning("Все данные уже есть в БД")

            except:
                st.warning("Не удалось прочитать данные external factors")