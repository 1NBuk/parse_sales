# etl/extract.py
import os
import pandas as pd

from parsers import lenta_parser, pyaterochka_parser, perekrestok_parser
# импортируй остальные парсеры только если файлы реально существуют

def orchestrate():
    all_data = []

    parsers = [
        lenta_parser,
        pyaterochka_parser,
        perekrestok_parser,
        # diksi_parser, azbuka_parser, metro_parser, ashan_parser
    ]

    for parser in parsers:
        try:
            print(f"🔍 Запускаем {parser.__name__} ...")
            data = parser.run()  # в каждом парсере должна быть функция run() которая возвращает DataFrame
            all_data.append(data)
        except Exception as e:
            print(f"⚠️ Ошибка при выполнении {parser.__name__}: {e}")

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        os.makedirs("../data/raw/", exist_ok=True)
        combined.to_csv("../data/raw/combined_prices.csv", index=False)
        print(f"✅ Сохранено {len(combined)} записей в data/raw/combined_prices.csv")
    else:
        print("⚠️ Нет данных для сохранения.")

if __name__ == "__main__":
    orchestrate()
