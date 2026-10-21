# 参考项目与迁移依据

核验日期：2026-10-21。来源为用户提供的 codexdrafter 下载快照；快照标注的上游为 [qzp001/codexdrafter](https://atomgit.com/qzp001/codexdrafter)。来源字节快照见下表，不能据此推定上游当前版本或部署状态。只读源码和文档，未运行其数据库初始化、发布工具、测试或生产服务。

## 迁移到套件的内容

| 本地来源 | 从实际文件采用的机制 | 在本套件的落点 |
|---|---|---|
| review_engine.py / models.py | 规则、疑点、证据、人工处置分离 | 共享契约、rule-author、closure |
| extractors.py | 单位归一、对象绑定、否定与相邻对象误取风险 | 数值比较校验、专业证据要求 |
| routing.py | 缺分类需明确、禁止受限数据云端兜底的设计思路 | intake；注明指令不具备网络强制能力 |
| signature.py | 文件哈希与版本相连、正式交付应有责任流程 | 来源哈希、当前基线复查；不模拟签章 |
| standard_library.py / fixtures | 依据字段、状态、来源及真实语料缺口 | standards、benchmark；无当前状态常量 |
| seed_rules.py | 规则应有依据与测试 | rule-author；未采用其工程演示阈值 |
| 回测与实用性报告 | 分开记录未评估、规则覆盖和回测精度 | 覆盖矩阵、试点验收边界 |

## 明确调整

1. 源码 `evaluate_rule` 对证据 status 使用“现行”常量；本套件要求实际版本和适用性核验。
2. 源码 `stats.rules_evaluated` 采用加载规则数量；本套件分别统计加载与实际求值。
3. 源码 `mark_reviewed` 在无 pending 时解锁，包括 undetermined；本套件保持待定阻塞，区分人工处置与整改闭环。
4. 原 README 和实现/后续章节在部分能力描述上不同，本套件按当前可见代码判断，不复述文档中的测试总数、图纸能力或部署成功主张。
5. 原项目有关法规名称、条号、版权及格式效力的解释没有直接转化为通用约束；真实法规与许可应以官方原文及适用条件查证。
6. 全专业检查表为本次原创工作方法扩展，不是该参考项目已具备的能力，也不是对规范条文的复制。

本次联网检索工具未返回可核验正文，因此没有把任何外部法规条号、真实规范阈值或现行状态固化进本包。Skills 要求在实际项目执行时核验官方正文和项目适用性；无法核验则明确弃权。

## 来源字节快照

| 相对文件 | SHA-256 |
|---|---|
| `README.md` | `183a293a482f699920a1c054ddf3384d84f95b7cf2bae8f911dd4e3b0ee13bb9` |
| `app/services/review_engine.py` | `07a582da1bae9d6e6e20b9a1c585ac2493611595241b9c309ec1573613e6ee58` |
| `app/services/extractors.py` | `b08f8c3eede1177980d97af83a9ae206017d56751ab384590a33aa95799796f2` |
| `app/services/routing.py` | `82950f632ce080161a7dc5a6dbc755a1cad513081a1b4f37f1bdb823fade618b` |
| `app/services/signature.py` | `fe662cd12e57a38632d2cbe89b2b75aef0be5c3bd3297127cc2d3fde7a95dd8e` |
| `app/services/standard_library.py` | `39c6fce5992ffa679190a7b6ced8bab22ca5d35e24aa84f3c803557dabf01e85` |
| `app/models.py` | `3015a855da7963cd269084cc52795b75aa9b8d83ece8ac076f29b1631234d37c` |
| `tools/seed_rules.py` | `978880bec1b8dffe307e4d2a25a35328494a3ef9cefd9c360c7c5f31a04f0a14` |
| `tests/fixtures/README.md` | `d50375104b48f20937d3cb4cd72436b4a195f49b529ac1276e89dd8890386f7f` |
| `实用性评估报告.md` | `5d2ebf3ebaecae830f9f695c29b9602d7ea73a894ee2e5a77433ed9539e5f909` |
| `阶段0回测报告.md` | `0d17b9b37cc1f34e5443566a7a843c6447d3bdcca962fd8fe6a83cbbc0342180` |
| `LICENSE` | `480ef33f5fb193a8055f8828f7c09ba95775ab4c6a63bfbc9a48697dd2d7f594` |
| `NOTICE` | `bf52770eeec37b3db84e530a74c8c1cb7fd24d28c67c21db2375981fac741ed6` |

## 署名与许可说明

参考项目 NOTICE 标题为“设计院 AI 辅助审查平台”，仓库 LICENSE 声明 Apache License 2.0。此套件参考其工作流概念，脚本与专业检查表为本次新写，未复制仓库源码或标准原文；未将原项目 NOTICE 中的法律解释视为已核验事实。
