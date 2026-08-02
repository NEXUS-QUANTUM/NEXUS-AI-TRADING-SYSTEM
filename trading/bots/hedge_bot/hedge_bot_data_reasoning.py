# trading/bots/hedge_bot/hedge_bot_data_reasoning.py

import asyncio
import logging
import time
import json
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque
import re
import itertools
from functools import reduce
import hashlib

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

try:
    from sympy import symbols, solve, simplify, diff, integrate, lambdify
    from sympy import Eq, And, Or, Not, Implies, Equivalent
    from sympy.logic.boolalg import to_cnf, to_dnf, simplify_logic
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False

try:
    from z3 import Solver, optimize, Int, Real, Bool, And as Z3And, Or as Z3Or, Not as Z3Not
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False

logger = logging.getLogger(__name__)


class ReasoningType(str, Enum):
    DEDUCTIVE = "deductive"
    INDUCTIVE = "inductive"
    ABDUCTIVE = "abductive"
    ANALOGICAL = "analogical"
    CAUSAL = "causal"
    COUNTERFACTUAL = "counterfactual"
    PROBABILISTIC = "probabilistic"
    FUZZY = "fuzzy"
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    LOGICAL = "logical"
    SYMBOLIC = "symbolic"
    STATISTICAL = "statistical"
    BAYESIAN = "bayesian"
    HEURISTIC = "heuristic"
    RULE_BASED = "rule_based"
    CASE_BASED = "case_based"


class TruthValue(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    POSSIBLE = "possible"
    IMPOSSIBLE = "impossible"
    LIKELY = "likely"
    UNLIKELY = "unlikely"
    PARTIALLY = "partially"
    INCONCLUSIVE = "inconclusive"


class InferenceRule(str, Enum):
    MODUS_PONENS = "modus_ponens"
    MODUS_TOLLENS = "modus_tollens"
    HYPOTHETICAL_SYLLOGISM = "hypothetical_syllogism"
    DISJUNCTIVE_SYLLOGISM = "disjunctive_syllogism"
    CONSTRUCTIVE_DILEMMA = "constructive_dilemma"
    DESTRUCTIVE_DILEMMA = "destructive_dilemma"
    ELIMINATION = "elimination"
    INTRODUCTION = "introduction"
    INSTANTIATION = "instantiation"
    GENERALIZATION = "generalization"
    CONTRAPOSITION = "contraposition"
    DE_MORGAN = "de_morgan"
    RESOLUTION = "resolution"
    UNIFICATION = "unification"
    ABDUCTION = "abduction"
    INDUCTION = "induction"
    ANALOGY = "analogy"


@dataclass
class Fact:
    id: str
    statement: str
    truth_value: TruthValue
    confidence: float = 1.0
    source: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)


@dataclass
class Rule:
    id: str
    name: str
    premises: List[str]
    conclusion: str
    rule_type: InferenceRule
    confidence: float = 1.0
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_defeasible: bool = False
    exceptions: List[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class Query:
    id: str
    question: str
    goal: str
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    preferred_truth_value: TruthValue = TruthValue.TRUE
    timeout: float = 30.0
    depth: int = 10
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningResult:
    query_id: str
    conclusion: str
    truth_value: TruthValue
    confidence: float
    explanation: str
    evidence: List[str]
    assumptions: List[str]
    proof_steps: List[Dict[str, Any]]
    alternatives: List[Dict[str, Any]]
    reasoning_type: ReasoningType
    inference_rules: List[InferenceRule]
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeBase:
    id: str
    name: str
    facts: Dict[str, Fact]
    rules: Dict[str, Rule]
    contexts: Dict[str, Any]
    created_at: float
    updated_at: float
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReasoningEngine:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._knowledge_bases: Dict[str, KnowledgeBase] = {}
        self._active_kb: Optional[str] = None
        self._facts: Dict[str, Fact] = {}
        self._rules: Dict[str, Rule] = {}
        self._contexts: Dict[str, Any] = {}
        self._queries: Dict[str, Query] = {}
        self._results: Dict[str, ReasoningResult] = {}
        self._reasoning_paths: Dict[str, List[Dict]] = defaultdict(list)
        self._truth_maintenance: Dict[str, Set[str]] = defaultdict(set)
        self._inference_engines: Dict[InferenceRule, Callable] = {}
        self._reasoners: Dict[ReasoningType, Callable] = {}
        self._heuristics: List[Callable] = []
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_inference_engines()
        self._initialize_reasoners()
        self._initialize_default_knowledge()

    def _initialize_inference_engines(self) -> None:
        self.register_inference_engine(InferenceRule.MODUS_PONENS, self._apply_modus_ponens)
        self.register_inference_engine(InferenceRule.MODUS_TOLLENS, self._apply_modus_tollens)
        self.register_inference_engine(InferenceRule.HYPOTHETICAL_SYLLOGISM, self._apply_hypothetical_syllogism)
        self.register_inference_engine(InferenceRule.DISJUNCTIVE_SYLLOGISM, self._apply_disjunctive_syllogism)
        self.register_inference_engine(InferenceRule.CONSTRUCTIVE_DILEMMA, self._apply_constructive_dilemma)
        self.register_inference_engine(InferenceRule.ELIMINATION, self._apply_elimination)
        self.register_inference_engine(InferenceRule.INTRODUCTION, self._apply_introduction)
        self.register_inference_engine(InferenceRule.INSTANTIATION, self._apply_instantiation)
        self.register_inference_engine(InferenceRule.GENERALIZATION, self._apply_generalization)
        self.register_inference_engine(InferenceRule.CONTRAPOSITION, self._apply_contraposition)
        self.register_inference_engine(InferenceRule.DE_MORGAN, self._apply_de_morgan)
        self.register_inference_engine(InferenceRule.RESOLUTION, self._apply_resolution)
        self.register_inference_engine(InferenceRule.UNIFICATION, self._apply_unification)

    def _initialize_reasoners(self) -> None:
        self.register_reasoner(ReasoningType.DEDUCTIVE, self._reason_deductive)
        self.register_reasoner(ReasoningType.INDUCTIVE, self._reason_inductive)
        self.register_reasoner(ReasoningType.ABDUCTIVE, self._reason_abductive)
        self.register_reasoner(ReasoningType.ANALOGICAL, self._reason_analogical)
        self.register_reasoner(ReasoningType.CAUSAL, self._reason_causal)
        self.register_reasoner(ReasoningType.COUNTERFACTUAL, self._reason_counterfactual)
        self.register_reasoner(ReasoningType.PROBABILISTIC, self._reason_probabilistic)
        self.register_reasoner(ReasoningType.FUZZY, self._reason_fuzzy)
        self.register_reasoner(ReasoningType.TEMPORAL, self._reason_temporal)
        self.register_reasoner(ReasoningType.LOGICAL, self._reason_logical)
        self.register_reasoner(ReasoningType.SYMBOLIC, self._reason_symbolic)
        self.register_reasoner(ReasoningType.STATISTICAL, self._reason_statistical)
        self.register_reasoner(ReasoningType.BAYESIAN, self._reason_bayesian)
        self.register_reasoner(ReasoningType.HEURISTIC, self._reason_heuristic)
        self.register_reasoner(ReasoningType.RULE_BASED, self._reason_rule_based)
        self.register_reasoner(ReasoningType.CASE_BASED, self._reason_case_based)

    def _initialize_default_knowledge(self) -> None:
        default_facts = [
            Fact(
                id="fact_1",
                statement="markets_are_efficient",
                truth_value=TruthValue.POSSIBLE,
                confidence=0.6
            ),
            Fact(
                id="fact_2",
                statement="prices_trend",
                truth_value=TruthValue.LIKELY,
                confidence=0.7
            ),
            Fact(
                id="fact_3",
                statement="volatility_increases_during_crisis",
                truth_value=TruthValue.TRUE,
                confidence=0.85
            ),
            Fact(
                id="fact_4",
                statement="liquidity_affects_price",
                truth_value=TruthValue.TRUE,
                confidence=0.9
            )
        ]
        
        default_rules = [
            Rule(
                id="rule_1",
                name="trend_following",
                premises=["prices_trend", "momentum_exists"],
                conclusion="trend_will_continue",
                rule_type=InferenceRule.MODUS_PONENS,
                confidence=0.75
            ),
            Rule(
                id="rule_2",
                name="mean_reversion",
                premises=["price_far_from_mean", "markets_are_efficient"],
                conclusion="price_will_revert",
                rule_type=InferenceRule.MODUS_PONENS,
                confidence=0.6
            ),
            Rule(
                id="rule_3",
                name="volatility_impact",
                premises=["volatility_increases_during_crisis", "crisis_occurs"],
                conclusion="risk_high",
                rule_type=InferenceRule.MODUS_PONENS,
                confidence=0.9
            )
        ]
        
        kb = KnowledgeBase(
            id="default",
            name="Default Knowledge Base",
            facts={f.id: f for f in default_facts},
            rules={r.id: r for r in default_rules},
            contexts={},
            created_at=time.time(),
            updated_at=time.time()
        )
        
        self._knowledge_bases[kb.id] = kb
        self._active_kb = kb.id
        self._facts.update(kb.facts)
        self._rules.update(kb.rules)

    def register_inference_engine(self, rule_type: InferenceRule, engine: Callable) -> None:
        self._inference_engines[rule_type] = engine

    def register_reasoner(self, reasoning_type: ReasoningType, reasoner: Callable) -> None:
        self._reasoners[reasoning_type] = reasoner

    def register_heuristic(self, heuristic: Callable) -> None:
        self._heuristics.append(heuristic)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_fact(self, fact: Fact) -> None:
        async with self._lock:
            self._facts[fact.id] = fact
            
            if self._active_kb in self._knowledge_bases:
                self._knowledge_bases[self._active_kb].facts[fact.id] = fact
                self._knowledge_bases[self._active_kb].updated_at = time.time()
            
            await self._notify_observers("fact_added", fact)

    async def add_rule(self, rule: Rule) -> None:
        async with self._lock:
            self._rules[rule.id] = rule
            
            if self._active_kb in self._knowledge_bases:
                self._knowledge_bases[self._active_kb].rules[rule.id] = rule
                self._knowledge_bases[self._active_kb].updated_at = time.time()
            
            await self._notify_observers("rule_added", rule)

    async def remove_fact(self, fact_id: str) -> bool:
        async with self._lock:
            if fact_id in self._facts:
                del self._facts[fact_id]
                
                if self._active_kb in self._knowledge_bases:
                    self._knowledge_bases[self._active_kb].facts.pop(fact_id, None)
                    self._knowledge_bases[self._active_kb].updated_at = time.time()
                
                await self._notify_observers("fact_removed", fact_id)
                return True
            return False

    async def remove_rule(self, rule_id: str) -> bool:
        async with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                
                if self._active_kb in self._knowledge_bases:
                    self._knowledge_bases[self._active_kb].rules.pop(rule_id, None)
                    self._knowledge_bases[self._active_kb].updated_at = time.time()
                
                await self._notify_observers("rule_removed", rule_id)
                return True
            return False

    async def reason(
        self,
        query: Query,
        reasoning_type: Optional[ReasoningType] = None,
        depth: Optional[int] = None,
        timeout: Optional[float] = None
    ) -> ReasoningResult:
        async with self._lock:
            start_time = time.time()
            reasoning_type = reasoning_type or ReasoningType.DEDUCTIVE
            depth = depth or query.depth
            timeout = timeout or query.timeout
            
            self._queries[query.id] = query
            query_id = query.id
            
            proof_steps = []
            evidence = []
            assumptions = []
            alternatives = []
            inference_rules = []
            
            try:
                if reasoning_type not in self._reasoners:
                    raise ValueError(f"Reasoner not found: {reasoning_type}")
                
                reasoner = self._reasoners[reasoning_type]
                result = await asyncio.wait_for(
                    reasoner(query, depth),
                    timeout=timeout
                )
                
                if isinstance(result, dict):
                    conclusion = result.get("conclusion", query.goal)
                    truth_value = result.get("truth_value", TruthValue.UNKNOWN)
                    confidence = result.get("confidence", 0.0)
                    explanation = result.get("explanation", "")
                    evidence = result.get("evidence", [])
                    assumptions = result.get("assumptions", [])
                    proof_steps = result.get("proof_steps", [])
                    alternatives = result.get("alternatives", [])
                    inference_rules = result.get("inference_rules", [])
                else:
                    conclusion = str(result)
                    truth_value = TruthValue.POSSIBLE
                    confidence = 0.5
                    explanation = f"Reasoned using {reasoning_type.value}"
                
                reasoning_result = ReasoningResult(
                    query_id=query_id,
                    conclusion=conclusion,
                    truth_value=truth_value,
                    confidence=confidence,
                    explanation=explanation,
                    evidence=evidence,
                    assumptions=assumptions,
                    proof_steps=proof_steps,
                    alternatives=alternatives,
                    reasoning_type=reasoning_type,
                    inference_rules=inference_rules,
                    execution_time=time.time() - start_time,
                    metadata=query.metadata
                )
                
                self._results[query_id] = reasoning_result
                self._reasoning_paths[query_id] = proof_steps
                
                await self._notify_observers("reasoning_completed", reasoning_result)
                
                return reasoning_result
                
            except asyncio.TimeoutError:
                return ReasoningResult(
                    query_id=query_id,
                    conclusion=query.goal,
                    truth_value=TruthValue.INCONCLUSIVE,
                    confidence=0.0,
                    explanation="Reasoning timed out",
                    evidence=[],
                    assumptions=[],
                    proof_steps=[],
                    alternatives=[],
                    reasoning_type=reasoning_type,
                    inference_rules=[],
                    execution_time=time.time() - start_time,
                    metadata={"timeout": True}
                )
            except Exception as e:
                logger.error(f"Reasoning error: {e}")
                return ReasoningResult(
                    query_id=query_id,
                    conclusion=query.goal,
                    truth_value=TruthValue.UNKNOWN,
                    confidence=0.0,
                    explanation=f"Error: {str(e)}",
                    evidence=[],
                    assumptions=[],
                    proof_steps=[],
                    alternatives=[],
                    reasoning_type=reasoning_type,
                    inference_rules=[],
                    execution_time=time.time() - start_time,
                    metadata={"error": str(e)}
                )

    async def _reason_deductive(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.UNKNOWN,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        applicable_rules = []
        for rule in self._rules.values():
            if all(premise in self._facts for premise in rule.premises):
                applicable_rules.append(rule)
        
        for rule in applicable_rules:
            if rule.conclusion == query.goal or "goal" in rule.conclusion:
                proof_step = {
                    "step": len(results["proof_steps"]) + 1,
                    "rule": rule.name,
                    "premises": rule.premises,
                    "conclusion": rule.conclusion,
                    "confidence": rule.confidence
                }
                results["proof_steps"].append(proof_step)
                results["inference_rules"].append(rule.rule_type)
                results["evidence"].extend(rule.premises)
                results["confidence"] = max(results["confidence"], rule.confidence)
        
        if results["proof_steps"]:
            results["truth_value"] = TruthValue.TRUE
            results["explanation"] = f"Deduced '{query.goal}' using {len(results['proof_steps'])} inference steps"
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = f"No deduction found for '{query.goal}'"
        
        return results

    async def _reason_inductive(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.LIKELY,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        patterns = []
        for fact in self._facts.values():
            if query.goal in fact.statement:
                patterns.append(fact)
        
        if patterns:
            confidence = sum(p.confidence for p in patterns) / len(patterns)
            results["confidence"] = min(1.0, confidence)
            results["evidence"] = [p.id for p in patterns]
            results["explanation"] = f"Induced from {len(patterns)} observations"
            results["truth_value"] = TruthValue.LIKELY if confidence > 0.6 else TruthValue.POSSIBLE
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "No inductive evidence found"
        
        return results

    async def _reason_abductive(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.POSSIBLE,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        best_explanations = []
        for rule in self._rules.values():
            if query.goal in rule.premises:
                explanation = {
                    "conclusion": rule.conclusion,
                    "confidence": rule.confidence,
                    "premises": rule.premises
                }
                best_explanations.append(explanation)
        
        if best_explanations:
            best = max(best_explanations, key=lambda x: x["confidence"])
            results["conclusion"] = best["conclusion"]
            results["confidence"] = best["confidence"]
            results["evidence"] = best["premises"]
            results["explanation"] = f"Best abductive explanation: {best['conclusion']}"
            results["truth_value"] = TruthValue.POSSIBLE
            results["assumptions"] = best["premises"]
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "No abductive explanation found"
        
        return results

    async def _reason_analogical(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.POSSIBLE,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        target_facts = [f for f in self._facts.values() if query.goal in f.statement]
        analogies = []
        
        for fact in self._facts.values():
            if fact.id not in [f.id for f in target_facts]:
                similarity = self._compute_similarity(fact.statement, query.goal)
                if similarity > 0.3:
                    analogies.append((fact, similarity))
        
        if analogies:
            analogies.sort(key=lambda x: x[1], reverse=True)
            best_analogy = analogies[0]
            results["confidence"] = best_analogy[1]
            results["evidence"] = [best_analogy[0].id]
            results["explanation"] = f"Analogical reasoning from: {best_analogy[0].statement}"
            results["truth_value"] = TruthValue.POSSIBLE
            results["assumptions"] = [f"Similar to: {best_analogy[0].statement}"]
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "No analogies found"
        
        return results

    async def _reason_causal(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.POSSIBLE,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        causal_chains = []
        for rule in self._rules.values():
            if query.goal in rule.conclusion:
                chain = [rule]
                current = rule
                while current and len(chain) < depth:
                    for premise in current.premises:
                        for r in self._rules.values():
                            if premise in r.conclusion:
                                chain.append(r)
                                current = r
                                break
                if chain:
                    causal_chains.append(chain)
        
        if causal_chains:
            best_chain = max(causal_chains, key=lambda x: sum(r.confidence for r in x) / len(x))
            results["confidence"] = sum(r.confidence for r in best_chain) / len(best_chain)
            results["evidence"] = [r.id for r in best_chain]
            results["explanation"] = f"Causal chain of {len(best_chain)} steps"
            results["truth_value"] = TruthValue.LIKELY if results["confidence"] > 0.6 else TruthValue.POSSIBLE
            results["proof_steps"] = [
                {"step": i, "rule": r.name, "conclusion": r.conclusion}
                for i, r in enumerate(best_chain)
            ]
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "No causal chain found"
        
        return results

    async def _reason_counterfactual(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.POSSIBLE,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        counterfactuals = []
        for rule in self._rules.values():
            if query.goal in rule.conclusion and rule.is_defeasible:
                counterfactuals.append(rule)
        
        if counterfactuals:
            best = max(counterfactuals, key=lambda x: x.confidence)
            results["confidence"] = best.confidence * 0.5
            results["evidence"] = [best.id]
            results["explanation"] = f"Counterfactual: If {', '.join(best.premises)}, then {best.conclusion}"
            results["truth_value"] = TruthValue.POSSIBLE
            results["assumptions"] = best.premises
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "No counterfactual reasoning possible"
        
        return results

    async def _reason_probabilistic(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.LIKELY,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        relevant_facts = [f for f in self._facts.values() if query.goal in f.statement]
        
        if relevant_facts:
            probs = [f.confidence for f in relevant_facts]
            avg_prob = sum(probs) / len(probs) if probs else 0
            results["confidence"] = avg_prob
            results["evidence"] = [f.id for f in relevant_facts]
            results["explanation"] = f"Probabilistic reasoning based on {len(relevant_facts)} facts"
            results["truth_value"] = TruthValue.LIKELY if avg_prob > 0.6 else TruthValue.POSSIBLE
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "No probabilistic evidence found"
        
        return results

    async def _reason_fuzzy(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.PARTIALLY,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        membership = 0.0
        for rule in self._rules.values():
            if query.goal in rule.conclusion:
                premise_truth = 0.0
                for premise in rule.premises:
                    if premise in self._facts:
                        premise_truth = max(premise_truth, self._facts[premise].confidence)
                membership = max(membership, min(premise_truth, rule.confidence))
        
        results["confidence"] = membership
        results["truth_value"] = TruthValue.PARTIALLY if membership > 0 else TruthValue.UNKNOWN
        results["explanation"] = f"Fuzzy reasoning yielded membership: {membership:.2f}"
        
        return results

    async def _reason_temporal(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.POSSIBLE,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        temporal_facts = []
        for fact in self._facts.values():
            if fact.timestamp:
                temporal_facts.append(fact)
        
        if temporal_facts:
            ordered = sorted(temporal_facts, key=lambda x: x.timestamp)
            if len(ordered) >= 2:
                time_delta = ordered[-1].timestamp - ordered[0].timestamp
                if query.metadata.get("temporal_threshold"):
                    threshold = query.metadata["temporal_threshold"]
                    if time_delta < threshold:
                        results["confidence"] = 0.8
                        results["truth_value"] = TruthValue.LIKELY
                        results["explanation"] = "Temporal sequence supports goal"
                    else:
                        results["confidence"] = 0.3
                        results["truth_value"] = TruthValue.POSSIBLE
                        results["explanation"] = "Temporal sequence weakly supports goal"
                else:
                    results["confidence"] = 0.5
                    results["truth_value"] = TruthValue.POSSIBLE
                    results["explanation"] = f"Temporal analysis: {time_delta:.2f}s between events"
                
                results["evidence"] = [f.id for f in ordered[-2:]]
            else:
                results["truth_value"] = TruthValue.UNKNOWN
                results["explanation"] = "Insufficient temporal data"
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "No temporal facts available"
        
        return results

    async def _reason_logical(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.UNKNOWN,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        if SYMPY_AVAILABLE:
            try:
                x = symbols('x')
                constraints = query.constraints
                if constraints:
                    expressions = [eval(c) for c in constraints]
                    solutions = solve(expressions, x)
                    if solutions:
                        results["conclusion"] = str(solutions)
                        results["truth_value"] = TruthValue.TRUE
                        results["confidence"] = 1.0
                        results["explanation"] = f"Logical solution: {solutions}"
                    else:
                        results["truth_value"] = TruthValue.FALSE
                        results["explanation"] = "No logical solution found"
            except Exception as e:
                results["explanation"] = f"Logical reasoning error: {e}"
                results["truth_value"] = TruthValue.UNKNOWN
        
        return results

    async def _reason_symbolic(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.UNKNOWN,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        if Z3_AVAILABLE:
            try:
                solver = Solver()
                symbols_dict = {}
                
                for fact in self._facts.values():
                    if "symbol" in fact.metadata:
                        sym = fact.metadata["symbol"]
                        if sym not in symbols_dict:
                            symbols_dict[sym] = Bool(sym)
                        if fact.truth_value == TruthValue.TRUE:
                            solver.add(symbols_dict[sym])
                        elif fact.truth_value == TruthValue.FALSE:
                            solver.add(Z3Not(symbols_dict[sym]))
                
                result = solver.check()
                if result == sat:
                    model = solver.model()
                    results["conclusion"] = str(model)
                    results["truth_value"] = TruthValue.TRUE
                    results["confidence"] = 0.9
                    results["explanation"] = "Symbolic reasoning satisfied"
                elif result == unsat:
                    results["truth_value"] = TruthValue.FALSE
                    results["explanation"] = "Symbolic constraints unsatisfiable"
                else:
                    results["truth_value"] = TruthValue.UNKNOWN
                    results["explanation"] = "Symbolic reasoning inconclusive"
            except Exception as e:
                results["explanation"] = f"Symbolic reasoning error: {e}"
        
        return results

    async def _reason_statistical(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.LIKELY,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        values = []
        for fact in self._facts.values():
            if "statistical" in fact.metadata:
                values.append(fact.confidence)
        
        if values:
            mean = sum(values) / len(values)
            std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
            results["confidence"] = 0.5 + (mean * 0.5)
            results["truth_value"] = TruthValue.LIKELY if mean > 0.5 else TruthValue.UNLIKELY
            results["explanation"] = f"Statistical analysis: mean={mean:.2f}, std={std:.2f}"
            results["evidence"] = ["statistical_analysis"]
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "Insufficient statistical data"
        
        return results

    async def _reason_bayesian(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.LIKELY,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        prior = 0.5
        likelihood = 0.5
        
        for fact in self._facts.values():
            if query.goal in fact.statement:
                prior = fact.confidence
                likelihood = prior * 0.8 + 0.2
        
        posterior = (likelihood * prior) / ((likelihood * prior) + (1 - likelihood) * (1 - prior))
        results["confidence"] = posterior
        results["truth_value"] = TruthValue.LIKELY if posterior > 0.5 else TruthValue.UNLIKELY
        results["explanation"] = f"Bayesian posterior: {posterior:.2f}"
        
        return results

    async def _reason_heuristic(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.POSSIBLE,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        heuristic_score = 0.0
        for heuristic in self._heuristics:
            try:
                score = await heuristic(query)
                heuristic_score = max(heuristic_score, score)
            except Exception as e:
                logger.error(f"Heuristic error: {e}")
        
        results["confidence"] = min(1.0, heuristic_score)
        results["truth_value"] = TruthValue.POSSIBLE
        results["explanation"] = f"Heuristic evaluation: {heuristic_score:.2f}"
        
        return results

    async def _reason_rule_based(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.UNKNOWN,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        applicable_rules = []
        for rule in self._rules.values():
            if all(premise in self._facts for premise in rule.premises):
                applicable_rules.append(rule)
        
        forward_chaining = []
        applied = set()
        
        while len(forward_chaining) < depth:
            new_rules = []
            for rule in applicable_rules:
                if rule.id not in applied:
                    if rule.rule_type in self._inference_engines:
                        engine = self._inference_engines[rule.rule_type]
                        result = await engine(rule, self._facts)
                        if result:
                            new_rules.append(rule)
                            applied.add(rule.id)
            
            if not new_rules:
                break
            
            forward_chaining.extend(new_rules)
        
        if forward_chaining:
            last = forward_chaining[-1]
            results["conclusion"] = last.conclusion
            results["confidence"] = last.confidence
            results["evidence"] = last.premises
            results["truth_value"] = TruthValue.TRUE
            results["explanation"] = f"Rule-based reasoning: {len(forward_chaining)} rules applied"
            results["inference_rules"] = [r.rule_type for r in forward_chaining]
            results["proof_steps"] = [
                {"step": i, "rule": r.name, "conclusion": r.conclusion}
                for i, r in enumerate(forward_chaining)
            ]
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "No applicable rules found"
        
        return results

    async def _reason_case_based(self, query: Query, depth: int) -> Dict[str, Any]:
        results = {
            "conclusion": query.goal,
            "truth_value": TruthValue.POSSIBLE,
            "confidence": 0.0,
            "explanation": "",
            "evidence": [],
            "assumptions": [],
            "proof_steps": [],
            "alternatives": [],
            "inference_rules": []
        }
        
        cases = []
        for fact in self._facts.values():
            similarity = self._compute_similarity(fact.statement, query.goal)
            if similarity > 0.3:
                cases.append((fact, similarity))
        
        if cases:
            cases.sort(key=lambda x: x[1], reverse=True)
            best_case = cases[0]
            results["confidence"] = best_case[1] * 0.8
            results["evidence"] = [best_case[0].id]
            results["explanation"] = f"Case-based reasoning using: {best_case[0].statement}"
            results["truth_value"] = TruthValue.POSSIBLE
            results["assumptions"] = [f"Case: {best_case[0].statement}"]
        else:
            results["truth_value"] = TruthValue.UNKNOWN
            results["explanation"] = "No similar cases found"
        
        return results

    async def _apply_modus_ponens(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return all(premise in facts for premise in rule.premises)

    async def _apply_modus_tollens(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        if rule.conclusion in facts and facts[rule.conclusion].truth_value == TruthValue.FALSE:
            return True
        return False

    async def _apply_hypothetical_syllogism(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return all(premise in facts for premise in rule.premises)

    async def _apply_disjunctive_syllogism(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        for premise in rule.premises:
            if premise in facts and facts[premise].truth_value == TruthValue.FALSE:
                return True
        return False

    async def _apply_constructive_dilemma(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return len(rule.premises) >= 4

    async def _apply_elimination(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return len(rule.premises) >= 2

    async def _apply_introduction(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return all(premise in facts for premise in rule.premises)

    async def _apply_instantiation(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return len(rule.premises) == 1

    async def _apply_generalization(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return len(rule.premises) >= 2

    async def _apply_contraposition(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return len(rule.premises) == 1

    async def _apply_de_morgan(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return len(rule.premises) >= 2

    async def _apply_resolution(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return len(rule.premises) >= 2

    async def _apply_unification(self, rule: Rule, facts: Dict[str, Fact]) -> bool:
        return len(rule.premises) == 2

    def _compute_similarity(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    async def explain(self, query_id: str) -> Optional[str]:
        if query_id not in self._results:
            return None
        
        result = self._results[query_id]
        explanation = f"Explanation for query: {result.query_id}\n"
        explanation += f"Conclusion: {result.conclusion}\n"
        explanation += f"Truth Value: {result.truth_value.value}\n"
        explanation += f"Confidence: {result.confidence:.2f}\n"
        explanation += f"Reasoning Type: {result.reasoning_type.value}\n"
        explanation += f"Explanation: {result.explanation}\n"
        
        if result.proof_steps:
            explanation += "Proof Steps:\n"
            for step in result.proof_steps:
                explanation += f"  {step.get('step', '')}: {step.get('rule', '')} -> {step.get('conclusion', '')}\n"
        
        if result.evidence:
            explanation += f"Evidence: {', '.join(result.evidence)}\n"
        
        if result.assumptions:
            explanation += f"Assumptions: {', '.join(result.assumptions)}\n"
        
        if result.alternatives:
            explanation += "Alternatives:\n"
            for alt in result.alternatives:
                explanation += f"  {alt}\n"
        
        return explanation

    async def create_knowledge_base(self, name: str, metadata: Dict[str, Any] = None) -> str:
        kb_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
        
        kb = KnowledgeBase(
            id=kb_id,
            name=name,
            facts=self._facts.copy(),
            rules=self._rules.copy(),
            contexts=self._contexts.copy(),
            created_at=time.time(),
            updated_at=time.time(),
            metadata=metadata or {}
        )
        
        self._knowledge_bases[kb_id] = kb
        return kb_id

    async def switch_knowledge_base(self, kb_id: str) -> bool:
        if kb_id not in self._knowledge_bases:
            return False
        
        kb = self._knowledge_bases[kb_id]
        self._active_kb = kb_id
        self._facts = kb.facts.copy()
        self._rules = kb.rules.copy()
        self._contexts = kb.contexts.copy()
        return True

    async def export_knowledge_base(self, kb_id: str) -> Optional[Dict[str, Any]]:
        if kb_id not in self._knowledge_bases:
            return None
        
        kb = self._knowledge_bases[kb_id]
        return {
            "id": kb.id,
            "name": kb.name,
            "facts": {fid: vars(fact) for fid, fact in kb.facts.items()},
            "rules": {rid: vars(rule) for rid, rule in kb.rules.items()},
            "contexts": kb.contexts,
            "created_at": kb.created_at,
            "updated_at": kb.updated_at,
            "version": kb.version,
            "metadata": kb.metadata
        }

    async def import_knowledge_base(self, data: Dict[str, Any]) -> str:
        facts = {fid: Fact(**fact_data) for fid, fact_data in data.get("facts", {}).items()}
        rules = {rid: Rule(**rule_data) for rid, rule_data in data.get("rules", {}).items()}
        
        kb = KnowledgeBase(
            id=data.get("id", hashlib.md5(f"{data.get('name')}_{time.time()}".encode()).hexdigest()),
            name=data.get("name", "Imported Knowledge Base"),
            facts=facts,
            rules=rules,
            contexts=data.get("contexts", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=time.time(),
            version=data.get("version", "1.0.0"),
            metadata=data.get("metadata", {})
        )
        
        self._knowledge_bases[kb.id] = kb
        return kb.id

    def get_stats(self) -> Dict[str, Any]:
        return {
            "knowledge_bases": len(self._knowledge_bases),
            "facts": len(self._facts),
            "rules": len(self._rules),
            "queries": len(self._queries),
            "results": len(self._results),
            "reasoning_paths": len(self._reasoning_paths),
            "inference_engines": len(self._inference_engines),
            "reasoners": len(self._reasoners),
            "heuristics": len(self._heuristics),
            "observers": len(self._observers),
            "active_kb": self._active_kb,
            "running": self._running
        }

    async def clear(self) -> None:
        async with self._lock:
            self._facts.clear()
            self._rules.clear()
            self._queries.clear()
            self._results.clear()
            self._reasoning_paths.clear()
            self._truth_maintenance.clear()
            self._initialize_default_knowledge()


__all__ = [
    "ReasoningType",
    "TruthValue",
    "InferenceRule",
    "Fact",
    "Rule",
    "Query",
    "ReasoningResult",
    "KnowledgeBase",
    "ReasoningEngine"
]
