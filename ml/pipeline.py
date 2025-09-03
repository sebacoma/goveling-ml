from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, Any
from settings import settings

class DurationModelPipeline:
    """Pipeline ML completo para predicción de duraciones de visita"""
    
    def __init__(self):
        self.pipeline = None
        self.feature_columns = ['place_type_encoded', 'hour', 'day_of_week', 
                               'is_weekend', 'season', 'visitor_age_group']
        self.encoders = {}
        self.model_metadata = {}
        
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Feature engineering avanzado"""
        df = df.copy()
        
        # Encoding categórico con manejo robusto de tipos
        if 'place_type' in df.columns:
            # Convertir a string explícitamente
            df['place_type'] = df['place_type'].astype(str)
            
            if 'place_type' not in self.encoders:
                self.encoders['place_type'] = LabelEncoder()
                df['place_type_encoded'] = self.encoders['place_type'].fit_transform(df['place_type'])
            else:
                # Manejo de categorías nuevas
                known_categories = set(self.encoders['place_type'].classes_)
                df['place_type_safe'] = df['place_type'].apply(
                    lambda x: x if x in known_categories else 'unknown'
                )
                
                # Agregar 'unknown' si no existe
                if 'unknown' not in known_categories:
                    import numpy as np
                    current_classes = list(self.encoders['place_type'].classes_)
                    current_classes.append('unknown')
                    self.encoders['place_type'].classes_ = np.array(current_classes, dtype=object)
                
                df['place_type_encoded'] = self.encoders['place_type'].transform(df['place_type_safe'])
        
        # Features temporales con conversión explícita a numérico
        df['hour'] = pd.to_numeric(df['hour'], errors='coerce').fillna(12).astype('int64')
        
        if 'day_of_week' in df.columns:
            df['day_of_week'] = pd.to_numeric(df['day_of_week'], errors='coerce').fillna(1).astype('int64')
        elif 'weekday' in df.columns:
            # Mapear nombres de días a números
            day_mapping = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            df['day_of_week'] = df['weekday'].map(day_mapping).fillna(0).astype('int64')
        else:
            df['day_of_week'] = 1  # Default
            
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype('int64')
        df['season'] = ((df.get('month', 6) - 1) // 3) % 4  # 0-3 para estaciones
        df['season'] = pd.to_numeric(df['season'], errors='coerce').fillna(0).astype('int64')
        
        # Features de comportamiento
        visitor_age = df.get('visitor_age', pd.Series([30] * len(df)))
        df['visitor_age_group'] = (visitor_age // 10).astype('int64')  # Grupos por década
        
        # Asegurar que todas las columnas existen y son del tipo correcto
        for col in self.feature_columns:
            if col not in df.columns:
                if col == 'place_type_encoded':
                    df[col] = 0
                elif col in ['hour', 'day_of_week']:
                    df[col] = 9 if col == 'hour' else 1
                else:
                    df[col] = 0
            # Convertir todo a float64 para sklearn
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('float64')
        
        return df[self.feature_columns]
    
    def train(self, csv_path: str = None, df: pd.DataFrame = None) -> Dict[str, Any]:
        """Entrenamiento con validación y métricas"""
        if df is None:
            if csv_path is None:
                csv_path = "data/raw/Simulated_Duration_Dataset_clean.csv"
            df = pd.read_csv(csv_path)
        
        # Preparar features
        X = self.prepare_features(df)
        y = df['duration']  # Corregido: usar 'duration' en lugar de 'duration_hours'
        
        if len(X) < 10:
            raise ValueError("Dataset muy pequeño para entrenamiento")
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Modelos a comparar
        models = {
            'rf': RandomForestRegressor(random_state=42),
            'gb': GradientBoostingRegressor(random_state=42)
        }
        
        best_model = None
        best_score = float('inf')
        results = {}
        
        for name, model in models.items():
            try:
                # Grid search simplificado para datasets pequeños
                if len(X_train) < 100:
                    # Parámetros simples para datasets pequeños
                    if name == 'rf':
                        model.set_params(n_estimators=50, max_depth=5)
                    else:
                        model.set_params(n_estimators=50, learning_rate=0.1, max_depth=3)
                    
                    model.fit(X_train, y_train)
                    best_estimator = model
                else:
                    # Grid search completo para datasets grandes
                    if name == 'rf':
                        param_grid = {
                            'n_estimators': [100, 200],
                            'max_depth': [10, 20, None],
                            'min_samples_split': [2, 5]
                        }
                    else:
                        param_grid = {
                            'n_estimators': [100, 200],
                            'learning_rate': [0.1, 0.01],
                            'max_depth': [3, 5]
                        }
                    
                    grid_search = GridSearchCV(model, param_grid, cv=3, scoring='neg_mean_absolute_error')
                    grid_search.fit(X_train, y_train)
                    best_estimator = grid_search.best_estimator_
                
                # Evaluar
                y_pred = best_estimator.predict(X_test)
                mae = mean_absolute_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)
                
                results[name] = {
                    'model': best_estimator,
                    'mae': mae,
                    'r2': r2,
                    'best_params': best_estimator.get_params()
                }
                
                if mae < best_score:
                    best_score = mae
                    best_model = best_estimator
                    
            except Exception as e:
                logging.warning(f"Error entrenando modelo {name}: {e}")
                continue
        
        if best_model is None:
            raise RuntimeError("No se pudo entrenar ningún modelo")
        
        # Crear pipeline final
        self.pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('model', best_model)
        ])
        
        self.pipeline.fit(X_train, y_train)
        
        # Metadata del modelo
        self.model_metadata = {
            'trained_at': datetime.now().isoformat(),
            'samples_count': len(df),
            'best_mae': best_score,
            'feature_columns': self.feature_columns
        }
        
        # Guardar modelo y encoders
        self.save_model()
        
        logging.info(f"Modelo entrenado exitosamente. MAE: {best_score:.3f}")
        return results
    
    def predict(self, place_type: str, hour: int, day_of_week: int, **kwargs) -> float:
        """Predicción con manejo de errores"""
        if not self.pipeline:
            if not self.load_model():
                # Fallback a duraciones por defecto
                return self._get_default_duration(place_type)
        
        try:
            # Preparar input
            input_data = pd.DataFrame([{
                'place_type': place_type,
                'hour': hour,
                'day_of_week': day_of_week,
                'weekday': self._day_of_week_to_name(day_of_week),
                'month': kwargs.get('month', 6),
                'visitor_age': kwargs.get('visitor_age', 30)
            }])
            
            X = self.prepare_features(input_data)
            prediction = self.pipeline.predict(X)[0]
            
            # Validación de output
            return max(0.5, min(8.0, prediction))  # Entre 30min y 8h
            
        except Exception as e:
            logging.warning(f"Error en predicción ML: {e}, usando duración por defecto")
            return self._get_default_duration(place_type)
    
    def _day_of_week_to_name(self, day_of_week: int) -> str:
        """Convierte número de día a nombre"""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        return days[day_of_week % 7]
    
    def _get_default_duration(self, place_type: str) -> float:
        """Duración por defecto si falla ML"""
        import json
        try:
            with open("data/default_durations.json", "r") as f:
                defaults = json.load(f)
            
            if place_type in defaults:
                if isinstance(defaults[place_type], list):
                    return sum(defaults[place_type]) / len(defaults[place_type])
                return defaults[place_type]
            
            return defaults.get("_default", 1.5)
        except:
            return 1.5  # Fallback absoluto
    
    def save_model(self):
        """Guardar modelo y metadatos"""
        model_data = {
            'pipeline': self.pipeline,
            'encoders': self.encoders,
            'feature_columns': self.feature_columns,
            'metadata': self.model_metadata
        }
        
        import os
        os.makedirs(os.path.dirname(settings.MODEL_PATH), exist_ok=True)
        joblib.dump(model_data, settings.MODEL_PATH)
        logging.info(f"Modelo guardado en {settings.MODEL_PATH}")
    
    def load_model(self) -> bool:
        """Cargar modelo existente"""
        try:
            model_data = joblib.load(settings.MODEL_PATH)
            self.pipeline = model_data['pipeline']
            self.encoders = model_data['encoders']
            self.feature_columns = model_data['feature_columns']
            self.model_metadata = model_data.get('metadata', {})
            logging.info(f"Modelo cargado desde {settings.MODEL_PATH}")
            return True
        except FileNotFoundError:
            logging.warning("Modelo no encontrado, usar duraciones por defecto")
            return False
        except Exception as e:
            logging.error(f"Error cargando modelo: {e}")
            return False
    
    def is_model_ready(self) -> bool:
        """Verificar si el modelo está listo"""
        return self.pipeline is not None or self.load_model()

# Funciones de compatibilidad con el código existente
def train_duration_model(csv_path: str = "data/raw/Simulated_Duration_Dataset.csv"):
    """Función de compatibilidad"""
    pipeline = DurationModelPipeline()
    results = pipeline.train(csv_path)
    print(f"✅ Modelo entrenado y guardado en {settings.MODEL_PATH}")
    return results

def predict_duration(place_type: str, hour: int, weekday: str) -> float:
    """Función de compatibilidad"""
    pipeline = DurationModelPipeline()
    
    # Mapear nombre del día a número
    day_mapping = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    day_of_week = day_mapping.get(weekday.lower(), 1)
    
    return pipeline.predict(place_type, hour, day_of_week)
