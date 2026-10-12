# 基础验收记录

实施环境：Linux，Python 3.13.16 / uv 0.13.0，Node 24.21.0 / pnpm 12.11.2。原课程 PPT 保留。三个子模块的完整 SHA 已与实际 HEAD 核对。

| 项目 | 结果与范围 |
| --- | --- |
| 后端测试 | 16 项通过；1 项真实模型测试因未配置密钥/环境明确跳过 |
| 三种结论 | 使用确定性模型验证 PASS、FAIL、INCONCLUSIVE 报告分支 |
| 操作预算 | 初始导航和失败计数；第 36 次操作拒绝，仍可观察和保存 Trace |
| 失败收尾 | 定位失败、虚构证据、取消、整体超时、浏览器启动异常、无效模型 JSON、API 超时 |
| 持久化 | SSE 游标补读、API 重启读取历史、未完成任务中断、跨服务运行锁 |
| 前端 | TypeScript、ESLint、Prettier、单元测试与生产构建；真实浏览器端到端流程 |
| 提交规范 | 实际 commit-msg 钩子拒绝错误消息并接受 Conventional Commits；Ruff/冲突检查可拦截错误 |
| 子模块 | 4gaBoards、Admidio、Discourse 三个 gitlink 已固定并核对 |
| Beamer | 本机 XeLaTeX + latexmk 生成 10 页 PDF；页面预览检查，无溢出警告 |
| CI | 工作流与本地统一检查入口已建立；尚未绑定远端，因此未在 GitHub runner 实跑 |
| 4gaBoards 容器 | 配置完成、镜像摘要核实；当前机器无 Docker，构建和健康启动待验证 |
| DeepSeek + 4gaBoards | 未验证；无本机密钥、目标容器未启动，不生成虚假实验成绩 |
| 新成员干净安装 | 初始化脚本与锁文件就绪；仍需在第二台机器实际验证完整初始化 |

浏览器离线测试在本机使用 `/usr/bin/google-chrome`；CI 安装锁文件版本对应的 Playwright Chromium。测试中使用的网页/模拟模型均不是教师调试场景。

最短真实验收路径：安装可用 Docker → `waat targets up` → 配置 `.env` 密钥 → 执行示例 → 检查 dashboard/sidebar 两个独立检查点和证据 → 导出真实统计。模型别名映射须按官方发布记录复核。

已知边界：单用户单进程；运行重启不续放动作；语义判定仍需真实课程场景与标准答案评测；前端 Element Plus 完整引入带来约 1 MB 未压缩脚本，后续可按需拆分。
