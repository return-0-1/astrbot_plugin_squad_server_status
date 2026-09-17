import asyncio
import re

import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

# GAMEMONITORING 公开 API(免费、无需认证)。镜像域名: https://api.gamemonitoring.net
API_BASE = "https://api.gamemonitoring.ro"
# Squad 的 Steam AppID,该接口的 game 参数即 Steam AppID
SQUAD_APP_ID = 393380
# 单页拉取数量(接口实测支持到 1000)与最大翻页数,最多覆盖 2000 台服务器
PAGE_SIZE = 500
MAX_PAGES = 4
# 数据源不提供延迟,统一用该哨兵值表示"未知"
PING_UNKNOWN = 999
# 服务器数据缓存时间(秒)
CACHE_TTL = 60
# 单次 HTTP 请求超时(秒)
REQUEST_TIMEOUT = 30
# 单次查询允许的最大返回条数(防止把 LLM 上下文撑爆)
MAX_RESULT_LIMIT = 100
# 支持的排序字段: 人数 / 名称 / 地图 / 满员度
SORT_FIELDS = ("players", "name", "map", "fill")
# 可选的额外显示字段
EXTRA_FIELD_CHOICES = ("map", "mode", "version", "ip", "country", "language", "queue")


def _as_int(value):
    """把工具入参转换为整数

    LLM 可能把数字参数传成字符串，统一在这里兜底。

    Args:
        value: 原始入参

    Returns:
        int|None: 转换成功返回整数，无法转换返回 None
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value):
    """把工具入参转换为布尔值

    Args:
        value: 原始入参

    Returns:
        bool|None: 无法识别时返回 None，由调用方回退到配置或默认行为
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "y", "on", "是"):
        return True
    if text in ("false", "0", "no", "n", "off", "否"):
        return False
    return None


def _as_str_list(value):
    """把工具入参规范化为字符串列表

    兼容 ["CN","US"]、单字符串 "CN"、逗号或顿号分隔的 "CN, US" 等写法。

    Args:
        value: 原始入参

    Returns:
        list[str]: 去除空白后的字符串列表
    """
    if value is None:
        return []
    if isinstance(value, str):
        items = re.split(r"[,\s;、]+", value)
    elif isinstance(value, (list, tuple, set)):
        items = [str(item) for item in value]
    else:
        items = [str(value)]
    return [item.strip() for item in items if str(item).strip()]


class SquadServerStatusPlugin(Star):
    """Squad服务器状态查询插件

    该插件用于查询战术小队(Squad)游戏服务器的实时状态信息，
    数据来自 GAMEMONITORING 公开 API(https://api.gamemonitoring.ro)，
    并提供缓存、筛选和格式化功能。
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        """初始化插件

        Args:
            context: AstrBot上下文对象
            config: 插件配置对象
        """
        super().__init__(context)
        self.config = config
        self.cache = {}
        self.cache_time = 0
        self.session = None

    def get_mock_servers(self):
        """获取模拟服务器数据

        返回一组预设的模拟服务器数据，用于调试和测试。

        Returns:
            list[dict]: 服务器信息列表
        """
        return [
            {
                "name": "[CN] 福星2 通宵侵攻服",
                "players": 98,
                "max_players": 100,
                "ping": 35,
                "queue": 5,
                "status": "online",
                "map": "Narva_Invasion_v2",
                "mode": "Invasion",
                "version": "v10.5.1",
                "ip": "180.188.21.57",
                "port": 22007,
            },
            {
                "name": "[CN] 利群 通宵猛攻服",
                "players": 95,
                "max_players": 100,
                "ping": 42,
                "queue": 3,
                "status": "online",
                "map": "AlBasrah_RAAS_v2",
                "mode": "RAAS",
                "version": "v10.5.1",
                "ip": "202.189.8.149",
                "port": 20101,
            },
            {
                "name": "[CN] W.E萌新轻松娱乐服",
                "players": 68,
                "max_players": 99,
                "ping": 55,
                "queue": 0,
                "status": "online",
                "map": "Mutaha_RAAS_v1",
                "mode": "RAAS",
                "version": "v10.5.1",
                "ip": "180.188.21.57",
                "port": 22001,
            },
            {
                "name": "[RU] PHEX 凤凰服务器",
                "players": 98,
                "max_players": 100,
                "ping": 180,
                "queue": 0,
                "status": "online",
                "map": "Mutaha_RAAS_v1",
                "mode": "RAAS",
                "version": "v10.5.1",
                "ip": "80.242.59.123",
                "port": 7807,
            },
            {
                "name": "[GER] Steel Division",
                "players": 75,
                "max_players": 98,
                "ping": 210,
                "queue": 0,
                "status": "online",
                "map": "Harju_Seed_v1",
                "mode": "Seed",
                "version": "v10.5.1",
                "ip": "84.200.132.197",
                "port": 7787,
            },
            {
                "name": "[CN] SDF叙利亚僵尸服",
                "players": 45,
                "max_players": 98,
                "ping": 48,
                "queue": 0,
                "status": "online",
                "map": "SQZR_AlBasrah_LastStand",
                "mode": "Zombies",
                "version": "v10.5.1",
                "ip": "202.189.10.78",
                "port": 7789,
            },
            {
                "name": "[AU] BigD.com.au #1",
                "players": 97,
                "max_players": 98,
                "ping": 220,
                "queue": 0,
                "status": "online",
                "map": "AlBasrah_RAAS_v3",
                "mode": "RAAS",
                "version": "v10.5.1",
                "ip": "squad1.bigd.com.au",
                "port": 26040,
            },
            {
                "name": "[US] Baja Boys Invasion",
                "players": 80,
                "max_players": 98,
                "ping": 195,
                "queue": 2,
                "status": "online",
                "map": "Sanxian_Invasion_v2",
                "mode": "Invasion",
                "version": "v10.5.1",
                "ip": "198.133.237.24",
                "port": 10250,
            },
            {
                "name": "[CN] 五年老服 僵尸服",
                "players": 55,
                "max_players": 98,
                "ping": 38,
                "queue": 0,
                "status": "online",
                "map": "SQZR_AlBasrah_LastStand",
                "mode": "Zombies",
                "version": "v10.5.1",
                "ip": "202.189.10.78",
                "port": 7789,
            },
            {
                "name": "[UA] Ukr.Games #1",
                "players": 99,
                "max_players": 100,
                "ping": 190,
                "queue": 0,
                "status": "online",
                "map": "Yehorivka_AAS_v2",
                "mode": "AAS",
                "version": "v10.5.1",
                "ip": "57.128.211.165",
                "port": 7787,
            },
            {
                "name": "[CN] 军团要塞 战术服",
                "players": 72,
                "max_players": 100,
                "ping": 45,
                "queue": 1,
                "status": "online",
                "map": "Gorodok_RAAS_v2",
                "mode": "RAAS",
                "version": "v10.5.1",
                "ip": "180.188.21.57",
                "port": 22005,
            },
        ]

    async def fetch_servers(self):
        """获取服务器列表

        从 GAMEMONITORING API 分页获取在线 Squad 服务器数据，支持缓存和模拟数据回退。

        Returns:
            list[dict]|None: 服务器列表，失败返回None
        """
        if self.config.get("debug_mode", False):
            logger.info("使用模拟数据模式")
            return self.get_mock_servers()

        current_time = asyncio.get_running_loop().time()
        if current_time - self.cache_time < CACHE_TTL and self.cache.get("servers"):
            logger.info("使用缓存的服务器数据")
            return self.cache["servers"]

        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                headers={"User-Agent": "AstrBot-Squad-Plugin/1.0"},
            )

        servers = await self._fetch_from_api()

        if servers:
            self.cache["servers"] = servers
            self.cache_time = current_time
            return servers

        if self.config.get("fallback_to_mock", True):
            logger.info("API不可用，使用模拟数据")
            return self.get_mock_servers()

        logger.error("API不可用，且未开启模拟数据回退")
        return None

    async def _fetch_from_api(self):
        """从 GAMEMONITORING API 分页拉取 Squad 服务器列表

        按在线状态过滤并按人数降序排序，逐页拉取直到不足一页或达到最大页数。

        Returns:
            list[dict]: 标准化后的服务器列表，全部失败时返回空列表
        """
        servers = []

        for page in range(MAX_PAGES):
            params = {
                "game": SQUAD_APP_ID,
                "status": 1,
                "sort": "numplayers",
                "order": "desc",
                "limit": PAGE_SIZE,
                "offset": page * PAGE_SIZE,
            }
            try:
                async with self.session.get(
                    f"{API_BASE}/servers", params=params
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
            except aiohttp.ClientError as e:
                logger.warning(f"API请求失败 {API_BASE}/servers: {e}")
                break
            except Exception as e:
                logger.warning(f"解析响应失败 {API_BASE}/servers: {e}")
                break

            items = self._extract_items(data)
            if not items:
                break

            for item in items:
                normalized_server = self.normalize_server_data(item)
                if normalized_server and normalized_server["name"]:
                    servers.append(normalized_server)

            if len(items) < PAGE_SIZE:
                break

        if servers:
            logger.info(f"成功从 {API_BASE} 获取 {len(servers)} 个在线服务器")
        return servers

    def _extract_items(self, data):
        """从 API 响应中取出服务器条目列表

        Args:
            data: API 返回的原始 JSON 数据

        Returns:
            list: 服务器条目列表，结构不符时返回空列表
        """
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        response = data.get("response", data)
        if not isinstance(response, dict):
            return []
        items = response.get("items", [])
        return items if isinstance(items, list) else []

    def normalize_server_data(self, server):
        """标准化 GAMEMONITORING 返回的服务器数据

        将 API 的字段(numplayers/maxplayers/status 布尔值等)映射为插件内部统一的格式。

        Args:
            server: 原始服务器数据(dict)

        Returns:
            dict|None: 标准化后的服务器数据，失败返回None
        """
        try:
            if not isinstance(server, dict):
                return None

            return {
                "name": str(server.get("name") or ""),
                "players": int(server.get("numplayers") or 0),
                "max_players": int(server.get("maxplayers") or 0),
                # 数据源不提供延迟与排队人数
                "ping": PING_UNKNOWN,
                "queue": 0,
                "status": "online" if server.get("status") else "offline",
                "map": str(server.get("map") or ""),
                # 列表接口不返回 gamemode，仅单服详情接口有
                "mode": str(server.get("gamemode") or ""),
                "version": str(server.get("version") or ""),
                "ip": str(server.get("ip") or ""),
                "port": str(server.get("port") or ""),
                "country": str(server.get("country") or "").upper(),
                "language": str(server.get("language") or ""),
            }
        except Exception as e:
            logger.error(f"标准化服务器数据失败: {e}")
            return None

    def select_servers(
        self,
        servers,
        keyword=None,
        countries=None,
        languages=None,
        map_keyword=None,
        min_players=None,
        max_players=None,
        limit=None,
        sort_by=None,
        order=None,
        only_joinable=None,
        include_empty=None,
        cn_only=None,
    ):
        """按条件筛选服务器

        显式传入的参数优先；未传入的参数在"宽泛查询"(无关键字)时回退到插件配置，
        在"关键字查询"时不额外施加人数/满员限制(与旧版行为保持一致)。

        Args:
            servers (list): 服务器列表
            keyword (str, optional): 名称关键字(模糊匹配，不区分大小写)
            countries (list|str, optional): 国别代码，传入后按 country 严格筛选并覆盖 cn_only
            languages (list|str, optional): 语言代码(如 zh / en)
            map_keyword (str, optional): 地图名关键字
            min_players (int, optional): 最低当前人数
            max_players (int, optional): 最高当前人数
            limit (int, optional): 返回条数上限，不传则用配置的 max_results
            sort_by (str, optional): players/name/map/fill，默认 players
            order (str, optional): asc 为升序，其它值按降序
            only_joinable (bool, optional): 只返回未满员的服务器
            include_empty (bool, optional): 是否包含 0 人服务器
            cn_only (bool, optional): 只看国内服(country 为 CN 或名称含中文)

        Returns:
            tuple[list, int]: (截断后的结果列表, 截断前的命中总数)
        """
        country_filter = {item.upper() for item in _as_str_list(countries)}
        language_filter = {item.lower() for item in _as_str_list(languages)}
        keyword = str(keyword or "").strip()
        map_keyword = str(map_keyword or "").strip()
        broad_query = not keyword

        explicit_min = _as_int(min_players)
        explicit_max = _as_int(max_players)
        explicit_joinable = _as_bool(only_joinable)
        explicit_empty = _as_bool(include_empty)
        explicit_cn_only = _as_bool(cn_only)

        configured_min = _as_int(self.config.get("min_players", 60)) or 0
        configured_cn_only = bool(self.config.get("cn_only", True))

        if broad_query:
            effective_min = configured_min if explicit_min is None else explicit_min
            keep_joinable = True if explicit_joinable is None else explicit_joinable
            keep_empty = False if explicit_empty is None else explicit_empty
            use_cn_only = (
                configured_cn_only if explicit_cn_only is None else explicit_cn_only
            )
        else:
            effective_min = explicit_min
            keep_joinable = bool(explicit_joinable)
            keep_empty = True if explicit_empty is None else explicit_empty
            use_cn_only = (
                configured_cn_only if explicit_cn_only is None else explicit_cn_only
            )

        result_limit = _as_int(limit)
        if result_limit is None or result_limit <= 0:
            result_limit = _as_int(self.config.get("max_results", 10)) or 10
        result_limit = max(1, min(result_limit, MAX_RESULT_LIMIT))

        matched = []
        for server in servers:
            try:
                if not isinstance(server, dict):
                    continue

                players = int(server.get("players", 0))
                max_players_value = int(server.get("max_players", 0))
                status = str(server.get("status", "")).lower()

                if status != "online":
                    continue

                name = server.get("name", "")
                if not name:
                    continue

                server_country = str(server.get("country", "")).upper()
                server_language = str(server.get("language", "")).lower()
                map_name = str(server.get("map", "")).lower()

                if country_filter and server_country not in country_filter:
                    continue
                if (
                    not country_filter
                    and use_cn_only
                    and not self._is_cn_server(server)
                ):
                    continue

                if language_filter and server_language not in language_filter:
                    continue
                if map_keyword and map_keyword.lower() not in map_name:
                    continue
                if keyword and keyword.lower() not in name.lower():
                    continue

                if effective_min is not None and players < effective_min:
                    continue
                if explicit_max is not None and players > explicit_max:
                    continue
                if not keep_empty and players <= 0:
                    continue
                if keep_joinable and 0 < max_players_value <= players:
                    continue

                matched.append(server)
            except (ValueError, TypeError) as e:
                logger.error(f"解析服务器数据出错: {e}")
                continue

        sort_field = str(sort_by or "").strip().lower()
        if sort_field not in SORT_FIELDS:
            sort_field = "players"
        descending = str(order or "").strip().lower() not in (
            "asc",
            "ascending",
            "升序",
        )
        matched.sort(key=lambda s: self._sort_value(s, sort_field), reverse=descending)

        return matched[:result_limit], len(matched)

    @staticmethod
    def _sort_value(server, sort_field):
        """取出排序用的字段值

        Args:
            server (dict): 服务器数据
            sort_field (str): players / name / map / fill 之一

        Returns:
            int|str|float: 排序键
        """
        if sort_field == "name":
            return str(server.get("name", ""))
        if sort_field == "map":
            return str(server.get("map", ""))
        if sort_field == "fill":
            max_players = int(server.get("max_players", 0) or 0)
            players = int(server.get("players", 0) or 0)
            return (players / max_players) if max_players > 0 else 0.0
        return int(server.get("players", 0) or 0)

    def filter_servers(self, servers, keyword=None, **options):
        """筛选服务器列表(兼容旧调用方式)

        Args:
            servers (list): 服务器列表
            keyword (str, optional): 搜索关键字
            **options: 透传给 select_servers 的筛选参数

        Returns:
            list: 筛选后的服务器列表
        """
        selected, _ = self.select_servers(servers, keyword, **options)
        return selected

    def _is_cn_server(self, server):
        """判断是否为国内服务器

        以 API 的 country 字段为准，名称含中文的服务器同样视为国内服务器
        (兼容部署在境外但面向中文玩家的服务器)。

        Args:
            server (dict): 服务器数据

        Returns:
            bool: 是国内服务器返回True，否则返回False
        """
        if str(server.get("country", "")).upper() == "CN":
            return True
        return self._contains_chinese(str(server.get("name", "")))

    def _contains_chinese(self, text):
        """检测文本是否包含中文字符

        Args:
            text (str): 待检测文本

        Returns:
            bool: 包含中文返回True，否则返回False
        """
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                return True
        return False

    def format_server_info(
        self, server, extra_fields=None, show_extra_fields=None, compact=False
    ):
        """格式化服务器信息为可读文本

        Args:
            server (dict): 服务器数据
            extra_fields (list, optional): 本次额外显示的字段，不传则用配置
            show_extra_fields (bool, optional): 是否显示额外字段，不传则用配置
            compact (bool): 为 True 时压成一行(名称+人数)，适合大 limit 查询

        Returns:
            str: 格式化后的服务器信息文本
        """
        name = server.get("name", "未知服务器")
        players = int(server.get("players", 0))
        max_players = int(server.get("max_players", 0))
        ping = int(server.get("ping", PING_UNKNOWN))
        queue = int(server.get("queue", 0))

        if show_extra_fields is None:
            show_extra_fields = bool(self.config.get("show_extra_fields", False))
        if extra_fields is None:
            extra_fields = self.config.get("extra_fields", []) or []
        fields = [str(field).strip().lower() for field in extra_fields]

        extra_values = []
        if show_extra_fields:
            if "map" in fields and server.get("map"):
                extra_values.append(("🗺️", "地图", server["map"]))
            if "mode" in fields and server.get("mode"):
                extra_values.append(("⚔️", "模式", server["mode"]))
            if "version" in fields and server.get("version"):
                extra_values.append(("📦", "版本", server["version"]))
            if "ip" in fields and server.get("ip"):
                extra_values.append(
                    ("🌐", "IP", f"{server['ip']}:{server.get('port', '')}")
                )
            if "country" in fields and server.get("country"):
                extra_values.append(("🌍", "地区", server["country"]))
            if "language" in fields and server.get("language"):
                extra_values.append(("🗣️", "语言", server["language"]))

        if compact:
            parts = [f"🎮 {name}", f"👥 {players}/{max_players}"]
            if queue > 0:
                parts.append(f"排队 {queue}")
            parts.extend(f"{emoji} {value}" for emoji, _, value in extra_values)
            return " | ".join(parts)

        result = f"🎮 {name}\n"
        result += f"👥 {players}/{max_players}"
        if queue > 0:
            result += f" | 排队: {queue}"
        result += f"\n⏱️ Ping: {'未知' if ping >= PING_UNKNOWN else f'{ping}ms'}"
        for emoji, label, value in extra_values:
            result += f"\n{emoji} {label}: {value}"

        return result

        return result

    @filter.llm_tool(name="query_squad_server")
    async def query_squad_server_tool(
        self,
        event,
        keyword: str = "",
        countries: list | None = None,
        languages: list | None = None,
        map_keyword: str = "",
        min_players: int | None = None,
        max_players: int | None = None,
        limit: int | None = None,
        sort_by: str = "",
        order: str = "",
        only_joinable: bool | None = None,
        include_empty: bool | None = None,
        cn_only: bool | None = None,
        show_fields: list | None = None,
        compact: bool = False,
    ):
        """查询战术小队(Squad)服务器实时状态。

        接口只返回在线服务器，可自由组合名称、国别、语言、地图、人数等条件，
        并指定返回条数与排序方式；不带任何参数时按插件配置返回"未满员且人数达标"的国内服。

        Args:
            keyword (string): 服务器名称关键字(模糊匹配，不区分大小写)，留空表示不限名称
            countries (array[string]): 国别代码列表，如 ["CN","US"]；传入后按服务器所在国家严格筛选并覆盖 cn_only
            languages (array[string]): 语言代码列表，如 ["zh"] 查中文服、["en"] 查英文服
            map_keyword (string): 地图名关键字，如 "Mutaha"
            min_players (number): 最低当前人数；留空时无关键字查询用插件配置的门槛
            max_players (number): 最高当前人数
            limit (number): 返回条数上限(1-100)；留空用插件配置(默认10)
            sort_by (string): 排序字段，可选 players(人数，默认)/name(名称)/map(地图)/fill(满员度)
            order (string): 排序方向，可选 desc(降序，默认)/asc(升序)
            only_joinable (boolean): 是否只返回未满员(还能进)的服务器；留空时无关键字查询默认为 true
            include_empty (boolean): 是否包含 0 人的服务器；留空时带关键字查询默认为 true
            cn_only (boolean): 是否只看国内服(country 为 CN 或名称含中文)；留空用插件配置
            show_fields (array[string]): 额外显示字段，可选 map/mode/version/ip/country/language
            compact (boolean): true 时每台服务器只输出一行(名称+人数)，适合一次查询较多服务器
        """
        options = {
            "countries": _as_str_list(countries),
            "languages": _as_str_list(languages),
            "map_keyword": map_keyword,
            "min_players": min_players,
            "max_players": max_players,
            "limit": limit,
            "sort_by": sort_by,
            "order": order,
            "only_joinable": only_joinable,
            "include_empty": include_empty,
            "cn_only": cn_only,
            "show_fields": _as_str_list(show_fields),
            "compact": compact,
        }
        results = await self.handle_query(str(keyword).strip() or None, **options)
        return "\n".join(results)

    @filter.command("squad_server")
    async def squad_server_command(self, event: AstrMessageEvent):
        """查询战术小队服务器状态 - /squad_server [服务器名称关键字]"""
        keyword = event.message_str.strip() or None
        results = await self.handle_query(keyword)
        for result in results:
            yield event.plain_result(result)

    @filter.command("战术小队服务器")
    async def squad_server_cn_command(self, event: AstrMessageEvent):
        """查询战术小队服务器状态 - /战术小队服务器 [服务器名称关键字]"""
        keyword = event.message_str.strip() or None
        results = await self.handle_query(keyword)
        for result in results:
            yield event.plain_result(result)

    async def handle_query(self, keyword=None, **options):
        """处理服务器查询请求

        获取服务器列表，按选项筛选并格式化结果。

        Args:
            keyword (str, optional): 搜索关键字
            **options: 查询选项，透传给 select_servers(limit/countries/min_players 等)
                以及 format_server_info(show_fields/compact)

        Returns:
            list[str]: 格式化后的服务器信息列表
        """
        logger.info(f"查询Squad服务器状态, 关键字: {keyword}, 选项: {options}")

        servers = await self.fetch_servers()

        if not servers:
            return ["查询失败，请稍后重试"]

        format_options = {"compact": bool(_as_bool(options.get("compact")))}
        show_fields = _as_str_list(options.get("show_fields"))
        if show_fields:
            unknown_fields = [
                field for field in show_fields if field not in EXTRA_FIELD_CHOICES
            ]
            if unknown_fields:
                logger.warning(f"忽略不支持的显示字段: {unknown_fields}")
            chosen_fields = [
                field for field in show_fields if field in EXTRA_FIELD_CHOICES
            ]
            if chosen_fields:
                format_options["extra_fields"] = chosen_fields
                format_options["show_extra_fields"] = True

        filter_keys = (
            "countries",
            "languages",
            "map_keyword",
            "min_players",
            "max_players",
            "limit",
            "sort_by",
            "order",
            "only_joinable",
            "include_empty",
            "cn_only",
        )
        filter_options = {key: options[key] for key in filter_keys if key in options}

        selected, total = self.select_servers(servers, keyword, **filter_options)

        if not selected:
            if keyword:
                return [f"未找到匹配 '{keyword}' 的服务器"]
            return ["未找到符合条件的服务器"]

        result_lines = [f"🔎 命中 {total} 台，返回 {len(selected)} 台"]
        for i, server in enumerate(selected, 1):
            if not format_options["compact"]:
                result_lines.append(f"--- [{i}] ---")
            result_lines.append(self.format_server_info(server, **format_options))

        result = "\n".join(result_lines)

        if len(result) > 2000:
            chunks = []
            current_chunk = ""
            for line in result_lines:
                if len(current_chunk) + len(line) > 1800:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += "\n" + line if current_chunk else line
            if current_chunk:
                chunks.append(current_chunk)
            return chunks
        else:
            return [result]

    async def terminate(self):
        """卸载插件时清理资源"""
        if self.session is not None:
            await self.session.close()
        logger.info("Squad服务器状态插件已卸载")
