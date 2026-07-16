# ai/self-learning/concept_drift_detector.py
"""
NEXUS AI TRADING SYSTEM - Concept Drift Detector
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import warnings
from collections import deque
import time

try:
    from scipy import stats
    from scipy.spatial.distance import jensenshannon
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ConceptDriftConfig:
    """Configuration pour Concept Drift Detector"""
    window_size: int = 100
    min_samples: int = 30
    detection_threshold: float = 0.05
    confidence_level: float = 0.95
    method: str = 'ddm'  # 'ddm', 'ph', 'adwin', 'ks', 'isolation_forest'
    update_frequency: int = 10
    history_size: int = 1000
    drift_warning_threshold: float = 0.03

    def to_dict(self) -> Dict[str, Any]:
        return {
            'window_size': self.window_size,
            'min_samples': self.min_samples,
            'detection_threshold': self.detection_threshold,
            'confidence_level': self.confidence_level,
            'method': self.method,
            'update_frequency': self.update_frequency,
            'history_size': self.history_size,
            'drift_warning_threshold': self.drift_warning_threshold,
        }


@dataclass
class DriftResult:
    """Résultat de détection de concept drift"""
    drift_detected: bool
    drift_score: float
    confidence: float
    method: str
    timestamp: datetime
    details: Dict[str, Any]
    warning: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'drift_detected': self.drift_detected,
            'drift_score': self.drift_score,
            'confidence': self.confidence,
            'method': self.method,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
            'warning': self.warning,
        }


class ConceptDriftDetector:
    """
    Détecteur de concept drift pour l'IA de trading.

    Features:
    - DDM (Drift Detection Method)
    - PH (Page-Hinkley)
    - ADWIN (Adaptive Windowing)
    - KS Test
    - Isolation Forest
    - Multiple detection strategies

    Example:
        ```python
        config = ConceptDriftConfig(
            window_size=100,
            method='ddm',
            detection_threshold=0.05
        )
        detector = ConceptDriftDetector(config)

        for sample in data_stream:
            detector.update(sample)
            if detector.detect():
                # Concept drift detected
                print("Concept drift detected!")
        ```
    """

    def __init__(self, config: Optional[ConceptDriftConfig] = None):
        self.config = config or ConceptDriftConfig()
        self.data_buffer: deque = deque(maxlen=self.config.history_size)
        self.drift_history: List[DriftResult] = []
        self.stats: Dict[str, Any] = {
            'total_samples': 0,
            'drift_count': 0,
            'warning_count': 0,
            'last_drift': None,
        }

        # DDM spécifique
        self.ddm_errors = deque(maxlen=self.config.window_size)
        self.ddm_min_errors = float('inf')
        self.ddm_min_std = float('inf')
        self.ddm_count = 0

        # PH spécifique
        self.ph_sum = 0.0
        self.ph_min = 0.0
        self.ph_count = 0

        # ADWIN spécifique
        self.adwin_window = deque(maxlen=self.config.window_size)

        # Isolation Forest
        self.isolation_forest = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None

        logger.info(f"ConceptDriftDetector initialisé avec {self.config.method}")

    def _update_ddm(self, value: float) -> DriftResult:
        """Détection par DDM (Drift Detection Method)"""
        self.ddm_errors.append(1 if value > 0 else 0)

        if len(self.ddm_errors) > self.config.min_samples:
            error_rate = np.mean(self.ddm_errors)
            std = np.std(self.ddm_errors)

            if len(self.ddm_errors) == self.config.window_size:
                if error_rate + std < self.ddm_min_errors + self.ddm_min_std:
                    self.ddm_min_errors = error_rate
                    self.ddm_min_std = std

                drift_score = (error_rate - self.ddm_min_errors) / (self.ddm_min_std + 1e-6)

                if drift_score > self.config.detection_threshold:
                    return DriftResult(
                        drift_detected=True,
                        drift_score=drift_score,
                        confidence=1 - drift_score,
                        method='ddm',
                        timestamp=datetime.now(),
                        details={'error_rate': error_rate, 'std': std},
                        warning=drift_score > self.config.drift_warning_threshold
                    )

        return DriftResult(
            drift_detected=False,
            drift_score=0.0,
            confidence=1.0,
            method='ddm',
            timestamp=datetime.now(),
            details={}
        )

    def _update_ph(self, value: float) -> DriftResult:
        """Détection par Page-Hinkley"""
        self.ph_sum += value
        self.ph_count += 1

        if self.ph_count > 1:
            mean = self.ph_sum / self.ph_count
            if mean < self.ph_min:
                self.ph_min = mean

            drift_score = (self.ph_sum - self.ph_min) / (np.sqrt(self.ph_count) + 1e-6)

            if drift_score > self.config.detection_threshold:
                return DriftResult(
                    drift_detected=True,
                    drift_score=drift_score,
                    confidence=1 - drift_score,
                    method='ph',
                    timestamp=datetime.now(),
                    details={'mean': mean, 'count': self.ph_count},
                    warning=drift_score > self.config.drift_warning_threshold
                )

        return DriftResult(
            drift_detected=False,
            drift_score=0.0,
            confidence=1.0,
            method='ph',
            timestamp=datetime.now(),
            details={}
        )

    def _update_adwin(self, value: float) -> DriftResult:
        """Détection par ADWIN (Adaptive Windowing)"""
        self.adwin_window.append(value)

        if len(self.adwin_window) > self.config.min_samples:
            # Calcul des statistiques sur deux sous-fenêtres
            n = len(self.adwin_window)
            for i in range(2, n // 2):
                w1 = list(self.adwin_window)[:i]
                w2 = list(self.adwin_window)[i:]

                if len(w1) > 0 and len(w2) > 0:
                    mean1 = np.mean(w1)
                    mean2 = np.mean(w2)
                    std1 = np.std(w1)
                    std2 = np.std(w2)

                    drift_score = abs(mean1 - mean2) / (np.sqrt(std1**2 + std2**2) + 1e-6)

                    if drift_score > self.config.detection_threshold:
                        return DriftResult(
                            drift_detected=True,
                            drift_score=drift_score,
                            confidence=1 - drift_score,
                            method='adwin',
                            timestamp=datetime.now(),
                            details={'split_point': i, 'mean1': mean1, 'mean2': mean2},
                            warning=drift_score > self.config.drift_warning_threshold
                        )

        return DriftResult(
            drift_detected=False,
            drift_score=0.0,
            confidence=1.0,
            method='adwin',
            timestamp=datetime.now(),
            details={}
        )

    def _update_ks(self, value: float) -> DriftResult:
        """Détection par Kolmogorov-Smirnov test"""
        self.data_buffer.append(value)

        if len(self.data_buffer) > self.config.window_size * 2:
            # Comparer deux fenêtres
            window1 = list(self.data_buffer)[-self.config.window_size*2:-self.config.window_size]
            window2 = list(self.data_buffer)[-self.config.window_size:]

            if SCIPY_AVAILABLE:
                ks_stat, p_value = stats.ks_2samp(window1, window2)

                if ks_stat > self.config.detection_threshold:
                    return DriftResult(
                        drift_detected=True,
                        drift_score=ks_stat,
                        confidence=1 - p_value,
                        method='ks',
                        timestamp=datetime.now(),
                        details={'ks_stat': ks_stat, 'p_value': p_value},
                        warning=ks_stat > self.config.drift_warning_threshold
                    )

        return DriftResult(
            drift_detected=False,
            drift_score=0.0,
            confidence=1.0,
            method='ks',
            timestamp=datetime.now(),
            details={}
        )

    def _update_isolation_forest(self, value: float) -> DriftResult:
        """Détection par Isolation Forest"""
        if not SKLEARN_AVAILABLE:
            return DriftResult(
                drift_detected=False,
                drift_score=0.0,
                confidence=1.0,
                method='isolation_forest',
                timestamp=datetime.now(),
                details={'error': 'scikit-learn not available'}
            )

        self.data_buffer.append(value)

        if len(self.data_buffer) > self.config.window_size:
            # Préparation des données
            data = np.array(list(self.data_buffer)).reshape(-1, 1)

            if self.scaler is not None:
                data = self.scaler.fit_transform(data)

            # Détection
            if self.isolation_forest is None:
                self.isolation_forest = IsolationForest(
                    contamination='auto',
                    random_state=42
                )

            self.isolation_forest.fit(data)
            predictions = self.isolation_forest.predict(data)

            # Score d'anomalie
            anomaly_score = np.mean(predictions == -1)

            if anomaly_score > self.config.detection_threshold:
                return DriftResult(
                    drift_detected=True,
                    drift_score=anomaly_score,
                    confidence=1 - anomaly_score,
                    method='isolation_forest',
                    timestamp=datetime.now(),
                    details={'anomaly_score': anomaly_score},
                    warning=anomaly_score > self.config.drift_warning_threshold
                )

        return DriftResult(
            drift_detected=False,
            drift_score=0.0,
            confidence=1.0,
            method='isolation_forest',
            timestamp=datetime.now(),
            details={}
        )

    def update(self, value: Union[float, np.ndarray]) -> DriftResult:
        """
        Met à jour le détecteur avec une nouvelle valeur.

        Args:
            value: Valeur à analyser

        Returns:
            DriftResult: Résultat de la détection
        """
        self.stats['total_samples'] += 1

        # Valeur unique pour la plupart des méthodes
        if isinstance(value, (list, np.ndarray)):
            value = np.mean(value)

        result = None

        if self.config.method == 'ddm':
            result = self._update_ddm(value)
        elif self.config.method == 'ph':
            result = self._update_ph(value)
        elif self.config.method == 'adwin':
            result = self._update_adwin(value)
        elif self.config.method == 'ks':
            result = self._update_ks(value)
        elif self.config.method == 'isolation_forest':
            result = self._update_isolation_forest(value)
        else:
            raise ValueError(f"Méthode non supportée: {self.config.method}")

        if result is not None:
            if result.drift_detected:
                self.stats['drift_count'] += 1
                self.stats['last_drift'] = result.timestamp
                logger.warning(f"Concept drift détecté! Score: {result.drift_score:.4f}")

            if result.warning:
                self.stats['warning_count'] += 1

            self.drift_history.append(result)

        return result

    def detect(self) -> bool:
        """
        Vérifie si un concept drift est détecté.

        Returns:
            bool: True si drift détecté
        """
        if not self.drift_history:
            return False

        latest = self.drift_history[-1]
        return latest.drift_detected

    def get_drift_rate(self) -> float:
        """
        Calcule le taux de drift.

        Returns:
            float: Taux de drift
        """
        if self.stats['total_samples'] == 0:
            return 0.0

        return self.stats['drift_count'] / self.stats['total_samples']

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du détecteur.

        Returns:
            Dict[str, Any]: Statistiques
        """
        stats = self.stats.copy()
        stats['history_size'] = len(self.drift_history)
        stats['data_buffer_size'] = len(self.data_buffer)
        stats['drift_rate'] = self.get_drift_rate()
        return stats

    def reset(self) -> None:
        """Réinitialise le détecteur"""
        self.data_buffer.clear()
        self.drift_history.clear()
        self.ddm_errors.clear()
        self.ddm_min_errors = float('inf')
        self.ddm_min_std = float('inf')
        self.ph_sum = 0.0
        self.ph_min = 0.0
        self.ph_count = 0
        self.adwin_window.clear()
        self.isolation_forest = None
        self.stats = {
            'total_samples': 0,
            'drift_count': 0,
            'warning_count': 0,
            'last_drift': None,
        }
        logger.info("ConceptDriftDetector réinitialisé")

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le détecteur.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegardé
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'stats': self.stats,
                'drift_history': [r.to_dict() for r in self.drift_history],
                'data_buffer': list(self.data_buffer),
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"ConceptDriftDetector sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'ConceptDriftDetector':
        """
        Charge un détecteur.

        Args:
            filepath: Chemin du fichier

        Returns:
            ConceptDriftDetector: Détecteur chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = ConceptDriftConfig(**data['config'])
            detector = cls(config)

            detector.stats = data.get('stats', {})
            detector.data_buffer = deque(data.get('data_buffer', []), maxlen=config.history_size)

            # Restaurer l'historique
            for r in data.get('drift_history', []):
                detector.drift_history.append(DriftResult(
                    drift_detected=r['drift_detected'],
                    drift_score=r['drift_score'],
                    confidence=r['confidence'],
                    method=r['method'],
                    timestamp=datetime.fromisoformat(r['timestamp']),
                    details=r['details'],
                    warning=r.get('warning', False)
                ))

            logger.info(f"ConceptDriftDetector chargé: {filepath}")
            return detector

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_concept_drift_detector(
    method: str = 'ddm',
    window_size: int = 100,
    detection_threshold: float = 0.05,
    **kwargs
) -> ConceptDriftDetector:
    """
    Factory pour créer un détecteur de concept drift.

    Args:
        method: Méthode de détection
        window_size: Taille de la fenêtre
        detection_threshold: Seuil de détection
        **kwargs: Arguments supplémentaires

    Returns:
        ConceptDriftDetector: Détecteur de concept drift
    """
    config = ConceptDriftConfig(
        method=method,
        window_size=window_size,
        detection_threshold=detection_threshold,
        **kwargs
    )
    return ConceptDriftDetector(config)


__all__ = [
    'ConceptDriftDetector',
    'ConceptDriftConfig',
    'DriftResult',
    'create_concept_drift_detector',
]
