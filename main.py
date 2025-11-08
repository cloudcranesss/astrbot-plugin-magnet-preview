import hashlib
import re
import json
import math
from functools import lru_cache
from typing import Any, AsyncGenerator
import aiohttp
from redis import asyncio as redis
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Star, register, Context
from .analysis import analysis
from .froward_message import ForwardMessage

FILE_TYPE_MAP = {
    'folder': '📁 文件夹',
    'video': '🎥 视频',
    'image': '🖼 图片',
    'text': '📄 文本',
    'audio': '🎵 音频',
    'archive': '📦 压缩包',
    'document': '📑 文档',
    'unknown': '❓ 其他'
}


@register("Magnet Previewer", "cloudcranesss", "预览磁力链接", "1.0.0")
class MagnetPreviewer(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        logger.info("Magnet Previewer initialized",
                    extra={"version": config.version})

        self.config = config
        self.whatslink_url = config.get("WHATSLINK_URL", "").rstrip('/')

        try:
            self.max_screenshots = min(int(config.get("MAX_IMAGES", 1)), 9)  # 限制最大值
        except (TypeError, ValueError):
            self.max_screenshots = 1
            logger.warning("Invalid MAX_IMAGES config, using default",
                           extra={"config_value": config.get("MAX_IMAGES")})

        # 使用连接池优化Redis连接
        self.redis_pool = redis.ConnectionPool(
            host=config.get("REDIS_HOST", "localhost"),
            port=int(config.get("REDIS_PORT", 6379)),
            db=int(config.get("REDIS_DB", 0)),
            password=config.get("REDIS_PASSWORD", None),
            decode_responses=True,
            max_connections=10
        )
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        self.redis_store = MagnetResultStore(self.redis)

        # 预编译正则表达式
        self._magnet_regex = re.compile(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*")
        self._command_regex = re.compile(r"text='(.*?)'")

    async def terminate(self):
        """清理资源"""
        logger.info("Magnet Previewer terminating")
        await self.redis.close()
        await super().terminate()

    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*")
    async def handle_magnet(self, event: AstrMessageEvent) -> AsyncGenerator[Any, Any]:
        """处理磁力链接请求(优化版)"""
        messages = event.get_messages()
        plain = str(messages[0])

        try:
            matches = self._command_regex.findall(plain)
            if not matches:
                yield event.plain_result("⚠️ 无效的磁力链接格式")
                return
            command = matches[0]
            link = command.split("&")[0]
        except (IndexError, AttributeError):
            yield event.plain_result("⚠️ 无效的磁力链接格式")
            return

        # 检查缓存
        cache_key = self.redis_store._get_key(link)
        result = None

        if await self.redis_store.exists(link):
            try:
                result = await self.redis_store.get(link)
                if isinstance(result, dict):
                    await self.redis.expire(cache_key, 86400)
                    logger.info("Cache hit", extra={"link": link})
                else:
                    logger.warning("Invalid cache data",
                                   extra={"link": link, "data_type": type(result)})
                    result = None
            except redis.RedisError as e:
                logger.error("Redis error", extra={"error": str(e), "link": link})

        # 未命中缓存时解析链接
        if result is None:
            async with aiohttp.ClientSession() as session:
                result = await analysis(link, self.whatslink_url, session)

            if result and result.get('error') == "":
                try:
                    await self.redis_store.store(link, result)
                    logger.info("New cache stored", extra={"link": link})
                except redis.RedisError as e:
                    logger.error("Cache store failed",
                                 extra={"error": str(e), "link": link})

        # 处理错误情况
        if not result or (isinstance(result, dict) and result.get('error')):
            error_msg = result.get('name', '未知错误') if isinstance(result, dict) else 'API无响应'
            yield event.plain_result(f"⚠️ 解析失败: {error_msg.split('contact')[0] if isinstance(error_msg, str) else '未知错误'}")
            return

        # 确保result是有效的字典
        if not isinstance(result, dict):
            yield event.plain_result("⚠️ 解析失败: API返回无效数据")
            return

        # 生成结果消息
        infos, screenshots = self._sort_infos(result)
        for msg in ForwardMessage(event, infos, screenshots).send():
            yield msg

    def _sort_infos(self, info: dict) -> tuple[list[str], list[str]]:
        """整理信息(优化版)"""
        # 确保info是有效的字典
        if not isinstance(info, dict):
            return ["⚠️ 数据格式错误：无法解析磁力链接信息"], []
        
        file_type = info.get('file_type', 'unknown').lower()
        base_info = [
            f"🔍 解析结果：\r"
            f"📝 名称：{info.get('name', '未知')}\r"
            f"📦 类型：{FILE_TYPE_MAP.get(file_type, FILE_TYPE_MAP['unknown'])}\r"
            f"📏 大小：{self._format_file_size(info.get('size', 0))}\r"
            f"📚 包含文件：{info.get('count', 0)}个"
        ]

        screenshots = [
            self.replace_image_url(s["screenshot"])
            for s in info.get('screenshots', [])[:self.max_screenshots]
            if isinstance(s, dict) and s.get("screenshot")
        ]

        return base_info, screenshots

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """格式化文件大小(优化版)"""
        if not size_bytes:
            return "0B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = min(int(math.log(size_bytes, 1024)), len(units) - 1)
        size = size_bytes / (1024 ** unit_index)
        return f"{size:.2f} {units[unit_index]}"

    def replace_image_url(self, image_url: str) -> str:
        """替换图片URL域名(优化版)"""
        return image_url.replace("https://whatslink.info", self.whatslink_url) if image_url else ""


class MagnetResultStore:
    """磁力结果存储(优化版)"""

    def __init__(self, redis: redis.Redis):
        self.redis = redis

    @lru_cache(maxsize=1024)
    def _get_key(self, magnet_link: str) -> str:
        """获取缓存键(带缓存)"""
        return f"magnet:{hashlib.sha256(magnet_link.encode()).hexdigest()}"

    async def exists(self, magnet_link: str) -> bool:
        """检查键是否存在"""
        return await self.redis.exists(self._get_key(magnet_link))

    async def store(self, magnet_link: str, result: dict) -> None:
        """存储结果"""
        await self.redis.setex(
            self._get_key(magnet_link),
            86400,
            json.dumps(result, ensure_ascii=False)
        )

    async def get(self, magnet_link: str) -> dict | None:
        """获取结果"""
        data = await self.redis.get(self._get_key(magnet_link))
        return json.loads(data) if data else None