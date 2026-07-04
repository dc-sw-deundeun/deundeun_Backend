import logging
from typing import Any

from neo4j import GraphDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self) -> None:
        uri = settings.neo4j_uri or "bolt://localhost:7687"
        auth = (
            (settings.neo4j_user, settings.neo4j_password)
            if settings.neo4j_user and settings.neo4j_password
            else None
        )
        self._driver = GraphDatabase.driver(uri, auth=auth)

    def close(self) -> None:
        self._driver.close()

    def search_diseases(self, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        query = """
        MATCH (d:Disease)
        WHERE toLower(d.name) CONTAINS toLower($keyword)
        OPTIONAL MATCH (d)-[:RELATION {type: "phenotype present"}]->(e:Effect)
        RETURN d.name AS name, collect(e.name)[..8] AS symptoms
        LIMIT $limit
        """
        try:
            with self._driver.session() as session:
                result = session.run(query, keyword=keyword, limit=limit)
                return [{"name": r["name"], "symptoms": r["symptoms"]} for r in result]
        except Exception as exc:
            logger.warning("Neo4j query failed: %s", exc)
            return []
