import asyncio

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

    def filter_servers(self, servers, keyword=None):
        """筛选服务器列表

        根据配置的筛选条件过滤服务器，支持关键字搜索。

        Args:
            servers (list): 服务器列表
            keyword (str, optional): 搜索关键字

        Returns:
            list: 筛选后的服务器列表
        """
        ping_threshold = self.config.get("ping_threshold", 200)
        min_players = self.config.get("min_players", 60)
        max_results = self.config.get("max_results", 10)
        cn_only = self.config.get("cn_only", True)

        filtered = []
        for server in servers:
            try:
                if not isinstance(server, dict):
                    continue

                ping = int(server.get("ping", PING_UNKNOWN))
                players = int(server.get("players", 0))
                max_players = int(server.get("max_players", 0))
                status = str(server.get("status", "")).lower()
                queue = int(server.get("queue", 0))

                if status != "online":
                    continue

                name = server.get("name", "")
                if not name:
                    continue

                if cn_only and not self._is_cn_server(server):
                    continue

                if keyword:
                    if keyword.lower() not in name.lower():
                        continue
                else:
                    if ping >= ping_threshold and ping != PING_UNKNOWN:
                        continue
                    if players < min_players:
                        continue
                    if players >= max_players:
                        continue
                    if queue > 0:
                        continue

                filtered.append(server)
            except (ValueError, TypeError) as e:
                logger.error(f"解析服务器数据出错: {e}")
                continue

        filtered.sort(key=lambda s: int(s.get("players", 0)), reverse=True)
        return filtered[:max_results]

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

    def format_server_info(self, server):
        """格式化服务器信息为可读文本

        Args:
            server (dict): 服务器数据

        Returns:
            str: 格式化后的服务器信息文本
        """
        name = server.get("name", "未知服务器")
        players = int(server.get("players", 0))
        max_players = int(server.get("max_players", 0))
        ping = int(server.get("ping", PING_UNKNOWN))
        queue = int(server.get("queue", 0))

        result = f"🎮 {name}\n"
        result += f"👥 {players}/{max_players}"
        if queue > 0:
            result += f" | 排队: {queue}"
        result += f"\n⏱️ Ping: {'未知' if ping >= PING_UNKNOWN else f'{ping}ms'}"

        if self.config.get("show_extra_fields", False):
            extra_fields = self.config.get("extra_fields", [])

            if "map" in extra_fields:
                map_name = server.get("map", "")
                if map_name:
                    result += f"\n🗺️ 地图: {map_name}"

            if "mode" in extra_fields:
                mode = server.get("mode", "")
                if mode:
                    result += f"\n⚔️ 模式: {mode}"

            if "version" in extra_fields:
                version = server.get("version", "")
                if version:
                    result += f"\n📦 版本: {version}"

            if "ip" in extra_fields:
                ip = server.get("ip", "")
                port = server.get("port", "")
                if ip:
                    result += f"\n🌐 IP: {ip}:{port}"

        return result

    @filter.llm_tool(name="query_squad_server")
    async def query_squad_server_tool(self, event, keyword: str = ""):
        """查询战术小队(Squad)服务器状态

        Args:
            keyword (str): 服务器名称关键字，不填则返回所有活跃服务器
        """
        if keyword == "":
            keyword = None
        results = await self.handle_query(keyword)
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

    async def handle_query(self, keyword=None):
        """处理服务器查询请求

        获取服务器列表，筛选并格式化结果。

        Args:
            keyword (str, optional): 搜索关键字

        Returns:
            list[str]: 格式化后的服务器信息列表
        """
        logger.info(f"查询Squad服务器状态, 关键字: {keyword}")

        servers = await self.fetch_servers()

        if not servers:
            return ["查询失败，请稍后重试"]

        filtered = self.filter_servers(servers, keyword)

        if not filtered:
            if keyword:
                return [f"未找到匹配 '{keyword}' 的服务器"]
            else:
                return ["未找到符合条件的服务器"]

        result_lines = []
        for i, server in enumerate(filtered, 1):
            info = self.format_server_info(server)
            result_lines.append(f"--- [{i}] ---")
            result_lines.append(info)

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
