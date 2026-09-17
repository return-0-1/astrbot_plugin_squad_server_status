# 更新日志

## [1.1.0] - 2026-09-17

### 修改

- **数据源替换为 GAMEMONITORING 公开 API**（`https://api.gamemonitoring.ro`，镜像 `api.gamemonitoring.net`），移除原 SquadCalc 与 BattleMetrics 数据源，不再保留备用源
- 新增数据适配层：将 GAMEMONITORING 的 `numplayers` / `maxplayers` / `status`(布尔) 等字段映射为插件内部统一格式（`players` / `max_players` / `status` 字符串）
- 抓取改为按 `game=393380`(Squad 的 Steam AppID) + `status=1` + 按人数降序分页拉取（每页 500 条，最多 4 页）
- `cn_only` 判定改为以 API 的 `country` 字段为准（`country=CN`），名称含中文的境外服务器同样纳入，不再仅靠中文字符猜测
- 服务器覆盖量由 100 余台提升至 500 余台在线服务器
- 使用 `asyncio.get_running_loop()` 替代已废弃的 `asyncio.get_event_loop()`

### 新增

- 新增 `_astrbot_stub.py`：AstrBot 依赖测试替身，使测试脚本可直接导入并实例化插件本体
- `test_plugin.py` 重写为离线单元测试（41 项断言，含假 HTTP 会话的分页/缓存/容错验证）
- `test_real_api.py` 重写为联网集成测试（20 项断言，直接驱动插件本体的抓取与查询链路）
- 配置文件 schema 补充数据源能力说明（Ping、模式、排队人数等字段的可用性）

### 已知限制

- GAMEMONITORING 不提供延迟(Ping)数据，服务器延迟统一显示为“未知”，`ping_threshold` 选项暂不生效
- 列表接口不返回 `gamemode`，仅单服详情接口提供，插件不额外发起逐服务器请求
- 不提供排队人数，`queue` 恒为 0

## [1.0.3] - 2026-07-03

### 新增

- 为所有公共方法添加中文 docstring 注释

### 修改

- 将同步网络请求库 `requests` 替换为异步库 `aiohttp`，提升性能
- 使用长生命周期 `ClientSession` 管理 HTTP 连接
- 在 `terminate()` 方法中关闭 `ClientSession`，避免资源泄漏
- 简化命令处理函数中的关键字解析逻辑，依赖框架自动处理命令前缀
- 使用 ruff 格式化代码，符合 PEP8 规范
- 更新 `metadata.yaml` 添加 `display_name`、`short_desc`、`astrbot_version` 字段
- 更新 `requirements.txt` 替换依赖为 `aiohttp`
- 更新 README.md 文档中的依赖说明

## [1.0.2] - 2026-07-02

### 新增

- 注册为 LLM Tool，AI 可根据对话上下文自动调用查询功能
- 新增 `cn_only` 配置项，默认只显示服务器名称包含中文字符的服务器

### 修改

- 优化命令解析逻辑，兼容带/不带斜杠的命令格式
- 更新 README 文档，添加 AI 智能调用说明
- 修复 LLM Tool 注册失败问题，改用 `@filter.llm_tool` 装饰器方式
- 修复 LLM Tool 参数传递错误，添加 `event` 参数支持
- 修复 docstring 参数类型注释缺失问题

## [1.0.1] - 2026-07-01

### 修改

- 优化查询逻辑：带参数查询时仅进行中文检测，不再过滤 Ping、人数等条件
- 优化不带参数查询：新增排队人数为 0 的过滤条件，只显示无需排队的服务器

## [1.0.0] - 2026-07-01

### 新增

- 实现服务器状态查询功能
- 支持 `/squad_server` 和 `/战术小队服务器` 命令
- 支持服务器名称关键字模糊搜索
- 实现 Ping 阈值过滤（默认 200ms）
- 实现无参数查询时的最低人数门槛（默认 60人）
- 实现最大返回条数限制（默认 10条）
- 支持扩展字段显示（地图、模式、版本、IP）
- 添加模拟数据模式，用于调试和网络受限环境
- 添加 API 失败时自动切换到模拟数据的回退机制
- 添加 60 秒数据缓存，减少 API 请求频率
- 添加多 API 源支持（gamemonitoring.net、battlemetrics.com）
- 实现服务器数据标准化处理
- 实现结果按人数从高到低排序
- 添加完整的错误处理和日志记录