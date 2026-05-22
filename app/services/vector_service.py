import os
import json
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)

class VectorService:
    def __init__(self):
        self.persist_dir = os.getenv("CHROMA_PERSIST_DIR", "knowledge_base/chroma_db")
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.client = None
        self.embedding_model = None
        self.collections = {}
        self._initialize()

    def _initialize(self):
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )
            
            logger.info("ChromaDB client initialized")
            
            try:
                self.embedding_model = SentenceTransformer(self.embedding_model_name)
                logger.info(f"Embedding model loaded: {self.embedding_model_name}")
            except Exception as e:
                logger.warning(f"Could not load sentence-transformers model: {e}")
                self.embedding_model = None
            
            self._load_existing_collections()
            
        except Exception as e:
            logger.error(f"Failed to initialize VectorService: {str(e)}")
            self.client = None

    def _load_existing_collections(self):
        if not self.client:
            return
        
        try:
            existing = self.client.list_collections()
            for col in existing:
                self.collections[col.name] = col
                logger.info(f"Loaded existing collection: {col.name}")
        except Exception as e:
            logger.error(f"Error loading collections: {str(e)}")

    def create_collection(self, name: str, metadata: Optional[Dict] = None) -> Any:
        if not self.client:
            raise RuntimeError("ChromaDB client not initialized")
        
        try:
            collection = self.client.get_or_create_collection(
                name=name,
                metadata=metadata or {"description": f"Collection {name}"}
            )
            self.collections[name] = collection
            logger.info(f"Collection created/get: {name}")
            return collection
            
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
        collection = self._get_collection(collection_name)
        
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        
        if metadatas is None:
            metadatas = [{"source": "manual"} for _ in documents]
        
        embeddings = self._generate_embeddings(documents)
        
        try:
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
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
        collection = self._get_collection(collection_name)
        
        query_embedding = self._generate_embeddings([query])[0]
        
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_metadata,
                include=["documents", "metadatas", "distances"]
            )
            
            processed_results = []
            if results and 'documents' in results:
                for i in range(len(results['documents'][0])):
                    processed_results.append({
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 0.0,
                        'relevance_score': 1.0 - results['distances'][0][i] if results['distances'] else 0.0
                    })
            
            logger.info(f"Query returned {len(processed_results)} results")
            return processed_results
            
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

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if self.embedding_model:
            try:
                embeddings = self.embedding_model.encode(texts)
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"Embedding generation failed: {str(e)}")
        
        raise RuntimeError("No embedding model available")

    def _get_collection(self, name: str) -> Any:
        if name not in self.collections:
            self.collections[name] = self.client.get_or_create_collection(name)
        return self.collections[name]

    def initialize_knowledge_base(self, legal_docs_path: str):
        ipc_collection = self.create_collection("ipc_sections", {"type": "criminal_law"})
        labor_collection = self.create_collection("labor_laws", {"type": "labor_law"})
        templates_collection = self.create_collection("legal_templates", {"type": "templates"})
        
        try:
            with open(os.path.join(legal_docs_path, "ipc_sections.json"), 'r', encoding='utf-8') as f:
                ipc_data = json.load(f)
                self._seed_ipc_sections(ipc_collection, ipc_data)
            
            with open(os.path.join(legal_docs_path, "labor_laws.json"), 'r', encoding='utf-8') as f:
                labor_data = json.load(f)
                self._seed_labor_laws(labor_collection, labor_data)
            
            logger.info("Knowledge base initialized successfully")
            
        except FileNotFoundError as e:
            logger.warning(f"Legal docs not found: {e}, creating empty collections")

    def _seed_ipc_sections(self, collection, ipc_data: Dict):
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
            self.add_documents(collection.name, documents, metadatas, ids)

    def _seed_labor_laws(self, collection, labor_data: Dict):
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
            self.add_documents(collection.name, documents, metadatas, ids)

    def get_collection_info(self, name: str) -> Dict[str, Any]:
        collection = self._get_collection(name)
        
        try:
            count = collection.count()
            return {
                'name': name,
                'document_count': count,
                'metadata': collection.metadata
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {str(e)}")
            return {'name': name, 'error': str(e)}

    def is_ready(self) -> bool:
        return self.client is not None and self.embedding_model is not None


vector_service = VectorService()
