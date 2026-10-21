from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeSource:
    name: str
    source_type: str
    path_or_url: str
    owner_agent: str


def register_knowledge_source(source: KnowledgeSource) -> KnowledgeSource:
    return source

