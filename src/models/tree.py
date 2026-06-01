"""FamilyTree — the graph container that ties everything together.

The FamilyTree holds all people, relationships, unions, events, sources,
and citations. It provides the core graph queries: parents, children,
siblings, ancestors, descendants.
"""

from dataclasses import dataclass, field

from .article import NewsArticle
from .citation import Citation, EntityType
from .event import LifeEvent
from .person import Person
from .relationship import Relationship, Union
from .source import Source


@dataclass
class FamilyTree:
    """A complete family tree graph.

    People are nodes. Relationships (parent→child) and Unions (partner↔partner) are edges.
    Events are attached to people as metadata.
    Sources and Citations track provenance of every fact.
    """

    people: dict[str, Person] = field(default_factory=dict)  # id → Person
    relationships: list[Relationship] = field(default_factory=list)  # parent→child edges
    unions: list[Union] = field(default_factory=list)  # partner↔partner
    events: list[LifeEvent] = field(default_factory=list)
    sources: dict[str, Source] = field(default_factory=dict)  # id → Source
    citations: list[Citation] = field(default_factory=list)
    articles: dict[str, NewsArticle] = field(default_factory=dict)  # id → NewsArticle
    person_article_links: dict[str, set[str]] = field(
        default_factory=dict
    )  # person_id → {article_ids}

    # --- Mutators ---

    def add_person(self, person: Person) -> None:
        self.people[person.id] = person

    def add_relationship(self, rel: Relationship) -> None:
        self.relationships.append(rel)

    def add_union(self, union: Union) -> None:
        self.unions.append(union)

    def add_event(self, event: LifeEvent) -> None:
        self.events.append(event)

    def add_source(self, source: Source) -> None:
        self.sources[source.id] = source

    def add_citation(self, citation: Citation) -> None:
        self.citations.append(citation)

    def add_article(self, article: NewsArticle) -> None:
        self.articles[article.id] = article

    def add_person_article_link(self, person_id: str, article_id: str) -> None:
        self.person_article_links.setdefault(person_id, set()).add(article_id)

    # --- Citation queries ---

    def citations_for(self, entity_type: EntityType, entity_id: str) -> list[Citation]:
        """Get all citations for a given entity."""
        return [
            c for c in self.citations if c.entity_type == entity_type and c.entity_id == entity_id
        ]

    def source_ids_for_person(self, person_id: str) -> set[str]:
        """Get all unique source IDs cited for a person."""
        return {
            c.source_id
            for c in self.citations
            if c.entity_type == EntityType.PERSON and c.entity_id == person_id
        }

    # --- Core queries ---

    def get_person(self, person_id: str) -> Person | None:
        return self.people.get(person_id)

    def parents_of(self, person_id: str) -> list[Person]:
        """Get biological/adoptive parents of a person."""
        parent_ids = [r.parent_id for r in self.relationships if r.child_id == person_id]
        return [self.people[pid] for pid in parent_ids if pid in self.people]

    def children_of(self, person_id: str) -> list[Person]:
        """Get all children of a person."""
        child_ids = [r.child_id for r in self.relationships if r.parent_id == person_id]
        return [self.people[cid] for cid in child_ids if cid in self.people]

    def siblings_of(self, person_id: str) -> list[Person]:
        """Get siblings (share at least one parent). Excludes self."""
        parent_ids = {r.parent_id for r in self.relationships if r.child_id == person_id}
        sibling_ids: set[str] = set()
        for pid in parent_ids:
            for r in self.relationships:
                if r.parent_id == pid and r.child_id != person_id:
                    sibling_ids.add(r.child_id)
        return [self.people[sid] for sid in sibling_ids if sid in self.people]

    def partners_of(self, person_id: str) -> list[Person]:
        """Get all marriage/partnership partners."""
        partner_ids = []
        for u in self.unions:
            if u.involves(person_id):
                partner_ids.append(u.other_partner(person_id))
        return [self.people[pid] for pid in partner_ids if pid in self.people]

    def ancestors_of(self, person_id: str, max_depth: int = 20) -> list[Person]:
        """Get all ancestors (parents, grandparents, etc.) via BFS."""
        visited: set[str] = set()
        queue = [person_id]
        ancestors: list[Person] = []
        depth = 0
        while queue and depth < max_depth:
            next_queue: list[str] = []
            for pid in queue:
                for parent in self.parents_of(pid):
                    if parent.id not in visited:
                        visited.add(parent.id)
                        ancestors.append(parent)
                        next_queue.append(parent.id)
            queue = next_queue
            depth += 1
        return ancestors

    def descendants_of(self, person_id: str, max_depth: int = 20) -> list[Person]:
        """Get all descendants (children, grandchildren, etc.) via BFS."""
        visited: set[str] = set()
        queue = [person_id]
        descendants: list[Person] = []
        depth = 0
        while queue and depth < max_depth:
            next_queue: list[str] = []
            for pid in queue:
                for child in self.children_of(pid):
                    if child.id not in visited:
                        visited.add(child.id)
                        descendants.append(child)
                        next_queue.append(child.id)
            queue = next_queue
            depth += 1
        return descendants

    def events_for(self, person_id: str) -> list[LifeEvent]:
        """Get all life events for a person, sorted by date."""
        person_events = [e for e in self.events if e.person_id == person_id]
        return sorted(person_events, key=lambda e: e.date or "")

    def generation_of(self, person_id: str) -> int:
        """Compute generation number (0 = oldest known ancestor in their line)."""
        parents = self.parents_of(person_id)
        if not parents:
            return 0
        return max(self.generation_of(p.id) for p in parents) + 1

    # --- Stats ---

    @property
    def num_people(self) -> int:
        return len(self.people)

    @property
    def num_living(self) -> int:
        return sum(1 for p in self.people.values() if p.is_living)

    @property
    def num_generations(self) -> int:
        if not self.people:
            return 0
        return max(self.generation_of(pid) for pid in self.people) + 1
