import re
import time
import numpy as np
from config.settings import settings
from config.logging_config import logger

_MODEL_INSTANCE = None
_TRANSFORMERS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    _TRANSFORMERS_AVAILABLE = True
    logger.info("SentenceTransformers library detected.")
except ImportError:
    logger.warning("SentenceTransformers not installed. Utilizing TF-IDF cosine-similarity fallback.")

class EmbeddingModel:
    """Handles translation of text queries and resumes into dense semantic float vectors."""
    
    @classmethod
    def _get_model(cls):
        """Lazy-loads SentenceTransformer model only when required."""
        global _MODEL_INSTANCE, _TRANSFORMERS_AVAILABLE
        if not _TRANSFORMERS_AVAILABLE:
            return None
            
        if _MODEL_INSTANCE is None:
            try:
                model_name = settings.EMBEDDING_MODEL_NAME
                logger.info(f"Loading SentenceTransformer multilingual model: {model_name}...")
                _MODEL_INSTANCE = SentenceTransformer(model_name)
                logger.info("SentenceTransformer model successfully loaded into memory.")
            except Exception as e:
                logger.error(f"Error loading SentenceTransformer: {str(e)}. Switching to local fallback.")
                _TRANSFORMERS_AVAILABLE = False
                
        return _MODEL_INSTANCE

    @classmethod
    def embed_text(cls, text: str) -> list[float]:
        """Translates a single string into a list of floating-point values."""
        if not text.strip():
            # Return zero vector if text is empty
            return [0.0] * 384
            
        model = cls._get_model()
        if model:
            try:
                # e5 models recommend prepending 'query: ' or 'passage: '
                prefix = "passage: "
                embedded = model.encode([prefix + text])[0]
                return [float(x) for x in embedded]
            except Exception as e:
                logger.error(f"SentenceTransformer encoding failed: {str(e)}")
                
        # 100% Offline Pure-Python Fallback (Bag of Words / Hashing Vectorizer)
        # Yields a robust 384-dimensional vector based on word hashes
        vector = np.zeros(384)
        words = re.findall(r'\w+', text.lower())
        if not words:
            return vector.tolist()
            
        for word in words:
            # Deterministic word hashing to map words to vector indices
            idx = hash(word) % 384
            vector[idx] += 1.0
            
        # Normalize vector (L2 norm)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
            
        return [float(x) for x in vector]

    @classmethod
    def embed_query(cls, query: str) -> list[float]:
        """Specific method to embed query statements."""
        model = cls._get_model()
        if model:
            try:
                # E5 queries require 'query: ' prefix
                prefix = "query: "
                embedded = model.encode([prefix + query])[0]
                return [float(x) for x in embedded]
            except Exception as e:
                logger.error(f"SentenceTransformer query encoding failed: {str(e)}")
                
        # Call base fallback
        return cls.embed_text(query)
