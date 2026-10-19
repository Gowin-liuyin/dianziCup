"""安全的RFC9457错误；保留既有error扩展，不返回异常栈或输入值。"""

import uuid

from fastapi import Request
from fastapi.responses import JSONResponse


def problem_response(
    request: Request, status: int, code: str, detail: str, retryable: bool = False
) -> JSONResponse:
    """detail只能由服务端固定业务消息构造，禁止传入原始外部异常。"""
    trace_id = str(uuid.uuid4())
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        headers={"X-Request-ID": trace_id},
        content={
            "type": f"urn:ai-intel:problem:{code}",
            "title": code,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
            "trace_id": trace_id,
            "error": {"code": code, "message": detail, "retryable": retryable, "details": {}},
        },
    )
