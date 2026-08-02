# trading/bots/hedge_bot/hedge_bot_data_purge.py

import asyncio
import logging
import time
import os
import shutil
import glob
import fnmatch
import re
import hashlib
import json
import sqlite3
import pickle
import gzip
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable, BinaryIO, Iterable
from decimal import Decimal
from collections import defaultdict, deque
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)


class PurgeTarget(str, Enum):
    FILES = "files"
    DIRECTORIES = "directories"
    DATABASE = "database"
    CACHE = "cache"
    LOGS = "logs"
    TEMP = "temp"
    BACKUPS = "backups"
    ARCHIVES = "archives"
    OLD_DATA = "old_data"
    DUPLICATES = "duplicates"
    EMPTY = "empty"
    BY_SIZE = "by_size"
    BY_AGE = "by_age"
    BY_PATTERN = "by_pattern"
    COMPRESSED = "compressed"
    ORPHANED = "orphaned"


class PurgeStrategy(str, Enum):
    DELETE = "delete"
    ARCHIVE = "archive"
    COMPRESS = "compress"
    MOVE = "move"
    TRUNCATE = "truncate"
    VACUUM = "vacuum"
    REINDEX = "reindex"
    SHARD = "shard"
    MERGE = "merge"
    DEDUPLICATE = "deduplicate"
    CASCADE = "cascade"


class AgeUnit(str, Enum):
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


@dataclass
class PurgeItem:
    path: str
    size: int
    last_modified: float
    created_at: float
    accessed_at: float
    is_directory: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    hash: Optional[str] = None


@dataclass
class PurgeResult:
    total_items: int
    total_size: int
    freed_items: int
    freed_size: int
    archived_items: int
    archived_size: int
    compressed_items: int
    compressed_size: int
    moved_items: int
    moved_size: int
    errors: int
    start_time: float
    end_time: float
    details: List[Dict[str, Any]] = field(default_factory=list)
    rules_applied: List[str] = field(default_factory=list)


@dataclass
class PurgeRule:
    name: str
    target: PurgeTarget
    strategy: PurgeStrategy
    conditions: Dict[str, Any]
    priority: int = 0
    enabled: bool = True
    max_items: Optional[int] = None
    max_size: Optional[int] = None
    recursive: bool = True
    pattern: Optional[str] = None
    exclude_patterns: List[str] = field(default_factory=list)
    min_age: Optional[Dict[str, int]] = None
    max_age: Optional[Dict[str, int]] = None
    min_size: Optional[int] = None
    max_size_bytes: Optional[int] = None
    archive_path: Optional[str] = None
    move_path: Optional[str] = None
    compression_level: int = 6
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DatabasePurgeTarget:
    table: str
    column: str
    conditions: Dict[str, Any]
    batch_size: int = 1000
    timeout: int = 30


@dataclass
class CachePurgeTarget:
    cache_type: str
    cache_name: str
    ttl: Optional[int] = None
    max_size: Optional[int] = None
    max_items: Optional[int] = None


class DataPurgeManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._rules: Dict[str, PurgeRule] = {}
        self._executors: Dict[str, ThreadPoolExecutor] = {}
        self._results: Dict[str, PurgeResult] = {}
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._cache: Dict[str, Any] = {}
        self._file_hashes: Dict[str, str] = {}
        self._duplicate_groups: Dict[str, List[str]] = defaultdict(list)
        self._stats = defaultdict(int)
        self._active_purges: Set[str] = set()
        
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        default_rules = [
            PurgeRule(
                name="temp_files_cleanup",
                target=PurgeTarget.TEMP,
                strategy=PurgeStrategy.DELETE,
                conditions={
                    "patterns": ["*.tmp", "*.temp", "*.log.tmp"],
                    "min_age_days": 1
                },
                recursive=True
            ),
            PurgeRule(
                name="old_logs_cleanup",
                target=PurgeTarget.LOGS,
                strategy=PurgeStrategy.ARCHIVE,
                conditions={
                    "patterns": ["*.log", "*.log.*", "*.out"],
                    "min_age_days": 30,
                    "max_age_days": 365
                },
                archive_path="./archives/logs/",
                compression_level=9
            ),
            PurgeRule(
                name="duplicate_files_cleanup",
                target=PurgeTarget.DUPLICATES,
                strategy=PurgeStrategy.DEDUPLICATE,
                conditions={
                    "min_size": 1024,
                    "use_hash": True
                },
                recursive=True
            ),
            PurgeRule(
                name="empty_directories_cleanup",
                target=PurgeTarget.EMPTY,
                strategy=PurgeStrategy.DELETE,
                conditions={},
                recursive=True,
                priority=10
            ),
            PurgeRule(
                name="old_backups_cleanup",
                target=PurgeTarget.BACKUPS,
                strategy=PurgeStrategy.ARCHIVE,
                conditions={
                    "patterns": ["*.zip", "*.tar.gz", "*.sql", "*.bak"],
                    "min_age_days": 90,
                    "max_age_days": 730
                },
                archive_path="./archives/backups/",
                compression_level=6
            ),
            PurgeRule(
                name="cache_cleanup",
                target=PurgeTarget.CACHE,
                strategy=PurgeStrategy.DELETE,
                conditions={
                    "patterns": ["cache_*", "*.cache"],
                    "min_age_days": 7,
                    "max_items": 10000
                },
                recursive=True
            ),
            PurgeRule(
                name="large_files_cleanup",
                target=PurgeTarget.BY_SIZE,
                strategy=PurgeStrategy.COMPRESS,
                conditions={
                    "min_size_bytes": 100 * 1024 * 1024,
                    "max_age_days": 30
                },
                compression_level=9
            ),
            PurgeRule(
                name="old_archives_cleanup",
                target=PurgeTarget.ARCHIVES,
                strategy=PurgeStrategy.DELETE,
                conditions={
                    "patterns": ["*.gz", "*.zip"],
                    "min_age_days": 365
                }
            )
        ]
        
        for rule in default_rules:
            self._rules[rule.name] = rule

    def add_rule(self, rule: PurgeRule) -> None:
        self._rules[rule.name] = rule
        logger.info(f"Added purge rule: {rule.name}")

    def remove_rule(self, rule_name: str) -> bool:
        if rule_name in self._rules:
            del self._rules[rule_name]
            return True
        return False

    def get_rule(self, rule_name: str) -> Optional[PurgeRule]:
        return self._rules.get(rule_name)

    def get_rules(self) -> List[PurgeRule]:
        return sorted(self._rules.values(), key=lambda r: r.priority)

    async def purge(self, rule_name: str, dry_run: bool = False) -> PurgeResult:
        async with self._lock:
            if rule_name not in self._rules:
                raise ValueError(f"Rule {rule_name} not found")
            
            if rule_name in self._active_purges:
                raise ValueError(f"Purge {rule_name} already running")
            
            rule = self._rules[rule_name]
            if not rule.enabled:
                raise ValueError(f"Rule {rule_name} is disabled")
            
            self._active_purges.add(rule_name)
            self._running = True
            
            start_time = time.time()
            result = PurgeResult(
                total_items=0,
                total_size=0,
                freed_items=0,
                freed_size=0,
                archived_items=0,
                archived_size=0,
                compressed_items=0,
                compressed_size=0,
                moved_items=0,
                moved_size=0,
                errors=0,
                start_time=start_time,
                end_time=0,
                details=[],
                rules_applied=[rule_name]
            )
            
            try:
                if rule.target == PurgeTarget.FILES:
                    result = await self._purge_files(rule, dry_run, result)
                elif rule.target == PurgeTarget.DIRECTORIES:
                    result = await self._purge_directories(rule, dry_run, result)
                elif rule.target == PurgeTarget.DATABASE:
                    result = await self._purge_database(rule, dry_run, result)
                elif rule.target == PurgeTarget.CACHE:
                    result = await self._purge_cache(rule, dry_run, result)
                elif rule.target == PurgeTarget.LOGS:
                    result = await self._purge_logs(rule, dry_run, result)
                elif rule.target == PurgeTarget.TEMP:
                    result = await self._purge_temp(rule, dry_run, result)
                elif rule.target == PurgeTarget.BACKUPS:
                    result = await self._purge_backups(rule, dry_run, result)
                elif rule.target == PurgeTarget.ARCHIVES:
                    result = await self._purge_archives(rule, dry_run, result)
                elif rule.target == PurgeTarget.OLD_DATA:
                    result = await self._purge_old_data(rule, dry_run, result)
                elif rule.target == PurgeTarget.DUPLICATES:
                    result = await self._purge_duplicates(rule, dry_run, result)
                elif rule.target == PurgeTarget.EMPTY:
                    result = await self._purge_empty(rule, dry_run, result)
                elif rule.target == PurgeTarget.BY_SIZE:
                    result = await self._purge_by_size(rule, dry_run, result)
                elif rule.target == PurgeTarget.BY_AGE:
                    result = await self._purge_by_age(rule, dry_run, result)
                elif rule.target == PurgeTarget.BY_PATTERN:
                    result = await self._purge_by_pattern(rule, dry_run, result)
                elif rule.target == PurgeTarget.COMPRESSED:
                    result = await self._purge_compressed(rule, dry_run, result)
                elif rule.target == PurgeTarget.ORPHANED:
                    result = await self._purge_orphaned(rule, dry_run, result)
                
                result.end_time = time.time()
                self._results[rule_name] = result
                self._stats['purges_completed'] += 1
                
            except Exception as e:
                logger.error(f"Error during purge {rule_name}: {e}")
                result.errors += 1
                result.end_time = time.time()
                raise
            finally:
                self._active_purges.discard(rule_name)
                self._running = False
            
            return result

    async def _purge_files(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        base_path = rule.conditions.get("base_path", ".")
        patterns = rule.conditions.get("patterns", ["*"])
        recursive = rule.recursive
        
        files = await self._find_files(base_path, patterns, recursive, rule.exclude_patterns)
        
        for file_path in files:
            try:
                stat_info = os.stat(file_path)
                size = stat_info.st_size
                age = time.time() - stat_info.st_mtime
                
                if not self._should_purge_file(stat_info, rule):
                    continue
                
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "action": "would_delete"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.DELETE:
                    os.remove(file_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                elif rule.strategy == PurgeStrategy.ARCHIVE:
                    archive_path = await self._archive_file(file_path, rule.archive_path, rule.compression_level)
                    os.remove(file_path)
                    result.archived_items += 1
                    result.archived_size += size
                    
                elif rule.strategy == PurgeStrategy.COMPRESS:
                    compressed_path = await self._compress_file(file_path, rule.compression_level)
                    result.compressed_items += 1
                    result.compressed_size += size
                    
                elif rule.strategy == PurgeStrategy.MOVE:
                    moved_path = await self._move_file(file_path, rule.move_path)
                    result.moved_items += 1
                    result.moved_size += size
                    
                elif rule.strategy == PurgeStrategy.TRUNCATE:
                    os.truncate(file_path, 0)
                    result.freed_items += 1
                    result.freed_size += size
                    
                result.details.append({
                    "path": file_path,
                    "size": size,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_directories(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        base_path = rule.conditions.get("base_path", ".")
        patterns = rule.conditions.get("patterns", ["*"])
        recursive = rule.recursive
        
        directories = await self._find_directories(base_path, patterns, recursive, rule.exclude_patterns)
        
        for dir_path in directories:
            try:
                if not os.path.isdir(dir_path):
                    continue
                
                if not self._should_purge_directory(dir_path, rule):
                    continue
                
                size = await self._get_directory_size(dir_path)
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": dir_path,
                        "size": size,
                        "action": "would_delete"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.DELETE:
                    shutil.rmtree(dir_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                elif rule.strategy == PurgeStrategy.ARCHIVE:
                    archive_path = await self._archive_directory(dir_path, rule.archive_path, rule.compression_level)
                    shutil.rmtree(dir_path)
                    result.archived_items += 1
                    result.archived_size += size
                    
                elif rule.strategy == PurgeStrategy.COMPRESS:
                    compressed_path = await self._compress_directory(dir_path, rule.compression_level)
                    shutil.rmtree(dir_path)
                    result.compressed_items += 1
                    result.compressed_size += size
                    
                elif rule.strategy == PurgeStrategy.MOVE:
                    moved_path = await self._move_directory(dir_path, rule.move_path)
                    result.moved_items += 1
                    result.moved_size += size
                    
                result.details.append({
                    "path": dir_path,
                    "size": size,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing directory {dir_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_database(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        db_path = rule.conditions.get("db_path")
        if not db_path or not os.path.exists(db_path):
            return result
        
        tables = rule.conditions.get("tables", [])
        conditions = rule.conditions.get("conditions", {})
        batch_size = rule.conditions.get("batch_size", 1000)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            for table in tables:
                table_conditions = conditions.get(table, {})
                where_clause = self._build_where_clause(table_conditions)
                
                if where_clause:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"
                    )
                    count = cursor.fetchone()[0]
                    
                    if count == 0:
                        continue
                    
                    result.total_items += count
                    
                    if dry_run:
                        result.details.append({
                            "table": table,
                            "count": count,
                            "action": "would_delete"
                        })
                        continue
                    
                    if rule.strategy == PurgeStrategy.DELETE:
                        cursor.execute(
                            f"DELETE FROM {table} WHERE {where_clause}"
                        )
                        result.freed_items += count
                        
                    elif rule.strategy == PurgeStrategy.TRUNCATE:
                        cursor.execute(f"DELETE FROM {table}")
                        result.freed_items += count
                        
                    elif rule.strategy == PurgeStrategy.VACUUM:
                        cursor.execute(f"DELETE FROM {table} WHERE {where_clause}")
                        conn.execute("VACUUM")
                        result.freed_items += count
                        
                    elif rule.strategy == PurgeStrategy.REINDEX:
                        cursor.execute(f"DELETE FROM {table} WHERE {where_clause}")
                        cursor.execute(f"REINDEX {table}")
                        result.freed_items += count
                        
                    conn.commit()
                    
                    result.details.append({
                        "table": table,
                        "count": count,
                        "action": rule.strategy.value
                    })
                    
        finally:
            conn.close()
        
        return result

    async def _purge_cache(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        cache_path = rule.conditions.get("cache_path", "./cache")
        cache_types = rule.conditions.get("cache_types", ["all"])
        max_age_days = rule.conditions.get("max_age_days", 7)
        max_items = rule.conditions.get("max_items", 10000)
        
        if not os.path.exists(cache_path):
            return result
        
        items = []
        for root, dirs, files in os.walk(cache_path):
            for file in files:
                file_path = os.path.join(root, file)
                stat_info = os.stat(file_path)
                age = time.time() - stat_info.st_mtime
                
                if age > max_age_days * 86400:
                    items.append(PurgeItem(
                        path=file_path,
                        size=stat_info.st_size,
                        last_modified=stat_info.st_mtime,
                        created_at=stat_info.st_ctime,
                        accessed_at=stat_info.st_atime,
                        is_directory=False
                    ))
        
        items.sort(key=lambda x: x.last_modified)
        
        if len(items) > max_items:
            items = items[:max_items]
        
        for item in items:
            result.total_items += 1
            result.total_size += item.size
            
            if dry_run:
                result.details.append({
                    "path": item.path,
                    "size": item.size,
                    "action": "would_delete"
                })
                continue
            
            try:
                if rule.strategy == PurgeStrategy.DELETE:
                    os.remove(item.path)
                    result.freed_items += 1
                    result.freed_size += item.size
                    
                elif rule.strategy == PurgeStrategy.COMPRESS:
                    compressed_path = await self._compress_file(item.path, rule.compression_level)
                    os.remove(item.path)
                    result.compressed_items += 1
                    result.compressed_size += item.size
                    
                result.details.append({
                    "path": item.path,
                    "size": item.size,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing cache item {item.path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_logs(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        log_path = rule.conditions.get("log_path", "./logs")
        patterns = rule.conditions.get("patterns", ["*.log", "*.log.*"])
        min_age_days = rule.conditions.get("min_age_days", 30)
        max_age_days = rule.conditions.get("max_age_days", 365)
        
        if not os.path.exists(log_path):
            return result
        
        files = await self._find_files(log_path, patterns, rule.recursive, rule.exclude_patterns)
        
        for file_path in files:
            try:
                stat_info = os.stat(file_path)
                age = time.time() - stat_info.st_mtime
                age_days = age / 86400
                
                if age_days < min_age_days or age_days > max_age_days:
                    continue
                
                size = stat_info.st_size
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "age_days": age_days,
                        "action": "would_archive"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.ARCHIVE:
                    archive_path = await self._archive_file(file_path, rule.archive_path, rule.compression_level)
                    os.remove(file_path)
                    result.archived_items += 1
                    result.archived_size += size
                    
                elif rule.strategy == PurgeStrategy.COMPRESS:
                    compressed_path = await self._compress_file(file_path, rule.compression_level)
                    result.compressed_items += 1
                    result.compressed_size += size
                    
                elif rule.strategy == PurgeStrategy.DELETE:
                    os.remove(file_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                result.details.append({
                    "path": file_path,
                    "size": size,
                    "age_days": age_days,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing log {file_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_temp(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        temp_paths = rule.conditions.get("temp_paths", ["/tmp", "./temp"])
        patterns = rule.conditions.get("patterns", ["*.tmp", "*.temp", "*.log.tmp"])
        min_age_days = rule.conditions.get("min_age_days", 1)
        
        for base_path in temp_paths:
            if not os.path.exists(base_path):
                continue
            
            files = await self._find_files(base_path, patterns, rule.recursive, rule.exclude_patterns)
            
            for file_path in files:
                try:
                    stat_info = os.stat(file_path)
                    age = time.time() - stat_info.st_mtime
                    age_days = age / 86400
                    
                    if age_days < min_age_days:
                        continue
                    
                    size = stat_info.st_size
                    result.total_items += 1
                    result.total_size += size
                    
                    if dry_run:
                        result.details.append({
                            "path": file_path,
                            "size": size,
                            "age_days": age_days,
                            "action": "would_delete"
                        })
                        continue
                    
                    if rule.strategy == PurgeStrategy.DELETE:
                        os.remove(file_path)
                        result.freed_items += 1
                        result.freed_size += size
                        
                    elif rule.strategy == PurgeStrategy.TRUNCATE:
                        os.truncate(file_path, 0)
                        result.freed_items += 1
                        result.freed_size += size
                        
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "age_days": age_days,
                        "action": rule.strategy.value
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing temp file {file_path}: {e}")
                    result.errors += 1
        
        return result

    async def _purge_backups(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        backup_path = rule.conditions.get("backup_path", "./backups")
        patterns = rule.conditions.get("patterns", ["*.zip", "*.tar.gz", "*.sql", "*.bak"])
        min_age_days = rule.conditions.get("min_age_days", 90)
        max_age_days = rule.conditions.get("max_age_days", 730)
        
        if not os.path.exists(backup_path):
            return result
        
        files = await self._find_files(backup_path, patterns, rule.recursive, rule.exclude_patterns)
        
        for file_path in files:
            try:
                stat_info = os.stat(file_path)
                age = time.time() - stat_info.st_mtime
                age_days = age / 86400
                
                if age_days < min_age_days or age_days > max_age_days:
                    continue
                
                size = stat_info.st_size
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "age_days": age_days,
                        "action": "would_archive"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.ARCHIVE:
                    archive_path = await self._archive_file(file_path, rule.archive_path, rule.compression_level)
                    os.remove(file_path)
                    result.archived_items += 1
                    result.archived_size += size
                    
                elif rule.strategy == PurgeStrategy.DELETE:
                    os.remove(file_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                elif rule.strategy == PurgeStrategy.COMPRESS:
                    compressed_path = await self._compress_file(file_path, rule.compression_level)
                    result.compressed_items += 1
                    result.compressed_size += size
                    
                result.details.append({
                    "path": file_path,
                    "size": size,
                    "age_days": age_days,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing backup {file_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_archives(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        archive_path = rule.conditions.get("archive_path", "./archives")
        patterns = rule.conditions.get("patterns", ["*.gz", "*.zip", "*.tar.gz", "*.7z"])
        min_age_days = rule.conditions.get("min_age_days", 365)
        
        if not os.path.exists(archive_path):
            return result
        
        files = await self._find_files(archive_path, patterns, rule.recursive, rule.exclude_patterns)
        
        for file_path in files:
            try:
                stat_info = os.stat(file_path)
                age = time.time() - stat_info.st_mtime
                age_days = age / 86400
                
                if age_days < min_age_days:
                    continue
                
                size = stat_info.st_size
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "age_days": age_days,
                        "action": "would_delete"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.DELETE:
                    os.remove(file_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                result.details.append({
                    "path": file_path,
                    "size": size,
                    "age_days": age_days,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing archive {file_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_old_data(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        data_paths = rule.conditions.get("data_paths", ["./data"])
        min_age_days = rule.conditions.get("min_age_days", 180)
        patterns = rule.conditions.get("patterns", ["*"])
        
        for base_path in data_paths:
            if not os.path.exists(base_path):
                continue
            
            files = await self._find_files(base_path, patterns, rule.recursive, rule.exclude_patterns)
            
            for file_path in files:
                try:
                    stat_info = os.stat(file_path)
                    age = time.time() - stat_info.st_mtime
                    age_days = age / 86400
                    
                    if age_days < min_age_days:
                        continue
                    
                    size = stat_info.st_size
                    result.total_items += 1
                    result.total_size += size
                    
                    if dry_run:
                        result.details.append({
                            "path": file_path,
                            "size": size,
                            "age_days": age_days,
                            "action": "would_archive"
                        })
                        continue
                    
                    if rule.strategy == PurgeStrategy.ARCHIVE:
                        archive_path = await self._archive_file(file_path, rule.archive_path, rule.compression_level)
                        os.remove(file_path)
                        result.archived_items += 1
                        result.archived_size += size
                        
                    elif rule.strategy == PurgeStrategy.COMPRESS:
                        compressed_path = await self._compress_file(file_path, rule.compression_level)
                        result.compressed_items += 1
                        result.compressed_size += size
                        
                    elif rule.strategy == PurgeStrategy.DELETE:
                        os.remove(file_path)
                        result.freed_items += 1
                        result.freed_size += size
                        
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "age_days": age_days,
                        "action": rule.strategy.value
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing old data {file_path}: {e}")
                    result.errors += 1
        
        return result

    async def _purge_duplicates(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        base_path = rule.conditions.get("base_path", ".")
        min_size = rule.conditions.get("min_size", 1024)
        use_hash = rule.conditions.get("use_hash", True)
        
        if not os.path.exists(base_path):
            return result
        
        files = []
        for root, dirs, file_list in os.walk(base_path):
            for file in file_list:
                file_path = os.path.join(root, file)
                try:
                    stat_info = os.stat(file_path)
                    if stat_info.st_size >= min_size:
                        files.append(file_path)
                except:
                    continue
        
        duplicates = defaultdict(list)
        processed = 0
        
        for file_path in files:
            try:
                if use_hash:
                    file_hash = await self._compute_file_hash(file_path)
                else:
                    file_hash = str(os.path.getsize(file_path))
                
                duplicates[file_hash].append(file_path)
                processed += 1
                
                if processed % 100 == 0:
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                logger.error(f"Error processing {file_path} for duplicates: {e}")
                result.errors += 1
        
        for file_hash, file_list in duplicates.items():
            if len(file_list) <= 1:
                continue
            
            keep_file = file_list[0]
            duplicate_files = file_list[1:]
            
            for dup_path in duplicate_files:
                try:
                    size = os.path.getsize(dup_path)
                    result.total_items += 1
                    result.total_size += size
                    
                    if dry_run:
                        result.details.append({
                            "path": dup_path,
                            "size": size,
                            "hash": file_hash[:16],
                            "action": "would_delete"
                        })
                        continue
                    
                    if rule.strategy == PurgeStrategy.DEDUPLICATE:
                        os.remove(dup_path)
                        result.freed_items += 1
                        result.freed_size += size
                        
                        result.details.append({
                            "path": dup_path,
                            "size": size,
                            "hash": file_hash[:16],
                            "action": "delete_duplicate"
                        })
                        
                except Exception as e:
                    logger.error(f"Error deleting duplicate {dup_path}: {e}")
                    result.errors += 1
        
        return result

    async def _purge_empty(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        base_path = rule.conditions.get("base_path", ".")
        recursive = rule.recursive
        
        if not os.path.exists(base_path):
            return result
        
        empty_dirs = []
        
        def find_empty_dirs(path):
            if not os.path.isdir(path):
                return
            
            try:
                items = os.listdir(path)
                if not items:
                    empty_dirs.append(path)
                    return
                
                if recursive:
                    for item in items:
                        item_path = os.path.join(path, item)
                        if os.path.isdir(item_path):
                            find_empty_dirs(item_path)
            except:
                pass
        
        find_empty_dirs(base_path)
        
        for dir_path in empty_dirs:
            try:
                if os.listdir(dir_path):
                    continue
                
                result.total_items += 1
                result.total_size += 0
                
                if dry_run:
                    result.details.append({
                        "path": dir_path,
                        "action": "would_delete"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.DELETE:
                    os.rmdir(dir_path)
                    result.freed_items += 1
                    
                    result.details.append({
                        "path": dir_path,
                        "action": "delete_empty"
                    })
                    
            except Exception as e:
                logger.error(f"Error deleting empty directory {dir_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_by_size(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        base_path = rule.conditions.get("base_path", ".")
        min_size_bytes = rule.conditions.get("min_size_bytes", 100 * 1024 * 1024)
        max_size_bytes = rule.conditions.get("max_size_bytes", None)
        patterns = rule.conditions.get("patterns", ["*"])
        
        if not os.path.exists(base_path):
            return result
        
        files = await self._find_files(base_path, patterns, rule.recursive, rule.exclude_patterns)
        
        for file_path in files:
            try:
                stat_info = os.stat(file_path)
                size = stat_info.st_size
                
                if size < min_size_bytes:
                    continue
                
                if max_size_bytes and size > max_size_bytes:
                    continue
                
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "action": "would_compress"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.COMPRESS:
                    compressed_path = await self._compress_file(file_path, rule.compression_level)
                    result.compressed_items += 1
                    result.compressed_size += size
                    
                elif rule.strategy == PurgeStrategy.ARCHIVE:
                    archive_path = await self._archive_file(file_path, rule.archive_path, rule.compression_level)
                    os.remove(file_path)
                    result.archived_items += 1
                    result.archived_size += size
                    
                elif rule.strategy == PurgeStrategy.DELETE:
                    os.remove(file_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                result.details.append({
                    "path": file_path,
                    "size": size,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_by_age(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        base_path = rule.conditions.get("base_path", ".")
        min_age_days = rule.conditions.get("min_age_days", 30)
        max_age_days = rule.conditions.get("max_age_days", None)
        patterns = rule.conditions.get("patterns", ["*"])
        
        if not os.path.exists(base_path):
            return result
        
        files = await self._find_files(base_path, patterns, rule.recursive, rule.exclude_patterns)
        
        for file_path in files:
            try:
                stat_info = os.stat(file_path)
                age = time.time() - stat_info.st_mtime
                age_days = age / 86400
                
                if age_days < min_age_days:
                    continue
                
                if max_age_days and age_days > max_age_days:
                    continue
                
                size = stat_info.st_size
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "age_days": age_days,
                        "action": "would_delete"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.DELETE:
                    os.remove(file_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                elif rule.strategy == PurgeStrategy.ARCHIVE:
                    archive_path = await self._archive_file(file_path, rule.archive_path, rule.compression_level)
                    os.remove(file_path)
                    result.archived_items += 1
                    result.archived_size += size
                    
                elif rule.strategy == PurgeStrategy.COMPRESS:
                    compressed_path = await self._compress_file(file_path, rule.compression_level)
                    result.compressed_items += 1
                    result.compressed_size += size
                    
                result.details.append({
                    "path": file_path,
                    "size": size,
                    "age_days": age_days,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_by_pattern(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        base_path = rule.conditions.get("base_path", ".")
        patterns = rule.conditions.get("patterns", [])
        recursive = rule.recursive
        
        if not patterns:
            return result
        
        if not os.path.exists(base_path):
            return result
        
        files = await self._find_files(base_path, patterns, recursive, rule.exclude_patterns)
        
        for file_path in files:
            try:
                stat_info = os.stat(file_path)
                size = stat_info.st_size
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "action": "would_delete"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.DELETE:
                    os.remove(file_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                elif rule.strategy == PurgeStrategy.ARCHIVE:
                    archive_path = await self._archive_file(file_path, rule.archive_path, rule.compression_level)
                    os.remove(file_path)
                    result.archived_items += 1
                    result.archived_size += size
                    
                result.details.append({
                    "path": file_path,
                    "size": size,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_compressed(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        base_path = rule.conditions.get("base_path", ".")
        patterns = rule.conditions.get("patterns", ["*.gz", "*.zip", "*.tar.gz", "*.7z", "*.bz2", "*.xz"])
        min_age_days = rule.conditions.get("min_age_days", 30)
        
        if not os.path.exists(base_path):
            return result
        
        files = await self._find_files(base_path, patterns, rule.recursive, rule.exclude_patterns)
        
        for file_path in files:
            try:
                stat_info = os.stat(file_path)
                age = time.time() - stat_info.st_mtime
                age_days = age / 86400
                
                if age_days < min_age_days:
                    continue
                
                size = stat_info.st_size
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "age_days": age_days,
                        "action": "would_delete"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.DELETE:
                    os.remove(file_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                result.details.append({
                    "path": file_path,
                    "size": size,
                    "age_days": age_days,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                result.errors += 1
        
        return result

    async def _purge_orphaned(self, rule: PurgeRule, dry_run: bool, result: PurgeResult) -> PurgeResult:
        base_path = rule.conditions.get("base_path", ".")
        reference_path = rule.conditions.get("reference_path", ".")
        patterns = rule.conditions.get("patterns", ["*"])
        
        if not os.path.exists(base_path) or not os.path.exists(reference_path):
            return result
        
        base_files = await self._find_files(base_path, patterns, rule.recursive, rule.exclude_patterns)
        ref_files = await self._find_files(reference_path, patterns, rule.recursive, rule.exclude_patterns)
        
        base_set = set(os.path.basename(f) for f in base_files)
        ref_set = set(os.path.basename(f) for f in ref_files)
        
        orphaned_files = [f for f in base_files if os.path.basename(f) not in ref_set]
        
        for file_path in orphaned_files:
            try:
                stat_info = os.stat(file_path)
                size = stat_info.st_size
                result.total_items += 1
                result.total_size += size
                
                if dry_run:
                    result.details.append({
                        "path": file_path,
                        "size": size,
                        "action": "would_delete"
                    })
                    continue
                
                if rule.strategy == PurgeStrategy.DELETE:
                    os.remove(file_path)
                    result.freed_items += 1
                    result.freed_size += size
                    
                result.details.append({
                    "path": file_path,
                    "size": size,
                    "action": rule.strategy.value
                })
                
            except Exception as e:
                logger.error(f"Error processing orphaned {file_path}: {e}")
                result.errors += 1
        
        return result

    async def _find_files(
        self,
        base_path: str,
        patterns: List[str],
        recursive: bool,
        exclude_patterns: List[str]
    ) -> List[str]:
        files = []
        
        if recursive:
            for pattern in patterns:
                search_path = os.path.join(base_path, "**", pattern)
                for file_path in glob.glob(search_path, recursive=True):
                    if os.path.isfile(file_path):
                        if not self._is_excluded(file_path, exclude_patterns):
                            files.append(file_path)
        else:
            for pattern in patterns:
                search_path = os.path.join(base_path, pattern)
                for file_path in glob.glob(search_path):
                    if os.path.isfile(file_path):
                        if not self._is_excluded(file_path, exclude_patterns):
                            files.append(file_path)
        
        return files

    async def _find_directories(
        self,
        base_path: str,
        patterns: List[str],
        recursive: bool,
        exclude_patterns: List[str]
    ) -> List[str]:
        directories = []
        
        if recursive:
            for pattern in patterns:
                search_path = os.path.join(base_path, "**", pattern)
                for dir_path in glob.glob(search_path, recursive=True):
                    if os.path.isdir(dir_path):
                        if not self._is_excluded(dir_path, exclude_patterns):
                            directories.append(dir_path)
        else:
            for pattern in patterns:
                search_path = os.path.join(base_path, pattern)
                for dir_path in glob.glob(search_path):
                    if os.path.isdir(dir_path):
                        if not self._is_excluded(dir_path, exclude_patterns):
                            directories.append(dir_path)
        
        return directories

    def _is_excluded(self, path: str, exclude_patterns: List[str]) -> bool:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def _should_purge_file(self, stat_info: os.stat_result, rule: PurgeRule) -> bool:
        conditions = rule.conditions
        
        if "min_size_bytes" in conditions:
            if stat_info.st_size < conditions["min_size_bytes"]:
                return False
        
        if "max_size_bytes" in conditions:
            if stat_info.st_size > conditions["max_size_bytes"]:
                return False
        
        if "min_age_days" in conditions:
            age = time.time() - stat_info.st_mtime
            if age < conditions["min_age_days"] * 86400:
                return False
        
        if "max_age_days" in conditions:
            age = time.time() - stat_info.st_mtime
            if age > conditions["max_age_days"] * 86400:
                return False
        
        return True

    def _should_purge_directory(self, path: str, rule: PurgeRule) -> bool:
        conditions = rule.conditions
        
        if "min_age_days" in conditions:
            try:
                stat_info = os.stat(path)
                age = time.time() - stat_info.st_mtime
                if age < conditions["min_age_days"] * 86400:
                    return False
            except:
                return False
        
        if "require_empty" in conditions and conditions["require_empty"]:
            try:
                if os.listdir(path):
                    return False
            except:
                return False
        
        return True

    def _build_where_clause(self, conditions: Dict[str, Any]) -> str:
        if not conditions:
            return ""
        
        clauses = []
        for key, value in conditions.items():
            if isinstance(value, list):
                placeholders = ', '.join(['?'] * len(value))
                clauses.append(f"{key} IN ({placeholders})")
            elif isinstance(value, dict):
                for op, val in value.items():
                    if op == "lt":
                        clauses.append(f"{key} < ?")
                    elif op == "lte":
                        clauses.append(f"{key} <= ?")
                    elif op == "gt":
                        clauses.append(f"{key} > ?")
                    elif op == "gte":
                        clauses.append(f"{key} >= ?")
                    elif op == "ne":
                        clauses.append(f"{key} != ?")
                    elif op == "like":
                        clauses.append(f"{key} LIKE ?")
                    elif op == "between":
                        clauses.append(f"{key} BETWEEN ? AND ?")
            else:
                clauses.append(f"{key} = ?")
        
        return " AND ".join(clauses)

    async def _archive_file(self, file_path: str, archive_path: str, compression_level: int) -> str:
        if not archive_path:
            raise ValueError("Archive path not specified")
        
        os.makedirs(archive_path, exist_ok=True)
        
        file_name = os.path.basename(file_path)
        archive_file = os.path.join(archive_path, f"{file_name}.gz")
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(archive_file, 'wb', compresslevel=compression_level) as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return archive_file

    async def _archive_directory(self, dir_path: str, archive_path: str, compression_level: int) -> str:
        if not archive_path:
            raise ValueError("Archive path not specified")
        
        os.makedirs(archive_path, exist_ok=True)
        
        dir_name = os.path.basename(dir_path)
        archive_file = os.path.join(archive_path, f"{dir_name}.tar.gz")
        
        with tarfile.open(archive_file, 'w:gz', compresslevel=compression_level) as tar:
            tar.add(dir_path, arcname=dir_name)
        
        return archive_file

    async def _compress_file(self, file_path: str, compression_level: int) -> str:
        compressed_path = f"{file_path}.gz"
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb', compresslevel=compression_level) as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return compressed_path

    async def _compress_directory(self, dir_path: str, compression_level: int) -> str:
        compressed_path = f"{dir_path}.tar.gz"
        
        with tarfile.open(compressed_path, 'w:gz', compresslevel=compression_level) as tar:
            tar.add(dir_path, arcname=os.path.basename(dir_path))
        
        return compressed_path

    async def _move_file(self, file_path: str, move_path: str) -> str:
        if not move_path:
            raise ValueError("Move path not specified")
        
        os.makedirs(move_path, exist_ok=True)
        
        dest_path = os.path.join(move_path, os.path.basename(file_path))
        shutil.move(file_path, dest_path)
        
        return dest_path

    async def _move_directory(self, dir_path: str, move_path: str) -> str:
        if not move_path:
            raise ValueError("Move path not specified")
        
        os.makedirs(move_path, exist_ok=True)
        
        dest_path = os.path.join(move_path, os.path.basename(dir_path))
        shutil.move(dir_path, dest_path)
        
        return dest_path

    async def _compute_file_hash(self, file_path: str, algorithm: str = "sha256") -> str:
        if file_path in self._file_hashes:
            return self._file_hashes[file_path]
        
        sha = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                sha.update(data)
        
        file_hash = sha.hexdigest()
        self._file_hashes[file_path] = file_hash
        return file_hash

    async def _get_directory_size(self, path: str) -> int:
        total = 0
        for root, dirs, files in os.walk(path):
            for file in files:
                try:
                    total += os.path.getsize(os.path.join(root, file))
                except:
                    pass
        return total

    def get_result(self, rule_name: str) -> Optional[PurgeResult]:
        return self._results.get(rule_name)

    def get_all_results(self) -> Dict[str, PurgeResult]:
        return dict(self._results)

    async def purge_all(self, dry_run: bool = False, rules: Optional[List[str]] = None) -> Dict[str, PurgeResult]:
        results = {}
        rules_to_run = rules or list(self._rules.keys())
        
        for rule_name in rules_to_run:
            if rule_name in self._rules:
                try:
                    result = await self.purge(rule_name, dry_run)
                    results[rule_name] = result
                except Exception as e:
                    logger.error(f"Error running purge {rule_name}: {e}")
                    results[rule_name] = PurgeResult(
                        total_items=0,
                        total_size=0,
                        freed_items=0,
                        freed_size=0,
                        archived_items=0,
                        archived_size=0,
                        compressed_items=0,
                        compressed_size=0,
                        moved_items=0,
                        moved_size=0,
                        errors=1,
                        start_time=time.time(),
                        end_time=time.time(),
                        details=[],
                        rules_applied=[rule_name]
                    )
        
        return results

    def get_stats(self) -> Dict[str, Any]:
        return {
            "rules": len(self._rules),
            "results": len(self._results),
            "running": self._running,
            "active_purges": list(self._active_purges),
            "cache_size": len(self._cache),
            "file_hashes": len(self._file_hashes),
            "duplicate_groups": len(self._duplicate_groups),
            "purges_completed": self._stats['purges_completed'],
            "thread_pool": self._executor._max_workers
        }

    def clear_cache(self) -> None:
        self._cache.clear()
        self._file_hashes.clear()
        self._duplicate_groups.clear()

    def clear_results(self) -> None:
        self._results.clear()

    def get_summary(self) -> Dict[str, Any]:
        total_freed_items = 0
        total_freed_size = 0
        total_archived_items = 0
        total_archived_size = 0
        total_compressed_items = 0
        total_compressed_size = 0
        total_moved_items = 0
        total_moved_size = 0
        total_errors = 0
        
        for result in self._results.values():
            total_freed_items += result.freed_items
            total_freed_size += result.freed_size
            total_archived_items += result.archived_items
            total_archived_size += result.archived_size
            total_compressed_items += result.compressed_items
            total_compressed_size += result.compressed_size
            total_moved_items += result.moved_items
            total_moved_size += result.moved_size
            total_errors += result.errors
        
        return {
            "total_freed_items": total_freed_items,
            "total_freed_size": total_freed_size,
            "total_archived_items": total_archived_items,
            "total_archived_size": total_archived_size,
            "total_compressed_items": total_compressed_items,
            "total_compressed_size": total_compressed_size,
            "total_moved_items": total_moved_items,
            "total_moved_size": total_moved_size,
            "total_errors": total_errors,
            "total_processed": len(self._results)
        }


__all__ = [
    "PurgeTarget",
    "PurgeStrategy",
    "AgeUnit",
    "PurgeItem",
    "PurgeResult",
    "PurgeRule",
    "DatabasePurgeTarget",
    "CachePurgeTarget",
    "DataPurgeManager"
]
