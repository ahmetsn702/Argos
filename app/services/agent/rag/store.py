import logging
import uuid
import app.core.feature_flags as ff
from app.core.config import settings
from app.services.agent.rag.embedder import LocalEmbedder

logger = logging.getLogger(__name__)

class ChromaStore:
    def __init__(self, session_id: str, persist_dir: str = None):
        self.session_id = session_id
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._embedder = LocalEmbedder()

    def _get_client_and_collection(self):
        if not ff.AGENT_ENABLED:
            return None, None
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self.persist_dir)
            collection_name = f"argos_{self.session_id}"
            collection = client.get_or_create_collection(collection_name)
            return client, collection
        except ImportError:
            logger.warning("chromadb package is not installed. ChromaStore will operate as a no-op.")
            return None, None
        except Exception as e:
            logger.error(f"Failed to initialize chromadb: {e}")
            return None, None

    async def add(self, text: str, metadata: dict) -> None:
        if not ff.AGENT_ENABLED:
            return

        client, collection = self._get_client_and_collection()
        if collection is None:
            return

        doc_id = str(uuid.uuid4())
        embeddings = self._embedder.embed([text])

        try:
            if embeddings:
                collection.add(
                    documents=[text],
                    metadatas=[metadata],
                    ids=[doc_id],
                    embeddings=embeddings
                )
            else:
                collection.add(
                    documents=[text],
                    metadatas=[metadata],
                    ids=[doc_id]
                )
        except Exception as e:
            logger.error(f"Error adding document to ChromaStore: {e}")

    async def search(self, query: str, n_results: int = 5) -> list[dict]:
        if not ff.AGENT_ENABLED:
            return []

        client, collection = self._get_client_and_collection()
        if collection is None:
            return []

        embeddings = self._embedder.embed([query])
        try:
            if embeddings:
                results = collection.query(
                    query_embeddings=embeddings,
                    n_results=n_results
                )
            else:
                results = collection.query(
                    query_texts=[query],
                    n_results=n_results
                )

            docs = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0] if "distances" in results else None

            output = []
            for i in range(len(docs)):
                item = {
                    "text": docs[i],
                    "metadata": metadatas[i] if metadatas else {},
                    "id": ids[i]
                }
                if distances is not None and i < len(distances):
                    item["distance"] = distances[i]
                output.append(item)
            return output
        except Exception as e:
            logger.error(f"Error querying ChromaStore: {e}")
            return []

    async def clear(self) -> None:
        if not ff.AGENT_ENABLED:
            return

        client, collection = self._get_client_and_collection()
        if client is None:
            return

        try:
            collection_name = f"argos_{self.session_id}"
            client.delete_collection(collection_name)
        except Exception as e:
            logger.error(f"Error clearing ChromaStore collection: {e}")
