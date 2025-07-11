from typing import Optional, Any, Generator
import astrbot.api.message_components as comp
from astrbot.core.platform import AstrMessageEvent
from astrbot.core import logger


class ForwardMessage:
    def __init__(self, event: AstrMessageEvent, messages: list[str], screenshots: Optional[list] = None) -> None:
        self.event = event
        self.self_id = int(self.event.get_self_id())
        self.messages = messages
        self.screenshots = screenshots

    def send_by_qq(self) -> Generator[Any, Any, None]:
        uin = self.self_id  # 预计算重复值
        bot_name = "CloudCrane Bot"
        nodes = []

        # 合并循环：每个message后紧跟对应图片
        for idx, message in enumerate(self.messages):
            # 处理消息
            text_content = str(message) if message is not None else ""
            nodes.append(
                comp.Node(
                    uin=uin,
                    name=bot_name,
                    content=[comp.Plain(text_content)]
                )
            )

            # 处理当前消息对应的图片 (如果存在可用截图)
            if idx < len(self.screenshots):  # 确保不越界
                url = self.screenshots[idx]
                nodes.append(
                    comp.Node(
                        uin=uin,
                        name=bot_name,
                        content=[comp.Image.fromURL(url)]
                    )
                )

        # 记录日志（复用预存变量）
        if self.screenshots:
            logger.info(f"{uin} forward screenshots: {self.screenshots}")

        yield self.event.chain_result([comp.Nodes(nodes)])