# 部署指南（自有服务器 + 域名）

## 架构

```
浏览器 --HTTPS(443, wss)--> nginx -- /         -> web/dist 静态文件
                                 -- /api,/ws -> 127.0.0.1:8000 (uvicorn 单 worker)
```

## 步骤

```bash
# 1. 上传代码到服务器
rsync -av --exclude node_modules --exclude .venv --exclude .git ./ root@server:/opt/splendor/

# 2. 后端环境（Python 3.10+）
cd /opt/splendor/server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 若服务器网络访问 PyPI 受限（同开发机问题），用清华镜像：
# .venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 前端构建
cd /opt/splendor/web
npm ci && npm run build     # 产物在 web/dist

# 4. systemd 服务
cp /opt/splendor/deploy/systemd/splendor.service /etc/systemd/system/
# 按需修改 User 与路径（默认 www-data / /opt/splendor）
systemctl daemon-reload
systemctl enable --now splendor
curl http://127.0.0.1:8000/api/health   # 应返回 {"status":"ok"}

# 5. nginx
cp /opt/splendor/deploy/nginx/splendor.conf /etc/nginx/sites-available/
# 把配置文件中的 your.domain.com 替换为真实域名
ln -s /etc/nginx/sites-available/splendor.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 6. HTTPS（Let's Encrypt 自动续期）
apt install certbot python3-certbot-nginx
certbot --nginx -d your.domain.com
# certbot 自动续期由 systemd timer 处理，续期后自动 reload nginx
```

## 验证

```bash
curl -I https://your.domain.com/            # 200
curl https://your.domain.com/api/health     # {"status":"ok"}
```

浏览器打开两个窗口（普通 + 隐身）→ 创建房间 → 加入 → 完整对局。
DevTools Network 里确认 WS 握手返回 101、心跳帧（25s 一次）正常。

## 排障

| 症状 | 原因 | 处理 |
|---|---|---|
| WS 连接失败/反复重连 | nginx 缺 Upgrade 头或超时过短 | 检查 `/ws` location 的 `proxy_set_header Upgrade/Connection` 与 `proxy_read_timeout` |
| 页面 502 | uvicorn 未启动 | `systemctl status splendor`，`journalctl -u splendor -f` |
| 房间突然全部消失 | 服务重启（房间在内存） | 重启即清空房间，属预期行为 |
| 前端加载但 API 404 | nginx 没代理 `/api/` | 检查 location 与 proxy_pass |

## 已知限制

- **单 worker 必须**：房间状态在进程内存。多 worker 会随机路由导致房间不可达。
  扩展路径：Redis 存房间 + pub/sub 广播 + 粘性路由（超出当前范围）。
- 服务重启会清空所有进行中的房间（对局短，影响小）。
- 对局中刷新页面可自动重连（token 在 sessionStorage）；重连窗口 120s，超时后房间废弃。
