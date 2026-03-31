import psycopg2
import requests
from xml.etree import ElementTree as ET
import yfinance as yf
import pandas as pd
import sys
import argparse
from datetime import datetime

PG_HOST = "localhost"
PG_DATABASE = "prices_db"
PG_USER = "postgres"
PG_PASSWORD = "12345"

def get_rate(code, date_obj):
    url = f"https://www.cbr.ru/scripts/XML_daily.asp?date_req={date_obj.strftime('%d/%m/%Y')}"
    try:
        r = requests.get(url)
        tree = ET.fromstring(r.content)
        for valute in tree.findall('Valute'):
            if valute.find('CharCode').text == code:
                return float(valute.find('Value').text.replace(',', '.'))
    except:
        return None
    return None

def get_oil_price(brent_df, date_obj):
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
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None, None
        data = r.json()
        if 'daily' in data:
            tmax = data['daily']['temperature_2m_max'][0]
            tmin = data['daily']['temperature_2m_min'][0]
            return round((tmax+tmin)/2, 2), data['daily']['precipitation_sum'][0]
    except:
        pass
    return None, None

def fetch_external_factor(date_str, factor):
    date_obj = pd.to_datetime(date_str).date()
    brent_df = yf.download("BZ=F", period="5y", interval="1d")

    values = {
        "usd_rub": get_rate("USD", date_obj),
        "eur_rub": get_rate("EUR", date_obj),
        "oil_price": get_oil_price(brent_df, date_obj),
        "temperature": get_weather(date_obj)[0],
        "precipitation": get_weather(date_obj)[1]
    }

    if factor:
        # вернем только выбранный фактор
        values = {factor: values.get(factor)}

    df = pd.DataFrame([{"date": date_obj, **values}])
    print(df.to_json(orient="records", date_format="iso"))
    sys.stdout.flush()
    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Дата в формате YYYY-MM-DD")
    parser.add_argument("--factor", required=False, help="Фактор: usd_rub, eur_rub, oil_price, temperature, precipitation")
    args = parser.parse_args()

    fetch_external_factor(args.date, args.factor)