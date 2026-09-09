# 部署

## 单机模式（个人，v0.1 第一形态）
```bash
# 目标：一条命令（开发中）
curl -fsSL https://raw.githubusercontent.com/RavenWangChina/yuanzhu/main/deploy/install-standalone.sh | bash
# 或 Docker
docker compose -f deploy/docker-compose.standalone.yml up -d
```

## 企业模式（server + edge）
```bash
# 服务器：中控
docker compose -f deploy/docker-compose.server.yml up -d
# 办公电脑：边缘代理（dsh 插件）
dsh plugin install yuanzhu-edge
```
