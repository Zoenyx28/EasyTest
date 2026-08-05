import requests
import json
from typing import Optional, Dict, Any, Union
from requests import Response

from common.base_log import logger


class HttpClient:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.base_url = ""
        self.timeout = 30
        self.headers = {}

    def set_base_url(self, base_url: str):
        self.base_url = base_url

    def set_timeout(self, timeout: int):
        self.timeout = timeout

    def set_headers(self, headers: Dict[str, str]):
        self.headers.update(headers)
        self.session.headers.update(headers)

    def set_token(self, token: str):
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def remove_token(self):
        self.token = None
        self.session.headers.pop("Authorization", None)

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Response:
        # 处理相对URL,处理以"/"开头的URL,添加到base_url
        full_url = self.base_url.rstrip("/") + url if url.startswith("/") else url

        logger.info(f"Request: {method.upper()} {full_url}")
        if params:
            logger.info(f"Params: {params}")
        if data:
            logger.info(f"Data: {data}")
        if json:
            logger.info(f"Json: {json}")

        # 当通过 files 发送 multipart/form-data 上传时，requests 会基于 files 自动
        # 生成正确的 Content-Type（含 boundary）。如果 session 默认 headers 里仍带
        # Content-Type: application/json，requests 会认为该请求是 JSON 请求而忽略
        # files 参数，导致后端报 422 '此字段为必填项'。
        # 此处仅当调用方未显式传入 Content-Type 时，才从 session 移除默认值。
        files = kwargs.get("files")
        is_multipart = bool(files)
        has_explicit_ct = bool(headers and "Content-Type" in headers)
        if is_multipart and not has_explicit_ct:
            self.session.headers.pop("Content-Type", None)

        try:
            _timeout = timeout if timeout is not None else self.timeout
            resp = self.session.request(
                method=method,
                url=full_url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                timeout=_timeout,
                **kwargs
            )

            logger.info(f"Response: {resp.status_code}")
            content_type = resp.headers.get("Content-Type", "")
            is_binary = content_type.startswith("application/octet-stream") or content_type.startswith("application/zip")
            if is_binary:
                logger.info(f"Response Body: <binary> (Content-Type={content_type}, size={len(resp.content)} bytes)")
            else:
                try:
                    logger.info(f"Response Body: {resp.json()}")
                except ValueError:
                    body_preview = resp.text[:500] + ("..." if len(resp.text) > 500 else "")
                    logger.info(f"Response Body: {body_preview}")

            return resp

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {full_url}")
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error: {full_url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception: {e}")
            raise
        finally:
            # 请求结束后如果曾移除过 Content-Type，需要还原为默认的 JSON，
            # 以免影响后续普通 JSON 请求。
            if is_multipart and not has_explicit_ct and self.headers.get("Content-Type"):
                self.session.headers["Content-Type"] = self.headers["Content-Type"]

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        return self._request("get", url, params=params, headers=headers, **kwargs)

    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Response:
        return self._request("post", url, data=data, json=json, headers=headers, timeout=timeout, **kwargs)

    def put(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        return self._request("put", url, data=data, json=json, headers=headers, **kwargs)

    def delete(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        return self._request("delete", url, params=params, headers=headers, **kwargs)

    def patch(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        return self._request("patch", url, data=data, json=json, headers=headers, **kwargs)

    def close(self):
        self.session.close()


http_client = HttpClient()
