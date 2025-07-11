import re

import aiohttp
from astrbot.core import logger

# 预编译正则表达式提高性能
_MAGNET_PATTERN = re.compile(r"^magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*")

async def analysis(link: str, url: str):
    # 验证失败时直接返回避免无效请求
    if not _validate_magnet(link):
        logger.error(f"无效的磁力链接: {link}")
        return None

    url = url + "/api/v1/link"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://tmp.nulla.top/"
    }
    params = {"url": link}  # 修复：直接使用原始链接

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"响应数据: {data}")
                    return data
                logger.error(f"请求失败，状态码: {response.status}")
    except Exception as e:
        logger.error(f"请求失败，错误信息: {str(e)}")
    return None  # 确保所有错误路径都返回None

def _validate_magnet(magnet: str) -> bool:
    """验证磁力链接格式有效性"""
    return bool(_MAGNET_PATTERN.match(magnet))