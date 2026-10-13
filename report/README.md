# 项目汇报

两份报告均沿用 ctexbeamer、Madrid 主题、Fandol 中文字体和 16:9 比例，各自通过 `main.tex` 引入 `sections/` 下的章节。

| 目录 | 用途 | 编译命令（项目根目录） |
| --- | --- | --- |
| [course-report/](course-report/) | 原阶段报告归档，保留原有内容 | `uv run waat report build` |
| [proposal/](proposal/) | 按课程开题要求组织的开题报告 | `uv run waat report build --kind proposal` |

各自输出到对应目录的 `build/main.pdf`。需要 XeLaTeX、latexmk 和中文字体包。
真实运行统计命令 `uv run waat report stats` 写入 `course-report/generated/`，供课程报告引用。

原 `main.tex`、`sections/`、`references.tex` 及配套目录已整体移至 `course-report/`，原阶段报告中的待测描述保留其历史状态，最新原型进展见开题报告及 `docs/acceptance.md`。
