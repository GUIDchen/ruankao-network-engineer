PY ?= python3

BASE := dist/软考中级网络工程师_2024-2026真题研究与考点精讲
MD := $(BASE).md

.PHONY: all build md toc pdf docx check clean

all: build

## 完整构建：拼装 → 生成目录 → 排版 → 回填页码 → 重新排版
build:
	$(PY) tools/assemble.py $(MD)
	$(PY) tools/toc.py $(MD)
	$(PY) tools/build.py $(MD) $(BASE)
	$(PY) tools/pages.py $(BASE).pdf $(MD) pages.json
	$(PY) tools/toc.py $(MD) --map pages.json
	$(PY) tools/build.py $(MD) $(BASE)
	$(PY) tools/pages.py $(BASE).pdf $(MD) pages2.json
	$(PY) tools/check.py $(BASE)
	@echo "✔ 已生成 $(BASE).pdf / .docx / .md"

## 只重新拼装 Markdown，不动排版
md: $(MD)

$(MD): src/part1.md src/part2.md src/part3.md src/part4.md tools/assemble.py
	$(PY) tools/assemble.py $(MD)

## 校验产物（PDF 页数/纸张、DOCX 包结构）
check:
	$(PY) tools/check.py $(BASE)

clean:
	rm -f dist/*.html pages.json pages2.json
