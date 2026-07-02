import requests
import asyncio
import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.api import AstrBotConfig

class SquadServerStatusPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.api_sources = [
            "https://squadcalc.app/api/get/servers",
            "https://api.battlemetrics.com/servers?filter[game]=squad&page[size]=50"
        ]
        self.cache = {}
        self.cache_time = 0

    def get_mock_servers(self):
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
                "port": 22007
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
                "port": 20101
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
                "port": 22001
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
                "port": 7807
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
                "port": 7787
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
                "port": 7789
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
                "port": 26040
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
                "port": 10250
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
                "port": 7789
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
                "port": 7787
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
                "port": 22005
            }
        ]

    async def fetch_servers(self):
        if self.config.get("debug_mode", False):
            logger.info("使用模拟数据模式")
            return self.get_mock_servers()

        current_time = asyncio.get_event_loop().time()
        if current_time - self.cache_time < 60 and self.cache.get("servers"):
            logger.info("使用缓存的服务器数据")
            return self.cache["servers"]

        for api_url in self.api_sources:
            try:
                headers = {"User-Agent": "AstrBot-Squad-Plugin/1.0"}
                response = await asyncio.to_thread(
                    requests.get, api_url, headers=headers, timeout=15
                )
                response.raise_for_status()
                data = response.json()

                if isinstance(data, list):
                    servers = data
                elif isinstance(data, dict):
                    servers = data.get("servers", data.get("data", []))
                else:
                    continue

                if servers and isinstance(servers, list) and len(servers) > 0:
                    normalized = []
                    for server in servers:
                        normalized_server = self.normalize_server_data(server)
                        if normalized_server:
                            normalized.append(normalized_server)

                    if normalized:
                        self.cache["servers"] = normalized
                        self.cache_time = current_time
                        logger.info(f"成功从 {api_url} 获取 {len(normalized)} 个服务器")
                        return normalized

            except requests.exceptions.RequestException as e:
                logger.warning(f"API请求失败 {api_url}: {e}")
                continue
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"解析响应失败 {api_url}: {e}")
                continue

        if self.config.get("fallback_to_mock", True):
            logger.info("API不可用，使用模拟数据")
            return self.get_mock_servers()

        logger.error("所有API源均无法获取服务器数据")
        return None

    def normalize_server_data(self, server):
        try:
            if isinstance(server, dict):
                data = server
            elif isinstance(server, list):
                data = {k: v for k, v in server} if len(server) == 2 else {}
            else:
                return None

            attributes = data.get("attributes", data)
            details = attributes.get("details", {})

            return {
                "name": str(attributes.get("name", data.get("name", ""))),
                "players": int(attributes.get("players", data.get("players", 0))),
                "max_players": int(attributes.get("maxPlayers", attributes.get("max_players", data.get("max_players", 0)))),
                "ping": int(attributes.get("ping", data.get("ping", 999))),
                "queue": int(details.get("squad_publicQueue", details.get("queue", attributes.get("queue", data.get("queue", 0))))),
                "status": str(attributes.get("status", data.get("status", "online"))).lower(),
                "map": str(details.get("map", attributes.get("map", data.get("map", "")))),
                "mode": str(details.get("gameMode", attributes.get("mode", data.get("mode", "")))),
                "version": str(details.get("version", attributes.get("version", data.get("version", "")))),
                "ip": str(attributes.get("ip", data.get("ip", ""))),
                "port": str(attributes.get("port", data.get("port", "")))
            }
        except Exception as e:
            logger.error(f"标准化服务器数据失败: {e}")
            return None

    def filter_servers(self, servers, keyword=None):
        ping_threshold = self.config.get("ping_threshold", 200)
        min_players = self.config.get("min_players", 60)
        max_results = self.config.get("max_results", 10)
        cn_only = self.config.get("cn_only", True)

        filtered = []
        for server in servers:
            try:
                if not isinstance(server, dict):
                    continue

                ping = int(server.get("ping", 999))
                players = int(server.get("players", 0))
                max_players = int(server.get("max_players", 0))
                status = str(server.get("status", "")).lower()
                queue = int(server.get("queue", 0))

                if status != "online":
                    continue

                name = server.get("name", "")
                if not name:
                    continue

                if cn_only and not self._contains_chinese(name):
                    continue

                if keyword:
                    if keyword.lower() not in name.lower():
                        continue
                else:
                    if ping >= ping_threshold and ping != 999:
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

    def _contains_chinese(self, text):
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return True
        return False

    def format_server_info(self, server):
        name = server.get("name", "未知服务器")
        players = int(server.get("players", 0))
        max_players = int(server.get("max_players", 0))
        ping = int(server.get("ping", 0))
        queue = int(server.get("queue", 0))

        result = f"🎮 {name}\n"
        result += f"👥 {players}/{max_players}"
        if queue > 0:
            result += f" | 排队: {queue}"
        result += f"\n⏱️ Ping: {'未知' if ping >= 999 else f'{ping}ms'}"

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
        message_str = event.message_str.strip()
        keyword = None

        if message_str:
            if "/squad_server" in message_str:
                parts = message_str.split("/squad_server", 1)
                if len(parts) > 1:
                    keyword = parts[1].strip()
            elif message_str.startswith("squad_server"):
                keyword = message_str[len("squad_server"):].strip()
            else:
                keyword = message_str.strip()

        if keyword == "":
            keyword = None

        results = await self.handle_query(keyword)
        for result in results:
            yield event.plain_result(result)

    @filter.command("战术小队服务器")
    async def squad_server_cn_command(self, event: AstrMessageEvent):
        """查询战术小队服务器状态 - /战术小队服务器 [服务器名称关键字]"""
        message_str = event.message_str.strip()
        keyword = None

        if message_str:
            if "/战术小队服务器" in message_str:
                parts = message_str.split("/战术小队服务器", 1)
                if len(parts) > 1:
                    keyword = parts[1].strip()
            elif message_str.startswith("战术小队服务器"):
                keyword = message_str[len("战术小队服务器"):].strip()
            else:
                keyword = message_str.strip()

        if keyword == "":
            keyword = None

        results = await self.handle_query(keyword)
        for result in results:
            yield event.plain_result(result)

    async def handle_query(self, keyword=None):
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
        logger.info("Squad服务器状态插件已卸载")