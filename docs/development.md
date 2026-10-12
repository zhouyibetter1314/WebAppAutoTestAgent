# 开发与环境

## 环境锁定

Python 3.13.16（uv 0.13.0）；Node 24.21.0；pnpm 12.11.2。Python 使用 `uv sync --frozen --all-groups`，前端使用 `pnpm --dir frontend install --frozen-lockfile`。不要手动更新子模块或跳过锁文件。

本机 uv 安装在 `.tools/bin/uv`，新终端可先将该目录加入 PATH。需要镜像源时由成员自行配置；不将私有 registry 凭据写入仓库。

## Docker 与目标应用

Docker 是系统级依赖，初始化脚本不擅自修改系统。Linux 根据 [Docker 官方安装文档](https://docs.docker.com/engine/install/) 安装 Engine 与 Compose 插件；macOS/Windows 使用 Docker Desktop。确认当前用户能执行 `docker info` 和 `docker compose version`。当前实施机器缺少 daemon 且 sudo 需要交互认证，因此容器启动仍需实机复核。

```bash
uv run waat targets up      # 固定源码构建，首次启动自动数据库迁移和种子初始化
uv run waat targets status  # 健康状态
uv run waat targets stop    # 停止但保留数据
uv run waat targets reset   # 明确确认后，仅删除 waat-boards 数据卷
```

- 4gaBoards：127.0.0.1:3000；数据库不发布宿主端口；上游默认账号 demo/demo。
- 使用 `targets/versions.json` 与 `infra/images.json` 保存 SHA/镜像摘要。构建直接使用上游 client/server package-lock.json 的 `npm ci`。
- 本地测试密码只用于此隔离环境，不能部署到公网。
- `reset` 会清空本项目测试数据；在课程允许的独立初始状态中评测，避免同名项目影响验收。
- Admidio 5.0.2：后续配置 PHP/Web server + 数据库及安装向导/种子账号，部署文件放 infra，不能改子模块。
- Discourse：后续提供与固定提交匹配的 Ruby/PostgreSQL/Redis/JS 环境和管理员种子；目前仅固定源码，不宣称已可运行。

## 模型与浏览器

复制 `.env.example` 为 `.env`。密钥仅保存在本机；前端只看到是否配置。`WAAT_API_MODEL=deepseek-flash` 对应课程要求的版本映射需要在正式评测前查 [官方更新](https://api-docs.deepseek.com/updates/)。报告保存请求/返回模型名、服务地址与时间。

默认使用 Playwright 下载的 Chromium；可通过 `WAAT_BROWSER_EXECUTABLE=/usr/bin/google-chrome` 使用本机 Chrome。后者版本由本机管理，正式评测优先使用锁文件对应的 Playwright 浏览器。

Web 后端需单进程运行；不启用多 worker。运行锁锁住整个数据目录。CLI 连接已启动服务使用 `--server http://127.0.0.1:8000`。任务在服务重启后标记中断，不重放浏览器副作用。

## API 类型和数据库

```bash
uv run python scripts/export_openapi.py
pnpm --dir frontend generate:api
pnpm --dir frontend format
```

类型由 FastAPI 的序列化 schema 生成，禁止手改 `frontend/src/schema.d.ts`。数据库启动时持锁执行 Alembic upgrade head；新迁移放包内 migrations/versions，不能修改已发布迁移。当前采用有索引的 JSON 记录与独立事件表，后续可迁移到拆分表。

## 调试与批量

CLI `batch` 输入为 `examples/create_project.json` 相同结构的数组；GUI 导入使用已有 application_id 的 ScenarioInput 数组。当前批量任务在单进程中顺序排队，取消某次运行不影响其他任务。

CLI 退出码 0=全部 PASS，1=包含 FAIL，2=无法判定或基础设施异常。这是应用测试结论，不是课程评测得分。

## 汇报和真实验收

Ubuntu 可安装 `texlive-xetex texlive-lang-chinese texlive-latex-extra latexmk`。`uv run waat report build` 生成 report/build/main.pdf。

```bash
WAAT_LIVE=1 uv run pytest -v -m live
```

没有 API Key 时真实测试明确跳过；不应把 skipped 视为通过。GitHub 手动工作流使用 `live-test` environment 的 `DEEPSEEK_API_KEY` secret，并创建独立的 4gaBoards 环境。运行前确认模型调用预算，上传证据仅保留 7 天。
