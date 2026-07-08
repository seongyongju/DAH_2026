# DAH 2026 — 유무인 복합체계(MUM-T) 신뢰 전파 공격과 자립형 AI 공방 에이전트

Defense AI Cyber Security Hackathon 2026 예선 부가자료. 방산 무인체계(UAV·UGV·위성통신·
군집)의 **신뢰 전파(Trust Propagation)** 위협을 정식화하고, 이에 대응하는 **탐지·차단·복구
방어 아키텍처**를 **자립형 RL 코어 + 선택적 LLM 상위계층(하이브리드)** 으로 구현·실증한다.

> ⚠️ 학습·경진대회용. 프로토콜 랩은 **인터넷과 격리된 환경**에서만 실행할 것.
> 실제 무기체계가 아닌 디지털 트윈/시뮬레이션이다.

## 두 개의 실험 트랙

| 트랙 | 위치 | 내용 | 의존성 |
|------|------|------|--------|
| **A. MUM-T 시뮬레이션 + RL** (핵심) | `src/` | 신뢰 전파 COP 방어의 탐지·차단·복구 메커니즘을 RL 자가대전으로 실증 | numpy, scikit-learn (외부 API·키·클라우드 0) |
| **B. 프로토콜 취약 랩 + 하이브리드 LLM** | `victim-server/` `attacker/` `agents/` | 5개 프로토콜 위협(L1~L5)을 Docker/Kali로 재현, 교체형 LLM Blue 에이전트가 탐지·차단·복구 | Docker, (선택) LLM provider |

두 트랙은 상호보완적이다. A는 **방어 메커니즘의 성립 조건**을 분석하고, B는 **프로토콜
수준 위협의 구체적 재현**과 하이브리드의 **LLM 상위계층**을 검증한다.

## 트랙 A — MUM-T 시뮬레이션 (자립형 RL)

```bash
pip install -r src/requirements.txt        # numpy, scikit-learn
python3 -m src.match.run_all               # 보고서 §5·§6 전체 수치 재생산
```

개별 실험:
```bash
python3 -m src.match.it_vs_defense     # 가용성 곱셈 계수: IT식 차단의 자멸(유효방어 0)
python3 -m src.match.realistic_eval    # 현실 모델 무결성/가용성 (resilient 94.6% 등)
python3 -m src.match.coverage          # 설계 밖 경로 일반화
python3 -m src.agents.self_play        # 자가대전 → (creep, resilient) 균형
python3 -m src.agents.adaptive_self_play  # 반응형 방어 정책 학습
python3 -m src.agents.orchestrator     # 적응형 공격 오케스트레이터(피벗)
python3 -m src.detector.gnss           # 신호레벨 탐지의 근본 한계(96%→7%)
python3 -m src.match.bench_latency     # RL 판단 지연(≈0.59µs, 10Hz 대비 16.9만배)
```

구성: `src/sim`(MUM-T 환경) · `src/agents`(오케스트레이터·RL·자가대전·반응형) ·
`src/detector`(GNSS 탐지기) · `src/match`(공방·커버리지·현실평가·벤치).

## 트랙 B — 프로토콜 취약 랩 (Docker/Kali + 하이브리드 LLM)

```bash
docker compose up --build              # 격리 랩 + 5라운드 공방(offline 기본, 키 불필요)
```

교체형 LLM 상위계층 선택(`AGENT_PROVIDER`):
```bash
AGENT_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-... docker compose run agents python3 orchestrator.py --rounds 5
AGENT_PROVIDER=claude-code docker compose run agents python3 orchestrator.py --rounds 5
AGENT_PROVIDER=gemini      docker compose run agents python3 orchestrator.py --rounds 5
AGENT_PROVIDER=codex       docker compose run agents python3 orchestrator.py --rounds 5
```

| provider | 백엔드 | 필요 |
|----------|--------|------|
| `anthropic` | Claude Opus 4.8 | `ANTHROPIC_API_KEY` |
| `claude-code`/`gemini`/`codex` | 각 CLI | 해당 도구 설치 |
| `offline` | 결정론(기본) | 없음 |

프로토콜 위협(L1~L5): L1 GCS 웹 SQLi/IDOR · L2 MAVLink 명령주입 · L3 SATCOM 재전송 ·
L4 펌웨어 OTA 변조 · L5 MQTT 스웜. Blue 에이전트 파이프라인: DETECT→DECIDE→BLOCK→RECOVER.

## 전체 구조

```
dah_2026/
├─ src/                         # 트랙 A: MUM-T 시뮬레이션 + 자립형 RL
│  ├─ sim/mumt.py               #   신뢰 전파 COP 환경
│  ├─ agents/                   #   qlearn · self_play · adaptive_self_play · orchestrator
│  ├─ detector/gnss.py          #   신호레벨 탐지 근본 한계(leave-one-type-out)
│  ├─ match/                    #   it_vs_defense · realistic_eval · coverage · bench_latency · run_all
│  └─ requirements.txt
├─ victim-server/               # 트랙 B: 지상통제소 취약 트윈(L1~L5)
├─ attacker/scenarios/          # 트랙 B: 프로토콜 공격 스크립트
├─ agents/                      # 트랙 B: 교체형 Blue/Red + orchestrator + providers
├─ docker-compose.yml · mosquitto.conf
└─ docs/DAH2026_예선보고서_본문_4-7.md   # 보고서 4~7장(병합본)
```

## 핵심 결과 (실측 요약)

- **가용성 곱셈 계수:** IT식 차단 유효방어 **0%**(자해) vs resilient **67.1%**.
- **팀 이중화 필수:** 지속 장악 시 zero_trust 단독 **38%** → +오버워치 **94.6%**.
- **가장 약한 지점(정직):** 은밀 크립 resilient **70.1%**.
- **자가대전 균형:** (공격=creep, 방어=resilient) 수렴.
- **신호레벨 탐지 한계:** 학습 유형 96% → 미학습 유형 **7.2%**.
- **RL 실시간성:** 판단당 **0.59µs**(10Hz 대비 16.9만배 여유).

수치는 모두 `src/` 스크립트 실제 실행 로그. 물리 파라미터는 모델링 가정, 탐지 성능과 현실
열화 요소는 실측 근거(§5.2, §5.7).
