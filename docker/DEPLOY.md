# Medical KG (Neo4j) 배포 가이드

외부 의학 지식그래프를 담은 **read-only Neo4j** 컨테이너 배포 문서.
이미지에 데이터(덤프)가 구워져 있어 **단독 실행**된다 — 별도 DB 적재 과정 불필요.

- 이미지: `deundeun/medical-kg-neo4j:v1`
- 내용: PrimeKG(질병·약물·효과) + 한국 검진 finding↔MONDO + 식약처 DUR 안전 레이어
- 규모: 노드 ~28.7K(Disease 17,064 / Effect 9,456 / Drug 2,232), 관계 ~577K
- 성격: **read-only**. 첫 기동 시 내장 덤프를 데이터 볼륨에 1회 자동 로드하고, 이후엔 스킵.

---

## 인프라 담당자에게 줄 것

다음 중 **하나**만 주면 됩니다.

**(A) 레지스트리(Docker Hub 등) 사용 시** — push 후 담당자가 pull
```bash
docker login                                  # PRIVATE 저장소 권장
PUSH=1 IMAGE=<user>/medical-kg-neo4j:v1 \
  PLATFORM=linux/amd64,linux/arm64 \
  bash docker/build-release.sh v1             # 멀티아치 빌드 + push
```
→ 담당자는 `docker pull <user>/medical-kg-neo4j:v1` 만 하면 됨 (아키텍처 자동 선택).

> ⚠️ **반드시 PRIVATE 저장소.** 이미지에 데이터가 구워져 있고, v2의 DrugBank 데이터는
>   공개 재배포가 라이선스 위반이다. 공개 repo 금지.
> ⚠️ **아키텍처 주의.** Mac(arm64)에서 만든 단일 이미지를 x86 VM에 올리면 안 돈다.
>   위처럼 `PLATFORM=linux/amd64,linux/arm64` 로 멀티아치 빌드해서 올릴 것.

**(B) 파일로 전달 시** — 단일 tar 파일
```bash
SAVE=1 bash docker/build-release.sh v1
# 산출물: kg/data/dist/medical-kg-neo4j-v1.tar.gz
```
→ 담당자는 이 파일을 받아 `docker load < medical-kg-neo4j-v1.tar.gz` 후 실행.

그 외 필요한 정보(아래 "운영 정보" 표) + 설정할 **NEO4J 비밀번호**.

---

## 실행 (docker run)

```bash
docker run -d --name medical-kg-neo4j \
  -e NEO4J_AUTH=neo4j/<STRONG_PASSWORD> \
  -e NEO4J_server_memory_heap_max__size=2G \
  -e NEO4J_server_memory_pagecache_size=1G \
  -p 7474:7474 -p 7687:7687 \
  -v medical_kg_data:/data \
  deundeun/medical-kg-neo4j:v1
```

- 첫 기동: 내장 덤프 자동 로드(로그에 `[entrypoint] dump 로드 완료`). 부팅+로드에 **1~2분** 소요.
- 재기동: `medical_kg_data` 볼륨에 `.kg_loaded` 마커가 있어 재로드하지 않음(빠름).
- `-v medical_kg_data:/data` 를 빼면 컨테이너 재생성 때마다 다시 로드됨 → 영속 볼륨 권장.

## 실행 (docker compose, 선택)

```yaml
services:
  medical-kg-neo4j:
    image: deundeun/medical-kg-neo4j:v1
    restart: unless-stopped
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_server_memory_heap_max__size: 2G
      NEO4J_server_memory_pagecache_size: 1G
    ports: ["7474:7474", "7687:7687"]
    volumes: ["medical_kg_data:/data"]
volumes:
  medical_kg_data:
```

---

## 운영 정보

| 항목 | 값 |
|---|---|
| Bolt (앱 연결) | `bolt://<host>:7687` |
| HTTP Browser | `http://<host>:7474` |
| 계정 | `neo4j` / `NEO4J_AUTH`로 지정한 비밀번호 |
| 데이터 영속 | 볼륨 `/data` (이름 볼륨 권장) |
| 메모리 권장 | heap 2G + pagecache 1G → 컨테이너 ≥4GB RAM |
| 베이스 | `neo4j:5.26-community` |

앱(백엔드)은 `bolt://<host>:7687` + 계정으로 접속해 **읽기 전용 쿼리**만 수행한다.

---

## 헬스체크 / 동작 확인

```bash
# 기동 로그
docker logs medical-kg-neo4j 2>&1 | grep entrypoint

# 노드 수 확인 (cypher-shell)
docker exec medical-kg-neo4j cypher-shell -u neo4j -p <PW> \
  "MATCH (n) RETURN labels(n)[0] AS label, count(*) ORDER BY count(*) DESC"
```
기대값: Disease 17,064 / Effect 9,456 / Drug 2,232.

---

## 버전 / 갱신

- 현재 `v1` 은 ATC 36%(name-bridge) + 한국필터 전 **스냅샷**.
- 데이터 갱신 절차(read-only라 이미지 교체로 끝):
  1. 로컬에서 KG 재적재
  2. `bash kg/scripts/08_export_dump.sh` → 새 `neo4j.dump`
  3. `bash docker/build-release.sh v2` → `:v2` 이미지
  4. 배포 타겟에서 이미지 태그만 교체 후 재기동(영속 볼륨 비우거나 새 볼륨 사용 → 새 덤프 로드)
