import os
import numpy as np
from config.settings import settings
from config.logging_config import logger
from services.embeddings.model import EmbeddingModel

_CHROMA_CLIENT = None
_COLLECTION = None
_CHROMA_AVAILABLE = False

try:
    import chromadb
    _CHROMA_AVAILABLE = True
    logger.info("ChromaDB library successfully detected.")
except ImportError:
    logger.warning("ChromaDB not installed. Standard search will rely on the pure-Python memory vector store.")

class LocalMemoryVectorStore:
    """Pure Python fallback vector store utilizing manual NumPy cosine similarity."""
    
    # Static dictionary to store index records: {resume_id: {"vector": [...], "text": "...", "metadata": {...}}}
    _memory_db = {}
    
    @classmethod
    def add(cls, resume_id: str, vector: list[float], text: str, metadata: dict):
        cls._memory_db[str(resume_id)] = {
            "vector": vector,
            "text": text,
            "metadata": metadata
        }
        logger.info(f"[In-Memory Vector DB] Indexed resume ID: {resume_id}")

    @classmethod
    def query(cls, query_vector: list[float], limit: int = 5) -> list[dict]:
        logger.info(f"[In-Memory Vector DB] Searching {len(cls._memory_db)} records...")
        if not cls._memory_db:
            return []
            
        results = []
        q_v = np.array(query_vector)
        q_norm = np.linalg.norm(q_v)
        
        if q_norm == 0:
            return []
            
        for rid, item in cls._memory_db.items():
            r_v = np.array(item["vector"])
            r_norm = np.linalg.norm(r_v)
            if r_norm == 0:
                continue
                
            # Cosine Similarity: dot(A, B) / (||A|| * ||B||)
            sim = float(np.dot(q_v, r_v) / (q_norm * r_norm))
            results.append({
                "id": rid,
                "score": sim,
                "text": item["text"],
                "metadata": item["metadata"]
            })
            
        # Sort descending by similarity score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

class VectorStoreService:
    """Enterprise coordinator for vector storage and semantic querying."""
    
    @classmethod
    def _get_collection(cls):
        """Initializes ChromaDB connection lazily."""
        global _CHROMA_CLIENT, _COLLECTION, _CHROMA_AVAILABLE
        if not _CHROMA_AVAILABLE:
            return None
            
        if _COLLECTION is None:
            try:
                # Setup persistent client
                db_dir = settings.CHROMA_DB_PATH
                os.makedirs(db_dir, exist_ok=True)
                
                _CHROMA_CLIENT = chromadb.PersistentClient(path=db_dir)
                
                # Get or create collection
                _COLLECTION = _CHROMA_CLIENT.get_or_create_collection(
                    name="workforce_resumes",
                    metadata={"hnsw:space": "cosine"} # Use cosine similarity
                )
                logger.info("ChromaDB vector collection 'workforce_resumes' successfully configured.")
            except Exception as e:
                logger.error(f"Failed to instantiate ChromaDB client: {str(e)}. Switching to local memory vector fallback.")
                _CHROMA_AVAILABLE = False
                
        return _COLLECTION

    @classmethod
    def add_to_collection(cls, doc_id: str, text: str, metadata: dict):
        """Wrapper method for indexing candidate data, alias to index_resume."""
        try:
            resume_id = int(doc_id)
        except ValueError:
            # Fallback to hash if doc_id is not integer-like
            resume_id = hash(doc_id) % 1000000
        cls.index_resume(resume_id, text, metadata)

    @classmethod
    def index_resume(cls, resume_id: int, text: str, metadata: dict):
        """Generates embeddings and index the candidate's parsed text."""
        # Clean text
        text_content = text.strip() if text else ""
        if not text_content:
            logger.warning(f"Empty text provided for index. Skipping indexation of resume: {resume_id}")
            return
            
        # 1. Compute vector
        vector = EmbeddingModel.embed_text(text_content)
        
        # 2. Add to active store
        collection = cls._get_collection()
        if collection:
            try:
                # ChromaDB requires values as lists and metadata keys to be simple (str, int, float, bool)
                cleaned_metadata = {}
                for k, v in metadata.items():
                    if isinstance(v, (str, int, float, bool)):
                        cleaned_metadata[k] = v
                    elif isinstance(v, list):
                        cleaned_metadata[k] = ", ".join(v)
                    else:
                        cleaned_metadata[k] = str(v)
                
                collection.upsert(
                    ids=[str(resume_id)],
                    embeddings=[vector],
                    documents=[text_content],
                    metadatas=[cleaned_metadata]
                )
                logger.info(f"Indexed resume ID {resume_id} into ChromaDB.")
                return
            except Exception as e:
                logger.error(f"ChromaDB indexing failed: {str(e)}. Redirecting to memory vector index.")
                
        # In-memory store fallback
        LocalMemoryVectorStore.add(str(resume_id), vector, text_content, metadata)

    @classmethod
    def search_candidates(cls, query: str, limit: int = 5) -> list[dict]:
        """Searches candidates semantically matching the query string."""
        logger.info(f"Executing semantic vector lookup for query: '{query}'")
        
        # 1. Compute query vector
        query_vector = EmbeddingModel.embed_query(query)
        
        # 2. Execute query against active database
        collection = cls._get_collection()
        if collection:
            try:
                res = collection.query(
                    query_embeddings=[query_vector],
                    n_results=limit
                )
                
                # Format response lists
                formatted = []
                if res and res["ids"] and res["ids"][0]:
                    for idx in range(len(res["ids"][0])):
                        # Cosine distance to similarity: 1 - distance
                        dist = res["distances"][0][idx] if "distances" in res else 0.0
                        score = 1.0 - dist if dist <= 1.0 else 0.0
                        
                        formatted.append({
                            "id": res["ids"][0][idx],
                            "score": score,
                            "text": res["documents"][0][idx] if "documents" in res else "",
                            "metadata": res["metadatas"][0][idx] if "metadatas" in res else {}
                        })
                return formatted
            except Exception as e:
                logger.error(f"ChromaDB search execution failed: {str(e)}. Querying memory vector store.")
                
        # Memory fallback search
        return LocalMemoryVectorStore.query(query_vector, limit)
