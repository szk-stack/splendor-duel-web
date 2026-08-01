# 项目规范

## 架构

- **服务端权威**：所有游戏规则逻辑只在 `server/engine/`（纯 Python，无 I/O）。客户端纯视图，不做任何规则推演。
- **单 worker**：房间状态在进程内存，uvicorn 必须 `--workers 1`。
- **全量同步**：每步行动后向双方广播全量 GameState，不做 diff。

## 修改纪律

1. **规则数值**：所有游戏数值必须定义在 `server/engine/data/*.json`（rules.json / tokens.json / cards_*.json / nobles.json），引擎代码禁止出现魔法数字。改规则 = 改 JSON + 改 `docs/rules.md`。
2. **协议三处同步**：`server/app/protocol.py` ↔ `docs/protocol.md` ↔ `web/src/types.ts`，改消息协议必须同时改三处。
3. **序列化**：GameState 用 `to_dict/from_dict` 手写序列化，字段名冻结，禁止 `__dict__`/`asdict` 直传，禁止序列化 token/secret。
4. **随机性**：引擎通过构造函数注入 `random.Random(seed)`，引擎内不直接 `import random`。
5. **中文路径**：项目根目录 `D:\project\璀璨宝石` 含中文。Python/Vite 一般兼容；若 npm 或构建工具异常，开发环境可放 ASCII 路径，服务器部署无此问题。

## 常用命令

```bash
# 后端测试
cd server && .venv/Scripts/python -m pytest

# 后端启动（开发）
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# 前端启动（开发）
cd web && npm run dev

# 前端构建
cd web && npm run build
```
