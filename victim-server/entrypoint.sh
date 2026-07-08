#!/usr/bin/env bash
# 세 개의 취약 서비스(웹 GCS / MAVLink / SATCOM / 스웜 노드)를 한 컨테이너에서 기동
set -e
cd /app
echo "[victim] initializing GCS database..."
python -c "import app; app.init_db()"

echo "[victim] starting MAVLink UAV sim (udp/14550)"
python mavlink_sim.py &

echo "[victim] starting SATCOM link sim (tcp/5600)"
python satcom_sim.py &

echo "[victim] starting swarm node (MQTT subscriber)"
python swarm_node.py &

echo "[victim] starting GCS web dashboard (tcp/8080)"
exec python app.py
