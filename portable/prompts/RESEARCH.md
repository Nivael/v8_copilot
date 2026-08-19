# Research task prompt

使用 `$st-research-codex` 回答我的 ST 研究问题。工作区是
`/Volumes/Leibniz/STResearch`，开始先运行：

```bash
cd /Volumes/Leibniz/STResearch/v8_copilot
./portable/st-portable doctor
./portable/st-portable research experiences --status accepted
```

每题先从 Leibniz 的本地版本化数据库生成只读 EvidencePack，再按 acquisition plan 决定是否
需要联网补当前官方事实；外部事实必须合入新 Pack 后才能作为 backing。先给人话判断，再给
必要逻辑链，保留 freshness、coverage gap 和主体/时点边界；validator 通过后记录 Research Run。

不要在这里更新数据库，不把 accepted experience 当事实，不把网页摘要替代历史机制计算，
不输出买卖、持有、仓位或目标价建议。若 data writer lock 存在，停止研究并等 Data task 完成。
浏览器 `http://127.0.0.1:8765/runs` 仅用于审计本次 Pack、Lens、backing 和判断因素。
