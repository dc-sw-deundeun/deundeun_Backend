# 질환 검색 API

> 기준일: 2026-07-03
> Base URL: `/api/v1/search`
> 인증: `Authorization: Bearer <access_token>` 헤더 필요

---

## 개요

한국어 키워드로 질환 정보를 검색합니다.

내부 동작:
1. 의학 지식 그래프(Neo4j)에서 영문 질환 데이터를 조회합니다.
2. AI(OpenAI)가 Neo4j 참조 데이터를 기반으로 한국어 설명을 생성합니다.
3. Neo4j 미연결 또는 데이터 없음 시에도 AI 단독으로 결과를 반환합니다.
4. OpenAI 호출 실패 시 Neo4j 원본 데이터를 가공하여 폴백 응답합니다.

---

## GET /search/diseases

**Query Parameter**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `q` | `string` | ✓ | 검색 키워드 (최소 1자). 한국어/영문 모두 지원 |

**Response**

```json
{
  "results": [
    {
      "name": "당뇨병",
      "description": "인슐린 분비 또는 기능 장애로 혈당이 만성적으로 높아지는 대사 질환입니다. 제1형과 제2형으로 구분되며, 제2형이 전체의 약 90%를 차지합니다.",
      "symptoms": ["잦은 소변", "과도한 갈증", "체중 감소", "피로감", "시력 저하"]
    },
    {
      "name": "고혈압",
      "description": "수축기 혈압 140mmHg 이상 또는 이완기 혈압 90mmHg 이상이 지속되는 상태입니다.",
      "symptoms": ["두통", "어지러움", "코피"]
    }
  ]
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `results` | `array` | 질환 결과 목록 (최대 5개). 결과 없으면 `[]` |
| `results[].name` | `string` | 질환명 (한국어) |
| `results[].description` | `string` | 질환 설명 (2~3문장) |
| `results[].symptoms` | `string[]` | 주요 증상 목록 |

---

## Neo4j 지식 그래프 구조

> Docker 이미지: `deundeun/medical-kg-neo4j:v1`
> 접속: `bolt://localhost:7687` (인증 없음)

### 노드 타입

| 레이블 | 설명 | 주요 속성 |
|--------|------|----------|
| `Disease` | 질환 | `name` (영문) |
| `Effect` | 증상/표현형 | `name` (영문) |
| `Drug` | 약물 | `name` (영문) |

### 관계 타입

| 관계 | 방향 | 설명 |
|------|------|------|
| `RELATION {type: "phenotype present"}` | Disease → Effect | 질환의 증상/표현형 |
| `RELATION {type: "drug used for treatment"}` | Disease → Drug | 치료 약물 |

---

## 서버 실행 시 Neo4j 컨테이너 필요

```bash
# Neo4j 컨테이너가 중지된 경우 재시작
docker start kg-neo4j

# 처음 실행하는 경우
docker run -d --name kg-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=none \
  deundeun/medical-kg-neo4j:v1
```

Neo4j 없이도 서버는 정상 실행되며, OpenAI 단독으로 검색 결과를 생성합니다.

---

## curl 예시

```bash
TOKEN="<access_token>"
BASE="http://localhost:8000/api/v1"

# 한국어 검색
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE/search/diseases?q=당뇨병" | jq

# 영문 검색
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE/search/diseases?q=diabetes" | jq

# 증상으로 검색
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE/search/diseases?q=고혈압" | jq
```

---

## 에러 코드

| HTTP | 상황 |
|------|------|
| 422 | `q` 파라미터 누락 또는 빈 문자열 |
| 401 | 인증 토큰 없음 또는 만료 |
