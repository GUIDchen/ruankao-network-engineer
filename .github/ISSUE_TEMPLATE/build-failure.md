---
name: 构建问题
about: make build / make check 失败
title: "[构建] "
labels: ["bug"]
assignees: []
---

## 环境

- 操作系统：
- Python 版本：
- Node 版本：
- Chrome 版本：
- poppler 版本（`pdfinfo -v`）：

## 复现步骤

~~~bash
make build
~~~

## 报错输出

~~~
粘贴关键报错
~~~

## 已尝试

- [ ] 删除 `dist/*.html` 与 `pages*.json` 后重试
- [ ] 确认 Chrome 路径为 `/Applications/Google Chrome.app/...`（tools/build.py 中的 CHROME 常量）
