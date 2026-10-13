# 阶段汇报

使用 ctexbeamer、Madrid、Fandol 字体，16:9。需要 XeLaTeX、latexmk、ctex 和中文字体包。

```bash
uv run waat report build
uv run waat report stats
```

输出 `build/main.pdf`。`sections/` 分章节协作，`figures/` 放可追溯图片，`references.tex` 维护引用。
`generated/` 的统计只从 execution_mode=real 的本地报告生成，不提交含原始场景/登录页面的数据。
初始实验页明确待测；有真实结果后修改页标题，并注明样本、标准答案、模型映射及环境版本。
