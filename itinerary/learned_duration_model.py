import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer

from ml.pipeline import DurationModelPipeline
from settings import settings

MODEL_PATH = settings.MODEL_PATH

def train_duration_model(csv_path: str = "data/raw/Simulated_Duration_Dataset.csv"):
    """
    Entrena un modelo para predecir duración en un lugar según tipo, hora y día.
    Usa el nuevo pipeline ML mejorado.
    """
    pipeline = DurationModelPipeline()
    results = pipeline.train(csv_path)
    print(f"✅ Modelo entrenado y guardado en {MODEL_PATH}")
    return results

def predict_duration(place_type: str, hour: int, weekday: str) -> float:
    """
    Predice la duración estimada (en horas) que un usuario estará en un lugar.
    Usa el nuevo pipeline ML mejorado.
    """
    pipeline = DurationModelPipeline()
    
    # Mapear nombre del día a número
    day_mapping = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    day_of_week = day_mapping.get(weekday.lower(), 1)
    
    try:
        prediction = pipeline.predict(place_type, hour, day_of_week)
        return round(float(prediction), 2)
    except Exception as e:
        print(f"⚠️ Error en predicción ML: {e}, usando duración por defecto")
        # Fallback a duración por defecto
        return pipeline._get_default_duration(place_type)
