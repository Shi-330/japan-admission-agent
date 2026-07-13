# 经验：CORS 踩坑

## 现象

浏览器访问 `127.0.0.1:8000`（FastAPI 服务），前端能加载但所有 API 请求报 `Failed to fetch`。

## 根因

浏览器把 `127.0.0.1` 和 `localhost` 当作**不同源**。前端 JS 里的 `VITE_API_URL=http://localhost:8000`，但页面地址是 `http://127.0.0.1:8000` → 跨域，CORS 拦截。

## 修法

`backend/api/server.py` CORS 配置中同时加 `localhost:8000` 和 `127.0.0.1:8000`：

```python
allow_origins=[
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    ...
]
```

## 避免方法

1. 浏览器统一用 `localhost:8000`，别混用 `127.0.0.1`
2. CORS 配置里把常用端口两个地址都写上
