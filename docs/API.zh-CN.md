# Amaya 管理 API（v1）

> 基地址：`http://<ADMIN_HTTP_HOST>:<ADMIN_HTTP_PORT>`

## 鉴权

单一鉴权方式：
- Header: `Authorization: Bearer <ADMIN_AUTH_TOKEN>`
- 或 `X-Amaya-Token: <ADMIN_AUTH_TOKEN>`
- Web 管理台登录页也是输入同一个 `ADMIN_AUTH_TOKEN`

## 健康检查

- `GET /healthz`：文本 `ok`
- `GET /health`：JSON 健康状态（无需鉴权）
- `GET /healthy`：JSON 健康状态（无需鉴权，兼容路径）
- `GET /api/v1/health`：JSON 运行状态、数据库连接、重启/关闭标记（无需鉴权）
- `GET /api/v1/auth/check`：校验 Token 是否有效

## 基础数据读取

- `GET /api/v1/overview`
- `GET /api/v1/users?limit=50&offset=0`
- `GET /api/v1/messages?user_id=&limit=50&offset=0`
- `GET /api/v1/reminders?user_id=&status=&limit=50&offset=0`
- `GET /api/v1/memory/groups?user_id=&limit=100&offset=0`
- `GET /api/v1/memory/points?memory_group_id=&user_id=&limit=100&offset=0`

## 日志读取

- `GET /api/v1/logs?lines=200&level=&stream=main`
- `stream=error` 时读取 `*_error.log`

## WebHook 预留

- `POST /api/v1/webhooks/{source}`
- 若设置 `WEBHOOK_SHARED_SECRET`，需 Header: `X-Amaya-Webhook-Secret`
- 未设置时走管理员鉴权
- 数据会保存到 `data/webhooks/{source}.jsonl`

## 远程操作

- `POST /api/v1/admin/restart`
- `POST /api/v1/admin/shutdown`

请求体示例：

```json
{
  "reason": "web-admin"
}
```

## Web 管理界面

- 登录页：`/admin/login`
- 管理台：`/admin`
