# EBCAR Intent-V4 P7 run evidence (archived 2026-09-17)

原始运行目录的逐字节拷贝（`cp -a`，未做任何修改/删减）。

## 运行身份

| 项 | 值 |
| --- | --- |
| `run_id` | `ebcar-intent-v4-p7-current-20260916T165846Z` |
| 原始 `out_root` | `/tmp/c2p-p7-ebcar-v4-intent-j9L1bn` |
| repo | `/data1/users/cuihengjia/code2paper/code_final/EBCAR - Embedding-Based Context-Aware Reranker` |
| author intent | `/data1/users/cuihengjia/code2paper/paperyaml3/EBCAR - Embedding-Based Context-Aware Reranker.yaml` |
| profile | `tests/live/profiles/qwen38_vllm_budgeted.example.env` |
| model | `qwen38-27b-nvfp4` @ `http://127.0.0.1:8006/v1`（本地 vLLM） |
| 代码基线 | `authoring_run_contract_v1.json` 记 `code_commit_sha=287506e3e2df30e3c840b8f6398b5010c25111e1`，`dirty_manifest_digest=sha256:b90285d6…` |

同一 `out_root` 在 2026-09-17 共尝试 4 次（11:30 / 11:44 / 11:59 / 12:02），
最终 `method_agent_process.json`：`status=failed`、`exit_code=2`、`terminal_reason=worker_exit_2`、结束于 12:08:31。

## 终止原因

```
unified_actual_shared_payload_delivery_failed:ValueError:
writer_v2_invocation_acceptance_count:inv:writer:MA-S3:page:751aa8b5352377a0766e7f7416c05553647380df74d5295f04d695646a47b815:0
```

`publication_method_writer.py` 的 Writer 页交付门要求每个 writer 调用恰好 1 条 accepted（非 repair）回执；该页为 0。

## 因果链（证据均在 `artifacts/06_authoring/invocations/inv-writer-MA-S3-page-751aa8b5…/`）

- 该页 `page_kind=join`（`mechanism=join:MA-S3`），`token_estimate=12345`，7 个 `allowed_detail_ids`，单次请求要求 16 个段落（`MA-S3:P1__f1, P3…P17`）。
- `attempt-0001`（11:37:06）：模型只产出 `MA-S3:P1__f1` 即结束（`finish_reason=structured_complete`，1287 completion tokens，非截断）→ 15 条 `missing_paragraph` + 2 条必需 detail witness 未满足。
- `attempt-0002`（11:37:31，唯一一次 content-repair）：段落齐全（6913 字符），但 `mech_sym:f6cf5bdfe2ae16f0:15` / `:76` 两个 witness 仍缺失 → 仍不接受。
- `attempt-0003`（11:55:43）/ `attempt-0004`（12:08:30）：**pre-send 拒绝**，`delivery_rejection_code=attempt_limit_exhausted:…:3>2` / `:4>2`，无 provider-request。
- `consumer_invocation_plan_v1.2.json` 中 20 个 writer 调用有 16 个属于 MA-S3，其余 15 页已在 11:30 那次运行写入并持久化；因此 12:02 的“重跑”对该页必然 0 accepted。

## 版本链（同一 run 内，digest 逐层可追）

```
intent_narrative_plan_v4.json        31 段   content_digest sha256:3da8d80f…
  └─ narrative_plan_v3.json          31 段   sha256:23b62108…
       └─ narrative_plan_v3.revision.2.json  46 段  sha256:722838f8…   （fit_narrative_plan_to_page_budget 拆段）
            └─ method_section_plan_v2.json   46 段  sha256:39472136…   （adapter narrative_to_method_section_plan_v1）
                 └─ consumer_workset_manifest_v2.writer.2.json（5 worksets / 20 pages）
                      └─ consumer_invocation_plan_v1.2（writer ×20）/ v1.3（realizer ×20）
                           └─ mechanism_formula_packages_v2 / realizer_receipts_v2 / writer receipts
```

注意同目录下并存的代际文件：`consumer_workset_manifest_v2.json` 是空 manifest（0 worksets），真身为 `.writer.2.json`；`narrative_plan_v3.json` 已被 `.revision.2.json` 取代；`method_section_plan_v2.json` 与 `.legacy_source.json` 字节相同。
