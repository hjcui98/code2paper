# Code2Paper R8 六项目验收状态

- `as_of`: 2026-08-01
- `status`: 项目级 R8 验收完成，6/6 accepted
- `scope`: RAP、EBCAR、DyG、LinearRAG、Lookahead、Bootstrapping 的真实 API
  主运行、resume、completion/readiness、证据与正文硬门
- `base_head`: `95ff02296b2e42409fd27282bad9cd52f58c2fb1`
- `release_freeze`: 待把当前未提交验收器修复提交，并从干净检出归档完整 artifact bundle

## 结论

六个真实项目的最终 `r8_acceptance_report_rechecked.json` 均为
`accepted=true`、`protocol_check_passed=true`，且每份报告的 17 个 criterion 全部
passed。R8 的项目级 pass/fail 已不再是规划假设。

这六个结果由两个串行矩阵组成：前五项来自 `20260731T004226Z`；Bootstrapping
修复 generic producer manifest、freshness 和 profile-aware protocol checker 后，由
`20260801T011526Z` 的真实主运行与 resume 产物完成最终重检。它不是一次单矩阵的
六项目 clean-checkout release freeze，因此后者仍列为独立的证据归档任务，不能把它
与“六项目当前验收是否通过”混为一谈。

## 权威结果摘要

每个报告位于对应 run root 的
`artifacts/10_run/r8_acceptance_report_rechecked.json`。下表持久化 run identity、报告
摘要和 final/resume state digest，避免只依赖临时日志中的布尔值。

| 项目 | Matrix ID | accepted / protocol | criteria | live traces | report content digest | final = resumed digest |
|---|---|---:|---:|---:|---|---|
| RAP | `20260731T004226Z` | True / True | 17/17 | 115 | `sha256:2ad38d12bf70ad6e531d05b52f17e8ec5c5bd0811e80ca0e27e4f731e819a4b6` | `sha256:3e998c3790b122489cb0d185d53f281cac43d9e4e1e4b73bfcfc82ea282dd358` |
| EBCAR | `20260731T004226Z` | True / True | 17/17 | 156 | `sha256:fe42023f7a7b726258668c1a35f8f9d0041c172c262296977c3a7f57194045e8` | `sha256:49ef9411daeb2d1597e70fdc1f2b9c3850692862a4fea16a597336187ac8217c` |
| DyG | `20260731T004226Z` | True / True | 17/17 | 116 | `sha256:b6aec11327026483f68a6148945983c06ce395f5e926f358f58fdf14a3d7a4d2` | `sha256:8071ccaf2ec0ff91fa9bae90456da23d3fd97d9e9c67cfb45daa6a878362e668` |
| LinearRAG | `20260731T004226Z` | True / True | 17/17 | 103 | `sha256:75557aff46fa1264e44fd205f1d17b3850df0884f628212c6c60ff825484984c` | `sha256:975689256b3c217d5f77977cb6b978fdb7600a0d8ea65a7bf0a44ed62a665302` |
| Lookahead | `20260731T004226Z` | True / True | 17/17 | 260 | `sha256:4db6a223eaf2356e5a5775febf7438d78ba10d2f31e7e3eeb0d4dfed6c81e5ea` | `sha256:7f1dd8a02ede7eee7cd1e671e03b4d1a77cd1432f526222ec2ea2e3b474faf60` |
| Bootstrapping | `20260801T011526Z` | True / True | 17/17 | 73 | `sha256:9969dbf2b7a1b9b699cf4c91c0141d02da3dae3b489ff2e25c68b326ee68eb0a` | `sha256:456d85f529082dd98aac7b8094bcfd62899ad6c99b657b3f0f4f6c8ceb520f48` |

## Bootstrapping 重检说明

`20260801T011526Z` 的主运行和 resume 均以 exit code 0 完成，completion/readiness
也在原运行中通过。driver 当时写下的 `accepted=false/protocol=false` 是旧 checker
把 Qwen resolved profile 与 Gemma 固定 sampling/TP=2 表比较所致，不是正文、证据链
或恢复失败。

修复后的 checker 没有取消协议门：

- 每条 trace 仍逐项核对 temperature、top-p、top-k 和 output ceiling；
- resolved profile 四张映射缺失、不完整或越界均硬失败；
- Qwen 的 TP=1/单 GPU 按 profile 冻结期望核对，实际拓扑漂移仍硬失败；
- 六个强制 live role 都必须存在非缓存、未阻塞、带 provider/model/endpoint 和非空
  response hash 的真实响应；
- Bootstrapping 的 73 条真实 trace 满足上述要求。

因此历史 `status.env` 和 `project_status.tsv` 应保留为“旧 checker 的原始 driver
结果”，最终项目判断以修复后 17/17 的 rechecked report 为准。

## 验证与边界

- 当前代码定向回归：`118 passed`。
- 当前仓库可执行基线：`2017 passed, 3 skipped, 12 subtests passed`；三个用户新增、
  依赖尚未合入 API 的 untracked 测试被显式排除，没有删除或修改。
- R8 证明六个已知项目在当前信任门下能够完成真实长流程；它不证明 Method 已达到
  原论文的信息密度，也不证明无 profile holdout、第二语言、跨 provider 或默认产品
  rollout 已完成。
- 当前验收器/profile/producer 修复尚未提交，因而“从干净检出可复现并归档”仍是
  下一项 release-evidence 工作，而不是重新打开六项目内容验收。
