# README

项目分为三部分

- `init`：搭建项目所需初始化
    - 对 PostgreSQL 和 Timescaledb 的建表初始化
    - 对 minio 对象生命周期与 webhook 的配置
- `server`
    - 后端主体
- `terminal`
    - 边缘计算设备的相关前后端通信组件

## demo 运行

后端主体通过`python main.py`即可运行，在`terminal`目录下包含两个模拟型demo，需要以`python -m file`的形式运行。

- `python -m terminal.demo`模拟多个摄像头的WebRTC端，与后端建立连接，向前端发送模拟数据与摄像头画面
- `python -m terminal.alert_demo`模拟一次警报触发，自由设置警报触发时间，警告记录视频总时长（前后平分）

## 环境变量

项目通过`.env`文件配置环境变量

```bash
# ==========================
# Backend LLM API
API_BASE_URL=
API_KEY=

# Backend Database
PGSQL_HOST=localhost
PGSQL_PORT=5432
PGSQL_DB=postgres
PGSQL_USER=postgres
PGSQL_PASSWORD=

# Backend & Algo Minio Server
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
# ==========================


# ==========================
# Algo WebRTC Server
WEBRTC_SERVER_URL=ws://localhost:5000
WEBRTC_DATA_HISTORY_MAXLEN=200

# Backend & Algo Minio Server
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
# ==========================

```