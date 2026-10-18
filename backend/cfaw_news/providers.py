import asyncio
import json
import time
from pathlib import Path

import httpx

from .database import utcnow
from .schemas import Citation, Judgment, Proposal


class ProviderError(ValueError):
    """Only a fixed public message and allowlisted telemetry may leave the adapter."""

    def __init__(self, code: str, message: str, metrics: dict):
        super().__init__(message)
        self.code = code
        self.metrics = {**metrics, "error_code": code}


class ProviderCancelled(asyncio.CancelledError):
    def __init__(self, metrics: dict):
        super().__init__()
        self.metrics = {**metrics, "error_code": "cancelled", "usage_complete": False}


def reported_usage(value):
    """Keep provider-reported counts, never response text or estimated token counts."""
    if not isinstance(value, dict):
        return None
    counts = {}
    for key in (
        "prompt_tokens", "completion_tokens", "total_tokens",
        "prompt_cache_hit_tokens", "prompt_cache_miss_tokens",
    ):
        count = value.get(key)
        if type(count) is int and count >= 0:
            counts[key] = count
    for key, allowed in (
        ("prompt_tokens_details", ("cached_tokens",)),
        ("completion_tokens_details", ("reasoning_tokens",)),
    ):
        details = value.get(key)
        if isinstance(details, dict):
            filtered = {
                name: details[name] for name in allowed
                if type(details.get(name)) is int and details[name] >= 0
            }
            if filtered:
                counts[key] = filtered
    return counts or None


def validate_judgment(result: Judgment, snapshot: dict) -> Judgment:
    evidence = {row["id"]: row for row in snapshot["evidence"]}
    for ref in result.citations:
        row = evidence.get(ref.article_id)
        if not row:
            raise ValueError("引用的报道不属于本轮证据")
        allowed = {paragraph["id"] for paragraph in row["paragraphs"]}
        if row.get("summary"):
            allowed.add("summary")
        if ref.paragraph_id not in allowed:
            raise ValueError("引用段落不存在于本轮快照")
    if result.outcome in {"update", "no_change"} and not result.citations:
        raise ValueError("有事实判断的结果必须引用本轮证据")
    if result.change_kind in {"updated", "withdrawn"}:
        previous = snapshot.get("previous")
        if not previous or not result.material_change:
            raise ValueError("更新/撤回需要前次判断与实质变化说明")
        if previous["basis_hash"] == snapshot["basis_hash"]:
            raise ValueError("相同证据不能宣称发现新的事实变化")
    if result.change_kind == "unchanged" and result.material_change:
        raise ValueError("无变化结果不能携带实质变化")
    if result.outcome == "no_change" and result.change_kind in {"updated", "withdrawn"}:
        raise ValueError("无变化与更新/撤回冲突")
    if result.proposal:
        if not result.citations or result.outcome == "insufficient_evidence":
            raise ValueError("证据不足不能授权行动提议")
        if result.proposal.kind == "trial" and not snapshot["goal"]["trial_requested"]:
            raise ValueError("用户未请求试用，只允许核实任务")
    decision = snapshot.get("previous_decision")
    if decision and decision["basis_hash"] == snapshot["basis_hash"]:
        result.proposal = None
    return result


class BaselineProvider:
    """A transparent retrieval fixture, not model reasoning or semantic change detection."""

    async def judge(self, snapshot: dict) -> tuple[Judgment, dict]:
        evidence = snapshot["evidence"]
        previous = snapshot.get("previous")
        if not evidence:
            return Judgment(
                outcome="insufficient_evidence",
                change_kind="unchanged" if previous else "new",
                summary="本轮有限资料库未召回匹配候选，不能据此认定外界没有新进展。",
                next_step="补充检索关键词或刷新来源，再检查与当前目标直接相关的资料。",
                uncertainties=["这是词法召回结果，尚未进行模型语义判断。"],
            ), {"provider": "baseline", "model_called": False, "token_usage": None}
        same = previous and previous["basis_hash"] == snapshot["basis_hash"]
        refs = [
            Citation(
                article_id=row["id"],
                paragraph_id=(row["paragraphs"][0]["id"] if row["paragraphs"] else "summary"),
            )
            for row in evidence[:3]
            if row["paragraphs"] or row.get("summary")
        ]
        summary = (
            "本轮召回的候选与上次相同；尚未验证是否存在语义层面的事实变化。"
            if same
            else f"BM25 从本地资料中召回 {len(evidence)} 篇候选，"
            "可先核对其中的原句及适用条件。词法匹配不证明这些材料适用于当前目标。"
        )
        proposal = (
            Proposal(
                title="核实资料与个人适用条件",
                kind="verification",
                duration_minutes=20,
                content="阅读本轮候选和原始来源；核对设备、地区、语言、套餐及时间限制；"
                "记录一项已确认条件和一项待核实问题。此安排不表示推荐或已完成产品试用。",
            )
            if snapshot["goal"]["trial_requested"] and refs
            else None
        )
        result = Judgment(
            outcome="needs_review",
            change_kind="unchanged" if same else ("candidates_changed" if previous else "new"),
            summary=summary,
            next_step="先核对候选原句和来源条件，再决定是否值得试用；也可以配置模型进行语义判断。",
            uncertainties=[
                "当前为 BM25 开发基线，未调用大模型。",
                "归档资料反映采集时状态，不代表今天的可用性或价格。",
            ],
            citations=refs,
            proposal=proposal,
        )
        return validate_judgment(result, snapshot), {
            "provider": "baseline", "model_called": False, "token_usage": None,
        }


class CompatibleProvider:
    def __init__(self, settings):
        self.settings = settings
        self.prompt = (Path(__file__).parent / "prompts/judgment.v1.txt").read_text("utf-8")

    async def judge(self, snapshot: dict) -> tuple[Judgment, dict]:
        # No candidate: skip paid inference and preserve an explicit evidence gap.
        if not snapshot["evidence"]:
            result, _ = await BaselineProvider().judge(snapshot)
            result.uncertainties = ["本地资料中没有匹配候选，本轮未调用模型。"]
            return result, {"provider": "compatible", "model_called": False, "token_usage": None}
        started = time.perf_counter()
        metrics = {
            "provider": "compatible",
            "model": self.settings.llm_model,
            "model_called": False,
            "requested_at": utcnow(),
            "max_tokens": self.settings.llm_max_tokens,
            "thinking": self.settings.llm_thinking,
            "prompt_revision": "judgment-v1",
            "request_count": 0,
            "repair_count": 0,
            "attempts": [],
            "token_usage": [],
            "usage_complete": False,
            "validation_passed": False,
        }

        def finish_metrics():
            metrics["provider_elapsed_ms"] = round((time.perf_counter() - started) * 1000)
            metrics["usage_complete"] = bool(metrics["request_count"]) and all(
                isinstance(item, dict) and "total_tokens" in item
                for item in metrics["token_usage"]
            ) and len(metrics["token_usage"]) == metrics["request_count"]

        def fail(code, message):
            finish_metrics()
            raise ProviderError(code, message, metrics)

        def identifier(value):
            if not isinstance(value, str):
                return None
            secret = self.settings.llm_api_key.get_secret_value()
            return (value.replace(secret, "[redacted]") if secret else value)[:200]

        messages = [
            {
                "role": "system",
                "content": self.prompt
                + "\nOUTPUT_SCHEMA:\n"
                + json.dumps(Judgment.model_json_schema(), ensure_ascii=False),
            },
            {"role": "user", "content": "SNAPSHOT:\n" + json.dumps(snapshot, ensure_ascii=False)},
        ]
        if sum(len(m["content"].encode()) for m in messages) > 64000:
            fail("input_too_large", "本轮输入超过 64KB 上限，请缩小范围；未调用模型")
        request_body = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.settings.llm_max_tokens,
            "response_format": {"type": "json_object"},
        }
        # Omit provider-specific options unless explicitly configured.
        if self.settings.llm_thinking != "provider_default":
            request_body["thinking"] = {"type": self.settings.llm_thinking}
        async with httpx.AsyncClient(
            timeout=self.settings.llm_timeout_seconds, trust_env=False
        ) as client:
            for attempt in range(2):
                request_started = time.perf_counter()
                record = {"attempt": attempt + 1, "started_at": utcnow()}
                metrics["attempts"].append(record)
                metrics["model_called"] = True
                metrics["request_count"] = attempt + 1
                metrics["repair_count"] = attempt
                try:
                    response = await client.post(
                        self.settings.llm_base_url.rstrip("/") + "/chat/completions",
                        headers={
                            "Authorization": "Bearer "
                            + self.settings.llm_api_key.get_secret_value()
                        },
                        json=request_body,
                    )
                    record["http_status"] = response.status_code
                    record["elapsed_ms"] = round((time.perf_counter() - request_started) * 1000)
                    response.raise_for_status()
                except asyncio.CancelledError:
                    record["status"] = "cancelled"
                    record["elapsed_ms"] = round((time.perf_counter() - request_started) * 1000)
                    finish_metrics()
                    raise ProviderCancelled(metrics) from None
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    record["status"] = "http_error"
                    if status in {401, 403}:
                        fail("authentication", "模型服务鉴权失败；请检查本地密钥及访问权限")
                    if status == 429:
                        fail("rate_limit", "模型服务限流或额度受限；请稍后重试并检查额度")
                    if status == 402:
                        fail("quota", "模型服务余额不足；请检查账户额度")
                    fail("provider_http", f"模型服务返回 HTTP {status}；本轮没有发布结果")
                except httpx.TimeoutException:
                    record["status"] = "timeout"
                    record["elapsed_ms"] = round((time.perf_counter() - request_started) * 1000)
                    fail("timeout", "模型请求超时；本轮没有发布结果，用量可能未返回")
                except httpx.RequestError:
                    record["status"] = "connection_error"
                    record["elapsed_ms"] = round((time.perf_counter() - request_started) * 1000)
                    fail("connection", "模型服务连接失败；请检查服务地址与网络")
                except httpx.InvalidURL:
                    record["status"] = "invalid_url"
                    fail("configuration", "模型服务地址无效；请检查本地配置")
                try:
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("invalid envelope")
                    usage = reported_usage(payload.get("usage"))
                    metrics["token_usage"].append(usage)
                    record["response_model"] = identifier(payload.get("model"))
                    record["response_id"] = identifier(payload.get("id"))
                    record["system_fingerprint"] = identifier(payload.get("system_fingerprint"))
                    choice = payload["choices"][0]
                    if not isinstance(choice, dict):
                        raise ValueError("invalid choice")
                    reason = choice.get("finish_reason")
                    record["finish_reason"] = identifier(reason)
                    if reason == "length":
                        record["status"] = "output_truncated"
                        fail("output_truncated", "模型输出达到长度上限；请调整输出预算后重试")
                    if reason == "content_filter":
                        record["status"] = "content_filtered"
                        fail("content_filtered", "模型服务未提供可用结果；本轮没有发布判断")
                    message = choice["message"]
                    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                        raise ValueError("missing final content")
                    result = validate_judgment(
                        Judgment.model_validate_json(message["content"]), snapshot
                    )
                    record["status"] = "validated"
                    metrics["response_model"] = record["response_model"]
                    metrics["validation_passed"] = True
                    finish_metrics()
                    return result, metrics
                except ProviderError:
                    raise
                except (ValueError, TypeError, KeyError, IndexError):
                    record["status"] = "invalid_output"
                    if attempt:
                        fail(
                            "invalid_output",
                            "模型两次输出均未通过结构/引用验证，本轮没有发布结果"
                        )
                    messages.append(
                        {
                            "role": "user",
                            "content": "输出未通过验证。仅返回符合 OUTPUT_SCHEMA 的完整JSON，"
                            "引用只选当前快照允许的ID；不要新增来源或日期。",
                        }
                    )
        raise RuntimeError("unreachable")
