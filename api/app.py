import streamlit as st
import pandas as pd
import subprocess
import psycopg2
from catboost import CatBoostRegressor
import os
import sys
import tempfile
import json
import re

DB_CONFIG = {
    "host": "localhost",
    "database": "prices_db",
    "user": "postgres",
    "password": "12345"
}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)
MODEL_PATH = os.path.join(BASE_DIR, "ml", "catboost_price_model.cbm")

from etl.upload_to_postgres import upload

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
    df = df.sort_values("date").copy()
    future_rows = []

    cat_features = ["product_id", "store_id", "brand_id", "day_of_week",
                    "week_of_year", "month", "is_weekend", "is_holiday"]

    num_features = ["quantity", "usd_rub", "eur_rub", "oil_price", "temperature", "precipitation",
                    "price_lag_1", "price_lag_3", "price_lag_7", "price_lag_14",
                    "price_mean_7", "price_std_7", "price_diff_1"]

    for i in range(days):
        last_rows = df.tail(14)
        new_row = last_rows.iloc[-1:].copy()

        new_row["price_lag_1"] = last_rows["price"].iloc[-1] if len(last_rows) >= 1 else 0
        new_row["price_lag_3"] = last_rows["price"].iloc[-3] if len(last_rows) >= 3 else last_rows[
            "price"].mean() if len(last_rows) > 0 else 0
        new_row["price_lag_7"] = last_rows["price"].iloc[-7] if len(last_rows) >= 7 else last_rows[
            "price"].mean() if len(last_rows) > 0 else 0
        new_row["price_lag_14"] = last_rows["price"].iloc[-14] if len(last_rows) >= 14 else last_rows[
            "price"].mean() if len(last_rows) > 0 else 0
        new_row["price_mean_7"] = last_rows["price"].tail(7).mean() if len(last_rows) >= 7 else last_rows[
            "price"].mean() if len(last_rows) > 0 else 0
        new_row["price_std_7"] = last_rows["price"].tail(7).std() or 0 if len(last_rows) >= 7 else 0
        new_row["price_diff_1"] = new_row["price_lag_1"].iloc[0] - last_rows["price"].iloc[-2] if len(
            last_rows) > 1 else 0

        if len(last_rows) >= 7:
            new_row["quantity"] = last_rows["quantity"].tail(7).mean()
        elif len(last_rows) > 0:
            new_row["quantity"] = last_rows["quantity"].mean()
        else:
            new_row["quantity"] = 0

        for col in ["is_weekend", "is_holiday"]:
            if col in new_row.columns:
                new_row[col] = new_row[col].fillna(False).apply(lambda x: "1" if x else "0")

        new_row["date"] = new_row["date"].iloc[0] + pd.Timedelta(days=1)

        X = pd.DataFrame()
        X["quantity"] = new_row["quantity"]

        for col in cat_features:
            X[col] = new_row[col].astype(str).replace('nan', 'unknown')

        for col in num_features:
            if col != "quantity":
                X[col] = pd.to_numeric(new_row[col], errors='coerce').fillna(0).astype(float)

        try:
            pred = model.predict(X)[0]
            new_row["price"] = pred
        except Exception as e:
            st.error(f"Ошибка при прогнозе: {e}")
            raise e

        df = pd.concat([df, new_row], ignore_index=True)
        future_rows.append(new_row)

    future_df = pd.concat(future_rows, ignore_index=True) if future_rows else pd.DataFrame()
    return future_df


REQUIRED_COLUMNS = [
    "store", "product_clean", "brand",
    "price", "quantity", "unit_normalized", "date"
]


def validate_csv(df):
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Нет колонок: {missing}")

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if df[["price", "quantity", "date"]].isna().any().any():
        raise ValueError("Есть некорректные значения (NaN)")

    if (df["price"] <= 0).any():
        raise ValueError("Цена <= 0")

    if (df["quantity"] <= 0).any():
        raise ValueError("Количество <= 0")

    return df


st.set_page_config(page_title="Price Forecast App", layout="wide")

st.title("Прогнозирование цен на продукты")
st.markdown("Проект создан: **Букарёвой Анастасией**")

page = st.sidebar.selectbox(
    "Выберите страницу",
    ["Главная", "Таблицы", "Графики", "Просмотр предсказаний", "Добавление данных", "Запуск парсингов"]
)

if page == "Главная":
    st.image(
        "https://avatars.mds.yandex.net/i?id=f35dcd33d22aeebc29f5d0617985c49a_l-7684353-images-thumbs&n=13",
        use_container_width=True
    )
    st.markdown("""
    # Выпускная квалификационная работа

    **Тема:** «Разработка системы для анализа и прогнозирования изменения цен на товары»

    **Выполнила:** студентка группы ИД22-1  
    **Букарёва Анастасия Павловна**

    ---
    """)

    st.markdown("""
    Это Streamlit приложение предназначено для:

    - Анализа исторических данных по ценам на товары  
    - Прогнозирования изменения цен с использованием модели CatBoost  
    - Просмотра и фильтрации данных по продуктам, брендам и магазинам  
    - Добавления собственных данных в базу  
    - Автоматизации процесса ETL и загрузки внешних факторов (курсы валют, цена нефти, погода)  

    **Навигация:** используйте боковую панель для перехода между страницами приложения.

    *Совет:* начните с раздела 'Таблицы', чтобы изучить данные, затем переходите к 'Графикам' и 'Просмотру предсказаний'.
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

    query = f"SELECT * FROM {selected_table} LIMIT 1000"
    df = pd.read_sql(query, conn)

    columns = st.multiselect(
        "Выберите колонки",
        df.columns.tolist(),
        default=df.columns.tolist()
    )

    df = df[columns]

    st.subheader("Фильтры")

    for col in df.columns:
        if df[col].dtype == "object":
            values = st.multiselect(f"{col}", df[col].unique())
            if values:
                df = df[df[col].isin(values)]

        elif "int" in str(df[col].dtype) or "float" in str(df[col].dtype):
            min_val = float(df[col].min())
            max_val = float(df[col].max())
            selected_range = st.slider(f"{col}", min_val, max_val, (min_val, max_val))
            df = df[df[col].between(*selected_range)]

        elif "date" in str(df[col].dtype):
            date_range = st.date_input(f"{col}", [])
            if len(date_range) == 2:
                df = df[
                    (df[col] >= pd.to_datetime(date_range[0])) &
                    (df[col] <= pd.to_datetime(date_range[1]))
                    ]

    limit = st.slider("Количество строк", 10, 1000, 100)
    st.dataframe(df.head(limit))

elif page == "Графики":
    import plotly.express as px

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
    df["date"] = pd.to_datetime(df["date"])

    st.sidebar.header("Фильтры")

    selected_product = st.sidebar.selectbox(
        "Продукт",
        sorted(df["product_name"].unique())
    )

    selected_brand = st.sidebar.multiselect(
        "Бренд",
        sorted(df["brand_name"].unique())
    )

    selected_store = st.sidebar.multiselect(
        "Магазин",
        sorted(df["store_name"].unique())
    )

    date_range = st.sidebar.date_input("Период", [])

    metric = st.selectbox("Метрика", ["price", "quantity"])

    chart_type = st.selectbox(
        "Тип графика",
        ["Линейный", "Бар", "Scatter"]
    )

    group_by = st.selectbox(
        "Группировка",
        ["По дням", "По месяцам"]
    )

    compare_by = st.selectbox(
        "Сравнение",
        ["Нет", "brand_name", "store_name"]
    )

    show_rolling = st.checkbox("Скользящее среднее (7 дней)")

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

    if group_by == "По месяцам":
        df_filtered["period"] = df_filtered["date"].dt.to_period("M").astype(str)
        x_col = "period"
    else:
        df_filtered["period"] = df_filtered["date"]
        x_col = "period"

    if compare_by != "Нет":
        df_plot = df_filtered.groupby([x_col, compare_by])[metric].mean().reset_index()

        if chart_type == "Линейный":
            fig = px.line(df_plot, x=x_col, y=metric, color=compare_by)
        elif chart_type == "Бар":
            fig = px.bar(df_plot, x=x_col, y=metric, color=compare_by)
        else:
            fig = px.scatter(df_plot, x=x_col, y=metric, color=compare_by)
    else:
        df_plot = df_filtered.groupby(x_col)[metric].mean().reset_index()

        if show_rolling:
            df_plot["rolling"] = df_plot[metric].rolling(7).mean()

        if chart_type == "Линейный":
            fig = px.line(df_plot, x=x_col, y=metric)
        elif chart_type == "Бар":
            fig = px.bar(df_plot, x=x_col, y=metric)
        else:
            fig = px.scatter(df_plot, x=x_col, y=metric)

        if show_rolling:
            fig.add_scatter(x=df_plot[x_col], y=df_plot["rolling"], mode="lines", name="rolling_7")

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Данные")
    st.dataframe(df_filtered.head(200))

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
        p.name as product_name,
        s.id as store_id,
        s.name as store_name,
        b.id as brand_id,
        b.name as brand_name,
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

    products = df["product_name"].unique()
    selected_product = st.sidebar.selectbox("Продукт", products)
    df = df[df["product_name"] == selected_product]

    brands = df["brand_name"].unique()
    selected_brand = st.sidebar.multiselect("Бренд", brands)
    if selected_brand:
        df = df[df["brand_name"].isin(selected_brand)]

    stores = df["store_name"].unique()
    selected_store = st.sidebar.multiselect("Магазин", stores)
    if selected_store:
        df = df[df["store_name"].isin(selected_store)]

    date_range = st.sidebar.date_input("Период", [])
    if len(date_range) == 2:
        df = df[(df["date"] >= pd.to_datetime(date_range[0])) & (df["date"] <= pd.to_datetime(date_range[1]))]

    df = df.sort_values("date")

    st.subheader("Исторические данные")
    st.line_chart(df.set_index("date")["price"])

    days = st.slider("Прогноз на дней", 1, 30, 7)

    if st.button("Спрогнозировать"):
        if df.empty:
            st.warning("Нет данных для выбранных фильтров!")
        else:
            future_df = forecast_future(df, model, days)

            df["type"] = "history"
            future_df["type"] = "forecast"
            full_df = pd.concat([df, future_df], ignore_index=True)

            st.subheader("Факт + Прогноз")
            st.line_chart(full_df.set_index("date")["price"])

            st.subheader("Таблица прогноза")
            st.dataframe(future_df[["date", "price"]])

elif page == "Добавление данных":
    st.header("Добавление своих данных")
    uploaded_file = st.file_uploader("Выберите CSV файл", type=["csv"])
    if uploaded_file:
        df_new = pd.read_csv(uploaded_file)
        st.write("Предпросмотр данных:")
        st.dataframe(df_new.head())
        if st.button("Сохранить в БД"):
            try:
                df_new = validate_csv(df_new)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                    df_new.to_csv(tmp.name, index=False)
                    upload(tmp.name)
                st.success("Данные успешно загружены через pipeline!")
            except Exception as e:
                st.error(f"Ошибка: {e}")

elif page == "Запуск парсингов":
    st.header("Запуск парсингов")

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    PRODUCTS_FILE = os.path.join(BASE_DIR, "products")
    PARSERS_DIR = os.path.join(BASE_DIR, "api", "app_parsers")
    TRANSFORM_SCRIPT = os.path.join(BASE_DIR, "etl", "transformer", "transform.py")
    EXTERNAL_SCRIPT = os.path.join(BASE_DIR, "etl", "load_external_factors.py")

    if not os.path.exists(PARSERS_DIR):
        st.error(f"Нет папки парсеров: {PARSERS_DIR}")
        st.stop()

    if not os.path.isfile(PRODUCTS_FILE):
        default_products = [
            "Яйцо куриное Окское отборное С0 10шт",
            "Молоко Простоквашино 1л",
            "Хлеб белый 500г",
            "Масло сливочное 200г",
            "Сахар песок 1кг"
        ]
        with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(default_products))

    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        products = [line.strip() for line in f.readlines() if line.strip()]

    parsers = [f for f in os.listdir(PARSERS_DIR) if f.endswith(".py")]
    selected_parser = st.selectbox("Выберите магазин (парсер)", parsers)
    parser_path = os.path.join(PARSERS_DIR, selected_parser)

    st.subheader("Выбор продуктов")

    col1, col2 = st.columns([1, 2])
    with col1:
        product_mode = st.radio("Режим выбора", ["Все продукты", "Выбрать вручную", "По категориям"])

    with col2:
        if product_mode == "Выбрать вручную":
            selected_products = st.multiselect("Выберите продукты", products)
        elif product_mode == "По категориям":
            categories = {
                "Яйца": [p for p in products if "яйцо" in p.lower()],
                "Молочные продукты": [p for p in products if
                                      any(word in p.lower() for word in ["молоко", "кефир", "сметана", "йогурт"])],
                "Хлебобулочные": [p for p in products if any(word in p.lower() for word in ["хлеб", "батон", "булка"])],
                "Бакалея": [p for p in products if
                            any(word in p.lower() for word in ["сахар", "соль", "крупа", "масло", "мука"])],
                "Овощи и фрукты": [p for p in products if any(
                    word in p.lower() for word in ["картофель", "лук", "морковь", "капуста", "яблоко"])],
                "Мясо и птица": [p for p in products if
                                 any(word in p.lower() for word in ["курица", "цыпленок", "филе", "мясо"])]
            }
            selected_category = st.selectbox("Выберите категорию", list(categories.keys()))
            if selected_category:
                selected_products = st.multiselect("Выберите продукты из категории", categories[selected_category])
            else:
                selected_products = []
        else:
            selected_products = products

    st.caption(f"Выбрано продуктов: {len(selected_products)}")

    if product_mode == "Выбрать вручную" and st.button("Выбрать все"):
        selected_products = products
        st.rerun()

    mode = st.radio("Режим работы", ["Только посмотреть", "Добавить в БД"])

    if st.button("Запустить парсинг", type="primary"):
        if not selected_products:
            st.warning("Не выбраны продукты!")
            st.stop()

        cleaned_products = []
        for p in selected_products:
            cleaned = p.strip().strip('"').strip("'").strip()
            cleaned = re.sub(r'^["\']+|["\']+$', '', cleaned)
            cleaned_products.append(cleaned)

        st.write(f"Обрабатываем продуктов: {len(cleaned_products)}")

        with st.expander("Показать список продуктов"):
            st.write(cleaned_products[:10])
            if len(cleaned_products) > 10:
                st.write(f"... и еще {len(cleaned_products) - 10} продуктов")

        products_json = json.dumps(cleaned_products, ensure_ascii=False)

        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("Запуск парсера...")
        progress_bar.progress(10)

        process = subprocess.Popen(
            [sys.executable, parser_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        progress_bar.progress(30)
        status_text.text("Парсинг данных...")

        stdout, stderr = process.communicate(input=products_json)

        progress_bar.progress(90)
        status_text.text("Обработка результатов...")

        if process.returncode != 0:
            st.error("Ошибка при парсинге")
            with st.expander("Детали ошибки"):
                st.text(f"Код ошибки: {process.returncode}")
                st.text(f"stderr:\n{stderr}")
            progress_bar.empty()
            status_text.empty()
            st.stop()

        try:
            if not stdout or stdout.strip() == "":
                st.error("Парсер не вернул данных")
                progress_bar.empty()
                status_text.empty()
                st.stop()

            json_match = re.search(r'\[\s*\{.*\}\s*\]', stdout, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed_data = json.loads(json_str)
            else:
                parsed_data = json.loads(stdout)

            final_df = pd.DataFrame(parsed_data)
            progress_bar.progress(100)
            status_text.text("Готово")

            st.subheader("Результат парсинга")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Всего обработано", len(final_df))
            with col2:
                found_count = final_df['price'].notna().sum()
                st.metric("Найдено товаров", found_count)
            with col3:
                not_found_count = final_df['price'].isna().sum()
                st.metric("Не найдено", not_found_count)

            st.dataframe(final_df, use_container_width=True)

            csv = final_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="Скачать результаты как CSV",
                data=csv,
                file_name=f"parsing_results_{selected_parser}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

            if mode == "Добавить в БД":
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

                try:
                    from etl.upload_to_postgres import upload

                    processed_dir = os.path.join(BASE_DIR, "data", "processed")
                    if os.path.exists(processed_dir):
                        csv_files = [f for f in os.listdir(processed_dir) if f.endswith('.csv')]
                        if csv_files:
                            for file in csv_files:
                                file_path = os.path.join(processed_dir, file)
                                st.write(f"Загрузка {file}...")
                                upload(file_path)
                            st.success(f"Загружено {len(csv_files)} файлов в базу данных")
                        else:
                            st.warning("Нет CSV файлов в папке processed")
                    else:
                        st.warning("Папка с обработанными данными не найдена")

                except Exception as e:
                    st.error(f"Ошибка при загрузке в БД: {e}")

            progress_bar.empty()
            status_text.empty()

        except json.JSONDecodeError as e:
            st.error(f"Не удалось обработать результат парсинга: {e}")
            with st.expander("Показать вывод парсера для отладки"):
                st.text(f"stdout:\n{stdout}")
                st.text(f"stderr:\n{stderr}")
            progress_bar.empty()
            status_text.empty()
        except Exception as e:
            st.error(f"Ошибка: {e}")
            with st.expander("Детали ошибки"):
                st.text(f"stdout: {stdout}")
                st.text(f"stderr: {stderr}")
            progress_bar.empty()
            status_text.empty()

    with st.expander("Управление списком продуктов"):
        st.subheader("Редактировать список продуктов")

        current_products_text = "\n".join(products)
        new_products_text = st.text_area(
            "Редактируйте список (каждый продукт с новой строки):",
            value=current_products_text,
            height=200
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Сохранить изменения"):
                new_products = [p.strip() for p in new_products_text.split('\n') if p.strip()]
                with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(new_products))
                st.success(f"Сохранено {len(new_products)} продуктов")
                st.rerun()

        with col2:
            if st.button("Сбросить к стандартному списку"):
                default_products = [
                    "Яйцо куриное Окское отборное С0 10шт",
                    "Молоко Простоквашино 1л",
                    "Хлеб белый 500г",
                    "Масло сливочное 200г",
                    "Сахар песок 1кг"
                ]
                with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(default_products))
                st.success("Список сброшен к стандартному")
                st.rerun()

    st.markdown("---")

    st.subheader("External factors по дате")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        ext_date = st.date_input("Выберите дату")
    with col2:
        ext_factor = st.selectbox(
            "Выберите фактор",
            ["Все", "usd_rub", "eur_rub", "oil_price", "temperature", "precipitation"]
        )
    with col3:
        ext_mode = st.radio("Режим", ["Просмотр", "Добавить в БД"], horizontal=True)

    if st.button("Загрузить external factors", type="secondary"):
        cmd = [sys.executable, EXTERNAL_SCRIPT, "--date", str(ext_date)]
        if ext_factor != "Все":
            cmd += ["--factor", ext_factor]

        with st.spinner("Загрузка данных..."):
            result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            st.error("Ошибка при получении external factor")
            st.text(result.stderr)
        else:
            try:
                df_ext = pd.read_json(result.stdout)
                st.subheader("Результат")
                st.dataframe(df_ext)

                if ext_mode == "Добавить в БД":
                    existing = pd.read_sql("SELECT date FROM external_factors", conn)
                    merged = df_ext.merge(existing, on="date", how="left", indicator=True)
                    new_data = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])

                    if len(new_data) > 0:
                        new_data.to_sql("external_factors", conn, if_exists="append", index=False)
                        st.success("External factors добавлены в БД")
                    else:
                        st.warning("Данные для этой даты уже есть в БД")
            except Exception as e:
                st.warning(f"Не удалось прочитать данные external factors: {e}")