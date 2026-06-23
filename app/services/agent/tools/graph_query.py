from app.services.agent.tools.base import BaseTool
from app.services.agent.tools.client import get_client

class GraphQueryTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="graph_query",
            description="Execute a Cypher query on the Neo4j graph database."
        )

    async def _run(self, params: dict) -> dict:
        query = params.get("query")
        if not query:
            return {"ok": False, "data": None, "error": "Missing 'query' parameter"}

        async with get_client() as client:
            response = await client.post(
                "/graph/cypher",
                json={"query": query}
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json(), "error": None}
            else:
                return {"ok": False, "data": None, "error": f"HTTP error {response.status_code}: {response.text}"}
