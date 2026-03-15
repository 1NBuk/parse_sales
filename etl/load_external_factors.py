import psycopg2
import requests
from datetime import datetime, date as dt
from xml.etree import ElementTree as ET
from yahoo_fin import stock_info as si
import yfinance as yf
import pandas as pd
PG_HOST = "localhost"
PG_DATABASE = "prices_db"
PG_USER = "postgres"
PG_PASSWORD = "12345"

# Подключение к БД
conn = psycopg2.connect(
    host=PG_HOST,
    database=PG_DATABASE,
    user=PG_USER,
    password=PG_PASSWORD
)
cursor = conn.cursor()

# 1. Получаем уникальные даты из prices_history
cursor.execute("""
    SELECT DISTINCT date
    FROM prices_history
    ORDER BY date
""")
dates = [row[0] for row in cursor.fetchall()]

# 2. Функции для получения данных
def get_usd_rub(date_obj):
    url = f"https://www.cbr.ru/scripts/XML_daily.asp?date_req={date_obj.strftime('%d/%m/%Y')}"
    r = requests.get(url)
    tree = ET.fromstring(r.content)
    for valute in tree.findall('Valute'):
        if valute.find('CharCode').text == 'USD':
            return float(valute.find('Value').text.replace(',', '.'))
    return None

def get_eur_rub(date_obj):
    url = f"https://www.cbr.ru/scripts/XML_daily.asp?date_req={date_obj.strftime('%d/%m/%Y')}"
    r = requests.get(url)
    tree = ET.fromstring(r.content)
    for valute in tree.findall('Valute'):
        if valute.find('CharCode').text == 'EUR':
            return float(valute.find('Value').text.replace(',', '.'))
    return None

brent_df = yf.download("BZ=F", period="5y", interval="1d")

def get_oil_price(date_obj):
    try:
        date_obj = pd.Timestamp(date_obj)

        subset = brent_df[brent_df.index <= date_obj]

        if not subset.empty:
            return round(subset['Close'].iloc[-1].item(), 2)

    except Exception as e:
        print("Ошибка Brent:", e)

    return None

def get_weather(date_obj):
    # Москва
    lat, lon = 55.7558, 37.6173
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}&start_date={date_obj}&end_date={date_obj}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=Europe/Moscow"
    )
    r = requests.get(url)
    if r.status_code != 200:
        print("Ошибка запроса погоды:", r.status_code)
        return None, None
    data = r.json()
    if 'daily' in data:
        temp_max = data['daily']['temperature_2m_max'][0]
        temp_min = data['daily']['temperature_2m_min'][0]
        temp_avg = round((temp_max + temp_min)/2, 2)
        prec = data['daily']['precipitation_sum'][0]
        return temp_avg, prec
    return None, None

# 3. Получаем данные и выводим в консоль
for date_obj in dates[:5]:  # Для примера первые 5 дат
    usd = get_usd_rub(date_obj)
    eur = get_eur_rub(date_obj)
    oil = get_oil_price(date_obj)
    temp, prec = get_weather(date_obj)

    print(f"Дата: {date_obj}")
    print(f"USD/RUB: {usd}, EUR/RUB: {eur}, Oil Brent: {oil}, Temp: {temp}, Precipitation: {prec}")
    print("-" * 50)

for date_obj in dates:

    usd = get_usd_rub(date_obj)
    eur = get_eur_rub(date_obj)
    oil = get_oil_price(date_obj)
    temp, prec = get_weather(date_obj)

    print(f"Обрабатываем: {date_obj}")

    cursor.execute("""
        INSERT INTO external_factors
        (date, usd_rub, eur_rub, oil_price, temperature, precipitation)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (date) DO UPDATE SET
            usd_rub = EXCLUDED.usd_rub,
            eur_rub = EXCLUDED.eur_rub,
            oil_price = EXCLUDED.oil_price,
            temperature = EXCLUDED.temperature,
            precipitation = EXCLUDED.precipitation
    """, (date_obj, usd, eur, oil, temp, prec))


# Сохраняем изменения
conn.commit()

cursor.close()
conn.close()

print("Готово. External factors загружены.")