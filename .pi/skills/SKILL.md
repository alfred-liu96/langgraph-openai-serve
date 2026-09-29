---
name: merge-upstream
description: 合并上游改动
---

# Merge Upstream

当前项目是 github 上 fork 出来的项目，做了一些定制化修改。
现在，我需要将上游的更新合并到项目中，帮我实现。

## 注意事项

1. 可以执行 git status 等不会改变 repo 内容的操作，但不要执行 commit 等会产生变动的操作，这些变动操作应该要用户手动执行；
2. 遇到冲突，先与用户讨论，确认后再进行修改
3. git add remote 等操作可能受到沙盒限制，这时候请求用户帮忙执行
