# Price Forecast System

Система для сбора, обработки, анализа и прогнозирования цен на товары на основе исторических данных и внешних факторов.

Проект реализован в рамках выпускной квалификационной работы.

## Технологии

* Python
* PostgreSQL
* Streamlit
* Apache Airflow
* Apache Spark / PySpark
* CatBoost
* Selenium
* Docker

## Возможности

* сбор данных о ценах с сайтов магазинов;
* ETL-обработка и загрузка данных в PostgreSQL;
* обработка и агрегация данных с помощью PySpark;
* анализ и визуализация исторических данных;
* учёт внешних факторов: валют, цены нефти и погоды;
* прогнозирование цен с помощью CatBoost;
* загрузка пользовательских данных;
* автоматизация процессов через Airflow.

## Структура данных

Основные таблицы:

* `prices_history`
* `products`
* `brands`
* `stores`
* `external_factors`
* `calendar`
* `price_aggregates_spark`

## Интерфейс

### Главная

<img width="1801" height="873" alt="Main page" src="https://github.com/user-attachments/assets/5ea24a42-e6e0-4327-a95c-8d19a8e9be0c" />

### Графики

<img width="1805" height="861" alt="Charts" src="https://github.com/user-attachments/assets/f298365e-180b-48c9-a866-ac0ea63594ae" />

### Прогнозирование

<img width="1810" height="848" alt="Forecasting" src="https://github.com/user-attachments/assets/1c9d3ec9-f713-4fa3-82ff-77e2b10e75e6" />

## Запуск

1. Клонировать репозиторий:

```bash
git clone https://github.com/your_username/your_repo.git
cd your_repo
```

2. Создать файл `.env` с необходимыми переменными окружения.

3. Запустить проект:

```bash
docker compose up -d --build
```

4. Открыть Streamlit и Airflow в браузере по адресам, указанным в `docker-compose.yml`.

Для остановки проекта:

```bash
docker compose down
```

