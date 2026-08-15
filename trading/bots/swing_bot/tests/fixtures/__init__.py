"""
Swing Bot Test Fixtures Package
================================

This package provides test fixtures for the Swing Bot trading system.
Includes data fixtures, configuration fixtures, and utility fixtures.
"""

import os
import json
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
import csv


class FixtureLoader:
    """
    Utility class for loading test fixtures.
    """
    
    def __init__(self, fixtures_dir: Optional[Path] = None):
        """
        Initialize the fixture loader.
        
        Args:
            fixtures_dir: Directory containing fixture files
        """
        self.fixtures_dir = fixtures_dir or Path(__file__).parent
        
    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        Load a YAML fixture file.
        
        Args:
            filename: Name of the YAML file
            
        Returns:
            Loaded YAML data
        """
        filepath = self.fixtures_dir / filename
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    
    def load_json(self, filename: str) -> Dict[str, Any]:
        """
        Load a JSON fixture file.
        
        Args:
            filename: Name of the JSON file
            
        Returns:
            Loaded JSON data
        """
        filepath = self.fixtures_dir / filename
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def load_csv(self, filename: str) -> List[Dict[str, Any]]:
        """
        Load a CSV fixture file.
        
        Args:
            filename: Name of the CSV file
            
        Returns:
            List of dictionaries
        """
        filepath = self.fixtures_dir / filename
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            return list(reader)
    
    def load_csv_as_df(self, filename: str) -> pd.DataFrame:
        """
        Load a CSV fixture file as a pandas DataFrame.
        
        Args:
            filename: Name of the CSV file
            
        Returns:
            Pandas DataFrame
        """
        filepath = self.fixtures_dir / filename
        return pd.read_csv(filepath)
    
    def load_text(self, filename: str) -> str:
        """
        Load a text fixture file.
        
        Args:
            filename: Name of the text file
            
        Returns:
            File content as string
        """
        filepath = self.fixtures_dir / filename
        with open(filepath, 'r') as f:
            return f.read()
    
    def get_fixture_path(self, filename: str) -> Path:
        """
        Get the full path to a fixture file.
        
        Args:
            filename: Name of the fixture file
            
        Returns:
            Full path to the file
        """
        return self.fixtures_dir / filename
    
    def list_fixtures(self, pattern: str = "*") -> List[Path]:
        """
        List all fixture files matching a pattern.
        
        Args:
            pattern: Glob pattern to match
            
        Returns:
            List of fixture file paths
        """
        return list(self.fixtures_dir.glob(pattern))


# Create a global fixture loader instance
fixture_loader = FixtureLoader()


# Load common fixtures
def get_config_fixture() -> Dict[str, Any]:
    """Load the test configuration fixture."""
    return fixture_loader.load_yaml("config_test.yaml")


def get_market_data_fixture() -> List[Dict[str, Any]]:
    """Load the market data fixture."""
    return fixture_loader.load_csv("market_data.csv")


def get_market_data_df_fixture() -> pd.DataFrame:
    """Load the market data fixture as a DataFrame."""
    return fixture_loader.load_csv_as_df("market_data.csv")


def get_level_test_fixture() -> List[Dict[str, Any]]:
    """Load the level test fixture."""
    return fixture_loader.load_csv("level_test.csv")


def get_target_test_fixture() -> List[Dict[str, Any]]:
    """Load the target test fixture."""
    return fixture_loader.load_csv("target_test.csv")


# Export all fixture loaders and fixtures
__all__ = [
    'FixtureLoader',
    'fixture_loader',
    'get_config_fixture',
    'get_market_data_fixture',
    'get_market_data_df_fixture',
    'get_level_test_fixture',
    'get_target_test_fixture',
]
