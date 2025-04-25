import httpx
import json
from httpx import Limits, Timeout


# results_example = [
#   {
#     "url": "https://www.weather.com.cn/weather/401070101.shtml",
#     "title": "【芝加哥天气】芝加哥天气预报,天气预报一周,天气预报15天查询",
#     "content": "24日（今天）. 阴. 8℃. <3级. 25日（明天）. 阴转小雨. 15℃ ...",
#     "thumbnail": null,
#     "engine": "google",
#     "template": "default.html",
#     "parsed_url": [
#       "https",
#       "www.weather.com.cn",
#       "/weather/401070101.shtml",
#       "",
#       "",
#       ""
#     ],
#     "img_src": "",
#     "priority": "",
#     "engines": [
#       "google"
#     ],
#     "positions": [
#       1
#     ],
#     "score": 1.0,
#     "category": "general"
#   },
# ]
def search(query: str):
    """执行搜索并返回结果"""
    params = {
        "q": query,
        "format": "json",
        "number_of_results": 4,
    }

    # 配置HTTP客户端
    limits = Limits(max_connections=100, max_keepalive_connections=20)
    timeout = Timeout(10.0, connect=5.0)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    with httpx.Client(limits=limits, timeout=timeout) as client:
        try:
            response = client.get(
                "https://searx.perennialte.ch//search", params=params, headers=headers
            )
            response.raise_for_status()
            results = response.json().get("results", [])  # 获取搜索结果列表
            return results
        except httpx.RequestError as e:
            print(f"请求出错: {e}")
            return []
        except httpx.HTTPStatusError as e:
            print(f"HTTP错误: {e.response.status_code}")
            return []


# 示例用法
if __name__ == "__main__":
    result = search("芝加哥今日天气")
    print(json.dumps(result, indent=2, ensure_ascii=False))
