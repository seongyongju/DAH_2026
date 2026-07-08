FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x entrypoint.sh
# 8080 웹 / 14550 MAVLink(udp) / 5600 SATCOM(tcp)
EXPOSE 8080 5600 14550/udp
ENTRYPOINT ["./entrypoint.sh"]
