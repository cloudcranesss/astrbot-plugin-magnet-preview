import re

import aiohttp
from astrbot.core import logger
async def analysis(link: str, url: str):
    url = url + "/api/v1/link"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://tmp.nulla.top/"
    }
    params = {
        "url": _validate_magnet(link)
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"响应数据: {data}")
                    return data
                else:
                    logger.error(f"请求失败，状态码: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"请求失败，错误信息: {str(e)}")
        return None
    finally:
        await session.close()

def _validate_magnet(magnet: str) -> bool:
    """验证磁力链接格式有效性"""
    pattern = r"^magnet:\?xt=urn:btih:[a-zA-Z0-9]{40}.*"
    return re.match(pattern, magnet) is not None