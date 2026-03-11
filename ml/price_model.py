import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

MODEL_FILE = "ml/price_predictor.pkl"

def train_model(csv_path):
    df = pd.read_csv(csv_path)

    # Простейший пример: предсказываем цену по 'unit' и 'store'
    X = pd.get_dummies(df[['store', 'unit']], drop_first=True)
    y = df['price']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Сохраняем модель
    joblib.dump((model, X.columns.tolist()), MODEL_FILE)

    print("Модель обучена и сохранена!")

def predict(store, unit):
    model, columns = joblib.load(MODEL_FILE)
    X = pd.DataFrame([{ 'store': store, 'unit': unit }])
    X = pd.get_dummies(X).reindex(columns=columns, fill_value=0)
    return model.predict(X)[0]