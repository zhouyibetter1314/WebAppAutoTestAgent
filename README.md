# WebAppAutoTestAgent

中文图形化 Web 自动测试工作台：输入自然语言场景，使用自主设计的 LangGraph 状态图驱动 Playwright，输出检查点、截图、Trace 和可追溯报告。Web 与 CLI 使用同一核心。

**当前状态：基础执行闭环已实现；真实 DeepSeek + 4gaBoards 验收尚未完成。** 本机未配置模型密钥、未安装可用 Docker daemon。离线测试使用确定性模拟模型与真实浏览器，不能作为真实模型成绩。教师的 5 个调试场景尚未获得。

## 快速开始

需要 Git、Node 24（`.node-version`）、pnpm 12.11.2。初始化脚本会安装项目内 uv、Python 3.13.16、依赖和浏览器，并安装 Git hooks。Linux 缺系统浏览器库时需执行 `uv run playwright install --with-deps chromium`（需要管理员权限）。

```bash
# 新成员从 GitHub 克隆后执行；当前项目尚未绑定远端
bash scripts/bootstrap.sh
export PATH="$PWD/.tools/bin:$PATH"
uv run waat doctor
uv run waat dev
```

工作台：<http://127.0.0.1:5173>，API 文档：<http://127.0.0.1:8000/docs>。不配置密钥也可管理场景与查看界面，启动真实运行时会明确提示缺少配置。

## 运行真实场景

1. 安装并启动 Docker Engine + Compose v2，确认 `docker info` 成功。
2. `.env` 填写 `DEEPSEEK_API_KEY`；默认应用账号为隔离测试环境的 demo/demo。
3. 执行以下命令。服务运行时 CLI 使用 `--server`，避免两个进程占用同一运行目录。

```bash
uv run waat targets up
uv run waat targets status
uv run waat run examples/create_project.json --server http://127.0.0.1:8000
# 或关闭后端，直接从 CLI 执行
uv run waat run examples/create_project.json
```

在界面中添加 `http://localhost:3000` 应用，再创建场景即可运行。使用固定 tag 的三个子模块；4gaBoards 配置使用源码构建和固定镜像摘要，未使用 latest。

## 常用开发入口

```bash
bash scripts/check.sh quick       # 类型检查和快速离线测试
bash scripts/check.sh all         # lint、构建与真实浏览器离线测试
bash scripts/check.sh format      # 统一格式化
pnpm --dir frontend test:e2e      # 工作台→API→模拟模型→真实浏览器
uv run cz commit                 # 交互式 Conventional Commits
uv run waat report build          # 中文 Beamer PDF
uv run waat report stats          # 仅真实执行记录的统计
```

`uv.lock`、前端 `pnpm-lock.yaml`、子模块 gitlink 均需提交。密钥、数据库、截图、Trace、浏览器状态与编译产物不提交。Trace 可能含页面敏感数据，分享报告前检查内容。

## 目录

| 目录 | 职责 |
| --- | --- |
| `src/webapp_auto_test_agent/` | 类型、模型适配器、浏览器、状态图、存储、API、CLI |
| `frontend/` | Vue 3 + TypeScript + Element Plus 工作台 |
| `tests/` | 核心、API、模型异常、浏览器与手动真实验收 |
| `targets/` | 3 个固定版本子模块与完整 SHA 清单 |
| `infra/` | 项目维护的 4gaBoards 构建与 Compose |
| `report/` | 中文 Beamer 源码与章节 |
| `docs/` | 架构、开发、验收与决策记录 |
| `.waat/` | 本机 SQLite 与运行证据，自动创建且忽略提交 |

详见 [开发指南](docs/development.md)、[架构](docs/architecture.md)、[验收记录](docs/acceptance.md)、[协作约定](CONTRIBUTING.md)。

迁移前的项目构想保留在 [原始项目说明](docs/original-project-notes.md)，当前目录和运行方式以本文为准。
