from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2
from ml.price_model import predict  # Импорт функции ML

app = FastAPI(title="Price API", version="1.0")

# Параметры подключения к PostgreSQL
PG_HOST = "localhost"
PG_DATABASE = "prices_db"
PG_USER = "postgres"
PG_PASSWORD = "12345"

# ---------------------------
# Модель запроса для ML
# ---------------------------
class PriceQuery(BaseModel):
    store: str
    unit: str

# ---------------------------
# Эндпоинт: реальные цены
# ---------------------------
@app.get("/prices")
def get_prices(limit: int = 100):
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            database=PG_DATABASE,
            user=PG_USER,
            password=PG_PASSWORD
        )
        cur = conn.cursor()
        cur.execute("SELECT store, product, unit, price FROM prices LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Возвращаем в виде списка словарей
        return [{"store": r[0], "product": r[1], "unit": r[2], "price": float(r[3])} for r in rows]

    except Exception as e:
        return {"error": str(e)}

# ---------------------------
# Эндпоинт: прогноз цены (ML)
# ---------------------------
@app.post("/predict_price")
def get_predicted_price(query: PriceQuery):
    try:
        predicted_price = predict(query.store, query.unit)
        return {"store": query.store, "unit": query.unit, "predicted_price": float(predicted_price)}

    except Exception as e:
        return {"error": str(e)}