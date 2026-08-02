# trading/bots/hedge_bot/hedge_bot_data_retention.py

import asyncio
import logging
import time
import json
import hashlib
import os
import shutil
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class RetentionPolicyType(str, Enum):
    TIME_BASED = "time_based"
    SIZE_BASED = "size_based"
    COUNT_BASED = "count_based"
    COMPOSITE = "composite"
    HIERARCHICAL = "hierarchical"
    TIERED = "tiered"
    ROLLING = "rolling"
    SLIDING = "sliding"


class RetentionAction(str, Enum):
    DELETE = "delete"
    ARCHIVE = "archive"
    COMPRESS = "compress"
    MOVE = "move"
    SUMMARIZE = "summarize"
    AGGREGATE = "aggregate"
    SAMPLE = "sample"
    REDACT = "redact"
    ANONYMIZE = "anonymize"
    NOTHING = "nothing"


class RetentionScope(str, Enum):
    GLOBAL = "global"
    CATEGORY = "category"
    DATASET = "dataset"
    TABLE = "table"
    COLLECTION = "collection"
    FILE = "file"


@dataclass
class RetentionRule:
    id: str
    name: str
    scope: RetentionScope
    scope_value: str
    policy_type: RetentionPolicyType
    actions: List[RetentionAction]
    conditions: Dict[str, Any]
    priority: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class RetentionPolicy:
    id: str
    name: str
    description: str
    rules: List[RetentionRule]
    default_action: RetentionAction = RetentionAction.NOTHING
    grace_period: int = 86400
    check_interval: int = 3600
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class RetentionResult:
    id: str
    policy_id: str
    items_processed: int
    items_affected: int
    items_deleted: int
    items_archived: int
    items_compressed: int
    items_moved: int
    items_summarized: int
    items_aggregated: int
    items_sampled: int
    items_redacted: int
    items_anonymized: int
    size_freed: int
    size_before: int
    size_after: int
    start_time: float
    end_time: float
    errors: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetentionSchedule:
    id: str
    policy_id: str
    frequency: str
    interval: int
    next_run: float
    last_run: Optional[float] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class RetentionSnapshot:
    id: str
    policy_id: str
    timestamp: float
    items_before: int
    items_after: int
    size_before: int
    size_after: int
    actions_taken: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)


class RetentionManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._policies: Dict[str, RetentionPolicy] = {}
        self._rules: Dict[str, RetentionRule] = {}
        self._schedules: Dict[str, RetentionSchedule] = {}
        self._results: Dict[str, RetentionResult] = {}
        self._snapshots: Dict[str, RetentionSnapshot] = {}
        self._handlers: Dict[RetentionAction, Callable] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._data_dirs: List[str] = []
        
        self._initialize_handlers()
        self._initialize_default_policies()

    def _initialize_handlers(self) -> None:
        self.register_handler(RetentionAction.DELETE, self._handle_delete)
        self.register_handler(RetentionAction.ARCHIVE, self._handle_archive)
        self.register_handler(RetentionAction.COMPRESS, self._handle_compress)
        self.register_handler(RetentionAction.MOVE, self._handle_move)
        self.register_handler(RetentionAction.SUMMARIZE, self._handle_summarize)
        self.register_handler(RetentionAction.AGGREGATE, self._handle_aggregate)
        self.register_handler(RetentionAction.SAMPLE, self._handle_sample)
        self.register_handler(RetentionAction.REDACT, self._handle_redact)
        self.register_handler(RetentionAction.ANONYMIZE, self._handle_anonymize)

    def _initialize_default_policies(self) -> None:
        default_policies = [
            RetentionPolicy(
                id="daily_logs",
                name="Daily Log Retention",
                description="Retain logs for 30 days, archive older logs",
                rules=[
                    RetentionRule(
                        id="log_age",
                        name="Log Age Rule",
                        scope=RetentionScope.CATEGORY,
                        scope_value="logs",
                        policy_type=RetentionPolicyType.TIME_BASED,
                        actions=[RetentionAction.DELETE],
                        conditions={"max_age_days": 30}
                    ),
                    RetentionRule(
                        id="log_archive",
                        name="Log Archive Rule",
                        scope=RetentionScope.CATEGORY,
                        scope_value="logs",
                        policy_type=RetentionPolicyType.TIME_BASED,
                        actions=[RetentionAction.ARCHIVE],
                        conditions={"min_age_days": 7, "max_age_days": 30}
                    )
                ]
            ),
            RetentionPolicy(
                id="trading_data",
                name="Trading Data Retention",
                description="Retain trading data based on importance",
                rules=[
                    RetentionRule(
                        id="tick_data",
                        name="Tick Data Rule",
                        scope=RetentionScope.DATASET,
                        scope_value="ticks",
                        policy_type=RetentionPolicyType.TIME_BASED,
                        actions=[RetentionAction.AGGREGATE],
                        conditions={"max_age_days": 7, "aggregation": "1m"}
                    ),
                    RetentionRule(
                        id="ohlc_data",
                        name="OHLC Data Rule",
                        scope=RetentionScope.DATASET,
                        scope_value="ohlc",
                        policy_type=RetentionPolicyType.TIME_BASED,
                        actions=[RetentionAction.DELETE],
                        conditions={"max_age_days": 365}
                    )
                ]
            ),
            RetentionPolicy(
                id="cache_cleanup",
                name="Cache Cleanup Policy",
                description="Remove old cache entries",
                rules=[
                    RetentionRule(
                        id="cache_size",
                        name="Cache Size Rule",
                        scope=RetentionScope.CATEGORY,
                        scope_value="cache",
                        policy_type=RetentionPolicyType.SIZE_BASED,
                        actions=[RetentionAction.DELETE],
                        conditions={"max_size_mb": 1024}
                    ),
                    RetentionRule(
                        id="cache_age",
                        name="Cache Age Rule",
                        scope=RetentionScope.CATEGORY,
                        scope_value="cache",
                        policy_type=RetentionPolicyType.TIME_BASED,
                        actions=[RetentionAction.DELETE],
                        conditions={"max_age_days": 7}
                    )
                ]
            )
        ]
        
        for policy in default_policies:
            self._policies[policy.id] = policy
            for rule in policy.rules:
                self._rules[rule.id] = rule

    def register_handler(self, action: RetentionAction, handler: Callable) -> None:
        self._handlers[action] = handler

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_policy(
        self,
        name: str,
        description: str,
        rules: List[Dict[str, Any]],
        default_action: RetentionAction = RetentionAction.NOTHING,
        grace_period: int = 86400,
        check_interval: int = 3600,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RetentionPolicy:
        async with self._lock:
            policy_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            policy_rules = []
            for rule_data in rules:
                rule = RetentionRule(
                    id=hashlib.md5(f"{rule_data['name']}_{time.time()}".encode()).hexdigest(),
                    name=rule_data["name"],
                    scope=RetentionScope(rule_data["scope"]),
                    scope_value=rule_data["scope_value"],
                    policy_type=RetentionPolicyType(rule_data["policy_type"]),
                    actions=[RetentionAction(a) for a in rule_data.get("actions", [])],
                    conditions=rule_data.get("conditions", {}),
                    priority=rule_data.get("priority", 0),
                    enabled=rule_data.get("enabled", True),
                    metadata=rule_data.get("metadata", {})
                )
                policy_rules.append(rule)
                self._rules[rule.id] = rule
            
            policy = RetentionPolicy(
                id=policy_id,
                name=name,
                description=description,
                rules=policy_rules,
                default_action=default_action,
                grace_period=grace_period,
                check_interval=check_interval,
                enabled=True,
                metadata=metadata or {}
            )
            
            self._policies[policy_id] = policy
            await self._notify_observers("policy_created", policy)
            
            return policy

    async def apply_policy(self, policy_id: str, dry_run: bool = False) -> RetentionResult:
        async with self._lock:
            if policy_id not in self._policies:
                raise ValueError(f"Policy not found: {policy_id}")
            
            policy = self._policies[policy_id]
            
            result = RetentionResult(
                id=hashlib.md5(f"{policy_id}_{time.time()}".encode()).hexdigest(),
                policy_id=policy_id,
                items_processed=0,
                items_affected=0,
                items_deleted=0,
                items_archived=0,
                items_compressed=0,
                items_moved=0,
                items_summarized=0,
                items_aggregated=0,
                items_sampled=0,
                items_redacted=0,
                items_anonymized=0,
                size_freed=0,
                size_before=0,
                size_after=0,
                start_time=time.time(),
                end_time=0
            )
            
            try:
                for rule in sorted(policy.rules, key=lambda r: r.priority):
                    if not rule.enabled:
                        continue
                    
                    await self._apply_rule(rule, result, dry_run)
                
                result.end_time = time.time()
                self._results[result.id] = result
                await self._notify_observers("policy_applied", policy, result)
                
                return result
                
            except Exception as e:
                logger.error(f"Error applying policy: {e}")
                result.errors.append({"error": str(e), "timestamp": time.time()})
                result.end_time = time.time()
                raise

    async def _apply_rule(
        self,
        rule: RetentionRule,
        result: RetentionResult,
        dry_run: bool
    ) -> None:
        data_items = await self._get_data_items(rule)
        result.size_before += sum(item.size for item in data_items)
        result.items_processed += len(data_items)
        
        items_to_process = []
        
        if rule.policy_type == RetentionPolicyType.TIME_BASED:
            items_to_process = await self._filter_by_time(data_items, rule.conditions)
        elif rule.policy_type == RetentionPolicyType.SIZE_BASED:
            items_to_process = await self._filter_by_size(data_items, rule.conditions)
        elif rule.policy_type == RetentionPolicyType.COUNT_BASED:
            items_to_process = await self._filter_by_count(data_items, rule.conditions)
        elif rule.policy_type == RetentionPolicyType.COMPOSITE:
            items_to_process = await self._filter_composite(data_items, rule.conditions)
        elif rule.policy_type == RetentionPolicyType.HIERARCHICAL:
            items_to_process = await self._filter_hierarchical(data_items, rule.conditions)
        elif rule.policy_type == RetentionPolicyType.TIERED:
            items_to_process = await self._filter_tiered(data_items, rule.conditions)
        elif rule.policy_type == RetentionPolicyType.ROLLING:
            items_to_process = await self._filter_rolling(data_items, rule.conditions)
        elif rule.policy_type == RetentionPolicyType.SLIDING:
            items_to_process = await self._filter_sliding(data_items, rule.conditions)
        
        result.items_affected += len(items_to_process)
        
        for item in items_to_process:
            if dry_run:
                await self._notify_observers("dry_run_item", rule, item)
                continue
            
            for action in rule.actions:
                if action in self._handlers:
                    try:
                        await self._handlers[action](item, rule, result)
                        result.__dict__[f"items_{action.value}"] += 1
                    except Exception as e:
                        logger.error(f"Error applying action {action} to {item.path}: {e}")
                        result.errors.append({
                            "action": action.value,
                            "path": item.path,
                            "error": str(e),
                            "timestamp": time.time()
                        })
        
        result.size_after = sum(item.size for item in data_items if not self._is_affected(item, items_to_process))
        result.size_freed = result.size_before - result.size_after

    async def _get_data_items(self, rule: RetentionRule) -> List[Dict[str, Any]]:
        items = []
        
        if rule.scope == RetentionScope.GLOBAL:
            for data_dir in self._data_dirs:
                items.extend(await self._scan_directory(data_dir))
        elif rule.scope == RetentionScope.CATEGORY:
            for data_dir in self._data_dirs:
                category_path = os.path.join(data_dir, rule.scope_value)
                if os.path.exists(category_path):
                    items.extend(await self._scan_directory(category_path))
        elif rule.scope == RetentionScope.DATASET:
            for data_dir in self._data_dirs:
                dataset_path = os.path.join(data_dir, rule.scope_value)
                if os.path.exists(dataset_path):
                    items.extend(await self._scan_directory(dataset_path))
        elif rule.scope == RetentionScope.TABLE:
            items.extend(await self._scan_table(rule.scope_value))
        elif rule.scope == RetentionScope.COLLECTION:
            items.extend(await self._scan_collection(rule.scope_value))
        elif rule.scope == RetentionScope.FILE:
            items.extend(await self._scan_files(rule.scope_value))
        
        return items

    async def _scan_directory(self, path: str) -> List[Dict[str, Any]]:
        items = []
        
        if not os.path.exists(path):
            return items
        
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    stat = os.stat(file_path)
                    items.append({
                        "path": file_path,
                        "size": stat.st_size,
                        "created": stat.st_ctime,
                        "modified": stat.st_mtime,
                        "accessed": stat.st_atime,
                        "type": "file",
                        "name": file
                    })
                except Exception as e:
                    logger.error(f"Error scanning {file_path}: {e}")
            
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                try:
                    stat = os.stat(dir_path)
                    items.append({
                        "path": dir_path,
                        "size": 0,
                        "created": stat.st_ctime,
                        "modified": stat.st_mtime,
                        "accessed": stat.st_atime,
                        "type": "directory",
                        "name": dir,
                        "child_count": len(os.listdir(dir_path))
                    })
                except Exception as e:
                    logger.error(f"Error scanning {dir_path}: {e}")
        
        return items

    async def _scan_table(self, table_name: str) -> List[Dict[str, Any]]:
        return []

    async def _scan_collection(self, collection_name: str) -> List[Dict[str, Any]]:
        return []

    async def _scan_files(self, pattern: str) -> List[Dict[str, Any]]:
        items = []
        for path in Path('.').glob(pattern):
            items.append({
                "path": str(path),
                "size": path.stat().st_size,
                "created": path.stat().st_ctime,
                "modified": path.stat().st_mtime,
                "accessed": path.stat().st_atime,
                "type": "file",
                "name": path.name
            })
        return items

    async def _filter_by_time(
        self,
        items: List[Dict[str, Any]],
        conditions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        now = time.time()
        filtered = []
        
        min_age_days = conditions.get("min_age_days", 0)
        max_age_days = conditions.get("max_age_days", float('inf'))
        
        min_age = now - (min_age_days * 86400)
        max_age = now - (max_age_days * 86400) if max_age_days != float('inf') else 0
        
        for item in items:
            age = now - item["created"]
            age_days = age / 86400
            
            if min_age_days <= age_days <= max_age_days:
                filtered.append(item)
        
        return filtered

    async def _filter_by_size(
        self,
        items: List[Dict[str, Any]],
        conditions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        filtered = []
        
        min_size = conditions.get("min_size_mb", 0) * 1024 * 1024
        max_size = conditions.get("max_size_mb", float('inf')) * 1024 * 1024
        
        for item in items:
            if min_size <= item["size"] <= max_size:
                filtered.append(item)
        
        return filtered

    async def _filter_by_count(
        self,
        items: List[Dict[str, Any]],
        conditions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        max_count = conditions.get("max_count", 1000)
        
        items.sort(key=lambda x: x["created"], reverse=True)
        return items[max_count:]

    async def _filter_composite(
        self,
        items: List[Dict[str, Any]],
        conditions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        filtered = items
        
        for key, value in conditions.items():
            if key == "min_age_days":
                now = time.time()
                filtered = [i for i in filtered if (now - i["created"]) / 86400 >= value]
            elif key == "max_age_days":
                now = time.time()
                filtered = [i for i in filtered if (now - i["created"]) / 86400 <= value]
            elif key == "min_size_mb":
                filtered = [i for i in filtered if i["size"] >= value * 1024 * 1024]
            elif key == "max_size_mb":
                filtered = [i for i in filtered if i["size"] <= value * 1024 * 1024]
            elif key == "max_count":
                filtered = filtered[:value]
        
        return filtered

    async def _filter_hierarchical(
        self,
        items: List[Dict[str, Any]],
        conditions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        levels = conditions.get("levels", [])
        if not levels:
            return items
        
        filtered = []
        for level in levels:
            level_items = await self._filter_by_time(items, level.get("time", {}))
            level_items = await self._filter_by_size(level_items, level.get("size", {}))
            filtered.extend(level_items)
        
        return filtered

    async def _filter_tiered(
        self,
        items: List[Dict[str, Any]],
        conditions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        tiers = conditions.get("tiers", [])
        if not tiers:
            return items
        
        filtered = []
        for tier in tiers:
            tier_items = await self._filter_by_time(items, tier.get("time", {}))
            tier_items = await self._filter_by_size(tier_items, tier.get("size", {}))
            if tier.get("limit"):
                tier_items = tier_items[:tier["limit"]]
            filtered.extend(tier_items)
        
        return filtered

    async def _filter_rolling(
        self,
        items: List[Dict[str, Any]],
        conditions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        window_size = conditions.get("window_size", 7)
        max_count = conditions.get("max_count", 1000)
        
        items.sort(key=lambda x: x["created"], reverse=True)
        
        now = time.time()
        window_start = now - (window_size * 86400)
        
        filtered = []
        for item in items:
            if item["created"] >= window_start:
                filtered.append(item)
        
        return filtered[max_count:]

    async def _filter_sliding(
        self,
        items: List[Dict[str, Any]],
        conditions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        window_size = conditions.get("window_size", 30)
        max_count = conditions.get("max_count", 1000)
        
        items.sort(key=lambda x: x["created"], reverse=True)
        
        result = []
        for i in range(0, len(items), max_count):
            window_items = items[i:i + max_count]
            if window_items:
                result.append(window_items[-1])
        
        return result

    async def _handle_delete(self, item: Dict[str, Any], rule: RetentionRule, result: RetentionResult) -> None:
        if item["type"] == "file":
            os.remove(item["path"])
            result.size_freed += item["size"]
        elif item["type"] == "directory":
            shutil.rmtree(item["path"])

    async def _handle_archive(self, item: Dict[str, Any], rule: RetentionRule, result: RetentionResult) -> None:
        archive_dir = rule.conditions.get("archive_dir", "./archive")
        os.makedirs(archive_dir, exist_ok=True)
        
        base_name = os.path.basename(item["path"])
        dest_path = os.path.join(archive_dir, base_name)
        
        if item["type"] == "file":
            shutil.copy2(item["path"], dest_path)
            os.remove(item["path"])
        elif item["type"] == "directory":
            shutil.copytree(item["path"], dest_path)
            shutil.rmtree(item["path"])

    async def _handle_compress(self, item: Dict[str, Any], rule: RetentionRule, result: RetentionResult) -> None:
        import gzip
        
        if item["type"] != "file":
            return
        
        with open(item["path"], 'rb') as f_in:
            with gzip.open(f"{item['path']}.gz", 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        os.remove(item["path"])

    async def _handle_move(self, item: Dict[str, Any], rule: RetentionRule, result: RetentionResult) -> None:
        dest_dir = rule.conditions.get("dest_dir", "./moved")
        os.makedirs(dest_dir, exist_ok=True)
        
        base_name = os.path.basename(item["path"])
        dest_path = os.path.join(dest_dir, base_name)
        
        if item["type"] == "file":
            shutil.move(item["path"], dest_path)
        elif item["type"] == "directory":
            shutil.move(item["path"], dest_path)

    async def _handle_summarize(self, item: Dict[str, Any], rule: RetentionRule, result: RetentionResult) -> None:
        if not item["path"].endswith('.csv') and not item["path"].endswith('.json'):
            return
        
        try:
            if item["path"].endswith('.csv'):
                df = pd.read_csv(item["path"])
            else:
                df = pd.read_json(item["path"])
            
            summary = {
                "rows": len(df),
                "columns": list(df.columns),
                "types": df.dtypes.astype(str).to_dict(),
                "null_counts": df.isnull().sum().to_dict(),
                "summary_stats": df.describe().to_dict() if len(df.columns) > 0 else {}
            }
            
            summary_path = f"{item['path']}.summary.json"
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)
            
        except Exception as e:
            logger.error(f"Error summarizing {item['path']}: {e}")

    async def _handle_aggregate(self, item: Dict[str, Any], rule: RetentionRule, result: RetentionResult) -> None:
        aggregation = rule.conditions.get("aggregation", "1m")
        column = rule.conditions.get("column", "close")
        
        try:
            if item["path"].endswith('.csv'):
                df = pd.read_csv(item["path"], parse_dates=['timestamp'], index_col='timestamp')
            else:
                return
            
            if 'timestamp' not in df.index.names:
                return
            
            aggregated = df.resample(aggregation).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            aggregated_path = f"{item['path']}.aggregated_{aggregation}.csv"
            aggregated.to_csv(aggregated_path)
            
        except Exception as e:
            logger.error(f"Error aggregating {item['path']}: {e}")

    async def _handle_sample(self, item: Dict[str, Any], rule: RetentionRule, result: RetentionResult) -> None:
        sample_rate = rule.conditions.get("sample_rate", 0.1)
        
        try:
            if item["path"].endswith('.csv'):
                df = pd.read_csv(item["path"])
                sampled = df.sample(frac=sample_rate, random_state=42)
                sampled_path = f"{item['path']}.sampled.csv"
                sampled.to_csv(sampled_path)
            else:
                return
                
        except Exception as e:
            logger.error(f"Error sampling {item['path']}: {e}")

    async def _handle_redact(self, item: Dict[str, Any], rule: RetentionRule, result: RetentionResult) -> None:
        fields = rule.conditions.get("fields", [])
        
        try:
            if item["path"].endswith('.csv'):
                df = pd.read_csv(item["path"])
                for field in fields:
                    if field in df.columns:
                        df[field] = 'REDACTED'
                df.to_csv(item["path"], index=False)
            elif item["path"].endswith('.json'):
                with open(item["path"], 'r') as f:
                    data = json.load(f)
                
                await self._redact_data(data, fields)
                
                with open(item["path"], 'w') as f:
                    json.dump(data, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Error redacting {item['path']}: {e}")

    async def _redact_data(self, data: Any, fields: List[str]) -> None:
        if isinstance(data, dict):
            for key in list(data.keys()):
                if key in fields:
                    data[key] = 'REDACTED'
                else:
                    await self._redact_data(data[key], fields)
        elif isinstance(data, list):
            for item in data:
                await self._redact_data(item, fields)

    async def _handle_anonymize(self, item: Dict[str, Any], rule: RetentionRule, result: RetentionResult) -> None:
        fields = rule.conditions.get("fields", [])
        
        try:
            if item["path"].endswith('.csv'):
                df = pd.read_csv(item["path"])
                for field in fields:
                    if field in df.columns:
                        df[field] = df[field].apply(lambda x: hashlib.sha256(str(x).encode()).hexdigest()[:16])
                df.to_csv(item["path"], index=False)
            elif item["path"].endswith('.json'):
                with open(item["path"], 'r') as f:
                    data = json.load(f)
                
                await self._anonymize_data(data, fields)
                
                with open(item["path"], 'w') as f:
                    json.dump(data, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Error anonymizing {item['path']}: {e}")

    async def _anonymize_data(self, data: Any, fields: List[str]) -> None:
        if isinstance(data, dict):
            for key in list(data.keys()):
                if key in fields:
                    data[key] = hashlib.sha256(str(data[key]).encode()).hexdigest()[:16]
                else:
                    await self._anonymize_data(data[key], fields)
        elif isinstance(data, list):
            for item in data:
                await self._anonymize_data(item, fields)

    def _is_affected(self, item: Dict[str, Any], affected_items: List[Dict[str, Any]]) -> bool:
        return any(i["path"] == item["path"] for i in affected_items)

    async def add_data_dir(self, directory: str) -> None:
        if os.path.exists(directory) and directory not in self._data_dirs:
            self._data_dirs.append(directory)

    async def remove_data_dir(self, directory: str) -> bool:
        if directory in self._data_dirs:
            self._data_dirs.remove(directory)
            return True
        return False

    async def get_snapshot(self, policy_id: str) -> Optional[RetentionSnapshot]:
        snapshots = [s for s in self._snapshots.values() if s.policy_id == policy_id]
        if snapshots:
            return max(snapshots, key=lambda s: s.timestamp)
        return None

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "policies": len(self._policies),
            "rules": len(self._rules),
            "schedules": len(self._schedules),
            "results": len(self._results),
            "snapshots": len(self._snapshots),
            "data_dirs": len(self._data_dirs),
            "handlers": len(self._handlers),
            "running": self._running
        }


__all__ = [
    "RetentionPolicyType",
    "RetentionAction",
    "RetentionScope",
    "RetentionRule",
    "RetentionPolicy",
    "RetentionResult",
    "RetentionSchedule",
    "RetentionSnapshot",
    "RetentionManager"
]
