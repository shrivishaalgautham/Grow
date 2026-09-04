import httpx
from curl_cffi import requests as curl

from app.config import settings

DECODED_BY_CURL = {"content-encoding", "content-length", "transfer-encoding"}


class ImpersonatingTransport(httpx.BaseTransport):
    def __init__(self, browser: str) -> None:
        self._session = curl.Session(impersonate=browser)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        try:
            upstream = self._session.request(
                request.method,
                str(request.url),
                headers=dict(request.headers),
                content=request.read(),
                timeout=request.extensions.get("timeout", {}).get("read", 10.0),
            )
        except curl.RequestsError as exc:
            raise httpx.TransportError(str(exc), request=request) from exc
        headers = {
            name: value
            for name, value in upstream.headers.items()
            if name.lower() not in DECODED_BY_CURL
        }
        return httpx.Response(upstream.status_code, headers=headers, content=upstream.content)

    def close(self) -> None:
        self._session.close()


def browser_client(headers: dict[str, str], timeout: float = 10.0) -> httpx.Client:
    transport = (
        ImpersonatingTransport(settings.yahoo_impersonate)
        if settings.yahoo_impersonate
        else httpx.HTTPTransport()
    )
    return httpx.Client(headers=headers, timeout=timeout, transport=transport)
