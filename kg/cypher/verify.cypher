// Step 9: 적재 검증 쿼리 모음 (cypher-shell 또는 Neo4j Browser에서 실행)

// 1. 노드 라벨별 카운트
MATCH (n) RETURN labels(n) AS labels, count(n) AS count ORDER BY count DESC;

// 2. PrimeKG relation(type 프로퍼티) 별 카운트
MATCH ()-[r:RELATION]->() RETURN r.type AS relation, count(r) AS count ORDER BY count DESC;

// 3. 전체 관계 타입별 카운트 (DUR/Food 포함)
MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY count DESC;

// 4. 당뇨 멀티홉 샘플
MATCH (d:Disease)-[r]-(n)
WHERE toLower(d.name) CONTAINS 'diabetes'
RETURN d.name, type(r), r.type, labels(n), n.name LIMIT 20;

// 5. 약물 병용금기 샘플
MATCH (a:Drug)-[c:CONTRAINDICATED_WITH]->(b:Drug)
RETURN a.name, c.content, b.name LIMIT 10;

// 6. 약물-식품 상호작용 샘플
MATCH (d:Drug)-[fi:FOOD_INTERACTION]->(f:Food)
RETURN d.name, fi.effect, fi.severity, f.name LIMIT 10;

// 7. 인덱스/제약 확인
SHOW INDEXES;
SHOW CONSTRAINTS;
