# NextPath MVP 架构

```text
微信小程序
  -> Nginx /api/ -> FastAPI API 层
                    -> 应用服务（成绩、导入、档案、报告）
                       -> 分析运行快照 -> HTML 报告快照
                    -> 数据生产线（来源、证据、候选事实、审核、发布）
                       -> Scheduler（定时任务与人工立即运行）
                       -> Collector Worker（网页、附件、文件与快照）
                       -> Governance Worker（提取、标准化、去重、冲突）
                       -> 运行日志、变化差异与运营告警
                       -> 已发布数据快照 -> 预测与家长端消费
                    -> 预测端口 PredictionEngine
                       -> 年度分布模型（预测年度分数—位次曲线）
                       -> 学生联合预测模型（分数 + 位次）
                       -> 学校录取边界模型
                       -> 基线规则 / 统计模型适配器
                    -> Repository 端口 -> PostgreSQL
                    -> 异步任务队列（OCR、分析、报告、采集、重算）
```

MVP 保持一个代码仓库和模块化单体边界，但生产运行拆为 API、scheduler、collector-worker、governance-worker 和 analysis-worker 等独立进程。成绩确认先以幂等方式保存并创建分析任务，家长端可看到处理中状态；分析与报告完成后原子发布。采集运行先保存不可变原始快照，再由治理 worker 生成候选事实；正式数据仍经运营端审核发布。生产使用 PostgreSQL、Redis 和对象存储；SQLite 只用于内部演示。

预测采用“版本化、可解释、可回测”原则。位置引擎联合输出相互匹配的中考分数区间和区域位次区间，输入包含初中、可选班型、成绩与排名历史、考试阶段及距中考时间。API 返回预测版本、数据年份、家长可理解的理由和不确定性；每次成绩录入生成快照，后续模型升级不覆盖历史结论。

分析引擎内的 `ScoreBridgeModel` 负责年度计分口径转换，`AnnualDistributionModel` 生成中考前可用的目标年度分数—位次曲线，`PositionEngine` 在统一口径上融合成绩和校内位置证据，`SchoolBoundaryModel` 生成学校录取位置区间。分析编排器同时保存考试日期、运行时间和数据截止时间，阻止未来结果数据进入预测。出分后的当年一分一段进入独立验证任务，只生成内部质量指标，不进入线上预测依赖。

升学基础数据采用“证据优先、发布后消费”原则。来源、网页快照、文件、人工录入先形成候选事实；审核通过并进入发布版本后，才可被预测与家长端读取。数据工作台以 PC 为主，手机只用于采集与轻审核，家长小程序永远不读取未发布信息。详细需求见 [data-operations-requirements.md](data-operations-requirements.md)。

分析引擎可向数据生产线提交 `DataGap`，但不能自行抓取后直接使用。公开信息和用户实际结果都必须经过采集、治理、审核、发布或模型验证流程；预测服务只读取已发布事实、已激活模型及其参数快照。

采集进程只访问配置允许的外部域名，不持有家长数据读取权限；治理进程读取原始快照并写入候选事实，不具备发布权限；只有审核发布服务可以创建生产 `DataRelease`。采集、治理和发布使用独立权限与审计日志。

生产预测的数据查询必须同时满足 `environment=production`、`usable_for_prediction=true`、`published_at <= data_cutoff_at`。测试数据、回测结果和当届出分后数据即使存在于同一数据库，也不能通过预测仓储接口返回。

家长身份通过微信 `code2Session` 换取 `openid`，服务端仅向小程序签发带有效期的身份令牌，不把 `session_key` 返回客户端。内部测试身份只用于尚未配置微信密钥的开发阶段；切换微信身份时可一次性认领同设备的内部测试档案。

HTML 报告不提供永久公开地址。小程序必须先通过家长身份校验申请短期签名地址，报告页验证报告编号、签名和有效期后才返回内容，并使用 `private, no-store` 禁止共享缓存。

性能、可靠性、安全、隐私、备份和扩容验收要求见 [non-functional-requirements.md](non-functional-requirements.md)。

统一开发顺序和阶段验收见 [development-plan.md](development-plan.md)。
