# 외부 의학 KG Neo4j 이미지 — dump 최초 1회 자동 로드.
# dump(neo4j.dump)는 Git에 포함하지 않고 볼륨(../kg/data/dumps)으로 마운트한다.
FROM neo4j:5.26-community

# root로 실행 → 엔트리포인트가 /data 권한 정리 후 공식 엔트리포인트가 neo4j 유저로 강등
USER root

COPY docker-entrypoint-kg.sh /docker-entrypoint-kg.sh
RUN chmod +x /docker-entrypoint-kg.sh

ENTRYPOINT ["/docker-entrypoint-kg.sh"]
CMD ["neo4j"]
