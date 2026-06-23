import logging
import app.core.feature_flags as ff

logger = logging.getLogger(__name__)

class LocalEmbedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not ff.AGENT_ENABLED:
            return []

        if not texts:
            return []

        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                logger.warning("sentence-transformers package is not installed. LocalEmbedder will return empty embeddings.")
                return []
            except Exception as e:
                logger.error(f"Failed to load sentence-transformers model {self.model_name}: {e}")
                return []

        try:
            embeddings = self._model.encode(texts)
            if hasattr(embeddings, "tolist"):
                return embeddings.tolist()
            return [list(map(float, emb)) for emb in embeddings]
        except Exception as e:
            logger.error(f"Error generating embeddings with sentence-transformers: {e}")
            return []
