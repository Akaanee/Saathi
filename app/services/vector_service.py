import os
import json
import logging
import math
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterable, Tuple

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

class _Collection:
    def __init__(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        self.name = name
        self.metadata = metadata or {}

def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

def _norm(a: List[float]) -> float:
    return math.sqrt(sum(x * x for x in a))

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    denom = _norm(a) * _norm(b)
    if denom == 0.0:
        return 0.0
    return _dot(a, b) / denom

class VectorService:
    def __init__(self):
        self.persist_dir = Path(os.getenv("CHROMA_PERSIST_DIR", "knowledge_base/vector_store"))
        self.collections: Dict[str, _Collection] = {}
        self._items_by_collection: Dict[str, List[Dict[str, Any]]] = {}
        self.init_error: Optional[str] = None
        self._initialize()

    def _initialize(self):
        try:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._load_existing_collections()

            if llm_service.is_ready() and (not self.collections or len(self._items_by_collection.get("legal_knowledge", [])) == 0):
                repo_root = Path(__file__).resolve().parents[2]
                legal_docs_path = repo_root / "knowledge_base" / "legal_docs"
                self.initialize_knowledge_base(str(legal_docs_path))
                self._load_existing_collections()

            logger.info(f"Vector store initialized at: {self.persist_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize VectorService: {e}")
            self.init_error = str(e)

    def _load_existing_collections(self):
        self.collections = {}
        self._items_by_collection = {}

        for meta_path in self.persist_dir.glob("*.meta.json"):
            try:
                collection_name = meta_path.stem.replace(".meta", "")
                metadata = json.loads(meta_path.read_text(encoding="utf-8") or "{}")
                self.collections[collection_name] = _Collection(collection_name, metadata=metadata)
                self._items_by_collection[collection_name] = self._load_collection_items(collection_name)
            except Exception as e:
                logger.warning(f"Failed to load collection metadata {meta_path}: {e}")

    def _collection_meta_path(self, name: str) -> Path:
        return self.persist_dir / f"{name}.meta.json"

    def _collection_data_path(self, name: str) -> Path:
        return self.persist_dir / f"{name}.jsonl"

    def _load_collection_items(self, name: str) -> List[Dict[str, Any]]:
        data_path = self._collection_data_path(name)
        if not data_path.exists():
            return []

        items: List[Dict[str, Any]] = []
        try:
            for line in data_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                items.append(json.loads(line))
        except Exception as e:
            logger.warning(f"Failed reading vector store file {data_path}: {e}")
        return items

    def create_collection(self, name: str, metadata: Optional[Dict] = None) -> Any:
        try:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            if name not in self.collections:
                meta = metadata or {"description": f"Collection {name}"}
                self._collection_meta_path(name).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                self.collections[name] = _Collection(name, metadata=meta)
                self._items_by_collection[name] = self._load_collection_items(name)
                logger.info(f"Collection created: {name}")
            else:
                if metadata:
                    self.collections[name].metadata = metadata
                    self._collection_meta_path(name).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return self.collections[name]
        except Exception as e:
            logger.error(f"Failed to create collection {name}: {str(e)}")
            raise RuntimeError(f"Failed to create collection: {str(e)}")

    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ):
        self._get_collection(collection_name)

        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        
        if metadatas is None:
            metadatas = [{"source": "manual"} for _ in documents]

        try:
            data_path = self._collection_data_path(collection_name)
            data_path.parent.mkdir(parents=True, exist_ok=True)

            items: List[Dict[str, Any]] = []
            for doc_id, doc, meta in zip(ids, documents, metadatas):
                embedding = llm_service.embed_text(doc)
                item = {
                    "id": doc_id,
                    "document": doc,
                    "metadata": meta or {},
                    "embedding": embedding
                }
                items.append(item)

            with data_path.open("a", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False))
                    f.write("\n")

            self._items_by_collection.setdefault(collection_name, []).extend(items)
            logger.info(f"Added {len(documents)} documents to {collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to add documents: {str(e)}")
            raise RuntimeError(f"Failed to add documents: {str(e)}")

    def query_legal_context(
        self,
        query: str,
        collection_name: str = "legal_knowledge",
        top_k: int = 5,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        if not self.is_ready():
            return []

        self._get_collection(collection_name)
        query_embedding = llm_service.embed_text(query)

        try:
            candidates = self._items_by_collection.get(collection_name, [])

            filtered: Iterable[Dict[str, Any]]
            if filter_metadata:
                def matches(item: Dict[str, Any]) -> bool:
                    meta = item.get("metadata", {}) or {}
                    return all(meta.get(k) == v for k, v in filter_metadata.items())
                filtered = (c for c in candidates if matches(c))
            else:
                filtered = candidates

            scored: List[Tuple[float, Dict[str, Any]]] = []
            for item in filtered:
                emb = item.get("embedding")
                if not isinstance(emb, list) or not emb:
                    continue
                sim = _cosine_similarity(query_embedding, emb)
                scored.append((sim, item))

            scored.sort(key=lambda x: x[0], reverse=True)
            top = scored[: max(0, top_k)]

            results: List[Dict[str, Any]] = []
            for sim, item in top:
                distance = 1.0 - float(sim)
                relevance_score = max(0.0, min(1.0, (float(sim) + 1.0) / 2.0))
                results.append(
                    {
                        "content": item.get("document", ""),
                        "metadata": item.get("metadata", {}) or {},
                        "distance": distance,
                        "relevance_score": relevance_score,
                    }
                )

            return results
            
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            return []

    def hybrid_search(
        self,
        query: str,
        collection_name: str = "legal_knowledge",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        vector_results = self.query_legal_context(query, collection_name, top_k)
        
        if not vector_results:
            return []
        
        return vector_results

    def _get_collection(self, name: str) -> Any:
        if name not in self.collections:
            return self.create_collection(name)
        return self.collections[name]

    def initialize_knowledge_base(self, legal_docs_path: str):
        self.create_collection("legal_knowledge", {"type": "mixed"})
        self.create_collection("ipc_sections", {"type": "criminal_law"})
        self.create_collection("labor_laws", {"type": "labor_law"})
        self.create_collection("legal_templates", {"type": "templates"})
        
        try:
            with open(os.path.join(legal_docs_path, "ipc_sections.json"), 'r', encoding='utf-8') as f:
                ipc_data = json.load(f)
                self._seed_ipc_sections(ipc_data)
            
            with open(os.path.join(legal_docs_path, "labor_laws.json"), 'r', encoding='utf-8') as f:
                labor_data = json.load(f)
                self._seed_labor_laws(labor_data)
            
            logger.info("Knowledge base initialized successfully")
            
        except FileNotFoundError as e:
            logger.warning(f"Legal docs not found: {e}, seeding minimal built-in knowledge")
            ipc_data = {
                "420": {
                    "title": "Cheating and dishonestly inducing delivery of property",
                    "description": "Applies when a person deceives another and induces delivery of property or valuable security."
                },
                "406": {
                    "title": "Criminal breach of trust",
                    "description": "Applies when entrusted property is dishonestly misappropriated or converted."
                }
            }
            labor_data = {
                "mwa": {
                    "title": "Minimum Wages Act",
                    "description": "Provides for fixation and enforcement of minimum wages and payment obligations."
                },
                "clra": {
                    "title": "Contract Labour (Regulation and Abolition) Act",
                    "description": "Regulates employment of contract labour and provides for welfare and dispute mechanisms."
                }
            }
            self._seed_ipc_sections(ipc_data)
            self._seed_labor_laws(labor_data)

    def _seed_ipc_sections(self, ipc_data: Dict):
        documents = []
        metadatas = []
        ids = []
        
        for section_id, content in ipc_data.items():
            doc_text = f"IPC Section {section_id}: {content['title']}. {content['description']}"
            documents.append(doc_text)
            metadatas.append({
                "section": section_id,
                "title": content.get('title', ''),
                "category": content.get('category', 'general'),
                "type": "ipc"
            })
            ids.append(f"ipc_{section_id}")
        
        if documents:
            self.add_documents("ipc_sections", documents, metadatas, ids)
            self.add_documents("legal_knowledge", documents, metadatas, ids)

    def _seed_labor_laws(self, labor_data: Dict):
        documents = []
        metadatas = []
        ids = []
        
        for law_id, content in labor_data.items():
            doc_text = f"{content['title']}: {content['description']}. Key provisions: {content.get('key_provisions', '')}"
            documents.append(doc_text)
            metadatas.append({
                "law_id": law_id,
                "title": content.get('title', ''),
                "category": content.get('category', 'general'),
                "type": "labor_law"
            })
            ids.append(f"labor_{law_id}")
        
        if documents:
            self.add_documents("labor_laws", documents, metadatas, ids)
            self.add_documents("legal_knowledge", documents, metadatas, ids)

    def get_collection_info(self, name: str) -> Dict[str, Any]:
        collection = self._get_collection(name)

        try:
            return {
                'name': name,
                'document_count': len(self._items_by_collection.get(name, [])),
                'metadata': collection.metadata
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {str(e)}")
            return {'name': name, 'error': str(e)}

    def is_ready(self) -> bool:
        if self.init_error:
            return False
        return llm_service.is_ready()


vector_service = VectorService()
