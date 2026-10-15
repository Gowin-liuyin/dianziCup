"""读取剩余两个已授权文档URL；不注入凭据，不跟随重定向。"""

import hashlib
import json
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkRequestError,
    create_network_gateway,
)

RUN_DIRECTORY = Path(__file__).parent
DOCUMENT_URLS = (
    ("hamal.cc.cd", "https://hamal.cc.cd/fofa.html"),
    (
        "xcnh3lhvc740.feishu.cn",
        "https://xcnh3lhvc740.feishu.cn/wiki/CkdiwxYP6ifQaukDalvceLJknOh",
    ),
)


class DocumentText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fragments: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, text: str) -> None:
        if not self.ignored_depth and text.strip():
            self.fragments.append(text.strip())


observations: list[dict[str, object]] = []
for domain, url in DOCUMENT_URLS:
    started_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    gateway = create_network_gateway(
        NetworkPolicy(
            allowed_domains=(domain,),
            max_response_bytes=1048576,
            allowed_content_types=("text/html",),
            total_timeout_seconds=12,
            dns_resolver="cloudflare_doh",
        ),
        max_concurrent_requests=1,
    )
    observation: dict[str, object] = {"url": url, "started_at": started_at}
    try:
        result = gateway.fetch(url, max_redirect_hops=0)
        observation.update(
            status_code=result.status_code,
            bytes=len(result.body),
            sha256=hashlib.sha256(result.body).hexdigest(),
            request_fingerprint_sha256=result.request_fingerprint_sha256,
        )
        if result.status_code == 200:
            parser = DocumentText()
            parser.feed(result.body.decode("utf-8", errors="replace"))
            observation["document_text_characters"] = len("\n".join(parser.fragments))
    except (NetworkRequestError, NetworkPolicyViolation) as error:
        observation["error_code"] = error.code
    observation["finished_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
        timespec="seconds"
    )
    observations.append(observation)
    (RUN_DIRECTORY / "document_gateway_reads.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(observation, ensure_ascii=True))
