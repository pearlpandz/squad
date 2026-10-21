from app.db.session import get_connection


def get_routing_rule(complexity: str) -> dict[str, str | float] | None:
    query = """
        SELECT
            model_routing_rules.complexity,
            model_routing_rules.intent_hint,
            model_catalog.model_name AS selected_model,
            model_routing_rules.reasoning,
            model_routing_rules.min_confidence,
            model_routing_rules.escalation_complexity
        FROM model_routing_rules
        JOIN model_catalog ON model_catalog.id = model_routing_rules.selected_model_id
        WHERE model_routing_rules.complexity = ?
          AND model_catalog.is_active = 1
    """
    with get_connection() as connection:
        row = connection.execute(query, (complexity,)).fetchone()
    return dict(row) if row else None

