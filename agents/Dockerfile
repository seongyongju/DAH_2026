# Kali Linux 기반 공격/방어 에이전트 컨테이너
# (실제 침투테스트 도구 + AI 에이전트 런타임을 함께 탑재)
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        nmap sqlmap hydra curl netcat-traditional iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/agents
COPY agents/requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# 시나리오 스크립트 + 에이전트 코드
COPY attacker /opt/attacker
COPY agents /opt/agents

ENV VICTIM_HTTP=http://victim:8080 \
    VICTIM_HOST=victim \
    MQTT_BROKER=mqtt \
    VICTIM_LOG_DIR=/logs \
    AGENT_MEMORY=/opt/agents/knowledge_base.json \
    AGENT_PROVIDER=offline

# 기본: 5라운드 공방 루프 (AGENT_PROVIDER 로 두뇌 선택; 기본 offline = 키 불필요)
CMD ["python3", "orchestrator.py", "--rounds", "5"]
