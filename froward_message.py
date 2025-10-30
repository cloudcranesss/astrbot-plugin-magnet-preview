from typing import Optional, Any, Generator, List
import io
import aiohttp
import astrbot.api.message_components as comp
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger


class ForwardMessage:
    def __init__(self, event: AstrMessageEvent, messages: list[str],
                 screenshots: Optional[list] = None) -> None:
        self.event = event
        self.platform = event.get_platform_name()
        logger.info("Forward message initialized",
                    extra={
                        "platform": self.platform,
                        "message_count": len(messages),
                        "screenshot_count": len(screenshots) if screenshots else 0
                    })
        self.self_id = event.get_self_id()
        self.messages = messages
        self.screenshots = screenshots or []  # 确保总是列表

    async def _download_image(self, url: str) -> Optional[bytes]:
        """下载图片内容
        
        Args:
            url: 图片URL
            
        Returns:
            图片字节数据，如果下载失败则返回None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10, ssl=False) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f"图片下载失败: HTTP {response.status}", extra={"url": url})
                        return None
        except Exception as e:
            logger.error(f"图片下载异常: {str(e)}", extra={"url": url})
            return None
            
    async def get_processed_images(self) -> List[Any]:
        """处理图片列表，下载并返回可用于发送的图片对象
        
        Returns:
            处理后的图片列表
        """
        processed_images = []
        
        for screenshot_url in self.screenshots[:9]:  # 限制最大数量
            if not screenshot_url:
                continue
                
            # 尝试下载图片
            image_data = await self._download_image(screenshot_url)
            if image_data:
                try:
                    # 使用bytes直接发送，而不是URL
                    processed_images.append(image_data)
                    logger.info("图片下载成功并已处理", extra={"url": screenshot_url})
                except Exception as e:
                    logger.error(f"图片处理失败: {str(e)}", extra={"url": screenshot_url})
            else:
                # 如果下载失败，仍然尝试使用原始URL作为后备方案
                processed_images.append(screenshot_url)
                logger.warning("使用原始图片URL作为后备", extra={"url": screenshot_url})
                
        return processed_images
    
    def send(self) -> Generator[Any, None, None]:
        """发送转发消息(优化版)"""
        uin = self.self_id
        bot_name = "CloudCrane Bot"

        if self.platform == "aiocqhttp":
            # 使用列表推导式优化节点生成
            nodes = [
                comp.Node(
                    uin=uin,
                    name=bot_name,
                    content=[comp.Plain(str(msg) if msg is not None else "")]
                )
                for msg in self.messages
            ]

            # 添加截图节点
            nodes.extend(
                comp.Node(
                    uin=uin,
                    name=bot_name,
                    content=[comp.Image.fromURL(screenshot)]
                )
                for screenshot in self.screenshots[:9]  # 限制最大数量
                if screenshot  # 过滤空值
            )

            yield self.event.chain_result([comp.Nodes(nodes)])
        else:
            # 非aiocqhttp平台处理
            if self.messages:
                yield self.event.plain_result("\n".join(msg for msg in self.messages if msg))

            # 创建一个异步任务来处理图片
            import asyncio
            loop = asyncio.get_event_loop()
            processed_images = loop.run_until_complete(self.get_processed_images())
            
            for image in processed_images:
                if isinstance(image, bytes):
                    # 直接使用字节数据发送，避免使用可能过期的URL
                    yield self.event.image_result(image)
                elif image:  # 字符串URL作为后备
                    yield self.event.image_result(image)

        # 结构化日志记录
        if self.screenshots:
            logger.info("Screenshots forwarded",
                        extra={"uin": uin, "count": len(self.screenshots)})