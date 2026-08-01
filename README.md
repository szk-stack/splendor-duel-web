# 璀璨宝石：对决（网页版）

双人桌游《璀璨宝石：对决》(Splendor Duel) 的网页版，支持两个真实玩家通过互联网实时对战。

## 技术栈

- **后端**：Python 3.10 + FastAPI + WebSocket（服务端权威，单 worker）
- **前端**：React 18 + Vite + TypeScript（纯视图，零规则逻辑）
- **部署**：nginx 反代 + HTTPS（用户自有服务器）

## 本地开发

```bash
# 后端（终端 1）
cd server
python -m venv .venv            # 或直接复用项目根 .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# 前端（终端 2）
cd web
npm install
npm run dev                     # http://localhost:5173
```

浏览器打开两个窗口（普通 + 隐身）→ 一个创建房间，另一个输入房间码加入，即可联机对战。

## 目录结构

```
docs/          规则文档（唯一事实来源）与协议文档
server/        FastAPI 后端：engine（纯规则引擎）+ app（服务层）
web/           React 前端
deploy/        nginx / systemd 部署配置
```

## 部署速查

见 `deploy/README.md`。
