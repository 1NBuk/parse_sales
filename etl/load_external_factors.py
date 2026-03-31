import psycopg2
import requests
from xml.etree import ElementTree as ET
import yfinance as yf
import pandas as pd

PG_HOST = "localhost"
PG_DATABASE = "prices_db"
PG_USER = "postgres"
PG_PASSWORD = "12345"


def update_external_factors():

    conn = psycopg2.connect(
        host=PG_HOST,
        database=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.date
        FROM calendar c
        LEFT JOIN external_factors e ON c.date = e.date
        WHERE e.date IS NULL
        ORDER BY c.date
    """)
    dates = [row[0] for row in cursor.fetchall()]

    if not dates:
        print("Нет новых дат для external_factors")
        cursor.close()
        conn.close()
        return

    def get_rate(code, date_obj):
        url = f"https://www.cbr.ru/scripts/XML_daily.asp?date_req={date_obj.strftime('%d/%m/%Y')}"
        r = requests.get(url)
        tree = ET.fromstring(r.content)
        for valute in tree.findall('Valute'):
            if valute.find('CharCode').text == code:
                return float(valute.find('Value').text.replace(',', '.'))
        return None

    brent_df = yf.download("BZ=F", period="5y", interval="1d")

    def get_oil_price(date_obj):
        try:
            subset = brent_df[brent_df.index <= pd.Timestamp(date_obj)]
            if not subset.empty:
                return round(subset['Close'].iloc[-1].item(), 2)
        except:
            return None
        return None

    def get_weather(date_obj):
        url = (
            f"https://archive-api.open-meteo.com/v1/archive?"
            f"latitude=55.7558&longitude=37.6173"
            f"&start_date={date_obj}&end_date={date_obj}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        )
        r = requests.get(url)
        if r.status_code != 200:
            return None, None
        data = r.json()
        if 'daily' in data:
            tmax = data['daily']['temperature_2m_max'][0]
            tmin = data['daily']['temperature_2m_min'][0]
            return round((tmax + tmin) / 2, 2), data['daily']['precipitation_sum'][0]
        return None, None

    for date_obj in dates:
        usd = get_rate("USD", date_obj)
        eur = get_rate("EUR", date_obj)
        oil = get_oil_price(date_obj)
        temp, prec = get_weather(date_obj)

        cursor.execute("""
            INSERT INTO external_factors
            (date, usd_rub, eur_rub, oil_price, temperature, precipitation)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (date_obj, usd, eur, oil, temp, prec))

    conn.commit()
    cursor.close()
    conn.close()