# 动中禅宏观发布触发器

在 Codex 里以后可以直接说：

```text
发布到动中禅宏观：
标题：……
副标题：……
一句话看懂：……
标签：口播稿, 大图, 宏观结构
图片：/path/to/image.png
正文：
……
```

Codex 执行流程：

1. 把正文保存成一个临时 Markdown 文件。
2. 运行 `everydayzen-macro/scripts/publish_entry.py` 生成页面，并更新 `everydayzen-macro/data/entries.json`。
3. 如需上线，使用 `--commit --push`，脚本只提交本次生成的页面、索引、源文案和图片资产。
4. GitHub Actions 在 push 后自动把 `everydayzen-macro/` 发布到 GitHub Pages。

本地生成示例：

```bash
python3 everydayzen-macro/scripts/publish_entry.py \
  --title "中国不是没钱了，而是钱开始想离开原来的位置" \
  --subtitle "外贸、外储、资金出海与人民币升值" \
  --thesis "出口在给经济续命，但内需没有真正接棒；外贸在创造外汇，但外汇没有完全留在外储。" \
  --slug china-capital-flow-2026 \
  --date 2026-05-28 \
  --content-file everydayzen-macro/content/china-capital-flow-2026.md \
  --image everydayzen-macro/assets/china-macro-flow-2026.png
```

上线示例：

```bash
python3 everydayzen-macro/scripts/publish_entry.py ... --commit --push
```

发布地址会在 GitHub Pages 工作流完成后出现在：

```text
https://htom78.github.io/btc-macro-system/everydayzen-macro/
```
