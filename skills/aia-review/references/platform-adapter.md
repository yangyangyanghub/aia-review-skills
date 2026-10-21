# 与 codexdrafter 或院内平台对接

## 可复用的工作流

| 参考能力 | 本套件记录 | 对接前应验证 |
|---|---|---|
| review_rules / extractors | rules / checks.comparison | 规则版本、对象、单位、适用前提与抽取器真实能力 |
| review_findings / evidence | findings / evidence | 来源哈希、图面定位、规则依据与原始片段 |
| standards / articles | bases | 真实现行性和项目适用性，不能由引擎常量写“现行” |
| finding review_status | findings.review | pending/adopted/not_applicable/undetermined 是人工处置状态 |
| document_versions / signature | sources、baseline_id、人工记录引用 | 版本内容、身份、签署范围与文件哈希是否真实绑定 |
| routing / audit | project.processing 与院内日志 | 处理当前会话、OCR、embedding、缓存、备份和输出的完整数据流 |

参考项目的具体 API、字段和认证方式应从所连接版本实查；本套件不内置调用或写入，不能假设当前下载目录对应在线部署。原项目的数据库初始化和发布脚本可能修改外部状态，不因阅读仓库就获得执行授权。

## 不能照搬的边界

- 参考引擎 `evaluate_rule` 的证据把 status 写成“现行”，不代表运行时核验了标准状态。
- 原引擎 `rules_evaluated=len(rules)` 更接近加载规则数；本套件按每个 check 的实际执行状态统计。
- 原项目 `mark_reviewed` 在无 pending 时允许解锁，undetermined 也会进入该路径；本套件仍将待定视为未闭环。
- 原项目采用格式白名单控制导出；本套件按工作稿、内部报告和正式对外设计文件的用途走实际审签，不能仅由扩展名推定效力。
- L1/L2/L3 属于参考项目内部分类，不能自动对应法定密级。仅有一个 local 配置值不能证明当前云端 Agent 会话在本地。
- 指令文件和 Python 本地检查不能提供数据库级约束、WORM、认证或电子签名。生产对接需验证这些外部能力，不能在报告写“已实现不可篡改”。

规范法规的现行文本、条号、效力与版权许可需独立查证。参考仓库文档的法规名称、条号和断言未作为本套件法律依据。
