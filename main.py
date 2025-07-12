import hashlib
import re
import json
from typing import Any, AsyncGenerator
from redis import asyncio as redis
from astrbot.core import logger, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Star, register
from astrbot.core.star import Context
from .analysis import analysis
from .froward_message import ForwardMessage

FILE_TYPE_MAP = {
    'folder': '📁 文件夹',
    'video': '🎥 视频',
    'image': '🖼️ 图片',
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
        logger.info("Magnet Previewer init")
        logger.info(f"AstrBot Version: {config.version}")
        self.config = config
        self.whatslink_url = self.config.get("WHATSLINK_URL", "")
        max_images = self.config.get("MAX_IMAGES", 1)
        try:
            self.max_screenshots = int(max_images)  # 强制转换为整数
        except (TypeError, ValueError):
            self.max_screenshots = 1  # 默认值
            logger.warning(f"无效的 MAX_IMAGES 配置: '{max_images}'，使用默认值 1")
        logger.info(f"MAX_IMAGES: {self.max_screenshots}")
        self.redis = redis.Redis(host=self.config.get("REDIS_HOST", "localhost"),
                                 port=self.config.get("REDIS_PORT", 6379),
                                 db=self.config.get("REDIS_DB", 0),
                                 decode_responses=True,
                                 max_connections=10)
        self.redis_store = MagnetResultStore(self.redis)
        logger.info("Magnet Preview Initialize Finished")

    async def terminate(self):
        """可选择实现 terminate 函数，当插件被卸载/停用时会调用。"""
        logger.info("Magnet Previewer terminate")
        await self.redis.close()
        await super().terminate()

    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.regex(r"magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*")
    async def handle_magnet(self, event: AstrMessageEvent) -> AsyncGenerator[Any, Any]:
        messages = event.get_messages()
        plain = str(messages[0])
        command = re.findall(r"text='(.*?)'", plain)[0]
        link = command.split("&")[0]

        # 使用缓存键获取数据（哈希优化）
        cache_key = self.redis_store._get_key(link)

        # 检查缓存是否存在
        if await self.redis_store.exists(link):
            try:
                result = await self.redis_store.get(link)  # 关键修复：添加await
                logger.info(f"磁力链接缓存命中: {link}")
                # 类型安全检查
                if not isinstance(result, dict):
                    raise TypeError(f"无效的缓存数据类型: {type(result)}")
                # 更新TTL
                await self.redis_store.redis.expire(cache_key, 86400)
            except Exception as e:
                logger.error(f"Redis缓存读取失败: {e}")
                result = None
        else:
            result = None

        # 未命中缓存时解析链接
        if result is None:
            try:
                result = await analysis(link, self.whatslink_url)
                # 缓存解析结果
                await self.redis_store.store(link, result)
                logger.info(f"新增磁力链接缓存: {link}")
            except Exception as e:
                logger.error(f"磁力解析失败: {link} | 错误: {str(e)}")
                yield event.plain_result("⚠️ 解析失败，请检查链接格式或重试")
                return

        # 处理API错误响应
        if not result or result.get('error'):
            error_msg = result.get('name', '未知错误') if result else 'API无响应'
            logger.error(f"API错误: {error_msg}")
            yield event.plain_result(f"⚠️ 解析失败: {error_msg.split('contact')[0]}")
            return

        # 生成结果消息
        infos, screenshots = self._sort_infos(result)
        for msg in ForwardMessage(event, infos, screenshots).send():
            yield msg


    def _sort_infos(self, info: dict) -> tuple[list[str], list[Any]]:
        # 使用更安全的字段获取方式
        base_info = [
            f"🔍 解析结果：\r"
            f"📝 名称：{info.get('name', '未知')}\r"
            f"📦 类型：{FILE_TYPE_MAP.get(info.get('file_type', 'unknown').lower(), FILE_TYPE_MAP['unknown'])}\r"
            f"📏 大小：{self._format_file_size(info.get('size', 0))}\r"
            f"📚 包含文件：{info.get('count', 0)}个"
        ]
        screenshots_data = info.get('screenshots') or []  # 关键修复：None时转为空列表
        screenshots = [
            self.replace_image_url(s.get("screenshot"))
            for s in screenshots_data[:self.max_screenshots]
            if s and isinstance(s, dict)  # 双重验证
        ]
        return base_info, [img for img in screenshots if img]

    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if not size_bytes:
            return "0B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"

    # 替换图片中的域名
    def replace_image_url(self, image_url: str) -> str:
        return image_url.replace("https://whatslink.info", self.whatslink_url)

class MagnetResultStore:
    def __init__(self, redis=None):
        self.redis = redis

    def _get_key(self, magnet_link):
        return f"magnet:{hashlib.sha256(magnet_link.encode()).hexdigest()}"

    async def exists(self, magnet_link):
        """异步检查键是否存在"""
        return await self.redis.exists(self._get_key(magnet_link))

    async def store(self, magnet_link, result):
        """存储结果（自动序列化）"""
        key = self._get_key(magnet_link)
        await self.redis.setex(key, 86400, json.dumps(result))

    async def get(self, magnet_link):
        """获取结果（自动反序列化）"""
        key = self._get_key(magnet_link)
        data = await self.redis.get(key)
        return json.loads(data) if data else None