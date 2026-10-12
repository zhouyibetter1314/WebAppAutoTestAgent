# 协作约定

1. 从 main 创建短分支，围绕一个问题提交 PR；不要直接修改第三方子模块内容。
2. 执行 bootstrap 安装三个 hooks。Python 使用 uv，前端使用固定 pnpm；依赖变化必须同时更新锁文件。
3. 提交采用 Conventional Commits：`feat(agent): 增加页面观察`、`fix(api): 修复取消后报告`、`docs(report): 更新实验说明`。可使用 `uv run cz commit`，普通 git commit 也会被校验。
4. 提交前运行 `bash scripts/check.sh all`；前端流程变动运行 `pnpm --dir frontend test:e2e`；汇报变动编译 Beamer。
5. 只为有风险的行为补充有意义的测试。模拟模型测试必须标注来源；没有真实模型实测不能写“真实验收通过”。
6. 两人团队可合并 Agent/环境与界面/实验；四人可分别负责 Agent、界面/API、环境质量、实验汇报。

pre-commit 检查格式、冲突、明显密钥、Ruff 与前端规范；commit-msg 使用 Commitizen；pre-push 运行类型和快速离线测试。CI 重复完整检查，无法依赖每位成员都安装 hooks。

本项目尚未绑定 GitHub 远端。创建仓库并推送后，在仓库设置中启用 main 分支保护和 checks 工作流；真实评测需要单独配置 live-test environment secret。
