import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import random
import logging
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures, LabelEncoder
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
import os
import math

logger = logging.getLogger(__name__)


class MLService:
    """Service de Machine Learning pour prédictions, classifications et priorités"""
    
    def __init__(self, model_dir='models/'):
        self.models = {}
        self.poly_features = None
        self.model_dir = model_dir
        self.vectorizer = None
        self.priorite_vectorizer = None  # AJOUTÉ : vectorizer spécifique pour priorité
        self.label_encoder_categorie = LabelEncoder()
        self.label_encoder_priorite = LabelEncoder()
        
        # Créer le dossier des modèles
        os.makedirs(model_dir, exist_ok=True)
        
        # Charger les modèles si existent
        self._load_models()
    
    def _load_models(self):
        """Charge les modèles pré-entraînés"""
        try:
            # Modèle de classification
            if os.path.exists(f'{self.model_dir}classifier.pkl'):
                self.models['classifier'] = joblib.load(f'{self.model_dir}classifier.pkl')
                self.models['vectorizer'] = joblib.load(f'{self.model_dir}vectorizer.pkl')
                self.models['label_encoder_cat'] = joblib.load(f'{self.model_dir}label_encoder_cat.pkl')
                logger.info("Modèles de classification chargés")
            
            # Modèle de priorité
            if os.path.exists(f'{self.model_dir}priorite.pkl'):
                self.models['priorite'] = joblib.load(f'{self.model_dir}priorite.pkl')
                self.models['priorite_vectorizer'] = joblib.load(f'{self.model_dir}priorite_vectorizer.pkl')
                self.models['label_encoder_prio'] = joblib.load(f'{self.model_dir}label_encoder_prio.pkl')
                logger.info("Modèle de priorité chargé")
            
            # Modèle de prédiction volume
            if os.path.exists(f'{self.model_dir}volume_linear.pkl'):
                self.models['volume_linear'] = joblib.load(f'{self.model_dir}volume_linear.pkl')
                self.models['volume_rf'] = joblib.load(f'{self.model_dir}volume_rf.pkl')
                self.models['poly_features'] = joblib.load(f'{self.model_dir}poly_features.pkl')
                logger.info("Modèles de prédiction volume chargés")
        
        except Exception as e:
            logger.warning(f"Impossible de charger les modèles: {e}")
    
    def _save_models(self):
        """Sauvegarde les modèles entraînés"""
        try:
            # ✅ CORRECTION : Liste complète des objets à ne pas sauvegarder comme modèles
            excluded_objects = [
                'vectorizer',
                'priorite_vectorizer',  # ✅ AJOUTÉ
                'label_encoder_cat',
                'label_encoder_prio',
                'poly_features'
            ]
            
            for name, model in self.models.items():
                if name not in excluded_objects:
                    joblib.dump(model, f'{self.model_dir}{name}.pkl')
            
            # Sauvegarder les vectorizers et encoders séparément
            if 'vectorizer' in self.models:
                joblib.dump(self.models['vectorizer'], f'{self.model_dir}vectorizer.pkl')
            if 'priorite_vectorizer' in self.models:
                joblib.dump(self.models['priorite_vectorizer'], f'{self.model_dir}priorite_vectorizer.pkl')
            if 'label_encoder_cat' in self.models:
                joblib.dump(self.models['label_encoder_cat'], f'{self.model_dir}label_encoder_cat.pkl')
            if 'label_encoder_prio' in self.models:
                joblib.dump(self.models['label_encoder_prio'], f'{self.model_dir}label_encoder_prio.pkl')
            if self.poly_features:
                joblib.dump(self.poly_features, f'{self.model_dir}poly_features.pkl')
            
            logger.info("Modèles sauvegardés avec succès")
        
        except Exception as e:
            logger.error(f"Erreur sauvegarde modèles: {e}")
    
    # ==================== PRÉDICTION VOLUME (REGRESSION) ====================
    
    def prepare_features_volume(self, historical_data):
        """Prépare les features pour le modèle de prédiction de volume"""
        if len(historical_data) < 14:
            return None, None
        
        X = []
        y = []
        
        for i in range(len(historical_data) - 7):
            week_data = historical_data[i:i+7]
            
            features = [
                sum(d['count'] for d in week_data) / 7,  # Moyenne semaine
                week_data[-1]['count'],                     # Dernier jour
                week_data[-1]['date'].weekday(),            # Jour de semaine
                week_data[-1]['date'].month,                # Mois
                self._calculate_trend(week_data)            # Tendance
            ]
            
            X.append(features)
            y.append(historical_data[i+7]['count'])
        
        return np.array(X), np.array(y)
    
    def _calculate_trend(self, data):
        """Calcule la tendance sur une période"""
        if len(data) < 2:
            return 0
        
        values = [d['count'] for d in data]
        x = list(range(len(values)))
        
        n = len(x)
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        return slope
    
    def train_linear_model_volume(self, historical_data):
        """Entraîne un modèle de régression linéaire polynomiale"""
        X, y = self.prepare_features_volume(historical_data)
        
        if X is None or len(X) < 10:
            logger.warning("Pas assez de données pour l'entraînement ML")
            return None
        
        try:
            self.poly_features = PolynomialFeatures(degree=2, include_bias=False)
            X_poly = self.poly_features.fit_transform(X)
            
            model = LinearRegression()
            model.fit(X_poly, y)
            
            score = model.score(X_poly, y)
            logger.info(f"Modèle linéaire entraîné avec score R²: {score:.3f}")
            
            self.models['volume_linear'] = model
            self._save_models()
            return model
        
        except Exception as e:
            logger.error(f"Erreur entraînement modèle linéaire: {e}")
            return None
    
    def train_random_forest_volume(self, historical_data):
        """Entraîne un modèle Random Forest pour le volume"""
        X, y = self.prepare_features_volume(historical_data)
        
        if X is None or len(X) < 10:
            return None
        
        try:
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X, y)
            
            score = model.score(X, y)
            logger.info(f"Random Forest entraîné avec score R²: {score:.3f}")
            
            self.models['volume_rf'] = model
            self._save_models()
            return model
        
        except Exception as e:
            logger.error(f"Erreur Random Forest: {e}")
            return None
    
    def predict_volume(self, historical_data, days=30, model_type='linear'):
        """Prédit le volume pour les X prochains jours avec ML"""
        if not historical_data or len(historical_data) < 14:
            logger.warning("Données historiques insuffisantes")
            return self._fallback_prediction(days)
        
        # Choix du modèle
        if model_type == 'linear' and 'volume_linear' in self.models:
            model = self.models['volume_linear']
        elif model_type == 'rf' and 'volume_rf' in self.models:
            model = self.models['volume_rf']
        else:
            # Entraîner si non disponible
            if model_type == 'linear':
                model = self.train_linear_model_volume(historical_data)
            else:
                model = self.train_random_forest_volume(historical_data)
        
        if model is None:
            return self._fallback_prediction(days)
        
        predictions = []
        last_week = historical_data[-7:]
        
        for day in range(days):
            pred_date = datetime.now() + timedelta(days=day)
            
            features = [
                sum(d['count'] for d in last_week) / 7,
                last_week[-1]['count'],
                pred_date.weekday(),
                pred_date.month,
                self._calculate_trend(last_week)
            ]
            
            features_array = np.array(features).reshape(1, -1)
            
            if model_type == 'linear' and self.poly_features:
                features_array = self.poly_features.transform(features_array)
            
            try:
                pred = max(0, int(model.predict(features_array)[0]))
            except Exception as e:
                logger.error(f"Erreur prédiction: {e}")
                pred = int(sum(d['count'] for d in last_week) / 7)
            
            # Ajouter un facteur saisonnier et du bruit réaliste
            seasonal = self._seasonal_factor(pred_date)
            noise = random.uniform(0.85, 1.15)
            
            pred = int(pred * seasonal * noise)
            pred = max(1, min(pred, 50))
            
            predictions.append(pred)
            
            last_week.append({'count': pred, 'date': pred_date})
            if len(last_week) > 7:
                last_week.pop(0)
        
        return predictions
    
    def _seasonal_factor(self, date):
        """Facteur saisonnier (feature métier)"""
        if date.weekday() >= 5:
            weekday_factor = 0.7
        else:
            weekday_factor = 1.0
        
        monthly_factors = {
            1: 0.9, 2: 0.85, 3: 1.0, 4: 1.05, 5: 1.1, 6: 1.15,
            7: 0.8, 8: 0.7, 9: 1.1, 10: 1.15, 11: 1.1, 12: 0.9
        }
        
        month_factor = monthly_factors.get(date.month, 1.0)
        return weekday_factor * month_factor
    
    def _fallback_prediction(self, days):
        """Prédiction de secours"""
        predictions = []
        base = 8
        trend = 0.05
        
        for i in range(days):
            cycle = math.sin(i * 2 * math.pi / 7) * 2
            pred = max(2, int(base + (i * trend) + cycle + random.randint(-2, 3)))
            predictions.append(pred)
        
        return predictions
    
    # ==================== CLASSIFICATION DES COURRIERS (ML) ====================
    
    def train_classifier(self, courriers_labelises):
        """
        Entraîne un modèle de classification supervisée
        courriers_labelises: list de {'texte': str, 'categorie': str}
        """
        if len(courriers_labelises) < 50:
            logger.warning("Pas assez de données labelisées pour la classification ML")
            return None
        
        try:
            # Extraire textes et labels
            textes = [c['texte'] for c in courriers_labelises]
            categories = [c['categorie'] for c in courriers_labelises]
            
            # Encoder les labels
            y = self.label_encoder_categorie.fit_transform(categories)
            
            # Vectorisation TF-IDF
            self.vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words='french',
                ngram_range=(1, 2)
            )
            X = self.vectorizer.fit_transform(textes)
            
            # Split train/test
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Entraîner Random Forest Classifier
            classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=15,
                random_state=42,
                class_weight='balanced'
            )
            classifier.fit(X_train, y_train)
            
            # Évaluation
            y_pred = classifier.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            logger.info(f"Classification ML - Accuracy: {accuracy:.3f}")
            logger.info(f"\n{classification_report(y_test, y_pred, target_names=self.label_encoder_categorie.classes_)}")
            
            # Sauvegarder
            self.models['classifier'] = classifier
            self.models['vectorizer'] = self.vectorizer
            self.models['label_encoder_cat'] = self.label_encoder_categorie
            self._save_models()
            
            return classifier
        
        except Exception as e:
            logger.error(f"Erreur entraînement classifieur: {e}")
            return None
    
    def categorize_courrier(self, texte):
        """
        Classification ML d'un courrier
        Retourne la catégorie et le service associé
        """
        if not texte:
            return {'categorie': 'Autre', 'service': 'Divers', 'confidence': 50}
        
        # Si modèle disponible, utiliser ML
        if 'classifier' in self.models and 'vectorizer' in self.models:
            try:
                # Vectoriser
                X = self.models['vectorizer'].transform([texte])
                
                # Prédiction
                pred = self.models['classifier'].predict(X)[0]
                probas = self.models['classifier'].predict_proba(X)[0]
                confidence = int(max(probas) * 100)
                
                categorie = self.models['label_encoder_cat'].inverse_transform([pred])[0]
                
                # Mapping catégorie -> service
                service_map = {
                    'Facturation': 'Finance',
                    'RH': 'Ressources Humaines',
                    'Juridique': 'Direction Juridique',
                    'Urbanisme': 'Urbanisme',
                    'Administratif': 'Administration',
                    'Technique': 'Direction Technique',
                    'Social': 'Action Sociale',
                    'Finances': 'Direction Financière'
                }
                
                return {
                    'categorie': categorie,
                    'service': service_map.get(categorie, 'Divers'),
                    'confidence': confidence,
                    'method': 'machine_learning'
                }
            
            except Exception as e:
                logger.error(f"Erreur classification ML: {e}")
                return self._categorize_rule_based(texte)
        
        # Fallback: système à base de règles
        return self._categorize_rule_based(texte)
    
    def _categorize_rule_based(self, texte):
        """Système expert de catégorisation (fallback)"""
        categories = {
            'Facturation': {
                'keywords': ['facture', 'paiement', 'montant', 'tva', 'invoice', 'règlement'],
                'service': 'Finance'
            },
            'RH': {
                'keywords': ['recrutement', 'conge', 'salaire', 'personnel', 'formation', 'rh'],
                'service': 'Ressources Humaines'
            },
            'Juridique': {
                'keywords': ['contrat', 'loi', 'decret', 'arreté', 'juridique', 'legal'],
                'service': 'Direction Juridique'
            },
            'Urbanisme': {
                'keywords': ['permis', 'construire', 'urbanisme', 'foncier', 'terrain'],
                'service': 'Urbanisme'
            }
        }
        
        if not texte:
            return {'categorie': 'Autre', 'service': 'Divers', 'confidence': 50}
        
        texte_lower = texte.lower()
        scores = {}
        
        for cat, info in categories.items():
            score = sum(1 for kw in info['keywords'] if kw in texte_lower)
            scores[cat] = score
        
        if max(scores.values()) > 0:
            best_cat = max(scores, key=scores.get)
            confidence = min(95, 50 + (scores[best_cat] / len(categories[best_cat]['keywords']) * 50))
            
            return {
                'categorie': best_cat,
                'service': categories[best_cat]['service'],
                'confidence': int(confidence),
                'method': 'rule_based'
            }
        
        return {'categorie': 'Autre', 'service': 'Divers', 'confidence': 50, 'method': 'rule_based'}
    
    # ==================== PRÉDICTION PRIORITÉ (ML) ====================
    
    def train_priorite_model(self, courriers_labelises):
        """
        Entraîne un modèle ML pour prédire la priorité
        courriers_labelises: list de {'texte': str, 'priorite': str}
        """
        if len(courriers_labelises) < 50:
            logger.warning("Pas assez de données pour entraîner la priorité ML")
            return None
        
        try:
            textes = [c['texte'] for c in courriers_labelises]
            priorites = [c['priorite'] for c in courriers_labelises]
            
            # Encoder les priorités
            y = self.label_encoder_priorite.fit_transform(priorites)
            
            # Vectorisation
            self.priorite_vectorizer = TfidfVectorizer(
                max_features=500,
                stop_words='french',
                ngram_range=(1, 2)
            )
            X = self.priorite_vectorizer.fit_transform(textes)
            
            # Split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Modèle
            classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight='balanced'
            )
            classifier.fit(X_train, y_train)
            
            # Évaluation
            y_pred = classifier.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            logger.info(f"Priorité ML - Accuracy: {accuracy:.3f}")
            
            # Sauvegarder
            self.models['priorite'] = classifier
            self.models['priorite_vectorizer'] = self.priorite_vectorizer  # ✅ AJOUTÉ
            self.models['label_encoder_prio'] = self.label_encoder_priorite
            self._save_models()
            
            return classifier
        
        except Exception as e:
            logger.error(f"Erreur entraînement priorité: {e}")
            return None
    
    def suggest_priority(self, texte, expediteur=None):
        """
        Suggère une priorité via ML ou règles
        """
        if not texte:
            return 'low'
        
        # Si modèle disponible, utiliser ML
        if 'priorite' in self.models and 'priorite_vectorizer' in self.models:
            try:
                X = self.models['priorite_vectorizer'].transform([texte])
                pred = self.models['priorite'].predict(X)[0]
                priorite = self.models['label_encoder_prio'].inverse_transform([pred])[0]
                
                # Si expéditeur prioritaire, augmenter
                if expediteur and self._is_priority_expediteur(expediteur):
                    if priorite == 'low':
                        priorite = 'medium'
                    elif priorite == 'medium':
                        priorite = 'high'
                
                return priorite
            
            except Exception as e:
                logger.error(f"Erreur prédiction priorité ML: {e}")
                return self._suggest_priority_rule_based(texte, expediteur)
        
        # Fallback: règles
        return self._suggest_priority_rule_based(texte, expediteur)
    
    def _is_priority_expediteur(self, expediteur):
        """Vérifie si l'expéditeur est prioritaire"""
        priority_expediteurs = [
            'ministre', 'cabinet', 'direction generale', 'prefet', 'wali'
        ]
        expediteur_lower = expediteur.lower()
        return any(pe in expediteur_lower for pe in priority_expediteurs)
    
    def _suggest_priority_rule_based(self, texte, expediteur=None):
        """Système expert de priorisation (fallback)"""
        texte_lower = texte.lower() if texte else ''
        
        high_priority_keywords = [
            'urgent', 'important', 'alerte', 'prioritaire', 'asap', 'immédiat',
            'critique', 'danger', 'accident', 'incident', 'panne', 'bloquant'
        ]
        
        score = 0
        
        for kw in high_priority_keywords:
            if kw in texte_lower:
                score += 20
        
        if expediteur and self._is_priority_expediteur(expediteur):
            score += 30
        
        word_count = len(texte_lower.split()) if texte_lower else 0
        if word_count < 10:
            score -= 10
        
        if score >= 40:
            return 'high'
        elif score >= 20:
            return 'medium'
        else:
            return 'low'
    
    # ==================== DÉTECTION D'ANOMALIES (ML + Statistiques) ====================
    
    def detect_anomalies(self, courriers):
        """
        Détection d'anomalies avec ML (Isolation Forest) + statistiques
        """
        anomalies = []
        
        if not courriers:
            return anomalies
        
        # ===== ANOMALIE 1: Volume anormal par service (ML) =====
        from sklearn.ensemble import IsolationForest
        
        service_counts = defaultdict(int)
        for c in courriers:
            service = c.get('service_destinataire', 'inconnu')
            service_counts[service] += 1
        
        if len(service_counts) >= 3:
            try:
                # Préparer données pour Isolation Forest
                data = np.array([[count] for count in service_counts.values()])
                
                iso_forest = IsolationForest(contamination=0.1, random_state=42)
                predictions = iso_forest.fit_predict(data)
                
                services = list(service_counts.keys())
                for i, (service, count) in enumerate(service_counts.items()):
                    if predictions[i] == -1:  # Anomalie
                        anomalies.append({
                            'type': 'volume_anormal_ml',
                            'service': service,
                            'count': count,
                            'expected': int(np.mean(list(service_counts.values()))),
                            'severity': 'high',
                            'method': 'machine_learning'
                        })
            except Exception as e:
                logger.error(f"Erreur détection anomalies ML: {e}")
                # Fallback statistique
                values = list(service_counts.values())
                avg_volume = np.mean(values)
                std_volume = np.std(values)
                threshold = avg_volume + 2 * std_volume
                
                for service, count in service_counts.items():
                    if count > threshold:
                        anomalies.append({
                            'type': 'volume_anormal_stat',
                            'service': service,
                            'count': count,
                            'expected': int(avg_volume),
                            'severity': 'high' if count > avg_volume + 3 * std_volume else 'medium',
                            'method': 'statistique'
                        })
        
        # ===== ANOMALIE 2: Priorité sous-estimée (ML + Règles) =====
        for c in courriers:
            if c.get('priorite') != 'high':
                texte = (c.get('objet', '') + ' ' + (c.get('contenu', '') or ''))
                predicted_priority = self.suggest_priority(texte, c.get('expediteur', ''))
                
                if predicted_priority == 'high':
                    anomalies.append({
                        'type': 'priorite_sous_estimee_ml',
                        'courrier_id': c.get('id'),
                        'courrier_objet': c.get('objet', '')[:50],
                        'current_priority': c.get('priorite', 'low'),
                        'suggested_priority': 'high',
                        'severity': 'high',
                        'method': 'machine_learning'
                    })
        
        # ===== ANOMALIE 3: Doublons potentiels =====
        objets = {}
        for c in courriers:
            objet = c.get('objet', '').lower()
            if objet and len(objet) > 5:
                if objet in objets:
                    if c.get('expediteur') != objets[objet].get('expediteur'):
                        anomalies.append({
                            'type': 'doublon_potentiel',
                            'courrier_id_1': objets[objet].get('id'),
                            'courrier_id_2': c.get('id'),
                            'objet': c.get('objet', '')[:50],
                            'severity': 'low',
                            'method': 'rule_based'
                        })
                else:
                    objets[objet] = c
        
        return anomalies
    
    # ==================== BATCH TRAINING ====================
    
    def train_all_models(self, historical_volume_data, courriers_labelises):
        """
        Entraîne tous les modèles ML en une fois
        """
        logger.info("Début de l'entraînement batch des modèles ML...")
        
        results = {}
        
        # 1. Modèles de volume
        if historical_volume_data:
            linear_model = self.train_linear_model_volume(historical_volume_data)
            rf_model = self.train_random_forest_volume(historical_volume_data)
            results['volume'] = {
                'linear': linear_model is not None,
                'random_forest': rf_model is not None
            }
        
        # 2. Classificateur
        if courriers_labelises:
            classifier = self.train_classifier(courriers_labelises)
            results['classification'] = classifier is not None
        
        # 3. Modèle de priorité
        if courriers_labelises:
            priorite_model = self.train_priorite_model(courriers_labelises)
            results['priorite'] = priorite_model is not None
        
        logger.info(f"Entraînement batch terminé: {results}")
        return results
    
    def get_model_metrics(self):
        """
        Retourne les métriques des modèles entraînés
        """
        metrics = {
            'models_loaded': list(self.models.keys()),
            'classification': 'loaded' if 'classifier' in self.models else 'not_loaded',
            'priorite': 'loaded' if 'priorite' in self.models else 'not_loaded',
            'volume': 'loaded' if 'volume_rf' in self.models or 'volume_linear' in self.models else 'not_loaded'
        }
        return metrics


# Import pour math.sin dans fallback
import math