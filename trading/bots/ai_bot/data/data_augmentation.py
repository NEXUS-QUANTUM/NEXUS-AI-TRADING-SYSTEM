"""
NEXUS AI TRADING SYSTEM - Data Augmentation for AI Trading Bot
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Module: trading/bots/ai_bot/data/data_augmentation.py
Description: Module d'augmentation de données pour l'entraînement des modèles AI.
             Supporte les techniques avancées comme le Time Warping, la jitter,
             la scalping, la génération synthétique et l'augmentation par GAN.
             Permet de multiplier les données d'entraînement pour améliorer
             la robustesse des modèles.
"""

import logging
import random
import math
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd
from scipy import signal
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import CubicSpline
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from shared.exceptions import DataAugmentationError
from shared.helpers.number_helpers import round_decimal

# Configuration du logging
logger = logging.getLogger(__name__)


class AugmentationMethod(Enum):
    """Méthodes d'augmentation de données."""
    JITTER = "jitter"
    SCALING = "scaling"
    MAGNITUDE_WARP = "magnitude_warp"
    TIME_WARP = "time_warp"
    PERMUTATION = "permutation"
    ROTATION = "rotation"
    CUTOUT = "cutout"
    MIXUP = "mixup"
    CUTMIX = "cutmix"
    GAUSSIAN_NOISE = "gaussian_noise"
    DROPOUT = "dropout"
    SLICING = "slicing"
    WINDOW_SLICE = "window_slice"
    WINDOW_WARP = "window_warp"
    SPATIAL_WARP = "spatial_warp"
    GAN = "gan"
    SYNTHETIC = "synthetic"
    BOOTSTRAP = "bootstrap"
    STOCHASTIC = "stochastic"


@dataclass
class AugmentationConfig:
    """
    Configuration de l'augmentation de données.
    """
    # Méthodes à utiliser
    methods: List[AugmentationMethod] = field(default_factory=lambda: [
        AugmentationMethod.JITTER,
        AugmentationMethod.SCALING,
        AugmentationMethod.TIME_WARP
    ])
    
    # Probabilité d'application de chaque méthode
    prob: float = 0.5
    
    # Paramètres de jitter
    jitter_sigma: float = 0.01
    jitter_amplitude: float = 0.05
    
    # Paramètres de scaling
    scaling_min: float = 0.8
    scaling_max: float = 1.2
    
    # Paramètres de magnitude warp
    magnitude_warp_sigma: float = 0.1
    magnitude_warp_knots: int = 4
    
    # Paramètres de time warp
    time_warp_sigma: float = 0.1
    time_warp_knots: int = 4
    
    # Paramètres de permutation
    permutation_max_segments: int = 5
    
    # Paramètres de cutout
    cutout_size: Tuple[int, int] = (10, 20)
    cutout_count: int = 1
    
    # Paramètres de mixup
    mixup_alpha: float = 0.2
    
    # Paramètres de cutmix
    cutmix_alpha: float = 0.2
    
    # Paramètres de bruit gaussien
    noise_sigma: float = 0.01
    
    # Paramètres de dropout
    dropout_rate: float = 0.1
    
    # Paramètres de slicing
    slice_ratio: float = 0.1
    
    # Paramètres de window warp
    window_warp_ratio: float = 0.1
    
    # Paramètres GAN
    gan_model_path: Optional[str] = None
    gan_latent_dim: int = 100
    
    # Paramètres synthétiques
    synthetic_samples: int = 100
    synthetic_noise: float = 0.1
    
    # Paramètres de bootstrap
    bootstrap_samples: int = 100
    
    # Paramètres généraux
    random_seed: Optional[int] = 42
    parallel: bool = True
    n_workers: int = 4
    
    def __post_init__(self):
        """Validation des paramètres."""
        if self.random_seed is not None:
            np.random.seed(self.random_seed)
            random.seed(self.random_seed)


@dataclass
class AugmentationResult:
    """
    Résultat de l'augmentation de données.
    """
    # Données augmentées
    data: np.ndarray = field(default_factory=lambda: np.array([]))
    labels: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Métadonnées
    original_shape: Tuple[int, ...] = (0,)
    augmented_shape: Tuple[int, ...] = (0,)
    n_augmented: int = 0
    n_original: int = 0
    augmentation_factor: float = 0.0
    
    # Méthodes appliquées
    methods_applied: List[str] = field(default_factory=list)
    
    # Statistiques
    stats: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            'original_shape': self.original_shape,
            'augmented_shape': self.augmented_shape,
            'n_augmented': self.n_augmented,
            'n_original': self.n_original,
            'augmentation_factor': self.augmentation_factor,
            'methods_applied': self.methods_applied,
            'stats': self.stats
        }


class DataAugmentor:
    """
    Augmenteur de données pour les séries temporelles financières.
    """
    
    def __init__(self, config: Optional[AugmentationConfig] = None):
        """
        Initialise l'augmenteur de données.
        
        Args:
            config: Configuration de l'augmentation.
        """
        self.config = config or AugmentationConfig()
        self._gan_generator = None
        
        logger.info("DataAugmentor initialisé")
        logger.info(f"Méthodes: {[m.value for m in self.config.methods]}")
    
    # ============================================================
    # MÉTHODES D'AUGMENTATION
    # ============================================================
    
    def augment(
        self,
        data: np.ndarray,
        labels: Optional[np.ndarray] = None,
        n_augmented: Optional[int] = None
    ) -> AugmentationResult:
        """
        Augmente les données avec les méthodes configurées.
        
        Args:
            data: Données à augmenter (shape: [n_samples, n_features] ou [n_samples, n_timesteps, n_features]).
            labels: Labels associés.
            n_augmented: Nombre d'échantillons augmentés à générer.
            
        Returns:
            Résultats de l'augmentation.
        """
        if data is None or len(data) == 0:
            raise DataAugmentationError("Données vides")
        
        logger.info(f"Augmentation des données: {data.shape[0]} échantillons")
        
        # Détermination des dimensions
        is_3d = len(data.shape) == 3
        n_samples = data.shape[0]
        
        if n_augmented is None:
            n_augmented = n_samples * len(self.config.methods)
        
        # Augmentation
        augmented_data = []
        augmented_labels = []
        methods_used = []
        
        for method in self.config.methods:
            if random.random() > self.config.prob:
                continue
            
            try:
                if method == AugmentationMethod.JITTER:
                    aug_data = self._apply_jitter(data)
                elif method == AugmentationMethod.SCALING:
                    aug_data = self._apply_scaling(data)
                elif method == AugmentationMethod.MAGNITUDE_WARP:
                    aug_data = self._apply_magnitude_warp(data)
                elif method == AugmentationMethod.TIME_WARP:
                    aug_data = self._apply_time_warp(data)
                elif method == AugmentationMethod.PERMUTATION:
                    aug_data = self._apply_permutation(data)
                elif method == AugmentationMethod.ROTATION:
                    aug_data = self._apply_rotation(data)
                elif method == AugmentationMethod.CUTOUT:
                    aug_data = self._apply_cutout(data)
                elif method == AugmentationMethod.GAUSSIAN_NOISE:
                    aug_data = self._apply_gaussian_noise(data)
                elif method == AugmentationMethod.DROPOUT:
                    aug_data = self._apply_dropout(data)
                elif method == AugmentationMethod.SLICING:
                    aug_data = self._apply_slicing(data)
                elif method == AugmentationMethod.WINDOW_SLICE:
                    aug_data = self._apply_window_slice(data)
                elif method == AugmentationMethod.WINDOW_WARP:
                    aug_data = self._apply_window_warp(data)
                elif method == AugmentationMethod.SPATIAL_WARP:
                    aug_data = self._apply_spatial_warp(data)
                elif method == AugmentationMethod.SYNTHETIC:
                    aug_data = self._generate_synthetic(data)
                elif method == AugmentationMethod.BOOTSTRAP:
                    aug_data = self._apply_bootstrap(data)
                elif method == AugmentationMethod.MIXUP:
                    if labels is not None:
                        aug_data, aug_labels = self._apply_mixup(data, labels)
                elif method == AugmentationMethod.CUTMIX:
                    if labels is not None:
                        aug_data, aug_labels = self._apply_cutmix(data, labels)
                elif method == AugmentationMethod.GAN:
                    aug_data = self._apply_gan(data)
                else:
                    continue
                
                if aug_data is not None and len(aug_data) > 0:
                    # Limiter le nombre d'échantillons
                    if len(aug_data) > n_augmented:
                        indices = np.random.choice(len(aug_data), n_augmented, replace=False)
                        aug_data = aug_data[indices]
                        if labels is not None and aug_labels is not None:
                            aug_labels = aug_labels[indices]
                    
                    augmented_data.append(aug_data)
                    if labels is not None:
                        augmented_labels.append(aug_labels if aug_labels is not None else labels[:len(aug_data)])
                    methods_used.append(method.value)
                    
            except Exception as e:
                logger.error(f"Erreur avec la méthode {method.value}: {e}")
                continue
        
        if not augmented_data:
            raise DataAugmentationError("Aucune donnée augmentée générée")
        
        # Combinaison des résultats
        combined_data = np.concatenate(augmented_data, axis=0)
        
        if labels is not None:
            combined_labels = np.concatenate(augmented_labels, axis=0) if augmented_labels else None
        else:
            combined_labels = None
        
        # Résultat
        result = AugmentationResult(
            data=combined_data,
            labels=combined_labels,
            original_shape=data.shape,
            augmented_shape=combined_data.shape,
            n_original=n_samples,
            n_augmented=len(combined_data),
            augmentation_factor=len(combined_data) / n_samples,
            methods_applied=methods_used
        )
        
        # Statistiques
        result.stats = {
            'data_mean': float(np.mean(combined_data)),
            'data_std': float(np.std(combined_data)),
            'data_min': float(np.min(combined_data)),
            'data_max': float(np.max(combined_data))
        }
        
        logger.info(f"Augmentation terminée: {result.n_augmented} échantillons")
        logger.info(f"Méthodes utilisées: {', '.join(result.methods_applied)}")
        
        return result
    
    # ============================================================
    # TECHNIQUES D'AUGMENTATION
    # ============================================================
    
    def _apply_jitter(self, data: np.ndarray) -> np.ndarray:
        """
        Applique du jitter (bruit aléatoire) aux données.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        noise = np.random.normal(
            0,
            self.config.jitter_sigma * np.std(data, axis=0),
            data.shape
        )
        return data + noise * self.config.jitter_amplitude
    
    def _apply_scaling(self, data: np.ndarray) -> np.ndarray:
        """
        Applique une mise à l'échelle aléatoire.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        scale = np.random.uniform(self.config.scaling_min, self.config.scaling_max)
        
        # Appliquer le scaling à chaque échantillon
        augmented = data.copy()
        for i in range(len(data)):
            factor = np.random.uniform(self.config.scaling_min, self.config.scaling_max)
            augmented[i] = data[i] * factor
        
        return augmented
    
    def _apply_magnitude_warp(self, data: np.ndarray) -> np.ndarray:
        """
        Applique une déformation de magnitude.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        n_samples, n_features = data.shape
        knots = self.config.magnitude_warp_knots
        sigma = self.config.magnitude_warp_sigma
        
        augmented = data.copy()
        
        for i in range(n_samples):
            # Génération des points de contrôle
            knot_values = np.random.normal(1, sigma, knots)
            
            # Interpolation
            knot_positions = np.linspace(0, 1, knots)
            positions = np.linspace(0, 1, n_features)
            warp = CubicSpline(knot_positions, knot_values)(positions)
            
            # Application
            augmented[i] = data[i] * warp
        
        return augmented
    
    def _apply_time_warp(self, data: np.ndarray) -> np.ndarray:
        """
        Applique une déformation temporelle.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        n_samples, n_features = data.shape
        knots = self.config.time_warp_knots
        sigma = self.config.time_warp_sigma
        
        augmented = data.copy()
        
        for i in range(n_samples):
            # Génération des points de contrôle pour la déformation temporelle
            knot_values = np.random.normal(0, sigma, knots)
            
            # Interpolation pour obtenir la déformation
            knot_positions = np.linspace(0, 1, knots)
            positions = np.linspace(0, 1, n_features)
            warp = CubicSpline(knot_positions, knot_values)(positions)
            
            # Application de la déformation
            warped_positions = np.clip(np.arange(n_features) + warp * n_features * 0.1, 0, n_features - 1)
            warped_positions = warped_positions.astype(int)
            augmented[i] = data[i][warped_positions]
        
        return augmented
    
    def _apply_permutation(self, data: np.ndarray) -> np.ndarray:
        """
        Applique une permutation des segments.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        n_samples, n_features = data.shape
        n_segments = random.randint(2, self.config.permutation_max_segments)
        
        augmented = data.copy()
        
        for i in range(n_samples):
            # Division en segments
            segment_size = n_features // n_segments
            segments = []
            for j in range(n_segments):
                start = j * segment_size
                end = (j + 1) * segment_size
                segments.append(data[i, start:end])
            
            # Permutation aléatoire des segments
            random.shuffle(segments)
            augmented[i] = np.concatenate(segments)[:n_features]
        
        return augmented
    
    def _apply_rotation(self, data: np.ndarray) -> np.ndarray:
        """
        Applique une rotation aléatoire (pour les données 2D ou 3D).
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
        
        n_samples, n_features = data.shape
        
        if n_features < 2:
            return data
        
        # Création d'une matrice de rotation aléatoire
        angle = np.random.uniform(-np.pi, np.pi)
        rotation_matrix = np.array([
            [np.cos(angle), -np.sin(angle)],
            [np.sin(angle), np.cos(angle)]
        ])
        
        augmented = data.copy()
        for i in range(n_samples):
            if n_features >= 2:
                augmented[i, :2] = data[i, :2] @ rotation_matrix
        
        return augmented
    
    def _apply_cutout(self, data: np.ndarray) -> np.ndarray:
        """
        Applique un cutout (masque aléatoire).
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        n_samples, n_features = data.shape
        cut_size = self.config.cutout_size
        cut_count = self.config.cutout_count
        
        augmented = data.copy()
        
        for i in range(n_samples):
            for _ in range(cut_count):
                # Position aléatoire
                start = random.randint(0, n_features - cut_size[1])
                end = min(start + cut_size[1], n_features)
                
                # Mise à zéro des valeurs dans la zone
                if len(augmented.shape) == 2:
                    augmented[i, start:end] = 0
                else:
                    augmented[i, :, start:end] = 0
        
        return augmented
    
    def _apply_gaussian_noise(self, data: np.ndarray) -> np.ndarray:
        """
        Applique un bruit gaussien.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        noise = np.random.normal(
            0,
            self.config.noise_sigma * np.std(data, axis=0),
            data.shape
        )
        return data + noise
    
    def _apply_dropout(self, data: np.ndarray) -> np.ndarray:
        """
        Applique un dropout aléatoire.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        mask = np.random.binomial(1, 1 - self.config.dropout_rate, data.shape)
        return data * mask
    
    def _apply_slicing(self, data: np.ndarray) -> np.ndarray:
        """
        Applique un slicing (découpage) aléatoire.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        n_samples, n_features = data.shape
        slice_ratio = self.config.slice_ratio
        
        augmented = []
        
        for i in range(n_samples):
            # Longueur du slice
            slice_length = int(n_features * slice_ratio)
            if slice_length < 1:
                continue
            
            # Position aléatoire
            start = random.randint(0, n_features - slice_length)
            end = start + slice_length
            
            # Interpolation pour retrouver la taille originale
            sliced = data[i, start:end]
            if len(sliced) > 1:
                interp = np.interp(
                    np.linspace(0, 1, n_features),
                    np.linspace(0, 1, len(sliced)),
                    sliced
                )
                augmented.append(interp)
        
        return np.array(augmented) if augmented else data
    
    def _apply_window_slice(self, data: np.ndarray) -> np.ndarray:
        """
        Applique un window slicing.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        n_samples, n_features = data.shape
        window_size = int(n_features * 0.5)
        
        augmented = []
        
        for i in range(n_samples):
            for j in range(2):
                start = random.randint(0, n_features - window_size)
                end = start + window_size
                
                window = data[i, start:end]
                if len(window) > 0:
                    # Padding pour retrouver la taille originale
                    padded = np.zeros(n_features)
                    padded[:len(window)] = window
                    augmented.append(padded)
        
        return np.array(augmented) if augmented else data
    
    def _apply_window_warp(self, data: np.ndarray) -> np.ndarray:
        """
        Applique un window warp.
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        n_samples, n_features = data.shape
        warp_ratio = self.config.window_warp_ratio
        
        augmented = data.copy()
        
        for i in range(n_samples):
            # Point de déformation aléatoire
            warp_point = random.randint(0, n_features - 1)
            warp_amount = random.uniform(-warp_ratio, warp_ratio) * n_features
            
            # Application de la déformation
            warped = np.zeros(n_features)
            for j in range(n_features):
                new_pos = j + warp_amount * np.exp(-((j - warp_point) ** 2) / (n_features * 0.1))
                if 0 <= new_pos < n_features:
                    idx = int(new_pos)
                    warped[j] = data[i, idx]
                else:
                    warped[j] = data[i, j]
            
            augmented[i] = warped
        
        return augmented
    
    def _apply_spatial_warp(self, data: np.ndarray) -> np.ndarray:
        """
        Applique une déformation spatiale (pour les données 3D).
        
        Args:
            data: Données originales.
            
        Returns:
            Données augmentées.
        """
        if len(data.shape) != 3:
            return data
        
        n_samples, n_timesteps, n_features = data.shape
        
        augmented = data.copy()
        
        for i in range(n_samples):
            # Déformation dans le temps
            warp = np.random.normal(0, 0.1, n_timesteps)
            warp = np.cumsum(warp)
            warp = (warp - np.min(warp)) / (np.max(warp) - np.min(warp)) * (n_timesteps - 1)
            
            # Application
            for j in range(n_features):
                augmented[i, :, j] = np.interp(
                    np.arange(n_timesteps),
                    warp,
                    data[i, :, j]
                )
        
        return augmented
    
    def _apply_mixup(
        self,
        data: np.ndarray,
        labels: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Applique la technique MixUp.
        
        Args:
            data: Données originales.
            labels: Labels associés.
            
        Returns:
            Tuple (données augmentées, labels augmentés).
        """
        n_samples = len(data)
        alpha = self.config.mixup_alpha
        
        augmented_data = []
        augmented_labels = []
        
        for i in range(n_samples):
            # Choix aléatoire d'un autre échantillon
            j = random.randint(0, n_samples - 1)
            
            # Lambda de mixage
            lam = np.random.beta(alpha, alpha)
            
            # Mixage des données
            mixed_data = lam * data[i] + (1 - lam) * data[j]
            mixed_labels = lam * labels[i] + (1 - lam) * labels[j]
            
            augmented_data.append(mixed_data)
            augmented_labels.append(mixed_labels)
        
        return np.array(augmented_data), np.array(augmented_labels)
    
    def _apply_cutmix(
        self,
        data: np.ndarray,
        labels: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Applique la technique CutMix.
        
        Args:
            data: Données originales.
            labels: Labels associés.
            
        Returns:
            Tuple (données augmentées, labels augmentés).
        """
        n_samples, n_features = data.shape
        alpha = self.config.cutmix_alpha
        
        augmented_data = []
        augmented_labels = []
        
        for i in range(n_samples):
            # Choix aléatoire d'un autre échantillon
            j = random.randint(0, n_samples - 1)
            
            # Lambda de mixage
            lam = np.random.beta(alpha, alpha)
            
            # Taille de la zone de remplacement
            cut_size = int(n_features * (1 - lam))
            cut_start = random.randint(0, n_features - cut_size)
            cut_end = cut_start + cut_size
            
            # Mixage des données
            mixed_data = data[i].copy()
            mixed_data[cut_start:cut_end] = data[j, cut_start:cut_end]
            
            # Mixage des labels
            lam_actual = cut_size / n_features
            mixed_labels = (1 - lam_actual) * labels[i] + lam_actual * labels[j]
            
            augmented_data.append(mixed_data)
            augmented_labels.append(mixed_labels)
        
        return np.array(augmented_data), np.array(augmented_labels)
    
    def _apply_gan(self, data: np.ndarray) -> np.ndarray:
        """
        Applique un GAN pour générer des données synthétiques.
        
        Args:
            data: Données originales.
            
        Returns:
            Données générées par le GAN.
        """
        if self._gan_generator is None:
            self._load_gan()
        
        if self._gan_generator is None:
            logger.warning("GAN non disponible, utilisation de données aléatoires")
            return self._generate_synthetic(data)
        
        n_samples = len(data)
        latent_dim = self.config.gan_latent_dim
        
        # Génération
        latent = np.random.normal(0, 1, (n_samples, latent_dim))
        generated = self._gan_generator.predict(latent)
        
        return generated
    
    def _load_gan(self) -> None:
        """
        Charge le modèle GAN.
        """
        if self.config.gan_model_path:
            try:
                import tensorflow as tf
                self._gan_generator = tf.keras.models.load_model(self.config.gan_model_path)
                logger.info(f"GAN chargé depuis {self.config.gan_model_path}")
            except Exception as e:
                logger.error(f"Erreur de chargement du GAN: {e}")
                self._gan_generator = None
    
    def _generate_synthetic(self, data: np.ndarray) -> np.ndarray:
        """
        Génère des données synthétiques.
        
        Args:
            data: Données originales.
            
        Returns:
            Données synthétiques.
        """
        n_samples, n_features = data.shape
        n_synthetic = self.config.synthetic_samples
        
        # Calcul des statistiques
        mean = np.mean(data, axis=0)
        std = np.std(data, axis=0)
        
        # Génération
        synthetic = []
        
        for _ in range(n_synthetic):
            # Mélange de distributions
            if np.random.random() > 0.5:
                # Distribution normale autour de la moyenne
                sample = np.random.normal(mean, std, n_features)
            else:
                # Bootstrap
                idx = np.random.randint(0, n_samples)
                sample = data[idx] + np.random.normal(0, self.config.synthetic_noise, n_features)
            
            synthetic.append(sample)
        
        return np.array(synthetic)
    
    def _apply_bootstrap(self, data: np.ndarray) -> np.ndarray:
        """
        Applique un bootstrap (rééchantillonnage avec remise).
        
        Args:
            data: Données originales.
            
        Returns:
            Données bootstrapées.
        """
        n_samples = len(data)
        n_bootstrap = self.config.bootstrap_samples
        
        augmented = []
        
        for _ in range(n_bootstrap):
            indices = np.random.randint(0, n_samples, n_samples)
            augmented.append(data[indices])
        
        return np.concatenate(augmented, axis=0)
    
    # ============================================================
    # AUGMENTATION AVANCÉE
    # ============================================================
    
    def augment_with_style_transfer(
        self,
        data: np.ndarray,
        style_data: np.ndarray
    ) -> np.ndarray:
        """
        Applique un transfert de style entre deux séries temporelles.
        
        Args:
            data: Données source.
            style_data: Données de style.
            
        Returns:
            Données avec le style transféré.
        """
        # Normalisation des données
        data_mean = np.mean(data, axis=0)
        data_std = np.std(data, axis=0)
        
        style_mean = np.mean(style_data, axis=0)
        style_std = np.std(style_data, axis=0)
        
        # Transfert de style
        augmented = (data - data_mean) / (data_std + 1e-8)
        augmented = augmented * style_std + style_mean
        
        return augmented
    
    def augment_with_trend_preserving(
        self,
        data: np.ndarray,
        trend_preserving: float = 0.5
    ) -> np.ndarray:
        """
        Augmente les données en préservant la tendance.
        
        Args:
            data: Données originales.
            trend_preserving: Facteur de préservation de la tendance.
            
        Returns:
            Données augmentées.
        """
        # Extraction de la tendance
        trend = gaussian_filter1d(data, sigma=10)
        
        # Détail (bruit)
        detail = data - trend
        
        # Augmentation des détails
        noise_scale = np.random.uniform(0.5, 1.5)
        augmented_detail = detail * noise_scale
        
        # Reconstruction
        augmented = trend * trend_preserving + augmented_detail * (1 - trend_preserving)
        
        return augmented
    
    def augment_with_regime_shift(
        self,
        data: np.ndarray,
        shift_points: int = 1
    ) -> np.ndarray:
        """
        Augmente les données avec des changements de régime.
        
        Args:
            data: Données originales.
            shift_points: Nombre de points de changement.
            
        Returns:
            Données avec changements de régime.
        """
        n_samples, n_features = data.shape
        
        augmented = data.copy()
        
        for i in range(n_samples):
            # Points de changement aléatoires
            points = sorted(np.random.choice(
                np.arange(1, n_features - 1),
                shift_points,
                replace=False
            ))
            
            # Application des changements
            prev_shift = 0
            for point in points:
                # Multiplicateur aléatoire pour le régime
                regime_factor = np.random.uniform(0.5, 1.5)
                augmented[i, prev_shift:point] = augmented[i, prev_shift:point] * regime_factor
                prev_shift = point
            
            # Dernier régime
            if prev_shift < n_features:
                regime_factor = np.random.uniform(0.5, 1.5)
                augmented[i, prev_shift:] = augmented[i, prev_shift:] * regime_factor
        
        return augmented
    
    # ============================================================
    # UTILITAIRES
    # ============================================================
    
    def get_augmentation_stats(
        self,
        result: AugmentationResult
    ) -> Dict[str, Any]:
        """
        Retourne les statistiques détaillées de l'augmentation.
        
        Args:
            result: Résultat de l'augmentation.
            
        Returns:
            Statistiques détaillées.
        """
        stats = {
            'original_count': result.n_original,
            'augmented_count': result.n_augmented,
            'factor': result.augmentation_factor,
            'methods': result.methods_applied,
            'shape_original': result.original_shape,
            'shape_augmented': result.augmented_shape,
            'data_stats': result.stats
        }
        
        # Statistiques supplémentaires
        if len(result.data) > 0:
            data_flat = result.data.flatten()
            stats['percentiles'] = {
                '10': float(np.percentile(data_flat, 10)),
                '25': float(np.percentile(data_flat, 25)),
                '50': float(np.percentile(data_flat, 50)),
                '75': float(np.percentile(data_flat, 75)),
                '90': float(np.percentile(data_flat, 90))
            }
        
        return stats
    
    def visualize_augmentation(
        self,
        original: np.ndarray,
        augmented: np.ndarray,
        save_path: Optional[str] = None
    ) -> None:
        """
        Visualise l'augmentation de données.
        
        Args:
            original: Données originales.
            augmented: Données augmentées.
            save_path: Chemin de sauvegarde (optionnel).
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("Matplotlib non disponible")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. Comparaison original vs augmenté
        ax = axes[0, 0]
        for i in range(min(3, len(original))):
            ax.plot(original[i], color='blue', alpha=0.5, label='Original' if i == 0 else None)
        for i in range(min(3, len(augmented))):
            ax.plot(augmented[i], color='red', alpha=0.5, linestyle='--', label='Augmented' if i == 0 else None)
        ax.set_title('Original vs Augmented')
        ax.legend()
        
        # 2. Distribution
        ax = axes[0, 1]
        ax.hist(original.flatten(), bins=50, alpha=0.5, label='Original')
        ax.hist(augmented.flatten(), bins=50, alpha=0.5, label='Augmented')
        ax.set_title('Data Distribution')
        ax.legend()
        
        # 3. Statistiques
        ax = axes[1, 0]
        ax.axis('off')
        stats_text = (
            f"Original: {len(original)} samples\n"
            f"Augmented: {len(augmented)} samples\n"
            f"Factor: {len(augmented)/len(original):.2f}x\n\n"
            f"Original stats:\n"
            f"  Mean: {np.mean(original):.4f}\n"
            f"  Std: {np.std(original):.4f}\n"
            f"  Min: {np.min(original):.4f}\n"
            f"  Max: {np.max(original):.4f}\n\n"
            f"Augmented stats:\n"
            f"  Mean: {np.mean(augmented):.4f}\n"
            f"  Std: {np.std(augmented):.4f}\n"
            f"  Min: {np.min(augmented):.4f}\n"
            f"  Max: {np.max(augmented):.4f}"
        )
        ax.text(0.1, 0.5, stats_text, transform=ax.transAxes, fontsize=10, verticalalignment='center')
        
        # 4. Heatmap de corrélation
        ax = axes[1, 1]
        if len(original) > 1:
            corr_original = np.corrcoef(original[:min(10, len(original))])
            corr_augmented = np.corrcoef(augmented[:min(10, len(augmented))])
            im = ax.imshow(corr_augmented - corr_original, cmap='RdBu', vmin=-0.5, vmax=0.5)
            ax.set_title('Correlation Difference (Aug - Orig)')
            plt.colorbar(im, ax=ax)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Visualisation sauvegardée: {save_path}")
        
        plt.close()


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def augment_time_series(
    data: np.ndarray,
    labels: Optional[np.ndarray] = None,
    method: str = 'jitter',
    **kwargs
) -> AugmentationResult:
    """
    Fonction utilitaire pour augmenter des séries temporelles.
    
    Args:
        data: Données à augmenter.
        labels: Labels associés.
        method: Méthode d'augmentation.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Résultats de l'augmentation.
    """
    # Configuration
    config = AugmentationConfig(**kwargs)
    
    # Sélection de la méthode
    method_map = {
        'jitter': AugmentationMethod.JITTER,
        'scaling': AugmentationMethod.SCALING,
        'time_warp': AugmentationMethod.TIME_WARP,
        'magnitude_warp': AugmentationMethod.MAGNITUDE_WARP,
        'permutation': AugmentationMethod.PERMUTATION,
        'cutout': AugmentationMethod.CUTOUT,
        'mixup': AugmentationMethod.MIXUP,
        'gaussian_noise': AugmentationMethod.GAUSSIAN_NOISE,
        'dropout': AugmentationMethod.DROPOUT,
        'synthetic': AugmentationMethod.SYNTHETIC,
        'bootstrap': AugmentationMethod.BOOTSTRAP
    }
    
    if method in method_map:
        config.methods = [method_map[method]]
    else:
        raise DataAugmentationError(f"Méthode inconnue: {method}")
    
    # Augmentation
    augmentor = DataAugmentor(config)
    return augmentor.augment(data, labels)


def create_augmented_dataset(
    data: np.ndarray,
    labels: np.ndarray,
    n_augmented: int = 1000,
    methods: Optional[List[str]] = None,
    **kwargs
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Crée un dataset augmenté complet.
    
    Args:
        data: Données originales.
        labels: Labels associés.
        n_augmented: Nombre d'échantillons augmentés.
        methods: Liste des méthodes à utiliser.
        **kwargs: Paramètres supplémentaires.
        
    Returns:
        Tuple (données augmentées, labels augmentés).
    """
    if methods is None:
        methods = ['jitter', 'scaling', 'time_warp']
    
    # Configuration
    config = AugmentationConfig(
        methods=[AugmentationMethod(m) for m in methods],
        **kwargs
    )
    
    # Augmentation
    augmentor = DataAugmentor(config)
    result = augmentor.augment(data, labels, n_augmented)
    
    return result.data, result.labels


# ============================================================
# EXPORTATION
# ============================================================

__all__ = [
    'DataAugmentor',
    'AugmentationConfig',
    'AugmentationResult',
    'AugmentationMethod',
    'augment_time_series',
    'create_augmented_dataset'
]

# ============================================================
# FIN DU FICHIER
# ============================================================
