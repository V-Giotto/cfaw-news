import json
from pathlib import Path

import httpx

from .schemas import Citation, Judgment, Proposal


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
            ), {"provider": "baseline", "token_usage": None}
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
        return validate_judgment(result, snapshot), {"provider": "baseline", "token_usage": None}


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
            raise ValueError("本轮输入超过 64KB 上限，请缩小范围")
        usage = []
        async with httpx.AsyncClient(
            timeout=self.settings.llm_timeout_seconds, trust_env=False
        ) as client:
            for attempt in range(2):
                try:
                    response = await client.post(
                        self.settings.llm_base_url.rstrip("/") + "/chat/completions",
                        headers={
                            "Authorization": "Bearer "
                            + self.settings.llm_api_key.get_secret_value()
                        },
                        json={
                            "model": self.settings.llm_model,
                            "messages": messages,
                            "temperature": 0,
                            "max_tokens": 2200,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise ValueError(
                        f"模型服务返回 HTTP {exc.response.status_code}；请核对配置或额度"
                    ) from None
                except httpx.TimeoutException:
                    raise ValueError("模型请求超时；本轮没有发布结果") from None
                except httpx.RequestError:
                    raise ValueError("模型服务连接失败；请检查服务地址与网络") from None
                try:
                    payload = response.json()
                    usage.append(payload.get("usage"))
                    content = payload["choices"][0]["message"]["content"]
                    result = validate_judgment(Judgment.model_validate_json(content), snapshot)
                    return result, {
                        "provider": "compatible",
                        "model": self.settings.llm_model,
                        "token_usage": usage,
                        "repair_count": attempt,
                        "prompt_revision": "judgment-v1",
                    }
                except (ValueError, TypeError, KeyError, IndexError):
                    if attempt:
                        raise ValueError(
                            "模型两次输出均未通过结构/引用验证，本轮没有发布结果"
                        ) from None
                    messages.append(
                        {
                            "role": "user",
                            "content": "输出未通过验证。仅返回符合 OUTPUT_SCHEMA 的完整JSON，"
                            "引用只选当前快照允许的ID；不要新增来源或日期。",
                        }
                    )
        raise RuntimeError("unreachable")
