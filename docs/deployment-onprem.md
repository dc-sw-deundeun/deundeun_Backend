# deundeun 온프레미스 배포·CD 가이드

> 마지막 업데이트: 2026-06-28  
> 대상: Rocky Linux 10.1 단일 서버 · Cloudflare DNS only · `develop` 브랜치 스테이징 배포

이 문서는 **deundeun 백엔드**를 온프레미스(홈) 서버에 배포하고 GitHub Actions CD와 연결하기 위한 **팀 공유 설정서**입니다.  
레포의 workflow·스크립트 계약은 [README.md](../README.md#cicd-파이프라인)와 동일합니다.

---

## 1. 현재 범위 (Phase)

| 항목 | 현재 결정 |
|------|-----------|
| 배포 대상 | **`develop` 브랜치 → 스테이징** (`deploy-develop.yml`) |
| 프로덕션 (`main`) | **아직 사용하지 않음** — `ENABLE_PRODUCTION_DEPLOY` 미설정 또는 `false` |
| API 도메인 | **`api.deundeun.xyz`** (Nginx 구성 후) |
| SSH 도메인 | **`deundeun.xyz`** (공유기 포트포워딩용) |
| 서버 | **1대** (스테이징/프로덕션 분리 없음) |

---

## 2. 인프라 요약

| 항목 | 값 |
|------|-----|
| OS | **Rocky Linux 10.1** |
| 사설 IP | **`172.30.1.77`** (집 LAN) |
| 공인 IP | **`211.51.96.127`** (예시 — DNS A 레코드 대상) |
| 관리자 계정 | `jangwoojung` (sudo · wheel) |
| 배포 전용 계정 | `deploy` (sudo 없음 · `docker` 그룹만) |
| **서버 sshd 포트** | **`22`** *(sshd가 listen)* |
| **외부 SSH 포트** | **`22222`** *(공유기 NAT)* |
| NAT | **외부 22222 → 내부 172.30.1.77:22** |
| Cloudflare | **Proxy OFF** (DNS only) |
| Cloudflare Tunnel | **미사용** |
| Reverse proxy | **Compose nginx** (`deundeun-nginx`, :80 → api:8000) |
| Database | **Compose Postgres** (`deundeun-postgres`, api 컨테이너는 `postgres:5432`로 접속) |
| 방화벽 (서버) | **22**(ssh), **80**, **443** |
| Docker Hub | `deundeun/backend` |
| Docker Engine | Rocky 공식 repo 아님 → [Docker CE `rhel` repo](#61-docker-ce-rocky-linux-101) |

### SSH·NAT (중요)

```
[외부 / GitHub Actions]
  deundeun.xyz:22222  ──▶  공유기 NAT  ──▶  172.30.1.77:22  ──▶  sshd

[집 내부망]
  172.30.1.77:22  ──▶  sshd (NAT 우회)
```

- **sshd는 Port 22만 listen** — `Port 22222`로 바꾸면 NAT와 어긋나 외부 접속 `Connection refused` 발생
- Mac·GitHub Actions는 **접속 포트 22222** (공유기 바깥 포트)
- `DEPLOY_PORT` Secret = **`22222`**

### Mac SSH 키

| 키 파일 | 계정 | 용도 | passphrase |
|---------|------|------|------------|
| `~/.ssh/homeserver_ed25519` | `jangwoojung` | 사람이 서버 관리 | **있음** |
| `~/.ssh/deundeun_deploy` | `deploy` | GitHub Actions CD | **없음** |

### 아직 미정

| 항목 | 메모 |
|------|------|
| **SMTP·Clova OCR** | 스테이징 `/opt/deundeun/.env`에 실제 secret 주입 |

---

## 3. Mac `~/.ssh/config`

관리자 Mac에 아래 Host가 설정되어 있습니다.

```sshconfig
Host homeserver
    HostName deundeun.xyz
    User jangwoojung
    Port 22222
    IdentityFile ~/.ssh/homeserver_ed25519
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3

Host homeserver-deploy
    HostName deundeun.xyz
    User deploy
    Port 22222
    IdentityFile ~/.ssh/deundeun_deploy
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3

Host homeserver-internal
    HostName 172.30.1.77
    User jangwoojung
    Port 22
    IdentityFile ~/.ssh/homeserver_ed25519
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

| 명령 | 용도 |
|------|------|
| `ssh homeserver` | 외부/도메인으로 **관리자** 접속 |
| `ssh homeserver-deploy` | **deploy** 접속 (CD와 동일 경로) |
| `ssh homeserver-internal` | 집 LAN에서 **관리자** 직접 접속 |

파일 복사 예:

```bash
# deundeun_Backend 디렉터리에서
scp scripts/deploy.sh homeserver-deploy:/opt/deundeun/deploy.sh
scp docker/docker-compose.yml homeserver-deploy:/opt/deundeun/docker-compose.yml
```

---

## 4. GitHub Secrets — `DEPLOY_SSH_KEY` 등록 방법

GitHub Actions가 서버에 SSH로 접속하려면 **deploy 개인키**를 Repository Secret으로 등록해야 합니다.

### 4.1 개인키 내용 복사 (Mac)

```bash
cat ~/.ssh/deundeun_deploy
```

아래 형태 **전체**를 복사합니다 (`-----BEGIN` ~ `-----END` 포함).

```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAAB...
...
-----END OPENSSH PRIVATE KEY-----
```

> **`.pub` 파일이 아닙니다.** `deundeun_deploy` (확장자 없는 개인키) 입니다.  
> `homeserver_ed25519` (passphrase 있음)는 Actions에 넣지 않습니다.

### 4.2 GitHub 웹 UI에서 등록

1. 브라우저에서 **deundeun_Backend** GitHub 레포지토리 열기  
2. 상단 **Settings** (레포 설정 — 계정 설정 아님)  
3. 왼쪽 **Secrets and variables** → **Actions**  
4. **Secrets** 탭 → **New repository secret**  
5. 아래 표대로 Secret 추가

| Name | Secret 값 |
|------|-----------|
| `DEPLOY_SSH_KEY` | `cat ~/.ssh/deundeun_deploy` 출력 **전체** |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_PORT` | `22222` |
| `DEPLOY_HOST_STAGING` | `deundeun.xyz` |
| `DOCKERHUB_USERNAME` | Docker Hub ID *(이미 등록)* |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token *(이미 등록)* |

경로 요약:

```
GitHub 레포 → Settings → Secrets and variables → Actions → Secrets → New repository secret
```

### 4.3 Variables (같은 Settings 페이지 · Variables 탭)

| Name | Value |
|------|-------|
| `ENABLE_STAGING_DEPLOY` | `true` *(수동 배포 테스트 **후** 켜기)* |
| `REGISTRY_IMAGE` | `deundeun/backend` *(기본값 그대로 가능)* |

`ENABLE_PRODUCTION_DEPLOY`는 **당분간 설정하지 않음**.

### 4.4 등록 확인

1. Mac에서 deploy SSH 성공:

   ```bash
   ssh homeserver-deploy
   ```

2. GitHub **Actions** → **Deploy (develop -> staging)** workflow 수동 실행은 없음 — `develop` merge 후 CI 통과 시 자동 실행

Secret 등록만으로는 테스트 안 됨. **로컬 deploy SSH + 수동 `deploy.sh`** 먼저 성공 후 `ENABLE_STAGING_DEPLOY=true`.

---

## 5. 아키텍처

### 5.1 CD 배포 흐름

```
feature/* ──PR──▶ develop
                    │
                    ▼ CI 통과 (ci.yml)
              deploy-develop.yml
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  Docker Hub push          SSH deploy@deundeun.xyz:22222
  :develop, :sha-xxxx      (NAT → 서버 :22)
        │                       │
        └───────────┬───────────┘
                    ▼
         bash /opt/deundeun/deploy.sh deundeun/backend:sha-xxxx
                    │
                    ▼
          compose postgres → migrate → api → nginx
```

### 5.2 API (Compose nginx)

```
클라이언트 → api.deundeun.xyz:80 → nginx (compose) → api:8000 (deundeun-api)
                                      │
                                      └→ postgres:5432 (compose 내부 네트워크)
```

HTTPS(:443)는 certbot 인증서 마운트 후 compose에 443 포트 추가 (추후).
nginx 설정은 `docker/nginx/templates/api.conf.template`를 컨테이너 시작 시 envsubst로 렌더링합니다.

---

## 6. Rocky Linux 서버 준비

### 6.1 Docker CE (Rocky Linux 10.1)

기본 `dnf install docker` 는 **패키지 없음**. Docker 공식 **rhel** repo 사용:

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# minimal 설치 시 네트워크 모듈
sudo dnf install -y kernel-modules-extra
sudo modprobe xt_addrtype

sudo systemctl enable --now docker
sudo usermod -aG docker deploy
sudo usermod -aG docker jangwoojung
```

### 6.2 `deploy` 사용자

```bash
sudo useradd -m -s /bin/bash deploy
sudo passwd -l deploy                    # 비밀번호 로그인 차단
sudo usermod -aG docker deploy
# wheel 그룹에 넣지 않음
```

### 6.3 deploy SSH 공개키 등록

Mac:

```bash
cat ~/.ssh/deundeun_deploy.pub
```

서버 (`ssh homeserver` 로 접속 후):

```bash
sudo install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
sudo tee /home/deploy/.ssh/authorized_keys << 'EOF'
ssh-ed25519 AAAA... deundeun_deploy.pub 한 줄 붙여넣기
EOF
sudo chmod 600 /home/deploy/.ssh/authorized_keys
sudo chown deploy:deploy /home/deploy/.ssh/authorized_keys
sudo restorecon -Rv /home/deploy/.ssh
```

확인:

```bash
ssh homeserver-deploy
whoami    # deploy
docker ps
```

### 6.4 sshd hardening (`/etc/ssh/sshd_config.d/10-hardening.conf`)

**Port 22** (NAT와 일치):

```bash
sudo tee /etc/ssh/sshd_config.d/10-hardening.conf << 'EOF'
# deundeun SSH hardening — sshd listen :22 / 공유기 외부 :22222

Port 22

PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
PermitEmptyPasswords no
KbdInteractiveAuthentication no

AllowUsers jangwoojung deploy

MaxAuthTries 3
LoginGraceTime 30
MaxSessions 10
MaxStartups 10:30:100

X11Forwarding no
AllowTcpForwarding no
PermitTunnel no
GatewayPorts no

ClientAliveInterval 300
ClientAliveCountMax 2

PrintMotd no
EOF

sudo sshd -t && sudo systemctl restart sshd
sudo ss -tlnp | grep ':22 '
```

> `Port 22222` 로 설정하지 마세요. 외부 22222는 **공유기**가 22로 넘깁니다.  
> SELinux `semanage port 22222` 는 sshd에 **불필요** (sshd는 22 사용).

### 6.5 firewalld · fail2ban

```bash
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

sudo dnf install -y fail2ban fail2ban-systemd
sudo tee /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
port    = ssh
filter  = sshd
logpath = /var/log/secure
maxretry = 5
bantime  = 1h
findtime = 10m
EOF
sudo systemctl enable --now fail2ban
```

### 6.6 배포 디렉터리

```bash
sudo mkdir -p /opt/deundeun
sudo chown deploy:deploy /opt/deundeun
```

Mac (`deundeun_Backend`):

```bash
scp scripts/deploy.sh homeserver-deploy:/opt/deundeun/deploy.sh
scp docker/docker-compose.yml homeserver-deploy:/opt/deundeun/docker-compose.yml
scp -r docker/nginx homeserver-deploy:/opt/deundeun/nginx
scp .env.server.example homeserver-deploy:/opt/deundeun/.env.example
ssh homeserver-deploy 'chmod +x /opt/deundeun/deploy.sh'
```

서버에서 최초 1회:

```bash
ssh homeserver-deploy
cp /opt/deundeun/.env.example /opt/deundeun/.env
chmod 600 /opt/deundeun/.env
vi /opt/deundeun/.env   # secret/password/도메인 값을 실제 값으로 교체
```

Compose 스택: **postgres** + **api** + **nginx**. `api`·`nginx`는 `--profile deploy`에 포함되며, `deploy.sh`가 `postgres → migration → api → nginx` 순서로 기동합니다.

---

## 7. 서버 `.env` (`/opt/deundeun/.env`)

[`.env.server.example`](../.env.server.example)을 `/opt/deundeun/.env`로 복사한 뒤 실제 secret을 채웁니다.
이 파일 하나가 두 역할을 합니다.

- `docker compose --env-file /opt/deundeun/.env`: compose 변수 보간(`IMAGE_TAG`, `POSTGRES_*`, `NGINX_*`)에 사용
- `api.env_file: /opt/deundeun/.env`: FastAPI 컨테이너 환경변수(`DATABASE_URL`, `JWT_SECRET_KEY`, `CLOVA_*`)로 주입
- `nginx.environment`: nginx template 렌더링 변수(`NGINX_SERVER_NAME`, `NGINX_UPSTREAM_*`)로 주입

핵심 값:

```bash
APP_ENV=staging
APP_ENV_FILE=/opt/deundeun/.env
IMAGE_TAG=deundeun/backend:develop

# Compose 경로 (compose 파일이 /opt/deundeun/docker-compose.yml일 때)
NGINX_CONF_DIR=/opt/deundeun/nginx
NGINX_HTTP_PORT=80
NGINX_SERVER_NAME=api.deundeun.xyz
NGINX_UPSTREAM_HOST=api
NGINX_UPSTREAM_PORT=8000
POSTGRES_BIND=127.0.0.1
POSTGRES_PORT=5432
API_HOST_BIND=127.0.0.1
API_HOST_PORT=8000

# api 컨테이너 → postgres 서비스 (호스트명 postgres)
DATABASE_URL=postgresql+psycopg2://deundeun:<POSTGRES_PASSWORD>@postgres:5432/deundeun
JWT_SECRET_KEY=<openssl rand -hex 32>

CORS_ALLOW_ORIGINS=["https://<frontend-domain>"]
TRUSTED_PROXY=true
TRUSTED_PROXY_CIDRS=["172.16.0.0/12","10.0.0.0/8"]

# staging 기동 필수 (config.py 검증)
CLOVA_OCR_INVOKE_URL=...
CLOVA_OCR_SECRET_KEY=...
```

> `POSTGRES_PASSWORD`와 `DATABASE_URL`의 비밀번호를 **동일**하게 맞춥니다.  
> `/opt/deundeun/.env`는 서버에만 두고 Git에 커밋하지 않습니다.
> 로컬 저장소의 `.env`, `.env.server`는 `.gitignore` 대상입니다. 실제 secret이 들어간 파일은 문서나 커밋에 포함하지 않습니다.
> `.env.server.example`의 `change-me`·빈 Clova 값은 의도적으로 앱 기동 검증을 실패시키는 기본값입니다. 실제 값으로 바꾼 뒤 배포합니다.
> `CORS_ALLOW_ORIGINS`에는 API 주소가 아니라 브라우저가 열린 프론트엔드 origin을 JSON 배열로 넣습니다. 예: `["https://app.deundeun.xyz","http://localhost:5173"]`.

서버에서 compose 렌더링 확인:

```bash
docker compose --env-file /opt/deundeun/.env \
  -f /opt/deundeun/docker-compose.yml --profile deploy config
```

---

## 8. 배포 검증 순서

### 8.1 최초 Postgres 기동

```bash
ssh homeserver-deploy
docker compose --env-file /opt/deundeun/.env \
  -f /opt/deundeun/docker-compose.yml up -d postgres
docker ps
```

### 8.2 수동 API + Nginx 배포

```bash
bash /opt/deundeun/deploy.sh deundeun/backend:develop
curl -s http://127.0.0.1:8000/health
curl -s -H 'Host: api.deundeun.xyz' http://127.0.0.1/health
```

### 8.3 CD 활성화

1. 위 수동 배포·health 성공
2. GitHub Secrets 등록 (4절)
3. Variable `ENABLE_STAGING_DEPLOY=true`
4. `develop` merge → Actions **Deploy (develop -> staging)** 확인

---

## 9. 스테이징 자동 vs 프로덕션 수동 승인

| | 스테이징 (develop) | 프로덕션 (main) |
|--|-------------------|-----------------|
| 현재 | **자동 배포 예정** | **비활성** |
| Variable | `ENABLE_STAGING_DEPLOY=true` | 미설정 |

---

## 10. 체크리스트

### 서버

- [ ] Docker CE 설치 · `deploy` ∈ docker 그룹
- [ ] `/opt/deundeun` + `deploy.sh` · `docker-compose.yml` · `.env`
- [ ] sshd **Port 22** · `AllowUsers jangwoojung deploy`
- [ ] `deploy` `authorized_keys` ← `deundeun_deploy.pub`
- [ ] `ssh homeserver-deploy` 성공

### GitHub

- [ ] Secret `DEPLOY_SSH_KEY` ← `deundeun_deploy` **개인키 전체**
- [ ] Secret `DEPLOY_USER`=`deploy`, `DEPLOY_PORT`=`22222`, `DEPLOY_HOST_STAGING`=`deundeun.xyz`
- [ ] Variable `ENABLE_STAGING_DEPLOY=true` (수동 배포 후)

### Mac

- [ ] `~/.ssh/config` — `homeserver`, `homeserver-deploy`, `homeserver-internal`
- [ ] `ssh homeserver` / `ssh homeserver-deploy` 동작

---

## 11. 관련 파일

| 파일 | 역할 |
|------|------|
| [`.github/workflows/deploy-develop.yml`](../.github/workflows/deploy-develop.yml) | develop → push + SSH 배포 |
| [`scripts/deploy.sh`](../scripts/deploy.sh) | 서버 배포 스크립트 |
| [`docker/docker-compose.yml`](../docker/docker-compose.yml) | Compose (`--profile deploy`) |
| [`docker/nginx/templates/api.conf.template`](../docker/nginx/templates/api.conf.template) | nginx envsubst template |
| [`.env.server.example`](../.env.server.example) | `/opt/deundeun/.env` 서버 템플릿 |

---

## 12. 트러블슈팅

| 증상 | 원인 | 조치 |
|------|------|------|
| 외부 `Connection refused` | sshd가 22222 listen | **`Port 22`** 로 변경 |
| `Permission denied (publickey)` deploy | `authorized_keys` 불일치 | `deundeun_deploy.pub` 재등록 |
| `Permission denied` jangwoojung | Mac에 `-i homeserver_ed25519` 필요 | `ssh homeserver` 사용 |
| sshd restart SELinux | (Port 22222 썼을 때) `name_bind denied` | **Port 22** 사용 |
| 집에서 공인 IP 접속 실패 | NAT hairpin | `homeserver-internal` 또는 `deundeun.xyz` |
| nginx 502 | api healthcheck 실패 또는 `NGINX_UPSTREAM_*` 불일치 | `docker compose logs api nginx` 확인 |
| nginx 설정 미반영 | `/opt/deundeun/nginx/templates` 누락 | `scp -r docker/nginx homeserver-deploy:/opt/deundeun/nginx` 재실행 |

복구: Cockpit `https://172.30.1.77:9090/` 또는 `ssh homeserver-internal` (LAN).
