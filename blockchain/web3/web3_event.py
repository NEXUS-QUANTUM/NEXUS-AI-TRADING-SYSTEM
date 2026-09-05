"""
Web3 Event Module
===================

This module provides event monitoring and processing capabilities for Web3 clients.
It supports real-time event listening, filtering, callback handling, and reconnection.
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Union, Any, Callable, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import queue

from web3 import Web3
from web3.types import LogReceipt, EventData
from eth_abi import decode_abi, encode_abi

from trading.bots.swing_bot.utils.cache import MemoryCache
from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.threads import ThreadPool, AsyncThreadPool

logger = logging.getLogger(__name__)


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Web3Event:
    """Web3 event data structure."""
    event_name: str
    contract_address: str
    block_number: int
    transaction_hash: str
    log_index: int
    args: Dict[str, Any]
    raw_data: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    status: EventStatus = EventStatus.PENDING
    processed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class EventFilter:
    """Event filter configuration."""
    contract_address: Optional[str] = None
    event_name: Optional[str] = None
    from_block: Union[int, str] = 'earliest'
    to_block: Union[int, str] = 'latest'
    argument_filters: Dict[str, Any] = field(default_factory=dict)
    topics: Optional[List[Any]] = None


@dataclass
class EventSubscription:
    """Event subscription configuration."""
    id: str
    filter: EventFilter
    callback: Callable[[Web3Event], None]
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_event: Optional[datetime] = None
    event_count: int = 0


class Web3EventManager:
    """
    Web3 event manager for monitoring and processing blockchain events.
    
    Supports:
    - Real-time event listening
    - Event filtering
    - Callback registration
    - Reconnection handling
    - Event caching
    - Multi-threaded processing
    """
    
    def __init__(
        self,
        web3_client: Any,
        poll_interval: float = 1.0,
        max_events_per_poll: int = 100,
        max_queue_size: int = 10000,
        enable_cache: bool = True,
        cache_ttl: int = 300
    ):
        """
        Initialize the event manager.
        
        Args:
            web3_client: Web3 client instance.
            poll_interval: Polling interval in seconds for new blocks.
            max_events_per_poll: Maximum events to fetch per poll.
            max_queue_size: Maximum event queue size.
            enable_cache: Enable caching of processed events.
            cache_ttl: Cache TTL in seconds.
        """
        self.web3_client = web3_client
        self.poll_interval = poll_interval
        self.max_events_per_poll = max_events_per_poll
        self.max_queue_size = max_queue_size
        
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._subscription_lock = threading.RLock()
        
        self._event_queue: deque = deque(maxlen=max_queue_size)
        self._event_lock = threading.RLock()
        
        self._processed_events: Set[str] = set()
        self._processed_lock = threading.RLock()
        
        self._cache = MemoryCache(max_size=10000, default_ttl=cache_ttl) if enable_cache else None
        
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._processor_thread: Optional[threading.Thread] = None
        
        self._last_block = 0
        self._last_poll_time: Optional[datetime] = None
        
        self._thread_pool = ThreadPool(max_workers=4)
        
        # Async support
        self._async_tasks: Dict[str, asyncio.Task] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        logger.info("Web3EventManager initialized")
    
    # ============ Subscription Management ============
    
    def subscribe(
        self,
        callback: Callable[[Web3Event], None],
        contract_address: Optional[str] = None,
        event_name: Optional[str] = None,
        from_block: Union[int, str] = 'latest',
        argument_filters: Optional[Dict[str, Any]] = None,
        topics: Optional[List[Any]] = None,
        subscription_id: Optional[str] = None
    ) -> str:
        """
        Subscribe to events.
        
        Args:
            callback: Function to call when an event is received.
            contract_address: Contract address to monitor.
            event_name: Event name to filter.
            from_block: Starting block for historical events.
            argument_filters: Filters for event arguments.
            topics: Topics to filter.
            subscription_id: Custom subscription ID (auto-generated if None).
            
        Returns:
            Subscription ID.
        """
        if subscription_id is None:
            subscription_id = f"sub_{int(time.time())}_{len(self._subscriptions)}"
        
        event_filter = EventFilter(
            contract_address=contract_address,
            event_name=event_name,
            from_block=from_block,
            argument_filters=argument_filters or {},
            topics=topics
        )
        
        subscription = EventSubscription(
            id=subscription_id,
            filter=event_filter,
            callback=callback
        )
        
        with self._subscription_lock:
            self._subscriptions[subscription_id] = subscription
        
        logger.info(f"Subscribed to events: {subscription_id}")
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: Subscription ID.
            
        Returns:
            True if unsubscribed, False otherwise.
        """
        with self._subscription_lock:
            if subscription_id in self._subscriptions:
                self._subscriptions[subscription_id].active = False
                del self._subscriptions[subscription_id]
                logger.info(f"Unsubscribed: {subscription_id}")
                return True
        return False
    
    def get_subscriptions(self) -> Dict[str, EventSubscription]:
        """Get all active subscriptions."""
        with self._subscription_lock:
            return {k: v for k, v in self._subscriptions.items() if v.active}
    
    # ============ Event Processing ============
    
    def add_event(self, event: Web3Event) -> None:
        """
        Add an event to the processing queue.
        
        Args:
            event: Web3Event object.
        """
        with self._event_lock:
            if len(self._event_queue) >= self.max_queue_size:
                logger.warning("Event queue full, dropping oldest event")
                self._event_queue.popleft()
            self._event_queue.append(event)
    
    def _process_events(self) -> None:
        """Process events from the queue."""
        while self._running:
            try:
                # Get batch of events
                events = []
                with self._event_lock:
                    while len(events) < 10 and self._event_queue:
                        events.append(self._event_queue.popleft())
                
                if not events:
                    time.sleep(0.1)
                    continue
                
                # Process each event
                for event in events:
                    self._process_single_event(event)
                    
            except Exception as e:
                logger.error(f"Event processing error: {e}")
                time.sleep(1)
    
    def _process_single_event(self, event: Web3Event) -> None:
        """
        Process a single event.
        
        Args:
            event: Web3Event object.
        """
        # Check if already processed
        event_id = f"{event.transaction_hash}_{event.log_index}"
        with self._processed_lock:
            if event_id in self._processed_events:
                event.status = EventStatus.SKIPPED
                return
            self._processed_events.add(event_id)
        
        event.status = EventStatus.PROCESSING
        
        try:
            # Find matching subscriptions
            subscriptions = self.get_subscriptions()
            for sub_id, subscription in subscriptions.items():
                if self._matches_filter(event, subscription.filter):
                    try:
                        subscription.callback(event)
                        subscription.event_count += 1
                        subscription.last_event = datetime.now()
                    except Exception as e:
                        logger.error(f"Event callback error for {sub_id}: {e}")
            
            event.status = EventStatus.COMPLETED
            event.processed_at = datetime.now()
            
        except Exception as e:
            event.status = EventStatus.FAILED
            event.error = str(e)
            event.retry_count += 1
            logger.error(f"Event processing failed: {e}")
            
            # Retry if configured
            if event.retry_count < 3:
                self.add_event(event)
    
    def _matches_filter(self, event: Web3Event, event_filter: EventFilter) -> bool:
        """
        Check if an event matches a filter.
        
        Args:
            event: Web3Event object.
            event_filter: EventFilter object.
            
        Returns:
            True if matches, False otherwise.
        """
        # Check contract address
        if event_filter.contract_address:
            if event.contract_address.lower() != event_filter.contract_address.lower():
                return False
        
        # Check event name
        if event_filter.event_name:
            if event.event_name != event_filter.event_name:
                return False
        
        # Check argument filters
        if event_filter.argument_filters:
            for key, value in event_filter.argument_filters.items():
                if key not in event.args or event.args[key] != value:
                    return False
        
        # Check topics (simplified)
        if event_filter.topics:
            # This is a simplified check - full topic matching is more complex
            pass
        
        return True
    
    # ============ Polling ============
    
    def _poll_events(self) -> None:
        """Poll for new events."""
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            logger.warning("No active Web3 provider, waiting...")
            time.sleep(5)
            return
        
        try:
            current_block = w3.eth.block_number
            
            if self._last_block == 0:
                self._last_block = current_block - 1
            
            if current_block > self._last_block:
                # Get events from block range
                for block_num in range(self._last_block + 1, current_block + 1):
                    self._fetch_events_for_block(block_num)
                
                self._last_block = current_block
                self._last_poll_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)
    
    def _fetch_events_for_block(self, block_number: int) -> None:
        """
        Fetch events for a specific block.
        
        Args:
            block_number: Block number.
        """
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            return
        
        try:
            # Get all logs in this block
            logs = w3.eth.get_logs({
                'fromBlock': block_number,
                'toBlock': block_number,
            })
            
            # Process logs
            for log in logs:
                event = self._parse_log(log)
                if event:
                    self.add_event(event)
                    
        except Exception as e:
            logger.error(f"Failed to fetch events for block {block_number}: {e}")
    
    def _parse_log(self, log: LogReceipt) -> Optional[Web3Event]:
        """
        Parse a log into a Web3Event.
        
        Args:
            log: LogReceipt from Web3.
            
        Returns:
            Web3Event or None.
        """
        try:
            # Extract basic info
            address = log['address']
            block_number = log['blockNumber']
            tx_hash = log['transactionHash'].hex()
            log_index = log['logIndex']
            
            # Decode topics
            # Try to determine event name from topics
            event_name = self._get_event_name_from_topics(log['topics'])
            
            # Decode arguments (simplified)
            args = {}
            if log.get('data'):
                # Try to decode data (simplified)
                data = log['data']
                if data and data != '0x':
                    # This is a simplification - actual decoding requires ABI
                    args['data'] = data
            
            # Add indexed arguments from topics
            for i, topic in enumerate(log['topics']):
                args[f'topic_{i}'] = topic.hex()
            
            event = Web3Event(
                event_name=event_name or 'unknown',
                contract_address=address,
                block_number=block_number,
                transaction_hash=tx_hash,
                log_index=log_index,
                args=args,
                raw_data=dict(log),
                timestamp=datetime.fromtimestamp(time.time())  # Approximate
            )
            
            return event
            
        except Exception as e:
            logger.error(f"Failed to parse log: {e}")
            return None
    
    def _get_event_name_from_topics(self, topics: List) -> str:
        """
        Try to determine event name from topics.
        
        Args:
            topics: List of topics.
            
        Returns:
            Event name or 'unknown'.
        """
        if not topics:
            return 'unknown'
        
        # First topic is usually the event signature hash
        signature_hash = topics[0].hex()
        
        # Check cache
        if self._cache is not None:
            cached = self._cache.get(signature_hash)
            if cached:
                return cached
        
        # Try to match common event signatures
        common_signatures = {
            '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef': 'Transfer',
            '0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925': 'Approval',
            '0x17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c31': 'ApprovalForAll',
            '0xfb0e6d5adc24a4407c996b4a8b393ac17d15580456ac39d29a148e3de27c9638': 'TransferSingle',
            '0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb': 'TransferBatch',
        }
        
        if signature_hash in common_signatures:
            event_name = common_signatures[signature_hash]
            if self._cache is not None:
                self._cache.set(signature_hash, event_name)
            return event_name
        
        return 'unknown'
    
    # ============ Control Methods ============
    
    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """
        Start the event manager.
        
        Args:
            loop: Optional asyncio event loop for async operations.
        """
        if self._running:
            return
        
        self._running = True
        self._loop = loop
        
        # Start poll thread
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        
        # Start processor thread
        self._processor_thread = threading.Thread(target=self._process_events, daemon=True)
        self._processor_thread.start()
        
        logger.info("Web3EventManager started")
    
    def stop(self) -> None:
        """Stop the event manager."""
        self._running = False
        
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
        if self._processor_thread:
            self._processor_thread.join(timeout=5)
        
        self._thread_pool.shutdown(wait=True)
        
        logger.info("Web3EventManager stopped")
    
    def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                self._poll_events()
            except Exception as e:
                logger.error(f"Polling loop error: {e}")
            
            # Wait for next poll
            for _ in range(int(self.poll_interval * 10)):
                if not self._running:
                    break
                time.sleep(0.1)
    
    def clear_processed_events(self) -> None:
        """Clear the processed events set."""
        with self._processed_lock:
            self._processed_events.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get event manager statistics.
        
        Returns:
            Statistics dictionary.
        """
        return {
            'running': self._running,
            'subscriptions': len(self._subscriptions),
            'queue_size': len(self._event_queue),
            'processed_events': len(self._processed_events),
            'last_block': self._last_block,
            'last_poll_time': self._last_poll_time.isoformat() if self._last_poll_time else None,
            'cache_size': len(self._cache._cache) if self._cache else 0,
        }
    
    # ============ Historical Events ============
    
    def get_historical_events(
        self,
        from_block: Union[int, str],
        to_block: Union[int, str] = 'latest',
        contract_address: Optional[str] = None,
        event_name: Optional[str] = None,
        argument_filters: Optional[Dict[str, Any]] = None,
        topics: Optional[List[Any]] = None
    ) -> List[Web3Event]:
        """
        Fetch historical events.
        
        Args:
            from_block: Starting block.
            to_block: Ending block.
            contract_address: Contract address.
            event_name: Event name.
            argument_filters: Argument filters.
            topics: Topics to filter.
            
        Returns:
            List of Web3Event objects.
        """
        w3 = self.web3_client._get_active_web3()
        if w3 is None:
            raise ConnectionError("No active Web3 provider")
        
        # Build filter
        filter_params = {
            'fromBlock': from_block,
            'toBlock': to_block,
        }
        if contract_address:
            filter_params['address'] = contract_address
        if topics:
            filter_params['topics'] = topics
        
        # Get logs
        logs = w3.eth.get_logs(filter_params)
        
        # Parse logs into events
        events = []
        for log in logs:
            event = self._parse_log(log)
            if event:
                # Apply additional filters
                if event_name and event.event_name != event_name:
                    continue
                if argument_filters:
                    match = True
                    for key, value in argument_filters.items():
                        if key not in event.args or event.args[key] != value:
                            match = False
                            break
                    if not match:
                        continue
                events.append(event)
        
        return events
    
    # ============ Async Support ============
    
    async def async_subscribe(
        self,
        callback: Callable[[Web3Event], Any],
        contract_address: Optional[str] = None,
        event_name: Optional[str] = None,
        from_block: Union[int, str] = 'latest',
        argument_filters: Optional[Dict[str, Any]] = None,
        topics: Optional[List[Any]] = None,
        subscription_id: Optional[str] = None
    ) -> str:
        """
        Async version of subscribe.
        
        Args:
            callback: Async callback function.
            contract_address: Contract address.
            event_name: Event name.
            from_block: Starting block.
            argument_filters: Argument filters.
            topics: Topics.
            subscription_id: Custom subscription ID.
            
        Returns:
            Subscription ID.
        """
        # Wrap async callback
        def sync_callback(event: Web3Event) -> None:
            if self._loop and asyncio.iscoroutinefunction(callback):
                asyncio.run_coroutine_threadsafe(callback(event), self._loop)
            else:
                # Fallback to sync
                callback(event)
        
        return self.subscribe(
            sync_callback,
            contract_address,
            event_name,
            from_block,
            argument_filters,
            topics,
            subscription_id
        )
    
    # ============ Utility Methods ============
    
    def get_event_signature(self, event_name: str, abi: List[Dict]) -> Optional[str]:
        """
        Get the event signature hash.
        
        Args:
            event_name: Event name.
            abi: Contract ABI.
            
        Returns:
            Event signature hash or None.
        """
        for item in abi:
            if item.get('type') == 'event' and item.get('name') == event_name:
                # Build signature
                inputs = item.get('inputs', [])
                types = [inp.get('type', '') for inp in inputs]
                signature = f"{event_name}({','.join(types)})"
                return Web3.keccak(text=signature).hex()
        return None


def create_event_manager(
    web3_client: Any,
    poll_interval: float = 1.0,
    enable_cache: bool = True,
    cache_ttl: int = 300
) -> Web3EventManager:
    """
    Create a Web3 event manager.
    
    Args:
        web3_client: Web3 client instance.
        poll_interval: Polling interval in seconds.
        enable_cache: Enable caching.
        cache_ttl: Cache TTL.
        
    Returns:
        Web3EventManager instance.
    """
    return Web3EventManager(
        web3_client=web3_client,
        poll_interval=poll_interval,
        enable_cache=enable_cache,
        cache_ttl=cache_ttl
    )


__all__ = [
    'EventStatus',
    'Web3Event',
    'EventFilter',
    'EventSubscription',
    'Web3EventManager',
    'create_event_manager'
]
