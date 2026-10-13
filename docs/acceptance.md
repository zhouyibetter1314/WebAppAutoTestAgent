# 基础验收记录

实施环境：Linux，Python 3.13.16 / uv 0.13.0，Node 24.21.0 / pnpm 12.11.2。原课程 PPT 保留。三个子模块的完整 SHA 已与实际 HEAD 核对。

| 项目 | 结果与范围 |
| --- | --- |
| 后端测试 | 23 项离线测试通过；真实模型单场景另行验证 |
| 三种结论 | 使用确定性模型验证 PASS、FAIL、INCONCLUSIVE 报告分支 |
| 操作预算 | 初始导航和失败计数；第 36 次操作拒绝，仍可观察和保存 Trace |
| 失败收尾 | 定位失败、虚构证据、取消、整体超时、浏览器启动异常、无效模型 JSON、API 超时 |
| 持久化 | SSE 游标补读、API 重启读取历史、未完成任务中断、跨服务运行锁 |
| 前端 | TypeScript、ESLint、Prettier、单元测试与生产构建；真实浏览器端到端流程 |
| 提交规范 | 实际 commit-msg 钩子拒绝错误消息并接受 Conventional Commits；Ruff/冲突检查可拦截错误 |
| 子模块 | 4gaBoards、Admidio、Discourse 三个 gitlink 已固定并核对 |
| Beamer | 本机 XeLaTeX + latexmk 生成 10 页 PDF；页面预览检查，无溢出警告 |
| CI | 工作流与本地统一检查入口已建立；尚未绑定远端，因此未在 GitHub runner 实跑 |
| 4gaBoards 容器 | 本机构建通过，应用与数据库均 healthy；http://localhost:3000 返回 HTTP 200 |
| DeepSeek + 4gaBoards | 最终复测 f75f744b563745b89a961952ca3e8a8a 为 PASS；8 次操作、38.574 秒，直接观察仪表盘与侧栏并通过独立证据审查 |
| 新成员干净安装 | 初始化脚本与锁文件就绪；仍需在第二台机器实际验证完整初始化 |

浏览器离线测试在本机使用 `/usr/bin/google-chrome`；CI 安装锁文件版本对应的 Playwright Chromium。测试中使用的网页/模拟模型均不是教师调试场景。

最短真实验收路径：安装可用 Docker → `waat targets up` → 配置 `.env` 密钥 → 执行示例 → 检查 dashboard/sidebar 两个独立检查点和证据 → 导出真实统计。模型别名映射须按官方发布记录复核。

已知边界：单用户单进程；运行重启不续放动作；语义判定仍需真实课程场景与标准答案评测；前端 Element Plus 完整引入带来约 1 MB 未压缩脚本，后续可按需拆分。

## “无法判定”问题定位与修复

首次运行只导航到登录页。模型同时输出 fill 动作和 wait_ms=300，违反互斥规则；
此前重试没有反馈具体错误。现已增加明确动作约束、字段诊断与校验反馈，并提供不含输入值的 DOM 定位信息。

复测还暴露了两个证据问题：不能用其他页面侧栏推断仪表盘；不能在引文未通过校验时
仅凭执行模型的 finish 请求结束。现已增加独立 evidence_audit、finalize 结束前复核，
以及导航前后 URL/title 一致性检查。拒绝的引文会反馈给下一轮验证。

最终项目名为 Course Test 1013-141025。创建后返回仪表盘，证据
`a7d2db56548b409caa33f4930bf039c4` 同时展示仪表盘卡片与侧栏入口。JSON、Markdown、
事件、模型调用记录、截图及 Trace 均包含在本机运行报告包中。此前运行记录保留，
旧版未经过新证据审查的 PASS 不作为本次验证依据。
