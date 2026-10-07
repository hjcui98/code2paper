# B00 开发输入冻结与任务交接

> 2026-09-28。Owner：LEAD（当前主 Agent）；独立复核：QA / kernel_execution_units。
> 当前状态：**B00 done，独立 QA PASS；B01/B02 ready。** 不涉及业务接入、运行兼容性或 live 准入。

## 分配及放行条件

B00由负责人执行，不占窗口一、窗口二的实施名额。窗口三承担独立复核职责；本次由同职责的
内核复核 Agent 执行只读检查。负责人统一维护台账，避免三个窗口同时修改基线或任务状态。

执行依据是 [01 执行文档的 B00](01_baseline_and_dsh_compatibility.md)、
[总执行入口](README.md) 与 [AT-B00](verification.md)。独立复核已通过，B00已记为done，
B01和B02已记为ready；只放行这两个无模型开发任务，不同时放行Gate-B、Gate-H或后续live。

## 实测输入

| 对象 | 本次结果 |
|---|---|
| 代码对照基线 | `0918ee76d079b9392ec03400c0c4c9fdff5bc784` |
| 当前HEAD | `d48b4e4b22c94c82b45d2179ba452d72b164102d`；两提交间仅文档/记录变化 |
| 已跟踪src/tests/scripts | 802文件：路径集合、Git blob、文件模式及工作树字节与基线一致；保存逐文件SHA-256 |
| 新环境脚本 | `scripts/dsh_dev.py`、`scripts/dsh_dev_smoke.py`单列，不混称0918原代码 |
| 实际DSH | npm快照`0.1.5-rc.3`，231个DSH包同版本，源码SHA未知 |
| 隔离runtime | 25,478文件/链接，完整摘要与原安装、既有保存清单一致；普通文件共享inode为0 |
| Node | `v25.8.2`；记录实际可执行路径及字节摘要 |
| 配置来源 | 8个具名文件按字节绑定，包括示例Qwen profile、能力声明、隔离profile、离线patch、启动器和pyproject |
| 尚缺组件 | 9个具名路径尚不存在，包括bundle源码/构建/锁文件、preset、Python bridge及集成测试；标为未实现 |
| 历史离线回执 | 4014 passed、0 failed、3 deselected、exit0，绑定0918；未重跑，不能用于本次DSH准入 |

本次没有加载示例live环境、探测8006、调用模型或启动DSH服务。示例profile中的模型、context和
预算只作为来源记录；实际tool-calling能力、DSH wire计量及有限epoch配额仍由后续任务验证。

## 交付及摘要

- [完整冻结清单](source_inventory.json)：`b00_freeze`保存802文件明细、运行包、配置、已知缺项和漂移检查规则；此前规划调查仍保留。
- [开发兼容输入清单](../../integrations/dsh/compatibility.json)：引用完整冻结对象并给出开发所需字段；不是兼容测试或live准入回执。
- [任务台账](task_board.json)：由负责人在复核后更新放行状态。

冻结摘要：`abb0b4324de04f94c9c8f393d750f74d781530469d4b62d1d2ba0e13b3f72099`。
算法是对`b00_freeze`去掉`freeze_digest`后，以UTF-8、排序键、紧凑分隔符、保留Unicode序列化并取SHA-256。
摘要不包括自身，也不绑定未来任务状态变化；开发兼容清单引用同一摘要，没有另造运行准入权威。

“冻结”保留可比较的开发起点，后续仍正常写代码。新增代码、构建或配置必须在后续任务记录其差异和
新的执行身份，不能覆盖本次观测后继续冒称同一输入。这里不是release freeze，也没有给仓库加只读锁。
实际发送/恢复的组成身份检查仍由I01及C02/R03/R04/A01接线。

## 验证记录

本次原始记录目录：`/tmp/c2p-dsh-b00-20260928-0gijha3h/`。

| 命令/检查 | 结果与范围 |
|---|---|
| `python /tmp/c2p-dsh-b00-20260928-0gijha3h/freeze_baseline.py` | exit0；读取Git对象、源码、原安装/隔离树、配置、Node及历史回执，生成唯一观测记录 |
| `python /tmp/c2p-dsh-b00-20260928-0gijha3h/check_baseline.py` | exit0；重算冻结摘要、紧凑清单映射、802代码文件、25,478运行条目、8配置、9缺项和旧回执字节 |
| 内存反例 | 改代码摘要、runtime摘要、配置摘要、模型身份，或把缺失构建冒标已实现，均破坏冻结摘要；这只检验记录覆盖，不冒充I01运行门 |
| `git diff --exit-code 0918ee76d079b9392ec03400c0c4c9fdff5bc784 -- src tests scripts` | exit0；已跟踪业务/测试/脚本保持基线 |
| `git diff --check` | exit0 |

首次清单脚本使用非`-z`的Git中文路径显示导致路径分类断言失败，已改为NUL分隔后重验；
失败发生在写出冻结记录之前，未用该次结果放行。未跑pytest/Node集成套件、未安装依赖、未提交Git、
未修改原安装或日常home。

## 独立复核结果

QA / kernel_execution_units 返回 **PASS，无阻断项**。其独立重算冻结摘要及紧凑清单映射、
802文件的路径/mode/Git blob/SHA-256、原安装与隔离runtime的25,478条目（25,468文件、10相对链接）、
231个DSH包、lock/CLI、8个配置、Node/Python观测、历史回执及9个缺项，均与记录一致，未修改文件。
逐文件清单能够定位已有输入漂移；缺组件出现需登记新阶段身份；没有将本次冻结当作I01运行准入。

负责人据此仅更新B00 done、B01/B02 ready。接下来窗口一执行B02、窗口二执行B01，窗口三
继续独立复核这两项；当前没有替它们实施业务改动，也没有启动后续兼容或live任务。
