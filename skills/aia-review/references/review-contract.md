# 审查数据与证据契约 v1.0

本契约是套件内部工作记录格式，不是国家标准或法定审签格式。脚本只校验记录关系与数值，不验证操作者身份和工程结论。

## 工作基线

- `schema_version`: `1.0`。
- `mode`: `project`（实际项目）或 `synthetic`（合成演示）。合成演示不得表示实际工程通过。
- `project`: id、name、region、building_type、stage、review_date、baseline_date、baseline_id、scope_ref、planned_check_ids、requested_disciplines，以及 data_class、processing。
- discipline 枚举：architecture、fire、structure、water、hvac、electrical、energy、coordination。
- `processing`: mode=local/cloud、environment_verified 布尔值、authorization_ref、sanitization_ref。声明 verified 只是提供了核验记录，不是脚本验证网络隔离。未分类或受限内容不应进入不适当的模型会话；优先在处理前确认。
- `sources`: id、path、sha256、revision、discipline、capability、locator_convention。path 相对本次资料根目录或绝对路径；绝对路径仍须位于 `--root` 内。哈希对字节内容计算，不能以文件名或日期代替。
- 文件目录、OCR 文字、转换件、图像和模型各有来源 ID；转换或摘录记录原来源与过程。清单脚本输出是候选清单，不自动获得签发权威性。

## 依据 bases

每项含 id、kind、title、identifier、clause、source_ref、authority、status、applicability、effective_from、effective_to、verified_at、verified_by、transition_ref、rights_basis、summary。

- kind：standard / project / drawing。
- authority：official / project_approved / synthetic / unknown。official 必须有可追溯的官方公告、正文或受控副本，不是凭名称选择。规范依据须追溯官方原来源，院内批准本身不能将非规范材料变成规范。
- status：effective / superseded / future / unknown / synthetic。
- applicability：confirmed / unknown / not_applicable。
- 已核验 standard 必须有可解析的实施起日；有效区间为 `[effective_from, effective_to)`，effective_to 为空表示未记录终止日，不证明永久有效。
- status=unknown 时，未知的 identifier/clause/source_ref/verified_by/verified_at/rights_basis/effective_from 可用 null，保留 title、summary 和检索缺口，authority/applicability 可为 unknown；不得为了通过格式检查编造元数据。关联规则保持 draft，检查记 unverified_basis。
- 基准日超出当前有效区间，或 status 为 superseded/future 时，只有项目适用性已确认且提供 transition_ref，才能作为本项目有效依据；该记录要引用真实过渡规定或经授权的适用性决策。不得仅凭填入非空字符串认定过渡有效。
- summary 仅摘要，不在本套件分发授权不明的标准全文。rights_basis 记录本次使用范围。

## 规则 rules

id、version、discipline、basis_ids、applicability（state/rationale）、status（draft/verified/disabled）、verified_by、verified_at、verification_ref、test_ref、criterion。

criterion 至少含 kind、quantity、object_scope、basis_locator、explanation。numeric 另含 operator（ge/le/gt/lt/eq）、threshold、unit；eq 可含 tolerance（与 unit 同量纲）。qualitative / consistency / completeness 说明如何判别及必须保留的证据。verified 是人工确认后的工作记录，AI 不得伪造责任人或证明文件。

draft 的未知 basis_locator、operator、threshold、unit 可为 null，直到获得适用依据后再填写；draft 不得作为 evaluated 的规则。不要为通过校验猜测阈值。内置数值检查器仅支持代码 UNITS 明列的单位及精确十进制换算；不支持的流量口径、复杂性能单位、四舍五入或工程容差须由经验证的专项工具处理并保留方法，不擅自换成近似值。

## 计划和执行 checks

每项 id、rule_id、source_ids、status、result、reason、evidence、comparison。

| status | result | 含义 |
|---|---|---|
| evaluated | signal/no_signal | 有适用依据且输入可评估，保留证据；signal 必有对应 finding |
| not_applicable | null | 有明确不适用理由；纳入覆盖分母但不算已求值 |
| insufficient_input | null | 材料或必要字段缺失 |
| unsupported | null | 当前工具不具备所需识别/计算能力 |
| unverified_basis | null | 依据或适用性未能核验 |
| error | null | 解析、规则或工具执行失败 |

每个 planned_check_ids 必须有且只有一条 check，禁止执行后删掉未完成项。计划清单来自任务范围和经确认的专业矩阵，不能为了门禁通过而只规划一项。脚本不能判断范围是否足够全面。

每条 evidence：source_id、source_sha256、locator、excerpt。locator 可用页序/图号/修订/轴网/楼层、表格单元格、文本行、模型 GUID；必要时补 bbox、view、coordinate_system。截图必须能回到原始来源。对“未找到”说明检索范围，不能把未知归零。

numeric 的 comparison：quantity、object_ref、observed_value、observed_unit、normalized_value、normalized_unit、operator、threshold、threshold_unit、conditions_verified、conditions_ref、evidence_index。对象语义和前提要由图面/计算书核对；脚本不能核验两者。数值用 JSON number 或十进制字符串，未知用 null 并记 insufficient_input，不用 0 代替。脚本支持少量显式单位换算；其他量纲交人工或专项工具，不能偷偷作无量纲比较。

## 疑点 findings

id、check_id、kind（rule_deviation/document_conflict/missing_information）、discipline、title、observation、priority、confidence、basis_ids、evidence、suggested_action、review、closure。

- priority=P1（潜在生命安全/关键系统，优先核实）、P2（功能或专业协调）、P3（表达与一般资料）。这是工作分流，不替代缺陷定级。
- confidence=high/medium/low，表示证据可靠程度。数值置信度若未校准不视为概率。优先级与置信度不可互相代替。
- rule_deviation 对应已核验规则及可定位设计证据；document_conflict 至少两个不同 source_id，且时间/基线可比较；missing_information 关联应提供资料的要求及已检索范围。
- 不用 AI 的“通过/不通过/合规/不合规”替代人工结论。允许在 evidence 中如实引用原文的判断词，也允许忠实转述已有人工结论并注明来源。
- review.status=pending/adopted/not_applicable/undetermined。非 pending 要有 actor、at、record_ref、note；只能按实际人工记录写入。不适用处置还要有当前 baseline_id；已采用的原问题可保留原处置基线，闭环复查必须对应本轮基线。adopted 不是已整改，undetermined 仍未闭环。
- closure.status=open/response_submitted/recheck_required/closed/not_applicable；另含 response、revision_source_ids、recheck（actor、at、record_ref、baseline_id、evidence）。closed 要有已采用的人工复核、修订来源和本轮基线复查证据；not_applicable 要有人工不适用记录及理由。
- 单纯设计回复或材料上传不能自动关闭问题。新版本修改证据后重查相关项，保留旧版本和事件记录，不能覆盖旧结论。

## 三类校验

结构校验：ID、枚举、证据引用、哈希格式、时间、状态关系、数值复算。待定/缺材料可以是结构有效的工作稿。

`--verify-files`：另核对所有声明来源在允许目录内且字节哈希一致。此步骤不证明文件签发状态或真实性。

`--gate`：强制重新核对来源，检查计划全覆盖、实际求值、依据确认、无规则错误、疑点人工复核及整改闭环，给出 ready_for_human_signoff 或 blocked。ready 仅表示记录满足本套件的审签准备规则；不得输出“工程已通过审查”。外发、注册签章、身份验证和不可篡改存证依实际平台。
