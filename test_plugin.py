"""插件离线单元测试

不联网，使用假 HTTP 会话验证字段适配、筛选、缓存、分页与格式化逻辑。
运行: python test_plugin.py
"""

import asyncio
import sys

import aiohttp

from _astrbot_stub import make_plugin

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print(
        f"{'PASS' if condition else 'FAIL'} | {name}"
        + (f" | {detail}" if detail else "")
    )


# ---------------------------------------------------------------- 假 HTTP 会话
class _FakeResponse:
    def __init__(self, payload, error):
        self._payload = payload
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    async def json(self):
        return self._payload


class _FakeCtx:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *args):
        return False


class FakeSession:
    """模拟 aiohttp.ClientSession，按 offset 返回预置分页数据"""

    def __init__(self, pages=None, error=None):
        self.pages = pages or []
        self.error = error
        self.calls = []

    def get(self, url, params=None):
        params = dict(params or {})
        self.calls.append({"url": url, **params})
        if self.error is not None:
            return _FakeCtx(_FakeResponse(None, self.error))
        limit = params.get("limit", 500)
        index = params.get("offset", 0) // limit
        payload = (
            self.pages[index]
            if index < len(self.pages)
            else {"response": {"items": []}}
        )
        return _FakeCtx(_FakeResponse(payload, None))


def gm_item(**overrides):
    """构造一条 GAMEMONITORING 原始服务器数据"""
    item = {
        "id": 10630655,
        "name": "[CN] 福星1 通宵攻防",
        "status": True,
        "numplayers": 100,
        "maxplayers": 100,
        "country": "CN",
        "language": "zh",
        "map": "Yehorivka_RAAS_v1",
        "version": "v10.5.6.675005.2981",
        "ip": "180.188.21.65",
        "port": 22005,
    }
    item.update(overrides)
    return item


# ---------------------------------------------------------------- 字段适配
def test_normalize_fields():
    plugin, _ = make_plugin()
    server = plugin.normalize_server_data(gm_item())

    check(
        "适配: numplayers -> players", server["players"] == 100, str(server["players"])
    )
    check(
        "适配: maxplayers -> max_players",
        server["max_players"] == 100,
        str(server["max_players"]),
    )
    check(
        "适配: status 布尔 True -> online",
        server["status"] == "online",
        server["status"],
    )
    check(
        "适配: status 布尔 False -> offline",
        plugin.normalize_server_data(gm_item(status=False))["status"] == "offline",
    )
    check(
        "适配: 无 ping 字段 -> 哨兵值 999", server["ping"] == 999, str(server["ping"])
    )
    check("适配: 无排队字段 -> 0", server["queue"] == 0)
    check("适配: country 保留并大写", server["country"] == "CN")
    check(
        "适配: port 转字符串",
        server["port"] == "22005" and isinstance(server["port"], str),
    )
    check(
        "适配: map/version 直通",
        server["map"] == "Yehorivka_RAAS_v1"
        and server["version"].startswith("v10.5.6"),
    )
    check(
        "适配: 列表接口无 gamemode -> mode 为空",
        plugin.normalize_server_data(gm_item(gamemode=None))["mode"] == "",
    )

    offline = plugin.normalize_server_data(
        gm_item(name=None, numplayers=None, maxplayers=None)
    )
    check(
        "适配: 缺失字段不抛异常且归零",
        offline["name"] == ""
        and offline["players"] == 0
        and offline["max_players"] == 0,
    )

    check(
        "适配: 非 dict 输入返回 None",
        plugin.normalize_server_data("not-a-dict") is None
        and plugin.normalize_server_data(None) is None,
    )


def test_extract_items():
    plugin, _ = make_plugin()
    check(
        "取条目: response.items",
        plugin._extract_items({"response": {"items": [1, 2]}}) == [1, 2],
    )
    check("取条目: 裸列表", plugin._extract_items([1, 2]) == [1, 2])
    check(
        "取条目: 结构异常返回空",
        plugin._extract_items({"foo": "bar"}) == []
        and plugin._extract_items("x") == [],
    )


# ---------------------------------------------------------------- 筛选逻辑
def test_filter_cn_only():
    plugin, _ = make_plugin(cn_only=True)
    servers = [
        plugin.normalize_server_data(gm_item(name="[CN] 福星1", country="CN")),
        plugin.normalize_server_data(gm_item(name="[RU] Kresty", country="RU")),
        plugin.normalize_server_data(
            gm_item(name="English Named Server", country="CN", ip="1.1.1.1")
        ),
        plugin.normalize_server_data(
            gm_item(name="中文名但境外机房", country="DE", ip="2.2.2.2")
        ),
    ]
    for server in servers:
        server["players"] = 80
        server["max_players"] = 100

    names = [s["name"] for s in plugin.filter_servers(servers, None)]
    check(
        "筛选: country=CN 的英文名服务器入选",
        "English Named Server" in names,
        str(names),
    )
    check("筛选: 中文名的境外服务器入选", "中文名但境外机房" in names, str(names))
    check("筛选: 纯外文境外服务器被排除", "[RU] Kresty" not in names, str(names))

    plugin_out, _ = make_plugin(cn_only=False)
    all_names = [s["name"] for s in plugin_out.filter_servers(servers, None)]
    check(
        "筛选: cn_only 关闭后外文服务器不再被排除",
        "[RU] Kresty" in all_names,
        str(all_names),
    )


def test_filter_conditions():
    plugin, _ = make_plugin(min_players=60, max_results=10)
    servers = [
        plugin.normalize_server_data(
            gm_item(name="[CN] 人数不足", numplayers=10, maxplayers=100)
        ),
        plugin.normalize_server_data(
            gm_item(name="[CN] 满员服", numplayers=100, maxplayers=100)
        ),
        plugin.normalize_server_data(gm_item(name="[CN] 离线服", status=False)),
        plugin.normalize_server_data(
            gm_item(name="[CN] 合格服A", numplayers=80, maxplayers=100)
        ),
        plugin.normalize_server_data(
            gm_item(name="[CN] 合格服B", numplayers=95, maxplayers=100)
        ),
    ]
    names = [s["name"] for s in plugin.filter_servers(servers, None)]
    check("筛选: 人数不足被排除", "[CN] 人数不足" not in names)
    check("筛选: 满员服被排除", "[CN] 满员服" not in names)
    check("筛选: 离线服被排除", "[CN] 离线服" not in names)
    check("筛选: 按人数降序排序", names == ["[CN] 合格服B", "[CN] 合格服A"], str(names))

    keyword_names = [s["name"] for s in plugin.filter_servers(servers, "人数不足")]
    check(
        "筛选: 关键字查询忽略人数门槛",
        keyword_names == ["[CN] 人数不足"],
        str(keyword_names),
    )
    check(
        "筛选: 关键字不区分大小写",
        [s["name"] for s in plugin.filter_servers(servers, "cn] 合格")] != [],
    )

    plugin3, _ = make_plugin(max_results=1)
    check("筛选: max_results 生效", len(plugin3.filter_servers(servers, None)) == 1)


# ---------------------------------------------------------------- 抓取与缓存
def test_fetch_pagination():
    plugin, _ = make_plugin()
    page0 = {
        "response": {
            "items": [
                gm_item(name=f"[CN] 服{i}", ip=f"1.1.1.{i % 250}") for i in range(500)
            ]
        }
    }
    page1 = {"response": {"items": [gm_item(name="[CN] 尾页服", ip="9.9.9.9")]}}
    plugin.session = FakeSession([page0, page1])

    servers = asyncio.run(plugin.fetch_servers())
    check("分页: 满页继续翻页、短页停止", len(servers) == 501, f"共 {len(servers)} 台")
    check(
        "分页: 请求参数正确",
        plugin.session.calls[0]["game"] == 393380
        and plugin.session.calls[0]["status"] == 1
        and plugin.session.calls[0]["sort"] == "numplayers"
        and plugin.session.calls[1]["offset"] == 500,
        str(plugin.session.calls[0]),
    )


def test_fetch_cache():
    plugin, _ = make_plugin()
    plugin.session = FakeSession([])
    plugin.cache = {"servers": [{"name": "[CN] 缓存服"}]}

    async def run():
        plugin.cache_time = asyncio.get_running_loop().time()
        return await plugin.fetch_servers()

    servers = asyncio.run(run())
    check("缓存: 60 秒内直接命中缓存", servers[0]["name"] == "[CN] 缓存服")
    check("缓存: 命中缓存时不发请求", plugin.session.calls == [])


def test_fetch_failure():
    plugin, _ = make_plugin(fallback_to_mock=True)
    plugin.session = FakeSession(error=aiohttp.ClientError("boom"))
    servers = asyncio.run(plugin.fetch_servers())
    check("容错: 请求失败回退模拟数据", len(servers) == 11, f"{len(servers)} 台")

    strict, _ = make_plugin(fallback_to_mock=False)
    strict.session = FakeSession(error=aiohttp.ClientError("boom"))
    check("容错: 关闭回退时返回 None", asyncio.run(strict.fetch_servers()) is None)

    debug, _ = make_plugin(debug_mode=True)
    debug.session = FakeSession(error=aiohttp.ClientError("boom"))
    check("容错: 调试模式走模拟数据", len(asyncio.run(debug.fetch_servers())) == 11)


# ---------------------------------------------------------------- 格式化与查询
def test_format():
    plugin, _ = make_plugin(
        show_extra_fields=True, extra_fields=["map", "version", "ip"]
    )
    text = plugin.format_server_info(plugin.normalize_server_data(gm_item()))
    check(
        "格式化: 名称与人数", "🎮 [CN] 福星1 通宵攻防" in text and "👥 100/100" in text
    )
    check(
        "格式化: 无延迟数据时显示未知", "Ping: 未知" in text, text.replace("\n", " / ")
    )
    check(
        "格式化: 扩展字段含地图/版本/IP",
        "🗺️ 地图: Yehorivka_RAAS_v1" in text
        and "📦 版本: v10.5.6" in text
        and "🌐 IP: 180.188.21.65:22005" in text,
    )

    mock_plugin, _ = make_plugin(show_extra_fields=False)
    mock = mock_plugin.get_mock_servers()[0]
    mock_text = mock_plugin.format_server_info(mock)
    check("格式化: 模拟数据仍能显示排队人数", "排队: 5" in mock_text)


def test_handle_query():
    plugin, _ = make_plugin()
    plugin.session = FakeSession(
        [
            {
                "response": {
                    "items": [
                        gm_item(name="[CN] A服", numplayers=90),
                        gm_item(name="[CN] B服", numplayers=80, ip="1.2.3.4"),
                    ]
                }
            }
        ]
    )
    results = asyncio.run(plugin.handle_query(None))
    check(
        "查询: 正常返回单段文本",
        len(results) == 1 and "[1]" in results[0] and "[2]" in results[0],
    )

    plugin2, _ = make_plugin()
    plugin2.session = FakeSession(
        [{"response": {"items": [gm_item(name="[RU] X", country="RU")]}}]
    )
    check(
        "查询: 无匹配时给出提示",
        asyncio.run(plugin2.handle_query(None)) == ["未找到符合条件的服务器"],
    )

    plugin3, _ = make_plugin()
    plugin3.session = FakeSession(
        [{"response": {"items": [gm_item(name="[RU] Kresty", country="RU")]}}]
    )
    check(
        "查询: 关键字无匹配时给出提示",
        asyncio.run(plugin3.handle_query("不存在")) == ["未找到匹配 '不存在' 的服务器"],
    )

    plugin4, _ = make_plugin(max_results=30)
    longs = [
        gm_item(
            name="[CN] " + "超长名字" * 20 + str(i),
            numplayers=80,
            maxplayers=100,
            ip=f"1.1.1.{i}",
        )
        for i in range(30)
    ]
    plugin4.session = FakeSession([{"response": {"items": longs}}])
    chunks = asyncio.run(plugin4.handle_query(None))
    check(
        "查询: 超长结果自动分段",
        len(chunks) > 1 and all(len(c) <= 2000 for c in chunks),
        f"{len(chunks)} 段",
    )


# ---------------------------------------------------------------- LLM 工具参数
def test_tool_parameters():
    plugin, module = make_plugin(min_players=60, max_results=10)
    servers = [
        plugin.normalize_server_data(
            gm_item(name="[CN] 满员大服", numplayers=100, maxplayers=100, ip="1.1.1.1")
        ),
        plugin.normalize_server_data(
            gm_item(
                name="[US] Big One",
                country="US",
                language="en",
                numplayers=90,
                maxplayers=100,
                ip="2.2.2.2",
            )
        ),
        plugin.normalize_server_data(
            gm_item(name="[CN] 小服", numplayers=20, maxplayers=100, ip="3.3.3.3")
        ),
        plugin.normalize_server_data(
            gm_item(name="[CN] 空服", numplayers=0, maxplayers=100, ip="4.4.4.4")
        ),
        plugin.normalize_server_data(
            gm_item(
                name="[CN] 中文服",
                language="zh",
                map="Mutaha_RAAS_v1",
                numplayers=70,
                maxplayers=100,
                ip="5.5.5.5",
            )
        ),
    ]

    # 默认(无关键字): 国内 + 未满员 + 人数>=60
    selected, total = plugin.select_servers(servers, None)
    check(
        "参数: 默认查询沿用配置门槛",
        [s["name"] for s in selected] == ["[CN] 中文服"] and total == 1,
        f"{[s['name'] for s in selected]} / {total}",
    )

    # limit 覆盖配置的 max_results，并回报命中总数
    wide = {"min_players": 0, "only_joinable": False}
    selected, total = plugin.select_servers(servers, None, limit=2, **wide)
    check(
        "参数: limit 生效且回报命中总数",
        len(selected) == 2 and total == 3,
        f"返回 {len(selected)} / 命中 {total}",
    )

    # countries 覆盖 cn_only（能查国外服）
    selected, _ = plugin.select_servers(servers, None, countries=["US"])
    check(
        "参数: countries 覆盖 cn_only 后能查境外服",
        [s["name"] for s in selected] == ["[US] Big One"],
        str([s["name"] for s in selected]),
    )
    selected, _ = plugin.select_servers(servers, None, countries="us")
    check("参数: countries 支持字符串写法与大小写", len(selected) == 1)

    # include_empty 放开 0 人服务器
    selected, total = plugin.select_servers(servers, None, include_empty=True, **wide)
    check(
        "参数: include_empty 放行 0 人服务器",
        total == 4 and any(s["players"] == 0 for s in selected),
        f"命中 {total}",
    )

    # 关键字查询仍不受人数门槛限制(旧行为)
    selected, _ = plugin.select_servers(servers, "小服")
    check("参数: 关键字查询仍忽略默认人数门槛", len(selected) == 1, str(selected))

    # 显式 min_players 在关键字查询下同样生效
    selected, total = plugin.select_servers(servers, "小服", min_players=50)
    check("参数: 关键字查询下显式 min_players 生效", not selected and total == 0)

    # max_players
    selected, _ = plugin.select_servers(servers, None, max_players=50, **wide)
    check(
        "参数: max_players 生效",
        [s["name"] for s in selected] == ["[CN] 小服"],
        str([s["name"] for s in selected]),
    )

    # map_keyword / languages
    selected, _ = plugin.select_servers(servers, None, map_keyword="mutaha")
    check(
        "参数: map_keyword 生效",
        [s["name"] for s in selected] == ["[CN] 中文服"],
        str([s["name"] for s in selected]),
    )
    selected, _ = plugin.select_servers(servers, None, languages=["en"], cn_only=False)
    check(
        "参数: languages 生效",
        [s["name"] for s in selected] == ["[US] Big One"],
        str([s["name"] for s in selected]),
    )

    # 排序
    selected, _ = plugin.select_servers(
        servers,
        None,
        countries=["CN"],
        sort_by="name",
        order="asc",
        include_empty=True,
        **wide,
    )
    names = [s["name"] for s in selected]
    check("参数: sort_by=name + order=asc", names == sorted(names), str(names))

    selected, _ = plugin.select_servers(
        servers, None, sort_by="fill", cn_only=False, min_players=0, only_joinable=False
    )
    check(
        "参数: sort_by=fill 按满员度排序",
        selected[0]["name"] == "[CN] 满员大服",
        str([s["name"] for s in selected]),
    )

    # 非法参数不抛异常，回退默认
    selected, _ = plugin.select_servers(
        servers,
        None,
        sort_by="不存在的字段",
        order="乱写",
        limit="abc",
        cn_only="不知道",
    )
    check("参数: 非法入参回退默认而不报错", len(selected) == 1, str(selected))

    # limit 硬上限
    many = [
        plugin.normalize_server_data(
            gm_item(
                name=f"[CN] 服{i}", numplayers=80, maxplayers=100, ip=f"1.1.1.{i % 250}"
            )
        )
        for i in range(150)
    ]
    selected, total = plugin.select_servers(many, None, countries=["CN"], limit=9999)
    check(
        "参数: limit 受硬上限约束",
        len(selected) == module.MAX_RESULT_LIMIT and total == 150,
        f"返回 {len(selected)} / 命中 {total}",
    )


def test_tool_output():
    plugin, _ = make_plugin(min_players=60, max_results=10)
    plugin.session = FakeSession(
        [
            {
                "response": {
                    "items": [
                        gm_item(
                            name="[US] Big One",
                            country="US",
                            language="en",
                            numplayers=90,
                            maxplayers=100,
                        ),
                        gm_item(
                            name="[CN] 中文服",
                            language="zh",
                            numplayers=70,
                            maxplayers=100,
                            ip="5.5.5.5",
                        ),
                    ]
                }
            }
        ]
    )

    text = asyncio.run(
        plugin.query_squad_server_tool(
            None,
            countries=["US", "CN"],
            limit=5,
            compact=True,
            show_fields=["country", "language"],
        )
    )
    check("工具: compact 一行一台", text.count("🎮") == 2, text.replace("\n", " / "))
    check(
        "工具: compact 下 show_fields 以简短形式附在行内",
        "🌍 US" in text and "🗣️ en" in text,
        text.replace("\n", " / "),
    )

    verbose = asyncio.run(
        plugin.query_squad_server_tool(
            None, countries=["US"], show_fields=["country", "language"]
        )
    )
    check(
        "工具: 非 compact 下 show_fields 带字段名",
        "🌍 地区: US" in verbose and "🗣️ 语言: en" in verbose,
        verbose.replace("\n", " / "),
    )
    check("工具: 输出命中总数", "命中 2 台" in text)

    text_us = asyncio.run(plugin.query_squad_server_tool(None, countries=["US"]))
    check(
        "工具: countries 参数可只查美国服",
        "Big One" in text_us and "中文服" not in text_us,
        text_us.replace("\n", " / "),
    )

    empty = asyncio.run(plugin.query_squad_server_tool(None, keyword="不存在的服务器"))
    check(
        "工具: 无匹配时返回提示",
        empty == "未找到匹配 '不存在的服务器' 的服务器",
        empty,
    )


def test_tool_docstring_contract():
    """AstrBot 只解析 docstring 的参数与类型，写错会静默丢参数。"""
    import inspect
    import re as _re

    plugin, _ = make_plugin()
    func = plugin.query_squad_server_tool
    params = [
        name
        for name in inspect.signature(func).parameters
        if name not in ("self", "event")
    ]
    args_block = (func.__doc__ or "").split("Args:")[-1]
    documented = dict(_re.findall(r"(\w+) \((\w+(?:\[\w+\])?)\)", args_block))

    missing = [name for name in params if name not in documented]
    check("工具: 每个参数都在 docstring 中标注类型", not missing, str(missing))

    supported = ("string", "number", "boolean", "array", "object")
    bad = {
        name: type_name
        for name, type_name in documented.items()
        if type_name.split("[")[0] not in supported
    }
    check("工具: 参数类型均在 AstrBot 支持列表内", not bad, str(bad))

    check(
        "工具: 已开放 limit / countries / sort_by",
        {"limit", "countries", "sort_by", "order", "show_fields"} <= set(documented),
        str(sorted(documented)),
    )


def main():
    for test in (
        test_normalize_fields,
        test_extract_items,
        test_filter_cn_only,
        test_filter_conditions,
        test_fetch_pagination,
        test_fetch_cache,
        test_fetch_failure,
        test_format,
        test_handle_query,
        test_tool_parameters,
        test_tool_output,
        test_tool_docstring_contract,
    ):
        print(f"\n--- {test.__name__} ---")
        test()

    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{'=' * 60}")
    print(f"通过 {len(RESULTS) - len(failed)}/{len(RESULTS)} 项")
    if failed:
        print("失败项:")
        for name in failed:
            print(f"  - {name}")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
