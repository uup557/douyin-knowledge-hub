# 部署指南

## 环境要求

### 系统要求

- **操作系统**: Ubuntu 20.04+ / macOS 10.15+ / Windows 10+
- **Python**: 3.10+
- **内存**: 1 GB+
- **磁盘**: 500 MB+
- **网络**: 稳定连接

### 依赖服务

- **抖音 API**: 需要有效的抖音 Cookie
- **AI 服务**: MiMo API 或其他 AI 服务

## 快速部署

### 1. 克隆项目

```bash
git clone https://github.com/uup557/douyin-knowledge-hub.git
cd douyin-knowledge-hub
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置项目

```bash
# 复制配置文件
cp config/config.example.yaml config/config.yaml

# 编辑配置文件
nano config/config.yaml
```

### 5. 启动服务

```bash
python -m src.main
```

## 详细配置

### 抖音 Cookie 配置

#### 获取 Cookie

1. 在浏览器登录抖音网页版
2. 打开开发者工具 (F12)
3. 切换到 Network 选项卡
4. 刷新页面，找到任意请求
5. 复制 Request Headers 中的 Cookie 值

#### 配置文件

```yaml
douyin:
  cookie: "ttwid=xxx; msToken=yyy; ..."
  target_account: "小号抖音ID"
  check_interval: 3600  # 检查间隔（秒）
  max_retries: 3  # 最大重试次数
```

### AI 分析配置

#### MiMo API 配置

```yaml
ai:
  provider: "mimo"
  api_key: "你的API密钥"
  model: "mimo-v2.5"
  max_tokens: 1000
  temperature: 0.7
```

#### 其他 AI 服务

```yaml
ai:
  provider: "openai"  # 或 "anthropic", "local"
  api_key: "你的API密钥"
  model: "gpt-4"
```

### 数据库配置

```yaml
database:
  path: "data/knowledge.db"
  backup_interval: 86400  # 备份间隔（秒）
  max_backups: 7  # 最大备份数
```

## Docker 部署

### 构建镜像

```bash
docker build -t douyin-knowledge-hub .
```

### 运行容器

```bash
docker run -d \
  --name douyin-kb \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  douyin-knowledge-hub
```

### Docker Compose

```yaml
version: '3.8'

services:
  douyin-kb:
    build: .
    container_name: douyin-knowledge-hub
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
      - ./data:/app/data
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

```bash
docker-compose up -d
```

## 生产环境部署

### 使用 systemd 服务

```bash
# 创建服务文件
sudo nano /etc/systemd/system/douyin-kb.service
```

```ini
[Unit]
Description=Douyin Knowledge Hub
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/douyin-knowledge-hub
ExecStart=/home/ubuntu/douyin-knowledge-hub/venv/bin/python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 启用并启动服务
sudo systemctl enable douyin-kb
sudo systemctl start douyin-kb

# 查看状态
sudo systemctl status douyin-kb
```

### 使用 PM2 (Node.js 进程管理)

```bash
# 安装 PM2
npm install pm2 -g

# 启动服务
pm2 start "python -m src.main" --name douyin-kb

# 查看状态
pm2 status

# 查看日志
pm2 logs douyin-kb
```

## 监控和维护

### 日志查看

```bash
# 查看实时日志
tail -f logs/app.log

# 查看错误日志
grep ERROR logs/app.log
```

### 数据备份

```bash
# 手动备份
cp data/knowledge.db data/knowledge.db.backup.$(date +%Y%m%d)

# 自动备份 (cron)
0 2 * * * cp /home/ubuntu/douyin-knowledge-hub/data/knowledge.db /backup/knowledge.db.$(date +\%Y\%m\%d)
```

### 性能监控

```bash
# 查看进程
ps aux | grep python

# 查看内存使用
free -h

# 查看磁盘使用
df -h
```

## 故障排查

### 常见问题

#### 1. Cookie 过期

**症状**: 无法获取视频数据

**解决**:
```bash
# 重新获取 Cookie
# 编辑配置文件
nano config/config.yaml

# 重启服务
sudo systemctl restart douyin-kb
```

#### 2. 内存不足

**症状**: 服务频繁重启

**解决**:
```bash
# 查看内存使用
free -h

# 增加 swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### 3. 磁盘空间不足

**症状**: 无法写入数据

**解决**:
```bash
# 清理旧数据
find data/ -name "*.log" -mtime +30 -delete

# 清理缓存
rm -rf cache/*
```

#### 4. 网络连接问题

**症状**: API 调用失败

**解决**:
```bash
# 检查网络连接
ping google.com

# 检查 DNS
nslookup api.douyin.wtf

# 检查防火墙
sudo ufw status
```

## 更新部署

```bash
# 拉取最新代码
git pull origin main

# 更新依赖
pip install -r requirements.txt --upgrade

# 重启服务
sudo systemctl restart douyin-kb
```

## 卸载

```bash
# 停止服务
sudo systemctl stop douyin-kb
sudo systemctl disable douyin-kb

# 删除服务文件
sudo rm /etc/systemd/system/douyin-kb.service

# 删除项目
rm -rf /home/ubuntu/douyin-knowledge-hub
```
