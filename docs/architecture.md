# NextPath MVP 架构

```text
微信小程序
  -> Nginx /api/ -> FastAPI API 层
                    -> 应用服务（成绩、导入、档案）
                    -> 预测端口 PredictionEngine
                       -> 基线规则引擎（MVP）
                       -> 统计模型 / 大模型适配器（后续）
                    -> Repository 端口 -> PostgreSQL
                    -> 异步任务队列（OCR、报告、重算，后续）
```

MVP 是模块化单体：一个可独立部署的服务，模块边界已经明确。高耗时的 OCR、报告和模型计算只能通过任务队列触发，不阻塞录入接口。生产使用 PostgreSQL、Redis 和对象存储；SQLite 只用于本地演示。

预测采用“版本化、可解释、可回测”原则。API 返回预测版本、数据年份、依据和不确定性；每次成绩录入生成快照，后续模型升级不覆盖历史结论。
