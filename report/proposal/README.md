# 课程项目开题报告

依据 `/home/joy/文档/WebAppAutoTestAgent/课程项目开题要求.pptx` 第 3--4 页编写，沿用原报告的中文 Beamer 样式。

## 文件结构与要求对应

| 文件 | 内容 |
| --- | --- |
| `main.tex` | 主题、封面信息与章节入口 |
| `sections/01-background.tex` | 项目名称、意义、实用价值与拟探索的改进 |
| `sections/02-scope.tex` | 项目内容、交付物与范围 |
| `sections/03-requirements.tex` | 业务、用户、功能与非功能需求 |
| `sections/04-architecture.tex` | 初步架构、执行流程与判定规则 |
| `sections/05-technology.tex` | 技术栈、开发工具、Git 协作与过程留痕 |
| `sections/06-plan.tex` | 已有基础、开发计划、进度与里程碑 |
| `sections/07-team.tex` | 团队组成及个人工作安排草案，不超过 5 人 |
| `sections/08-risks.tex` | 评测方法、风险与应对 |
| `references.tex` | 材料依据与答辩准备 |

## 编译

从项目根目录执行：

```bash
uv run waat report build --kind proposal
```

也可在本目录执行 `latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=build main.tex`。
输出为 `build/main.pdf`，无须生成实验统计即可独立编译。

## Overleaf



## 汇报前需补全

- 在 `main.tex` 填写成员姓名、课程信息和实际汇报日期。
- 在 `sections/07-team.tex` 按实际人数替换责任人，目前采用四个责任方向草案。
- 在 `sections/06-plan.tex` 将六周相对计划对齐课程截止日期。
- 建立远端仓库后补充地址，并更新协作平台的实际启用情况。

已有进展来自仓库 README、`docs/architecture.md` 和 `docs/acceptance.md`，课程约束沿用原报告。单个真实场景通过不代表课程评测完成；改进效果与对照实验均按待验证计划描述。
