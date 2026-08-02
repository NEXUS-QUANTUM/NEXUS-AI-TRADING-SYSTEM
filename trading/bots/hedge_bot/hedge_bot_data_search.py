# trading/bots/hedge_bot/hedge_bot_data_search.py

import asyncio
import logging
import time
import json
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import numpy as np
import pandas as pd

try:
    from elasticsearch import Elasticsearch, AsyncElasticsearch
    from elasticsearch.helpers import bulk, async_bulk
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False

try:
    import whoosh
    from whoosh.index import create_in, open_dir
    from whoosh.fields import Schema, TEXT, KEYWORD, ID, DATETIME, NUMERIC, STORED
    from whoosh.qparser import QueryParser, MultifieldParser
    from whoosh.query import Term, And, Or, Not, FuzzyTerm, Prefix, Wildcard
    from whoosh.analysis import StemmingAnalyzer, StandardAnalyzer
    WHOOSH_AVAILABLE = True
except ImportError:
    WHOOSH_AVAILABLE = False

logger = logging.getLogger(__name__)


class SearchEngine(str, Enum):
    ELASTICSEARCH = "elasticsearch"
    WHOOSH = "whoosh"
    MEILI = "meilisearch"
    TYPESENSE = "typesense"
    ALGOLIA = "algolia"
    SOLR = "solr"
    IN_MEMORY = "in_memory"


class SearchType(str, Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    PREFIX = "prefix"
    WILDCARD = "wildcard"
    PHRASE = "phrase"
    BOOLEAN = "boolean"
    RANGE = "range"
    GEO = "geo"
    VECTOR = "vector"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class SearchSort(str, Enum):
    RELEVANCE = "relevance"
    DATE = "date"
    SCORE = "score"
    FIELD = "field"


@dataclass
class SearchIndex:
    id: str
    name: str
    engine: SearchEngine
    fields: List[str]
    analyzers: Dict[str, Any]
    settings: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchQuery:
    id: str
    text: str
    search_type: SearchType
    fields: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    sort: Optional[SearchSort] = None
    limit: int = 10
    offset: int = 0
    highlight: bool = False
    fuzzy_degree: int = 2
    prefix_length: int = 3
    analyzer: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    id: str
    query_id: str
    documents: List[Dict[str, Any]]
    total: int
    score: float
    execution_time: float
    highlighted: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchDocument:
    id: str
    index_id: str
    data: Dict[str, Any]
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class DataSearchManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._indices: Dict[str, SearchIndex] = {}
        self._documents: Dict[str, SearchDocument] = {}
        self._queries: Dict[str, SearchQuery] = {}
        self._results: Dict[str, SearchResult] = {}
        self._clients: Dict[SearchEngine, Any] = {}
        self._analyzers: Dict[str, Callable] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_analyzers()
        self._initialize_clients()

    def _initialize_analyzers(self) -> None:
        self.register_analyzer("standard", self._analyze_standard)
        self.register_analyzer("stemming", self._analyze_stemming)
        self.register_analyzer("phonetic", self._analyze_phonetic)
        self.register_analyzer("ngram", self._analyze_ngram)
        self.register_analyzer("synonym", self._analyze_synonym)

    def _initialize_clients(self) -> None:
        if ELASTICSEARCH_AVAILABLE:
            elastic_config = self.config.get("elasticsearch", {})
            if elastic_config:
                self._clients[SearchEngine.ELASTICSEARCH] = AsyncElasticsearch(
                    hosts=elastic_config.get("hosts", ["localhost:9200"]),
                    http_auth=elastic_config.get("auth"),
                    use_ssl=elastic_config.get("ssl", False),
                    verify_certs=elastic_config.get("verify_certs", True)
                )

    def register_analyzer(self, name: str, analyzer: Callable) -> None:
        self._analyzers[name] = analyzer

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_index(
        self,
        name: str,
        fields: List[str],
        engine: SearchEngine = SearchEngine.WHOOSH,
        analyzers: Optional[Dict[str, str]] = None,
        settings: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SearchIndex:
        async with self._lock:
            index_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            index = SearchIndex(
                id=index_id,
                name=name,
                engine=engine,
                fields=fields,
                analyzers=analyzers or {},
                settings=settings or {},
                metadata=metadata or {}
            )
            
            if engine == SearchEngine.WHOOSH and WHOOSH_AVAILABLE:
                await self._create_whoosh_index(index)
            
            elif engine == SearchEngine.ELASTICSEARCH and ELASTICSEARCH_AVAILABLE:
                await self._create_elasticsearch_index(index)
            
            elif engine == SearchEngine.IN_MEMORY:
                self._documents = {}
            
            self._indices[index_id] = index
            await self._notify_observers("index_created", index)
            
            return index

    async def _create_whoosh_index(self, index: SearchIndex) -> None:
        schema = Schema()
        schema_fields = {}
        
        for field in index.fields:
            if field == "id":
                schema_fields["id"] = ID(stored=True, unique=True)
            elif field in ["timestamp", "date", "created_at", "updated_at"]:
                schema_fields[field] = DATETIME(stored=True)
            elif field in ["score", "value", "amount", "price"]:
                schema_fields[field] = NUMERIC(stored=True)
            elif field in ["tags", "categories", "labels"]:
                schema_fields[field] = KEYWORD(stored=True, lowercase=True)
            else:
                analyzer = index.analyzers.get(field, "standard")
                if analyzer == "stemming":
                    schema_fields[field] = TEXT(stored=True, analyzer=StemmingAnalyzer())
                else:
                    schema_fields[field] = TEXT(stored=True, analyzer=StandardAnalyzer())
        
        if "id" not in schema_fields:
            schema_fields["id"] = ID(stored=True, unique=True)
        
        schema = Schema(**schema_fields)
        create_in(index.settings.get("path", "./search_index"), schema)

    async def _create_elasticsearch_index(self, index: SearchIndex) -> None:
        if SearchEngine.ELASTICSEARCH not in self._clients:
            return
        
        client = self._clients[SearchEngine.ELASTICSEARCH]
        
        mappings = {
            "properties": {}
        }
        
        for field in index.fields:
            if field in ["id", "uuid"]:
                mappings["properties"][field] = {"type": "keyword"}
            elif field in ["timestamp", "date", "created_at", "updated_at"]:
                mappings["properties"][field] = {"type": "date"}
            elif field in ["score", "value", "amount", "price"]:
                mappings["properties"][field] = {"type": "float"}
            elif field in ["tags", "categories", "labels"]:
                mappings["properties"][field] = {"type": "keyword"}
            else:
                mappings["properties"][field] = {
                    "type": "text",
                    "analyzer": index.analyzers.get(field, "standard")
                }
        
        await client.indices.create(
            index=index.name,
            mappings=mappings,
            settings=index.settings
        )

    async def index_document(
        self,
        index_id: str,
        data: Dict[str, Any],
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SearchDocument]:
        async with self._lock:
            if index_id not in self._indices:
                return None
            
            index = self._indices[index_id]
            
            if doc_id is None:
                doc_id = hashlib.md5(f"{index_id}_{time.time()}".encode()).hexdigest()
            
            document = SearchDocument(
                id=doc_id,
                index_id=index_id,
                data=data,
                metadata=metadata or {}
            )
            
            self._documents[doc_id] = document
            
            if index.engine == SearchEngine.WHOOSH and WHOOSH_AVAILABLE:
                await self._index_whoosh(index, document)
            elif index.engine == SearchEngine.ELASTICSEARCH and ELASTICSEARCH_AVAILABLE:
                await self._index_elasticsearch(index, document)
            
            await self._notify_observers("document_indexed", document)
            return document

    async def _index_whoosh(self, index: SearchIndex, document: SearchDocument) -> None:
        import whoosh.index as whoosh_index
        
        ix = whoosh_index.open_dir(index.settings.get("path", "./search_index"))
        writer = ix.writer()
        
        doc_data = document.data.copy()
        doc_data["id"] = document.id
        
        writer.add_document(**doc_data)
        writer.commit()

    async def _index_elasticsearch(self, index: SearchIndex, document: SearchDocument) -> None:
        if SearchEngine.ELASTICSEARCH not in self._clients:
            return
        
        client = self._clients[SearchEngine.ELASTICSEARCH]
        
        await client.index(
            index=index.name,
            id=document.id,
            document=document.data
        )

    async def bulk_index(
        self,
        index_id: str,
        documents: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        async with self._lock:
            if index_id not in self._indices:
                return 0
            
            count = 0
            for data in documents:
                result = await self.index_document(index_id, data, metadata=metadata)
                if result:
                    count += 1
            
            return count

    async def search(
        self,
        query: SearchQuery,
        index_ids: Optional[List[str]] = None,
        engine: Optional[SearchEngine] = None
    ) -> SearchResult:
        async with self._lock:
            start_time = time.time()
            
            if index_ids is None:
                index_ids = list(self._indices.keys())
            elif isinstance(index_ids, str):
                index_ids = [index_ids]
            
            results = []
            total = 0
            
            for index_id in index_ids:
                if index_id not in self._indices:
                    continue
                
                index = self._indices[index_id]
                search_engine = engine or index.engine
                
                if search_engine == SearchEngine.WHOOSH and WHOOSH_AVAILABLE:
                    result = await self._search_whoosh(index, query)
                elif search_engine == SearchEngine.ELASTICSEARCH and ELASTICSEARCH_AVAILABLE:
                    result = await self._search_elasticsearch(index, query)
                else:
                    result = await self._search_in_memory(index, query)
                
                results.extend(result.get("documents", []))
                total += result.get("total", 0)
            
            if query.limit:
                results = results[:query.limit]
            
            search_result = SearchResult(
                id=hashlib.md5(f"{query.text}_{time.time()}".encode()).hexdigest(),
                query_id=query.id,
                documents=results,
                total=total,
                score=0.0,
                execution_time=time.time() - start_time,
                highlighted={}
            )
            
            self._results[search_result.id] = search_result
            await self._notify_observers("search_completed", search_result)
            
            return search_result

    async def _search_whoosh(self, index: SearchIndex, query: SearchQuery) -> Dict[str, Any]:
        import whoosh.index as whoosh_index
        
        ix = whoosh_index.open_dir(index.settings.get("path", "./search_index"))
        
        fields = query.fields or index.fields
        parser = MultifieldParser(fields, schema=ix.schema)
        
        if query.search_type == SearchType.FUZZY:
            parsed_query = parser.parse(query.text)
            search_query = FuzzyTerm(parsed_query.fieldname, parsed_query.text, maxdist=query.fuzzy_degree)
        elif query.search_type == SearchType.PREFIX:
            parsed_query = parser.parse(query.text)
            search_query = Prefix(parsed_query.fieldname, parsed_query.text[:query.prefix_length])
        elif query.search_type == SearchType.WILDCARD:
            parsed_query = parser.parse(query.text)
            search_query = Wildcard(parsed_query.fieldname, parsed_query.text)
        elif query.search_type == SearchType.PHRASE:
            search_query = parser.parse(f'"{query.text}"')
        else:
            search_query = parser.parse(query.text)
        
        if query.filters:
            filter_queries = []
            for field, value in query.filters.items():
                if isinstance(value, list):
                    filter_queries.append(Or([Term(field, str(v)) for v in value]))
                else:
                    filter_queries.append(Term(field, str(value)))
            search_query = And([search_query, And(filter_queries)])
        
        with ix.searcher() as searcher:
            results = searcher.search(
                search_query,
                limit=query.limit,
                offset=query.offset
            )
            
            documents = []
            for hit in results:
                doc = {
                    "id": hit["id"],
                    "score": hit.score,
                    **{field: hit.get(field) for field in index.fields if field in hit}
                }
                documents.append(doc)
            
            return {
                "documents": documents,
                "total": len(results)
            }

    async def _search_elasticsearch(self, index: SearchIndex, query: SearchQuery) -> Dict[str, Any]:
        if SearchEngine.ELASTICSEARCH not in self._clients:
            return {"documents": [], "total": 0}
        
        client = self._clients[SearchEngine.ELASTICSEARCH]
        
        es_query = {
            "query": {
                "bool": {
                    "must": []
                }
            },
            "size": query.limit,
            "from": query.offset
        }
        
        if query.search_type == SearchType.EXACT:
            es_query["query"]["bool"]["must"].append({
                "term": {"_all": query.text}
            })
        elif query.search_type == SearchType.FUZZY:
            es_query["query"]["bool"]["must"].append({
                "match": {
                    "_all": {
                        "query": query.text,
                        "fuzziness": query.fuzzy_degree
                    }
                }
            })
        elif query.search_type == SearchType.PHRASE:
            es_query["query"]["bool"]["must"].append({
                "match_phrase": {"_all": query.text}
            })
        else:
            es_query["query"]["bool"]["must"].append({
                "match": {"_all": query.text}
            })
        
        if query.filters:
            for field, value in query.filters.items():
                if isinstance(value, list):
                    es_query["query"]["bool"]["filter"] = {
                        "terms": {field: value}
                    }
                else:
                    es_query["query"]["bool"]["filter"] = {
                        "term": {field: value}
                    }
        
        response = await client.search(index=index.name, body=es_query)
        
        documents = []
        for hit in response["hits"]["hits"]:
            doc = {
                "id": hit["_id"],
                "score": hit["_score"],
                **hit["_source"]
            }
            documents.append(doc)
        
        return {
            "documents": documents,
            "total": response["hits"]["total"]["value"]
        }

    async def _search_in_memory(self, index: SearchIndex, query: SearchQuery) -> Dict[str, Any]:
        documents = []
        
        for doc in self._documents.values():
            if doc.index_id != index.id:
                continue
            
            text = " ".join(str(doc.data.get(field, "")) for field in index.fields)
            
            if query.search_type == SearchType.EXACT:
                if query.text.lower() in text.lower():
                    documents.append(doc)
            elif query.search_type == SearchType.FUZZY:
                # Simple fuzzy matching
                words = query.text.lower().split()
                doc_words = text.lower().split()
                matches = sum(1 for w in words if any(w in dw or dw in w for dw in doc_words))
                if matches >= len(words) - query.fuzzy_degree:
                    documents.append(doc)
            elif query.search_type == SearchType.PREFIX:
                if text.lower().startswith(query.text.lower()):
                    documents.append(doc)
            elif query.search_type == SearchType.PHRASE:
                if query.text.lower() in text.lower():
                    documents.append(doc)
            else:
                if query.text.lower() in text.lower():
                    documents.append(doc)
        
        total = len(documents)
        documents = documents[query.offset:query.offset + query.limit]
        
        return {
            "documents": [
                {
                    "id": doc.id,
                    "score": 1.0,
                    **doc.data
                }
                for doc in documents
            ],
            "total": total
        }

    async def delete_document(self, doc_id: str) -> bool:
        async with self._lock:
            if doc_id not in self._documents:
                return False
            
            doc = self._documents[doc_id]
            index = self._indices.get(doc.index_id)
            
            if index:
                if index.engine == SearchEngine.WHOOSH and WHOOSH_AVAILABLE:
                    import whoosh.index as whoosh_index
                    ix = whoosh_index.open_dir(index.settings.get("path", "./search_index"))
                    writer = ix.writer()
                    writer.delete_by_term("id", doc_id)
                    writer.commit()
                elif index.engine == SearchEngine.ELASTICSEARCH and ELASTICSEARCH_AVAILABLE:
                    client = self._clients[SearchEngine.ELASTICSEARCH]
                    await client.delete(index=index.name, id=doc_id)
            
            del self._documents[doc_id]
            await self._notify_observers("document_deleted", doc_id)
            return True

    async def delete_index(self, index_id: str) -> bool:
        async with self._lock:
            if index_id not in self._indices:
                return False
            
            index = self._indices[index_id]
            
            if index.engine == SearchEngine.WHOOSH and WHOOSH_AVAILABLE:
                import shutil
                shutil.rmtree(index.settings.get("path", "./search_index"))
            elif index.engine == SearchEngine.ELASTICSEARCH and ELASTICSEARCH_AVAILABLE:
                client = self._clients[SearchEngine.ELASTICSEARCH]
                await client.indices.delete(index=index.name)
            
            doc_ids = [doc_id for doc_id, doc in self._documents.items() if doc.index_id == index_id]
            for doc_id in doc_ids:
                del self._documents[doc_id]
            
            del self._indices[index_id]
            await self._notify_observers("index_deleted", index_id)
            return True

    async def _analyze_standard(self, text: str) -> List[str]:
        return text.lower().split()

    async def _analyze_stemming(self, text: str) -> List[str]:
        from nltk.stem import PorterStemmer
        stemmer = PorterStemmer()
        return [stemmer.stem(word) for word in text.lower().split()]

    async def _analyze_phonetic(self, text: str) -> List[str]:
        import phonetics
        return [phonetics.dmetaphone(word) for word in text.lower().split()]

    async def _analyze_ngram(self, text: str) -> List[str]:
        n = 3
        words = text.lower().split()
        ngrams = []
        for word in words:
            for i in range(len(word) - n + 1):
                ngrams.append(word[i:i+n])
        return ngrams

    async def _analyze_synonym(self, text: str) -> List[str]:
        synonyms = {
            "btc": ["bitcoin", "xbt"],
            "eth": ["ethereum"],
            "usdt": ["tether", "usd"]
        }
        words = text.lower().split()
        result = []
        for word in words:
            result.append(word)
            if word in synonyms:
                result.extend(synonyms[word])
        return result

    async def suggest(self, text: str, limit: int = 10) -> List[str]:
        suggestions = []
        
        for doc in self._documents.values():
            for value in doc.data.values():
                if isinstance(value, str):
                    if text.lower() in value.lower():
                        suggestions.append(value)
        
        return list(set(suggestions))[:limit]

    async def get_index(self, index_id: str) -> Optional[SearchIndex]:
        return self._indices.get(index_id)

    async def get_indices(self) -> List[SearchIndex]:
        return list(self._indices.values())

    async def get_document(self, doc_id: str) -> Optional[SearchDocument]:
        return self._documents.get(doc_id)

    async def get_result(self, result_id: str) -> Optional[SearchResult]:
        return self._results.get(result_id)

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
            "indices": len(self._indices),
            "documents": len(self._documents),
            "queries": len(self._queries),
            "results": len(self._results),
            "analyzers": len(self._analyzers),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "SearchEngine",
    "SearchType",
    "SearchSort",
    "SearchIndex",
    "SearchQuery",
    "SearchResult",
    "SearchDocument",
    "DataSearchManager"
]
