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
