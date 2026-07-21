"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Data Tests
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tests des données et de la gestion des données pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import pytest
import json
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import tempfile
import os

# Import du module à tester
from trading.bots.arbitrage_bot.data.data_manager import DataManager
from trading.bots.arbitrage_bot.data.data_loader import DataLoader
from trading.bots.arbitrage_bot.data.data_processor import DataProcessor
from trading.bots.arbitrage_bot.data.data_validator import DataValidator
from trading.bots.arbitrage_bot.data.data_cache import DataCache
from trading.bots.arbitrage_bot.data.data_storage import DataStorage
from trading.bots.arbitrage_bot.data.data_stream import DataStream

# Fixtures
from trading.bots.arbitrage_bot.tests.fixtures import (
    test_data,
    market_data,
    test_tickers,
    test_order_books,
    test_trades
)

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# DATA MANAGER TESTS
# ============================================================

class TestDataManager:
    """Tests pour le gestionnaire de données"""

    def test_initialization(self):
        """Test l'initialisation"""
        manager = DataManager()
        assert manager is not None
        assert manager.get_data_sources() == []

    def test_add_data_source(self):
        """Test l'ajout d'une source de données"""
        manager = DataManager()
        source = {'name': 'Test Source', 'type': 'market_data', 'enabled': True}
        
        manager.add_data_source(source)
        sources = manager.get_data_sources()
        assert len(sources) == 1
        assert sources[0]['name'] == 'Test Source'

    def test_remove_data_source(self):
        """Test la suppression d'une source de données"""
        manager = DataManager()
        source = {'name': 'Test Source', 'type': 'market_data', 'enabled': True}
        
        manager.add_data_source(source)
        manager.remove_data_source('Test Source')
        sources = manager.get_data_sources()
        assert len(sources) == 0

    def test_get_data(self, test_data):
        """Test la récupération des données"""
        manager = DataManager()
        
        # Ajouter des données
        manager.add_data('tickers', test_data['tickers'])
        manager.add_data('balances', test_data['balances'])
        manager.add_data('orders', test_data['orders'])
        
        # Récupérer les données
        tickers = manager.get_data('tickers')
        assert tickers is not None
        assert len(tickers) > 0
        
        balances = manager.get_data('balances')
        assert balances is not None
        assert len(balances) > 0

    def test_update_data(self):
        """Test la mise à jour des données"""
        manager = DataManager()
        
        # Ajouter des données initiales
        initial_data = {'BTC': 45000.0, 'ETH': 3000.0}
        manager.add_data('prices', initial_data)
        
        # Mettre à jour les données
        updated_data = {'BTC': 46000.0, 'ETH': 3100.0, 'SOL': 150.0}
        manager.update_data('prices', updated_data)
        
        # Vérifier les données mises à jour
        data = manager.get_data('prices')
        assert data['BTC'] == 46000.0
        assert data['ETH'] == 3100.0
        assert data['SOL'] == 150.0

    def test_delete_data(self):
        """Test la suppression des données"""
        manager = DataManager()
        
        manager.add_data('test_data', {'key': 'value'})
        assert manager.get_data('test_data') is not None
        
        manager.delete_data('test_data')
        assert manager.get_data('test_data') is None

    def test_data_validation(self):
        """Test la validation des données"""
        manager = DataManager()
        
        # Valider des données valides
        valid_data = {'BTC': 45000.0, 'ETH': 3000.0}
        is_valid = manager.validate_data(valid_data, 'ticker')
        assert is_valid is True
        
        # Valider des données invalides
        invalid_data = {'BTC': 'invalid', 'ETH': 'invalid'}
        is_valid = manager.validate_data(invalid_data, 'ticker')
        assert is_valid is False

# ============================================================
# DATA LOADER TESTS
# ============================================================

class TestDataLoader:
    """Tests pour le chargeur de données"""

    def test_initialization(self):
        """Test l'initialisation"""
        loader = DataLoader()
        assert loader is not None

    def test_load_csv(self):
        """Test le chargement d'un fichier CSV"""
        loader = DataLoader()
        
        # Créer un fichier CSV temporaire
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("timestamp,symbol,price,volume\n")
            f.write("2024-01-01 00:00:00,BTC/USDT,45000.0,1.5\n")
            f.write("2024-01-01 00:01:00,BTC/USDT,45100.0,2.0\n")
            f.write("2024-01-01 00:02:00,BTC/USDT,45200.0,1.8\n")
            temp_file = f.name
        
        # Charger le fichier
        data = loader.load_csv(temp_file)
        assert len(data) == 3
        assert data[0]['symbol'] == 'BTC/USDT'
        assert data[0]['price'] == 45000.0
        
        # Nettoyer
        os.unlink(temp_file)

    def test_load_json(self):
        """Test le chargement d'un fichier JSON"""
        loader = DataLoader()
        
        # Créer un fichier JSON temporaire
        test_data = {
            'tickers': {'BTC/USDT': {'price': 45000.0, 'volume': 1.5}},
            'timestamp': '2024-01-01T00:00:00Z'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name
        
        # Charger le fichier
        data = loader.load_json(temp_file)
        assert data['tickers']['BTC/USDT']['price'] == 45000.0
        assert data['timestamp'] == '2024-01-01T00:00:00Z'
        
        # Nettoyer
        os.unlink(temp_file)

    def test_load_parquet(self):
        """Test le chargement d'un fichier Parquet"""
        loader = DataLoader()
        
        # Créer des données
        df = pd.DataFrame({
            'timestamp': ['2024-01-01 00:00:00', '2024-01-01 00:01:00'],
            'symbol': ['BTC/USDT', 'ETH/USDT'],
            'price': [45000.0, 3000.0],
            'volume': [1.5, 10.0]
        })
        
        # Sauvegarder en Parquet
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
            df.to_parquet(f.name)
            temp_file = f.name
        
        # Charger le fichier
        data = loader.load_parquet(temp_file)
        assert len(data) == 2
        assert data[0]['symbol'] == 'BTC/USDT'
        
        # Nettoyer
        os.unlink(temp_file)

    def test_load_from_url(self):
        """Test le chargement depuis une URL"""
        loader = DataLoader()
        
        # Tester avec une URL invalide
        with pytest.raises(Exception):
            loader.load_from_url('http://invalid-url.example.com/data.csv')

    def test_load_multiple_formats(self):
        """Test le chargement de multiples formats"""
        loader = DataLoader()
        
        # Créer des fichiers de différents formats
        files = {}
        
        # CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("timestamp,symbol,price\n")
            f.write("2024-01-01 00:00:00,BTC/USDT,45000.0\n")
            files['csv'] = f.name
        
        # JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([{'symbol': 'BTC/USDT', 'price': 45000.0}], f)
            files['json'] = f.name
        
        # Charger tous les fichiers
        all_data = {}
        for format_type, file_path in files.items():
            if format_type == 'csv':
                all_data[format_type] = loader.load_csv(file_path)
            elif format_type == 'json':
                all_data[format_type] = loader.load_json(file_path)
        
        assert len(all_data['csv']) > 0
        assert len(all_data['json']) > 0
        
        # Nettoyer
        for file_path in files.values():
            os.unlink(file_path)

# ============================================================
# DATA PROCESSOR TESTS
# ============================================================

class TestDataProcessor:
    """Tests pour le processeur de données"""

    def test_initialization(self):
        """Test l'initialisation"""
        processor = DataProcessor()
        assert processor is not None

    def test_clean_data(self):
        """Test le nettoyage des données"""
        processor = DataProcessor()
        
        raw_data = [
            {'price': 45000.0, 'volume': 1.5},
            {'price': None, 'volume': 2.0},
            {'price': 45100.0, 'volume': None},
            {'price': -100.0, 'volume': 1.0},
            {'price': 0, 'volume': 0},
        ]
        
        cleaned = processor.clean_data(raw_data)
        assert len(cleaned) == 3  # Les lignes avec des valeurs None/0 sont supprimées

    def test_normalize_data(self):
        """Test la normalisation des données"""
        processor = DataProcessor()
        
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        normalized = processor.normalize_data(data)
        
        assert len(normalized) == 5
        assert min(normalized) == 0.0
        assert max(normalized) == 1.0

    def test_standardize_data(self):
        """Test la standardisation des données"""
        processor = DataProcessor()
        
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        standardized = processor.standardize_data(data)
        
        assert len(standardized) == 5
        assert abs(np.mean(standardized)) < 1e-10
        assert abs(np.std(standardized) - 1.0) < 1e-10

    def test_detect_outliers(self):
        """Test la détection des outliers"""
        processor = DataProcessor()
        
        data = [1.0, 2.0, 3.0, 4.0, 100.0, 3.5, 2.5]
        outliers = processor.detect_outliers(data)
        
        assert len(outliers) == 1
        assert outliers[0] == 100.0

    def test_fill_missing_values(self):
        """Test le remplissage des valeurs manquantes"""
        processor = DataProcessor()
        
        data = [1.0, None, 3.0, None, 5.0]
        filled = processor.fill_missing_values(data, method='mean')
        
        assert len(filled) == 5
        assert filled[1] == 3.0  # Moyenne des valeurs non-nulles
        
        filled_linear = processor.fill_missing_values(data, method='linear')
        assert filled_linear[1] == 2.0
        assert filled_linear[3] == 4.0

    def test_resample_data(self):
        """Test le rééchantillonnage des données"""
        processor = DataProcessor()
        
        # Créer des données avec timestamp
        timestamps = [datetime.now() + timedelta(minutes=i) for i in range(10)]
        data = [{'timestamp': ts, 'value': i * 10} for i, ts in enumerate(timestamps)]
        
        resampled = processor.resample_data(data, interval='5min')
        assert len(resampled) <= len(data)

    def test_aggregate_data(self):
        """Test l'agrégation des données"""
        processor = DataProcessor()
        
        data = [
            {'symbol': 'BTC/USDT', 'price': 45000.0, 'volume': 1.5},
            {'symbol': 'BTC/USDT', 'price': 45100.0, 'volume': 2.0},
            {'symbol': 'ETH/USDT', 'price': 3000.0, 'volume': 10.0},
            {'symbol': 'ETH/USDT', 'price': 3050.0, 'volume': 12.0},
        ]
        
        aggregated = processor.aggregate_data(data, key='symbol', agg_func='mean')
        
        assert 'BTC/USDT' in aggregated
        assert 'ETH/USDT' in aggregated
        assert aggregated['BTC/USDT']['price'] == 45050.0

# ============================================================
# DATA VALIDATOR TESTS
# ============================================================

class TestDataValidator:
    """Tests pour le validateur de données"""

    def test_initialization(self):
        """Test l'initialisation"""
        validator = DataValidator()
        assert validator is not None

    def test_validate_price(self):
        """Test la validation des prix"""
        validator = DataValidator()
        
        # Prix valides
        assert validator.validate_price(45000.0) is True
        assert validator.validate_price(0.0001) is True
        assert validator.validate_price(1000000.0) is True
        
        # Prix invalides
        assert validator.validate_price(-100.0) is False
        assert validator.validate_price(0.0) is False
        assert validator.validate_price(None) is False

    def test_validate_volume(self):
        """Test la validation des volumes"""
        validator = DataValidator()
        
        # Volumes valides
        assert validator.validate_volume(1.5) is True
        assert validator.validate_volume(1000.0) is True
        assert validator.validate_volume(0.0001) is True
        
        # Volumes invalides
        assert validator.validate_volume(-10.0) is False
        assert validator.validate_volume(0.0) is False
        assert validator.validate_volume(None) is False

    def test_validate_symbol(self):
        """Test la validation des symboles"""
        validator = DataValidator()
        
        # Symboles valides
        assert validator.validate_symbol('BTC/USDT') is True
        assert validator.validate_symbol('ETH/USDT') is True
        assert validator.validate_symbol('SOL/USDT') is True
        
        # Symboles invalides
        assert validator.validate_symbol('') is False
        assert validator.validate_symbol('BTC') is False
        assert validator.validate_symbol('BTC-USDT') is False

    def test_validate_timestamp(self):
        """Test la validation des timestamps"""
        validator = DataValidator()
        
        # Timestamps valides
        assert validator.validate_timestamp('2024-01-01T00:00:00Z') is True
        assert validator.validate_timestamp(datetime.now()) is True
        
        # Timestamps invalides
        assert validator.validate_timestamp('invalid') is False
        assert validator.validate_timestamp(None) is False

    def test_validate_data_structure(self):
        """Test la validation de la structure des données"""
        validator = DataValidator()
        
        # Structure valide
        valid_data = {
            'symbol': 'BTC/USDT',
            'price': 45000.0,
            'volume': 1.5,
            'timestamp': '2024-01-01T00:00:00Z'
        }
        assert validator.validate_data_structure(valid_data, 'ticker') is True
        
        # Structure invalide
        invalid_data = {
            'symbol': 'BTC/USDT',
            'price': 'invalid',
            'volume': 'invalid'
        }
        assert validator.validate_data_structure(invalid_data, 'ticker') is False

# ============================================================
# DATA CACHE TESTS
# ============================================================

class TestDataCache:
    """Tests pour le cache de données"""

    def test_initialization(self):
        """Test l'initialisation"""
        cache = DataCache()
        assert cache is not None
        assert cache.get_size() == 0

    def test_set_get(self):
        """Test la mise en cache et la récupération"""
        cache = DataCache()
        
        cache.set('key1', 'value1')
        cache.set('key2', {'data': 'value2'})
        
        assert cache.get('key1') == 'value1'
        assert cache.get('key2') == {'data': 'value2'}
        assert cache.get('key3') is None

    def test_delete(self):
        """Test la suppression du cache"""
        cache = DataCache()
        
        cache.set('key1', 'value1')
        assert cache.get('key1') is not None
        
        cache.delete('key1')
        assert cache.get('key1') is None

    def test_clear(self):
        """Test le vidage du cache"""
        cache = DataCache()
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        assert cache.get_size() == 2
        
        cache.clear()
        assert cache.get_size() == 0

    def test_expiration(self):
        """Test l'expiration du cache"""
        cache = DataCache(ttl=1)  # 1 seconde
        
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
        
        # Attendre l'expiration
        import time
        time.sleep(1.1)
        
        assert cache.get('key1') is None

    def test_max_size(self):
        """Test la taille maximale du cache"""
        cache = DataCache(max_size=2)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        assert cache.get_size() == 2
        assert cache.get('key1') is None  # Évincé
        assert cache.get('key2') is not None
        assert cache.get('key3') is not None

# ============================================================
# DATA STORAGE TESTS
# ============================================================

class TestDataStorage:
    """Tests pour le stockage de données"""

    def test_initialization(self):
        """Test l'initialisation"""
        storage = DataStorage()
        assert storage is not None

    def test_save_load_json(self):
        """Test la sauvegarde et le chargement JSON"""
        storage = DataStorage()
        
        data = {'key': 'value', 'nested': {'data': 123}}
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            storage.save_json(data, f.name)
            loaded = storage.load_json(f.name)
            os.unlink(f.name)
        
        assert loaded == data

    def test_save_load_csv(self):
        """Test la sauvegarde et le chargement CSV"""
        storage = DataStorage()
        
        data = [
            {'timestamp': '2024-01-01 00:00:00', 'symbol': 'BTC/USDT', 'price': 45000.0},
            {'timestamp': '2024-01-01 00:01:00', 'symbol': 'BTC/USDT', 'price': 45100.0}
        ]
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            storage.save_csv(data, f.name)
            loaded = storage.load_csv(f.name)
            os.unlink(f.name)
        
        assert len(loaded) == 2
        assert loaded[0]['symbol'] == 'BTC/USDT'

    def test_save_load_parquet(self):
        """Test la sauvegarde et le chargement Parquet"""
        storage = DataStorage()
        
        data = pd.DataFrame({
            'timestamp': ['2024-01-01 00:00:00', '2024-01-01 00:01:00'],
            'symbol': ['BTC/USDT', 'ETH/USDT'],
            'price': [45000.0, 3000.0]
        })
        
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
            storage.save_parquet(data, f.name)
            loaded = storage.load_parquet(f.name)
            os.unlink(f.name)
        
        assert len(loaded) == 2
        assert loaded['symbol'].iloc[0] == 'BTC/USDT'

    def test_save_load_pickle(self):
        """Test la sauvegarde et le chargement Pickle"""
        storage = DataStorage()
        
        data = {'key': 'value', 'list': [1, 2, 3], 'dict': {'a': 1, 'b': 2}}
        
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            storage.save_pickle(data, f.name)
            loaded = storage.load_pickle(f.name)
            os.unlink(f.name)
        
        assert loaded == data

# ============================================================
# DATA STREAM TESTS
# ============================================================

class TestDataStream:
    """Tests pour le flux de données"""

    def test_initialization(self):
        """Test l'initialisation"""
        stream = DataStream()
        assert stream is not None
        assert stream.is_running() is False

    def test_start_stop(self):
        """Test le démarrage et l'arrêt"""
        stream = DataStream()
        
        stream.start()
        assert stream.is_running() is True
        
        stream.stop()
        assert stream.is_running() is False

    def test_subscribe(self):
        """Test l'abonnement"""
        stream = DataStream()
        
        def callback(data):
            pass
        
        stream.subscribe('ticker', callback)
        assert len(stream.get_subscribers('ticker')) == 1

    def test_unsubscribe(self):
        """Test le désabonnement"""
        stream = DataStream()
        
        def callback(data):
            pass
        
        stream.subscribe('ticker', callback)
        assert len(stream.get_subscribers('ticker')) == 1
        
        stream.unsubscribe('ticker', callback)
        assert len(stream.get_subscribers('ticker')) == 0

    def test_publish(self):
        """Test la publication"""
        stream = DataStream()
        
        received_data = []
        
        def callback(data):
            received_data.append(data)
        
        stream.subscribe('test', callback)
        stream.publish('test', {'message': 'Hello World'})
        
        assert len(received_data) == 1
        assert received_data[0]['message'] == 'Hello World'

    def test_multiple_subscribers(self):
        """Test les multiples abonnés"""
        stream = DataStream()
        
        data1 = []
        data2 = []
        
        def callback1(data):
            data1.append(data)
        
        def callback2(data):
            data2.append(data)
        
        stream.subscribe('test', callback1)
        stream.subscribe('test', callback2)
        stream.publish('test', {'message': 'Hello'})
        
        assert len(data1) == 1
        assert len(data2) == 1

    def test_filtering(self):
        """Test le filtrage des données"""
        stream = DataStream()
        
        received = []
        
        def callback(data):
            if data.get('value', 0) > 5:
                received.append(data)
        
        stream.subscribe('test', callback)
        
        stream.publish('test', {'value': 3})
        stream.publish('test', {'value': 7})
        stream.publish('test', {'value': 2})
        stream.publish('test', {'value': 10})
        
        assert len(received) == 2
        assert received[0]['value'] == 7
        assert received[1]['value'] == 10

# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestDataIntegration:
    """Tests d'intégration des données"""

    def test_full_data_pipeline(self):
        """Test le pipeline complet de données"""
        # Créer les composants
        loader = DataLoader()
        processor = DataProcessor()
        validator = DataValidator()
        cache = DataCache()
        storage = DataStorage()
        manager = DataManager()
        
        # Créer des données de test
        test_data = [
            {'symbol': 'BTC/USDT', 'price': 45000.0, 'volume': 1.5},
            {'symbol': 'BTC/USDT', 'price': 45100.0, 'volume': 2.0},
            {'symbol': 'ETH/USDT', 'price': 3000.0, 'volume': 10.0},
        ]
        
        # Valider les données
        for item in test_data:
            assert validator.validate_data_structure(item, 'ticker') is True
        
        # Nettoyer les données
        cleaned = processor.clean_data(test_data)
        assert len(cleaned) > 0
        
        # Mettre en cache
        for item in cleaned:
            cache.set(f"{item['symbol']}_price", item['price'])
        
        # Sauvegarder
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            storage.save_json(cleaned, f.name)
            loaded = storage.load_json(f.name)
            os.unlink(f.name)
        
        # Charger dans le gestionnaire
        manager.add_data('tickers', loaded)
        
        # Vérifier
        data = manager.get_data('tickers')
        assert len(data) == 3
        assert data[0]['symbol'] == 'BTC/USDT'

    def test_performance_data_processing(self):
        """Test la performance du traitement des données"""
        import time
        
        # Générer un grand volume de données
        data = []
        for i in range(10000):
            data.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': 'BTC/USDT' if i % 2 == 0 else 'ETH/USDT',
                'price': 45000.0 + i * 0.1,
                'volume': 1.0 + i * 0.001
            })
        
        processor = DataProcessor()
        
        # Mesurer le temps de traitement
        start_time = time.time()
        processed = processor.clean_data(data)
        end_time = time.time()
        
        processing_time = end_time - start_time
        assert processing_time < 1.0  # Moins d'1 seconde pour 10000 lignes
        
        # Vérifier que les données ont été traitées
        assert len(processed) > 0

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
