from app.models.task import TaskRequest, TaskRoutingDecision
from app.repositories.routing_repository import get_routing_rule


def _decision_from_rule(
    *,
    request: TaskRequest,
    intent: str,
    complexity: str,
    confidence: float,
    reason: str,
) -> TaskRoutingDecision:
    rule = get_routing_rule(complexity)
    if rule is None:
        raise ValueError(f"No routing rule configured for complexity: {complexity}")
    return TaskRoutingDecision(
        intent=intent,
        complexity=complexity,
        selected_model=str(rule["selected_model"]),
        reasoning=str(rule["reasoning"]),
        confidence=confidence,
        reason=reason,
    )


def route_task(request: TaskRequest) -> TaskRoutingDecision:
    prompt = request.prompt.lower()

    if any(word in prompt for word in ["architecture", "security", "migration", "production"]):
        return _decision_from_rule(
            request=request,
            intent="analysis",
            complexity="xhigh",
            confidence=0.72,
            reason="The task appears broad, high-impact, or architecture-sensitive.",
        )

    if any(word in prompt for word in ["debug", "implement", "refactor", "integrate"]):
        return _decision_from_rule(
            request=request,
            intent="engineering",
            complexity="high",
            confidence=0.78,
            reason="The task likely needs code reasoning and tool use.",
        )

    if any(word in prompt for word in ["explain", "summarize", "fundamentals", "draft"]):
        return _decision_from_rule(
            request=request,
            intent="knowledge",
            complexity="low",
            confidence=0.88,
            reason="The task is clear, bounded, and mostly informational.",
        )

    return _decision_from_rule(
        request=request,
        intent="general",
        complexity="medium",
        confidence=0.65,
        reason="Defaulting to a balanced model because the task intent is not explicit.",
    )
