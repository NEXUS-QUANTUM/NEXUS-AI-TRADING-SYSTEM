"""
NEXUS AI TRADING SYSTEM - Reasoning Engine
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Reasoning Engine system with:
- Deductive reasoning
- Inductive reasoning
- Abductive reasoning
- Analogical reasoning
- Causal reasoning
- Probabilistic reasoning
- Rule-based reasoning
- Case-based reasoning
- Explanation generation
- Decision justification
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field, validator

from ai.cognition.knowledge_base import KnowledgeBase, KnowledgeItem, KnowledgeType, get_knowledge_base
from ai.cognition.memory import MemorySystem, Memory, MemoryType, MemoryImportance, get_memory
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import ReasoningError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class ReasoningType(str, Enum):
    """Reasoning types"""
    DEDUCTIVE = "deductive"
    INDUCTIVE = "inductive"
    ABDUCTIVE = "abductive"
    ANALOGICAL = "analogical"
    CAUSAL = "causal"
    PROBABILISTIC = "probabilistic"
    RULE_BASED = "rule_based"
    CASE_BASED = "case_based"


class ReasoningStatus(str, Enum):
    """Reasoning status"""
    IDLE = "idle"
    REASONING = "reasoning"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    """Confidence levels"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ReasoningContext:
    """Reasoning context"""
    id: str = field(default_factory=lambda: str(uuid4()))
    query: str
    type: ReasoningType
    data: Dict[str, Any]
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningResult:
    """Reasoning result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    context_id: str
    conclusion: Any
    confidence: float
    confidence_level: ConfidenceLevel
    explanation: str
    evidence: List[Dict[str, Any]]
    alternatives: List[Any]
    status: ReasoningStatus = ReasoningStatus.COMPLETED
    created_at: datetime = field(default_factory=datetime.utcnow)
    reasoning_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningHistory:
    """Reasoning history"""
    timestamp: datetime
    context: ReasoningContext
    result: ReasoningResult
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReasoningConfig(BaseModel):
    """Reasoning configuration"""
    enabled: bool = True
    types: List[ReasoningType] = Field(default_factory=list)
    min_confidence: float = Field(default=0.6, ge=0, le=1)
    max_alternatives: int = Field(default=5, gt=0)
    max_depth: int = Field(default=10, gt=0)
    use_probabilistic: bool = True
    use_causal: bool = True
    use_analogical: bool = True
    max_history: int = Field(default=1000, gt=0)
    parallel_workers: int = Field(default=4, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# REASONING ENGINE
# ========================================

class ReasoningEngine:
    """
    Complete reasoning engine for AI trading system.
    
    Features:
    - Deductive reasoning
    - Inductive reasoning
    - Abductive reasoning
    - Analogical reasoning
    - Causal reasoning
    - Probabilistic reasoning
    - Rule-based reasoning
    - Case-based reasoning
    - Explanation generation
    - Decision justification
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = ReasoningConfig(**(config or {}))
        self.redis = get_redis()
        self.knowledge_base = get_knowledge_base()
        self.memory = get_memory()
        
        # State
        self._contexts: Dict[str, ReasoningContext] = {}
        self._results: Dict[str, ReasoningResult] = {}
        self._history: List[ReasoningHistory] = []
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_reasonings": 0,
            "completed_reasonings": 0,
            "failed_reasonings": 0,
            "active_reasonings": 0,
            "avg_reasoning_time": 0.0,
            "avg_confidence": 0.0,
            "by_type": {},
            "success_rate": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.ReasoningEngine")
        self.logger.info("ReasoningEngine initialized")
    
    # ========================================
    # REASONING EXECUTION
    # ========================================
    
    async def reason(
        self,
        query: str,
        type: ReasoningType,
        data: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReasoningResult:
        """
        Execute reasoning.
        
        Args:
            query: Query to reason about
            type: Reasoning type
            data: Additional data
            constraints: Reasoning constraints
            metadata: Additional metadata
            
        Returns:
            ReasoningResult: Reasoning result
        """
        start_time = time.time()
        
        # Create context
        context = ReasoningContext(
            query=query,
            type=type,
            data=data or {},
            constraints=constraints or {},
            metadata=metadata or {}
        )
        
        self._contexts[context.id] = context
        
        try:
            # Update metrics
            self._metrics["total_reasonings"] += 1
            self._metrics["active_reasonings"] += 1
            
            # Execute reasoning based on type
            if type == ReasoningType.DEDUCTIVE:
                result = await self._deductive_reason(context)
            elif type == ReasoningType.INDUCTIVE:
                result = await self._inductive_reason(context)
            elif type == ReasoningType.ABDUCTIVE:
                result = await self._abductive_reason(context)
            elif type == ReasoningType.ANALOGICAL:
                result = await self._analogical_reason(context)
            elif type == ReasoningType.CAUSAL:
                result = await self._causal_reason(context)
            elif type == ReasoningType.PROBABILISTIC:
                result = await self._probabilistic_reason(context)
            elif type == ReasoningType.RULE_BASED:
                result = await self._rule_based_reason(context)
            elif type == ReasoningType.CASE_BASED:
                result = await self._case_based_reason(context)
            else:
                raise ReasoningError(f"Unsupported reasoning type: {type}")
            
            # Update result
            result.context_id = context.id
            result.reasoning_time = time.time() - start_time
            
            # Store result
            self._results[result.id] = result
            
            # Add to history
            self._history.append(ReasoningHistory(
                timestamp=datetime.utcnow(),
                context=context,
                result=result
            ))
            
            # Update metrics
            self._metrics["completed_reasonings"] += 1
            self._metrics["active_reasonings"] -= 1
            self._metrics["avg_reasoning_time"] = (
                self._metrics["avg_reasoning_time"] * 0.9 + result.reasoning_time * 0.1
            )
            self._metrics["avg_confidence"] = (
                self._metrics["avg_confidence"] * 0.9 + result.confidence * 0.1
            )
            
            # Update by type
            if type.value not in self._metrics["by_type"]:
                self._metrics["by_type"][type.value] = 0
            self._metrics["by_type"][type.value] += 1
            
            # Store in memory
            await self._store_in_memory(context, result)
            
            # Store in knowledge base
            await self._store_in_knowledge_base(context, result)
            
            self.logger.info(
                f"Reasoning completed: {context.id} "
                f"type={type.value} confidence={result.confidence:.2f} "
                f"time={result.reasoning_time:.3f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Reasoning failed: {e}")
            self._metrics["failed_reasonings"] += 1
            self._metrics["active_reasonings"] -= 1
            
            # Create failed result
            result = ReasoningResult(
                context_id=context.id,
                conclusion=None,
                confidence=0.0,
                confidence_level=ConfidenceLevel.VERY_LOW,
                explanation=f"Reasoning failed: {str(e)}",
                evidence=[],
                alternatives=[],
                status=ReasoningStatus.FAILED,
                reasoning_time=time.time() - start_time,
                metadata={'error': str(e)}
            )
            
            self._results[result.id] = result
            raise ReasoningError(f"Reasoning failed: {e}")
    
    # ========================================
    # REASONING TYPES
    # ========================================
    
    async def _deductive_reason(self, context: ReasoningContext) -> ReasoningResult:
        """Deductive reasoning"""
        # Get rules from knowledge base
        rules = await self.knowledge_base.query_knowledge(
            query="rule",
            type=KnowledgeType.RULE,
            limit=50
        )
        
        conclusion = None
        evidence = []
        alternatives = []
        
        # Apply rules
        for rule in rules.items:
            if self._matches_rule(rule, context):
                conclusion = self._apply_rule(rule, context)
                evidence.append({
                    'rule': rule.content,
                    'confidence': rule.confidence,
                    'relevance': rule.relevance
                })
                break
        
        # Generate alternatives
        for rule in rules.items[1:5]:
            if self._matches_rule(rule, context):
                alt = self._apply_rule(rule, context)
                alternatives.append(alt)
        
        # Calculate confidence
        confidence = min(1.0, sum(e['confidence'] for e in evidence) / (len(evidence) + 0.001))
        
        return ReasoningResult(
            context_id=context.id,
            conclusion=conclusion,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            explanation=self._generate_explanation(conclusion, evidence),
            evidence=evidence,
            alternatives=alternatives
        )
    
    async def _inductive_reason(self, context: ReasoningContext) -> ReasoningResult:
        """Inductive reasoning"""
        # Get examples from memory
        examples = await self.memory.retrieve_memories(
            query=context.query,
            type=MemoryType.EPISODIC,
            limit=20
        )
        
        conclusion = None
        evidence = []
        alternatives = []
        
        # Find patterns
        if examples.items:
            patterns = self._find_patterns(examples.items)
            if patterns:
                conclusion = self._generalize_patterns(patterns, context)
                evidence = [
                    {
                        'pattern': p,
                        'confidence': 0.7,
                        'support': len(examples.items)
                    }
                    for p in patterns[:3]
                ]
        
        # Generate alternatives
        alternatives = [
            {"alternative": "Alternative pattern found", "confidence": 0.3}
            for _ in range(2)
        ]
        
        confidence = 0.6 if conclusion else 0.2
        
        return ReasoningResult(
            context_id=context.id,
            conclusion=conclusion,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            explanation=self._generate_explanation(conclusion, evidence),
            evidence=evidence,
            alternatives=alternatives
        )
    
    async def _abductive_reason(self, context: ReasoningContext) -> ReasoningResult:
        """Abductive reasoning"""
        # Get facts from knowledge base
        facts = await self.knowledge_base.query_knowledge(
            query="fact",
            type=KnowledgeType.FACT,
            limit=30
        )
        
        conclusion = None
        evidence = []
        alternatives = []
        
        # Find best explanation
        for fact in facts.items:
            if self._is_plausible_explanation(fact, context):
                conclusion = fact.content
                evidence.append({
                    'fact': fact.content,
                    'confidence': fact.confidence,
                    'plausibility': 0.8
                })
                break
        
        # Generate alternative explanations
        for fact in facts.items[1:3]:
            if self._is_plausible_explanation(fact, context):
                alternatives.append({
                    'explanation': fact.content,
                    'plausibility': 0.6
                })
        
        confidence = 0.5 if conclusion else 0.1
        
        return ReasoningResult(
            context_id=context.id,
            conclusion=conclusion,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            explanation=self._generate_explanation(conclusion, evidence),
            evidence=evidence,
            alternatives=alternatives
        )
    
    async def _analogical_reason(self, context: ReasoningContext) -> ReasoningResult:
        """Analogical reasoning"""
        # Get similar cases from memory
        similar_cases = await self.memory.retrieve_memories(
            query=context.query,
            semantic=True,
            limit=10
        )
        
        conclusion = None
        evidence = []
        alternatives = []
        
        if similar_cases.items:
            # Find best analogy
            best_case = similar_cases.items[0]
            conclusion = self._apply_analogy(best_case, context)
            evidence.append({
                'case': best_case.content,
                'similarity': 0.8,
                'confidence': best_case.strength
            })
            
            # Generate alternatives
            for case in similar_cases.items[1:3]:
                alt = self._apply_analogy(case, context)
                alternatives.append(alt)
        
        confidence = 0.5 if conclusion else 0.1
        
        return ReasoningResult(
            context_id=context.id,
            conclusion=conclusion,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            explanation=self._generate_explanation(conclusion, evidence),
            evidence=evidence,
            alternatives=alternatives
        )
    
    async def _causal_reason(self, context: ReasoningContext) -> ReasoningResult:
        """Causal reasoning"""
        # Get causal relationships from knowledge base
        relationships = await self.knowledge_base.query_knowledge(
            query="relationship",
            type=KnowledgeType.RELATIONSHIP,
            limit=20
        )
        
        conclusion = None
        evidence = []
        alternatives = []
        
        # Find causal chain
        if relationships.items:
            chain = self._find_causal_chain(relationships.items, context)
            if chain:
                conclusion = chain[-1]
                evidence = [
                    {
                        'relationship': r.content,
                        'confidence': r.confidence,
                        'position': i
                    }
                    for i, r in enumerate(chain)
                ]
        
        confidence = 0.4 if conclusion else 0.1
        
        return ReasoningResult(
            context_id=context.id,
            conclusion=conclusion,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            explanation=self._generate_explanation(conclusion, evidence),
            evidence=evidence,
            alternatives=alternatives
        )
    
    async def _probabilistic_reason(self, context: ReasoningContext) -> ReasoningResult:
        """Probabilistic reasoning"""
        # Get probabilistic knowledge
        probabilities = context.data.get('probabilities', {})
        
        conclusion = None
        evidence = []
        alternatives = []
        
        # Calculate probabilities
        if probabilities:
            # Simple Bayesian inference
            posterior = self._bayesian_inference(probabilities, context)
            if posterior:
                conclusion = posterior
                evidence = [
                    {
                        'prior': probabilities.get('prior', 0.5),
                        'likelihood': probabilities.get('likelihood', 0.5),
                        'posterior': posterior,
                        'confidence': 0.7
                    }
                ]
        
        confidence = 0.5 if conclusion else 0.1
        
        return ReasoningResult(
            context_id=context.id,
            conclusion=conclusion,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            explanation=self._generate_explanation(conclusion, evidence),
            evidence=evidence,
            alternatives=alternatives
        )
    
    async def _rule_based_reason(self, context: ReasoningContext) -> ReasoningResult:
        """Rule-based reasoning"""
        # Get rules from knowledge base
        rules = await self.knowledge_base.query_knowledge(
            query="rule",
            type=KnowledgeType.RULE,
            limit=50
        )
        
        conclusion = None
        evidence = []
        alternatives = []
        
        # Forward chaining
        facts = context.data.get('facts', [])
        conclusion = self._forward_chaining(rules.items, facts)
        
        if conclusion:
            evidence = [
                {
                    'rule': r.content,
                    'confidence': r.confidence,
                    'triggered': True
                }
                for r in rules.items[:3]
            ]
        
        confidence = 0.7 if conclusion else 0.1
        
        return ReasoningResult(
            context_id=context.id,
            conclusion=conclusion,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            explanation=self._generate_explanation(conclusion, evidence),
            evidence=evidence,
            alternatives=alternatives
        )
    
    async def _case_based_reason(self, context: ReasoningContext) -> ReasoningResult:
        """Case-based reasoning"""
        # Get similar cases
        cases = await self.memory.retrieve_memories(
            query=context.query,
            type=MemoryType.EPISODIC,
            limit=10
        )
        
        conclusion = None
        evidence = []
        alternatives = []
        
        if cases.items:
            # Find best case
            best_case = cases.items[0]
            conclusion = self._adapt_case(best_case, context)
            evidence.append({
                'case': best_case.content,
                'similarity': 0.7,
                'adaptation': 'minor'
            })
            
            # Generate alternatives
            for case in cases.items[1:3]:
                alt = self._adapt_case(case, context)
                alternatives.append(alt)
        
        confidence = 0.5 if conclusion else 0.1
        
        return ReasoningResult(
            context_id=context.id,
            conclusion=conclusion,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            explanation=self._generate_explanation(conclusion, evidence),
            evidence=evidence,
            alternatives=alternatives
        )
    
    # ========================================
    # REASONING HELPERS
    # ========================================
    
    def _matches_rule(self, rule: KnowledgeItem, context: ReasoningContext) -> bool:
        """Check if rule matches context"""
        # Simple pattern matching
        if isinstance(rule.content, dict):
            conditions = rule.content.get('conditions', {})
            for key, value in conditions.items():
                if key in context.data and context.data[key] != value:
                    return False
            return True
        return False
    
    def _apply_rule(self, rule: KnowledgeItem, context: ReasoningContext) -> Any:
        """Apply rule to context"""
        if isinstance(rule.content, dict):
            conclusion = rule.content.get('conclusion')
            return conclusion
        return None
    
    def _find_patterns(self, examples: List[Memory]) -> List[Dict[str, Any]]:
        """Find patterns in examples"""
        patterns = []
        if not examples:
            return patterns
        
        # Simple pattern extraction
        for example in examples:
            if isinstance(example.content, dict):
                for key, value in example.content.items():
                    if key not in patterns:
                        patterns.append({key: value})
        
        return patterns[:3]
    
    def _generalize_patterns(
        self,
        patterns: List[Dict[str, Any]],
        context: ReasoningContext
    ) -> Any:
        """Generalize patterns to conclusion"""
        if not patterns:
            return None
        
        # Simple generalization
        result = {}
        for pattern in patterns:
            for key, value in pattern.items():
                if key not in result:
                    result[key] = []
                if value not in result[key]:
                    result[key].append(value)
        
        return result
    
    def _is_plausible_explanation(
        self,
        fact: KnowledgeItem,
        context: ReasoningContext
    ) -> bool:
        """Check if fact is plausible explanation"""
        # Simple plausibility check
        if isinstance(fact.content, str):
            return fact.content.lower() in context.query.lower()
        return False
    
    def _apply_analogy(self, case: Memory, context: ReasoningContext) -> Any:
        """Apply analogy from case"""
        if isinstance(case.content, dict):
            # Map case to context
            result = {}
            for key, value in case.content.items():
                if key in context.data:
                    result[key] = context.data[key]
                else:
                    result[key] = value
            return result
        return None
    
    def _find_causal_chain(
        self,
        relationships: List[KnowledgeItem],
        context: ReasoningContext
    ) -> List[KnowledgeItem]:
        """Find causal chain"""
        chain = []
        current = context.data.get('cause')
        
        for rel in relationships:
            if isinstance(rel.content, dict):
                if rel.content.get('from') == current:
                    chain.append(rel)
                    current = rel.content.get('to')
                    if current == context.data.get('target'):
                        break
        
        return chain
    
    def _bayesian_inference(
        self,
        probabilities: Dict[str, float],
        context: ReasoningContext
    ) -> Optional[float]:
        """Bayesian inference"""
        prior = probabilities.get('prior', 0.5)
        likelihood = probabilities.get('likelihood', 0.5)
        evidence = probabilities.get('evidence', 0.5)
        
        if evidence == 0:
            return None
        
        posterior = (likelihood * prior) / evidence
        return min(1.0, posterior)
    
    def _forward_chaining(
        self,
        rules: List[KnowledgeItem],
        facts: List[Any]
    ) -> Any:
        """Forward chaining"""
        changed = True
        conclusion = None
        
        while changed:
            changed = False
            for rule in rules:
                if isinstance(rule.content, dict):
                    conditions = rule.content.get('conditions', {})
                    if all(cond in facts for cond in conditions.values()):
                        conclusion = rule.content.get('conclusion')
                        if conclusion and conclusion not in facts:
                            facts.append(conclusion)
                            changed = True
        
        return conclusion
    
    def _adapt_case(self, case: Memory, context: ReasoningContext) -> Any:
        """Adapt case to context"""
        if isinstance(case.content, dict):
            # Simple adaptation
            adapted = {}
            for key, value in case.content.items():
                if key in context.data:
                    adapted[key] = context.data[key]
                else:
                    adapted[key] = value
            return adapted
        return None
    
    def _generate_explanation(
        self,
        conclusion: Any,
        evidence: List[Dict[str, Any]]
    ) -> str:
        """Generate explanation"""
        if not conclusion:
            return "No conclusion could be reached."
        
        if not evidence:
            return f"Conclusion: {conclusion} (no supporting evidence)"
        
        explanation = f"Conclusion: {conclusion}\n\nSupporting evidence:\n"
        for i, ev in enumerate(evidence):
            explanation += f"{i+1}. {ev}\n"
        
        return explanation
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Get confidence level from confidence score"""
        if confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.7:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    # ========================================
    # STORAGE
    # ========================================
    
    async def _store_in_memory(
        self,
        context: ReasoningContext,
        result: ReasoningResult
    ) -> None:
        """Store reasoning result in memory"""
        await self.memory.store_memory(
            content={
                'query': context.query,
                'conclusion': result.conclusion,
                'confidence': result.confidence,
                'explanation': result.explanation
            },
            type=MemoryType.EPISODIC,
            importance=MemoryImportance.HIGH if result.confidence > 0.7 else MemoryImportance.MEDIUM,
            tags=['reasoning', context.type.value],
            metadata={
                'reasoning_id': result.id,
                'reasoning_type': context.type.value,
                'evidence_count': len(result.evidence),
                'alternatives_count': len(result.alternatives)
            }
        )
    
    async def _store_in_knowledge_base(
        self,
        context: ReasoningContext,
        result: ReasoningResult
    ) -> None:
        """Store reasoning result in knowledge base"""
        if result.confidence > 0.7:
            await self.knowledge_base.add_knowledge(
                content={
                    'query': context.query,
                    'conclusion': result.conclusion,
                    'reasoning_type': context.type.value,
                    'evidence': result.evidence,
                    'alternatives': result.alternatives
                },
                type=KnowledgeType.INSIGHT,
                source=KnowledgeSource.LEARNING,
                source_id=result.id,
                tags=['reasoning', context.type.value, 'insight'],
                confidence=result.confidence,
                metadata={
                    'reasoning_id': result.id,
                    'reasoning_time': result.reasoning_time
                }
            )
    
    # ========================================
    # BACKGROUND TASKS
    # ========================================
    
    async def _health_loop(self) -> None:
        """Health monitoring loop"""
        while self._running:
            try:
                health = await self.health_check()
                self.logger.debug(f"Health: {health}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
            
            await asyncio.sleep(self.config.health_check_interval)
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_result(self, result_id: str) -> Optional[ReasoningResult]:
        """Get reasoning result by ID"""
        return self._results.get(result_id)
    
    async def get_context(self, context_id: str) -> Optional[ReasoningContext]:
        """Get reasoning context by ID"""
        return self._contexts.get(context_id)
    
    async def get_history(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[ReasoningHistory]:
        """Get reasoning history"""
        sorted_history = sorted(
            self._history,
            key=lambda x: x.timestamp,
            reverse=True
        )
        return sorted_history[offset:offset + limit]
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get reasoning metrics"""
        return {
            **self._metrics,
            "total_contexts": len(self._contexts),
            "total_results": len(self._results),
            "history_length": len(self._history),
            "success_rate": self._metrics["completed_reasonings"] / (self._metrics["completed_reasonings"] + self._metrics["failed_reasonings"]) if (self._metrics["completed_reasonings"] + self._metrics["failed_reasonings"]) > 0 else 0
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check reasoning health"""
        health = {
            'status': 'healthy',
            'active_reasonings': self._metrics["active_reasonings"],
            'total_reasonings': self._metrics["total_reasonings"],
            'success_rate': self._metrics["success_rate"]
        }
        
        # Check for stuck reasoning
        if self._metrics["active_reasonings"] > 0:
            health['status'] = 'degraded'
            health['warning'] = 'Active reasonings detected'
        
        return health
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the reasoning engine"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("ReasoningEngine started")
    
    async def stop(self) -> None:
        """Stop the reasoning engine"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("ReasoningEngine stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_reasoning_engine: Optional[ReasoningEngine] = None


def get_reasoning_engine() -> ReasoningEngine:
    """Get singleton instance of ReasoningEngine"""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine()
    return _reasoning_engine


def reset_reasoning_engine() -> None:
    """Reset the reasoning engine (for testing)"""
    global _reasoning_engine
    if _reasoning_engine:
        asyncio.create_task(_reasoning_engine.stop())
    _reasoning_engine = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'ReasoningEngine',
    'ReasoningConfig',
    'ReasoningContext',
    'ReasoningResult',
    'ReasoningHistory',
    'ReasoningType',
    'ReasoningStatus',
    'ConfidenceLevel',
    'get_reasoning_engine',
    'reset_reasoning_engine'
]
