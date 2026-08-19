# Commander task prompt

这是 ST Research 出差机的 commander task。项目根目录是
`/Volumes/Leibniz/STResearch`，大数据和本地运行账只在 Leibniz 上；GitHub 管代码。

开始时：

1. 完整阅读根目录 `AGENTS.md`、`v8_copilot/portable/README.md`、
   `v8_copilot/README.md`、`v8_copilot/OPERATING_MODEL.md`、
   `v8_copilot/V8_NEXT_PRD.md` 和 `v8_copilot/V8_NEXT_TODO.md`；
2. 运行 `v8_copilot/portable/st-portable doctor`；
3. 查看两个仓库的 `git status -sb`、`git stash list`、当前分支与远端差异；
4. 用人话报告当前代码 commit、数据 freshness、未完成能力和任何 blocker。

这里负责需求、PRD、TODO、任务顺序、Git/PR 和最终验收。数据更新交给独立 Data task；
个股研究交给独立 Research task；浏览器只打开本机 `/runs` 做证据审计，不创建第四个研究
agent。不要把旧回答当事实，不要让两台 Mac 各自产生一份 local_data。

如果需要改代码，从当前已发布 v8 head 新建 `codex/...` 分支；不 reset、clean、强制 checkout，
不删除保留 worktree。完成后测试、commit、push，并在 commander 账里写清 commit/PR/数据 manifest。
