# trading/bots/hedge_bot/hedge_bot_data_xml.py

import asyncio
import logging
import time
import json
import hashlib
import base64
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from xml.dom import pulldom
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import io

try:
    import lxml.etree as lxml_etree
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False

try:
    import xmlschema
    XMLSCHEMA_AVAILABLE = True
except ImportError:
    XMLSCHEMA_AVAILABLE = False

logger = logging.getLogger(__name__)


class XMLParserType(str, Enum):
    ELEMENT_TREE = "element_tree"
    LXML = "lxml"
    PULL_DOM = "pull_dom"
    SAX = "sax"


class XMLValidationType(str, Enum):
    NONE = "none"
    DTD = "dtd"
    XSD = "xsd"
    RELAXNG = "relaxng"
    SCHEMATRON = "schematron"


class XMLOutputType(str, Enum):
    XML = "xml"
    JSON = "json"
    DICT = "dict"
    CSV = "csv"
    PANDAS = "pandas"


@dataclass
class XMLDocument:
    id: str
    name: str
    root: ET.Element
    tree: ET.ElementTree
    parser_type: XMLParserType
    validation_type: XMLValidationType
    schema: Optional[Any] = None
    namespaces: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    size: int = 0
    version: str = "1.0.0"


@dataclass
class XMLQuery:
    id: str
    xpath: str
    namespaces: Dict[str, str]
    document_id: str
    result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    execution_time: float = 0.0


@dataclass
class XMLTransformation:
    id: str
    name: str
    xslt_path: Optional[str] = None
    stylesheet: Optional[str] = None
    output_type: XMLOutputType
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class XMLValidationResult:
    id: str
    document_id: str
    validation_type: XMLValidationType
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class XMLNode:
    id: str
    tag: str
    attributes: Dict[str, str]
    text: Optional[str] = None
    children: List['XMLNode'] = field(default_factory=list)
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataXMLManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._documents: Dict[str, XMLDocument] = {}
        self._queries: Dict[str, XMLQuery] = {}
        self._transformations: Dict[str, XMLTransformation] = {}
        self._validations: Dict[str, XMLValidationResult] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._xpath_cache: Dict[str, Any] = {}
        self._schema_cache: Dict[str, Any] = {}
        
        self._initialize_default_namespaces()

    def _initialize_default_namespaces(self) -> None:
        self._default_namespaces = {
            "xml": "http://www.w3.org/XML/1998/namespace",
            "xs": "http://www.w3.org/2001/XMLSchema",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsl": "http://www.w3.org/1999/XSL/Transform"
        }

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_document(
        self,
        name: str,
        root_tag: str,
        namespaces: Optional[Dict[str, str]] = None,
        parser_type: XMLParserType = XMLParserType.ELEMENT_TREE,
        validation_type: XMLValidationType = XMLValidationType.NONE,
        schema: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> XMLDocument:
        async with self._lock:
            doc_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            root = ET.Element(root_tag)
            tree = ET.ElementTree(root)
            
            doc = XMLDocument(
                id=doc_id,
                name=name,
                root=root,
                tree=tree,
                parser_type=parser_type,
                validation_type=validation_type,
                schema=schema,
                namespaces=namespaces or {},
                metadata=metadata or {}
            )
            
            self._documents[doc_id] = doc
            await self._notify_observers("document_created", doc)
            return doc

    async def parse_xml(
        self,
        xml_data: Union[str, bytes],
        name: str,
        parser_type: XMLParserType = XMLParserType.ELEMENT_TREE,
        validation_type: XMLValidationType = XMLValidationType.NONE,
        schema: Optional[Any] = None,
        namespaces: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> XMLDocument:
        async with self._lock:
            doc_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            if isinstance(xml_data, str):
                xml_data = xml_data.encode('utf-8')
            
            if parser_type == XMLParserType.ELEMENT_TREE:
                root = ET.fromstring(xml_data)
                tree = ET.ElementTree(root)
            elif parser_type == XMLParserType.LXML and LXML_AVAILABLE:
                root = lxml_etree.fromstring(xml_data)
                tree = lxml_etree.ElementTree(root)
            elif parser_type == XMLParserType.PULL_DOM:
                root = await self._parse_pull_dom(xml_data)
                tree = ET.ElementTree(root)
            else:
                root = ET.fromstring(xml_data)
                tree = ET.ElementTree(root)
            
            if validation_type != XMLValidationType.NONE:
                validation_result = await self._validate_xml(xml_data, validation_type, schema)
                if not validation_result.is_valid:
                    logger.warning(f"XML validation failed: {validation_result.errors}")
            
            doc = XMLDocument(
                id=doc_id,
                name=name,
                root=root,
                tree=tree,
                parser_type=parser_type,
                validation_type=validation_type,
                schema=schema,
                namespaces=namespaces or {},
                metadata=metadata or {},
                size=len(xml_data)
            )
            
            self._documents[doc_id] = doc
            await self._notify_observers("document_parsed", doc)
            return doc

    async def _parse_pull_dom(self, xml_data: bytes) -> ET.Element:
        xml_string = xml_data.decode('utf-8')
        dom = minidom.parseString(xml_string)
        return await self._convert_dom_to_element(dom.documentElement)

    async def _convert_dom_to_element(self, dom_node) -> ET.Element:
        element = ET.Element(dom_node.tagName)
        
        if dom_node.attributes:
            for attr_name, attr_value in dom_node.attributes.items():
                element.set(attr_name, attr_value)
        
        if dom_node.childNodes:
            for child in dom_node.childNodes:
                if child.nodeType == child.ELEMENT_NODE:
                    element.append(await self._convert_dom_to_element(child))
                elif child.nodeType == child.TEXT_NODE and child.data.strip():
                    element.text = child.data.strip()
        
        return element

    async def _validate_xml(
        self,
        xml_data: bytes,
        validation_type: XMLValidationType,
        schema: Any
    ) -> XMLValidationResult:
        errors = []
        warnings = []
        is_valid = True
        
        if validation_type == XMLValidationType.DTD:
            try:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(xml_data)
                is_valid = True
            except ET.ParseError as e:
                is_valid = False
                errors.append(str(e))
        
        elif validation_type == XMLValidationType.XSD and XMLSCHEMA_AVAILABLE:
            try:
                xsd_schema = xmlschema.XMLSchema(schema)
                is_valid = xsd_schema.is_valid(xml_data)
                if not is_valid:
                    errors = [str(e) for e in xsd_schema.validate(xml_data)]
            except Exception as e:
                is_valid = False
                errors.append(str(e))
        
        return XMLValidationResult(
            id=hashlib.md5(f"{validation_type.value}_{time.time()}".encode()).hexdigest(),
            document_id="",
            validation_type=validation_type,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            timestamp=time.time()
        )

    async def query_xpath(
        self,
        document_id: str,
        xpath: str,
        namespaces: Optional[Dict[str, str]] = None,
        use_cache: bool = True
    ) -> Optional[XMLQuery]:
        async with self._lock:
            if document_id not in self._documents:
                return None
            
            doc = self._documents[document_id]
            
            query_id = hashlib.md5(f"{document_id}_{xpath}_{time.time()}".encode()).hexdigest()
            
            query = XMLQuery(
                id=query_id,
                xpath=xpath,
                namespaces=namespaces or doc.namespaces,
                document_id=document_id,
                created_at=time.time()
            )
            
            start_time = time.time()
            
            try:
                if doc.parser_type == XMLParserType.LXML and LXML_AVAILABLE:
                    result = doc.tree.xpath(xpath, namespaces=query.namespaces)
                else:
                    result = doc.root.findall(xpath, query.namespaces)
                
                query.result = result
                query.execution_time = time.time() - start_time
                
                self._queries[query_id] = query
                await self._notify_observers("query_completed", query)
                return query
                
            except Exception as e:
                logger.error(f"XPath query error: {e}")
                return None

    async def find_element(
        self,
        document_id: str,
        tag: str,
        attributes: Optional[Dict[str, str]] = None,
        recursive: bool = True
    ) -> Optional[ET.Element]:
        if document_id not in self._documents:
            return None
        
        doc = self._documents[document_id]
        
        if recursive:
            elements = doc.root.findall(f".//{tag}")
        else:
            elements = doc.root.findall(tag)
        
        if attributes:
            for elem in elements:
                match = True
                for key, value in attributes.items():
                    if elem.get(key) != value:
                        match = False
                        break
                if match:
                    return elem
        
        return elements[0] if elements else None

    async def find_all_elements(
        self,
        document_id: str,
        tag: str,
        attributes: Optional[Dict[str, str]] = None,
        recursive: bool = True
    ) -> List[ET.Element]:
        if document_id not in self._documents:
            return []
        
        doc = self._documents[document_id]
        
        if recursive:
            elements = doc.root.findall(f".//{tag}")
        else:
            elements = doc.root.findall(tag)
        
        if attributes:
            result = []
            for elem in elements:
                match = True
                for key, value in attributes.items():
                    if elem.get(key) != value:
                        match = False
                        break
                if match:
                    result.append(elem)
            return result
        
        return elements

    async def add_element(
        self,
        document_id: str,
        parent_path: str,
        tag: str,
        text: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
        namespaces: Optional[Dict[str, str]] = None
    ) -> Optional[ET.Element]:
        async with self._lock:
            if document_id not in self._documents:
                return None
            
            doc = self._documents[document_id]
            
            parent = doc.root.find(parent_path, namespaces or doc.namespaces)
            if parent is None:
                return None
            
            element = ET.Element(tag)
            if text:
                element.text = text
            if attributes:
                for key, value in attributes.items():
                    element.set(key, value)
            
            parent.append(element)
            doc.updated_at = time.time()
            
            await self._notify_observers("element_added", document_id, tag)
            return element

    async def update_element(
        self,
        document_id: str,
        element_path: str,
        new_tag: Optional[str] = None,
        new_text: Optional[str] = None,
        new_attributes: Optional[Dict[str, str]] = None,
        namespaces: Optional[Dict[str, str]] = None
    ) -> bool:
        async with self._lock:
            if document_id not in self._documents:
                return False
            
            doc = self._documents[document_id]
            
            element = doc.root.find(element_path, namespaces or doc.namespaces)
            if element is None:
                return False
            
            if new_tag:
                element.tag = new_tag
            if new_text is not None:
                element.text = new_text
            if new_attributes:
                for key, value in new_attributes.items():
                    element.set(key, value)
            
            doc.updated_at = time.time()
            await self._notify_observers("element_updated", document_id, element_path)
            return True

    async def remove_element(
        self,
        document_id: str,
        element_path: str,
        namespaces: Optional[Dict[str, str]] = None
    ) -> bool:
        async with self._lock:
            if document_id not in self._documents:
                return False
            
            doc = self._documents[document_id]
            
            element = doc.root.find(element_path, namespaces or doc.namespaces)
            if element is None:
                return False
            
            parent = doc.root.find(element_path[:element_path.rfind('/')], namespaces or doc.namespaces)
            if parent is not None:
                parent.remove(element)
            
            doc.updated_at = time.time()
            await self._notify_observers("element_removed", document_id, element_path)
            return True

    async def to_xml(
        self,
        document_id: str,
        pretty: bool = True,
        encoding: str = "utf-8"
    ) -> Optional[str]:
        if document_id not in self._documents:
            return None
        
        doc = self._documents[document_id]
        
        if pretty:
            rough_string = ET.tostring(doc.root, encoding=encoding)
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ")
        else:
            return ET.tostring(doc.root, encoding=encoding).decode(encoding)

    async def to_json(
        self,
        document_id: str,
        include_attributes: bool = True
    ) -> Optional[Dict[str, Any]]:
        if document_id not in self._documents:
            return None
        
        doc = self._documents[document_id]
        return await self._element_to_dict(doc.root, include_attributes)

    async def _element_to_dict(
        self,
        element: ET.Element,
        include_attributes: bool = True
    ) -> Dict[str, Any]:
        result = {}
        
        if include_attributes and element.attrib:
            result["attributes"] = element.attrib
        
        if element.text and element.text.strip():
            result["text"] = element.text.strip()
        
        if element.getchildren():
            children = defaultdict(list)
            for child in element:
                child_dict = await self._element_to_dict(child, include_attributes)
                children[child.tag].append(child_dict)
            result["children"] = dict(children)
        
        return result

    async def get_nodes(
        self,
        document_id: str,
        xpath: str
    ) -> List[XMLNode]:
        if document_id not in self._documents:
            return []
        
        doc = self._documents[document_id]
        
        elements = doc.root.findall(xpath, doc.namespaces)
        nodes = []
        
        for elem in elements:
            node = await self._convert_to_node(elem)
            if node:
                nodes.append(node)
        
        return nodes

    async def _convert_to_node(self, element: ET.Element) -> XMLNode:
        node_id = hashlib.md5(f"{element.tag}_{time.time()}".encode()).hexdigest()
        
        node = XMLNode(
            id=node_id,
            tag=element.tag,
            attributes=element.attrib,
            text=element.text.strip() if element.text else None
        )
        
        for child in element:
            child_node = await self._convert_to_node(child)
            if child_node:
                child_node.parent_id = node_id
                node.children.append(child_node)
        
        return node

    async def create_transformation(
        self,
        name: str,
        xslt_path: Optional[str] = None,
        stylesheet: Optional[str] = None,
        output_type: XMLOutputType = XMLOutputType.XML,
        metadata: Optional[Dict[str, Any]] = None
    ) -> XMLTransformation:
        async with self._lock:
            transform_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            transform = XMLTransformation(
                id=transform_id,
                name=name,
                xslt_path=xslt_path,
                stylesheet=stylesheet,
                output_type=output_type,
                metadata=metadata or {}
            )
            
            self._transformations[transform_id] = transform
            await self._notify_observers("transformation_created", transform)
            return transform

    async def transform(
        self,
        document_id: str,
        transform_id: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        if document_id not in self._documents:
            return None
        
        if transform_id not in self._transformations:
            return None
        
        doc = self._documents[document_id]
        transform = self._transformations[transform_id]
        
        if transform.xslt_path:
            if LXML_AVAILABLE:
                xslt = lxml_etree.parse(transform.xslt_path)
                transform_obj = lxml_etree.XSLT(xslt)
                
                if params:
                    result = transform_obj(doc.tree, **params)
                else:
                    result = transform_obj(doc.tree)
                
                if transform.output_type == XMLOutputType.XML:
                    return str(result)
                elif transform.output_type == XMLOutputType.JSON:
                    return str(result)
                else:
                    return str(result)
        
        return None

    async def get_document(self, document_id: str) -> Optional[XMLDocument]:
        return self._documents.get(document_id)

    async def get_documents(self) -> List[XMLDocument]:
        return list(self._documents.values())

    async def get_query(self, query_id: str) -> Optional[XMLQuery]:
        return self._queries.get(query_id)

    async def get_transformation(self, transform_id: str) -> Optional[XMLTransformation]:
        return self._transformations.get(transform_id)

    async def delete_document(self, document_id: str) -> bool:
        async with self._lock:
            if document_id in self._documents:
                del self._documents[document_id]
                await self._notify_observers("document_deleted", document_id)
                return True
            return False

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
            "documents": len(self._documents),
            "queries": len(self._queries),
            "transformations": len(self._transformations),
            "validations": len(self._validations),
            "observers": len(self._observers),
            "running": self._running,
            "xpath_cache": len(self._xpath_cache),
            "schema_cache": len(self._schema_cache)
        }


__all__ = [
    "XMLParserType",
    "XMLValidationType",
    "XMLOutputType",
    "XMLDocument",
    "XMLQuery",
    "XMLTransformation",
    "XMLValidationResult",
    "XMLNode",
    "DataXMLManager"
]
