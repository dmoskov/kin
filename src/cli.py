#!/usr/bin/env python3
"""Family Tree CLI — manage your family tree from the command line.

Usage:
    python -m cli init                          # Create the database
    python -m cli add-person ...                # Add a person
    python -m cli add-parent --parent X --child Y
    python -m cli add-union --partner1 X --partner2 Y
    python -m cli add-event --person X --type career ...
    python -m cli relationship X Y              # Describe how X and Y are related
    python -m cli timeline [person_id | --all]  # Chronological narrative
    python -m cli list                          # List everyone
    python -m cli show PERSON_ID                # Show one person's details
    python -m cli search QUERY                  # Search by name
    python -m cli stats                         # Summary counts
    python -m cli import FILE                   # Import from JSON
    python -m cli export FILE                   # Export to JSON
    python -m cli audit [--fix]                 # Find/fix bad relationship data
    python -m cli serve [--port 8000]           # Start web dashboard
"""

import argparse
import sys

from database.connection import init_db
from database.repository import TreeRepository
from import_export.json_io import load_tree, save_tree
from models.citation import Citation, Confidence, EntityType
from models.event import EventType, LifeEvent
from models.person import Gender, Person
from models.relationship import Relationship, RelationshipType, Union, Visibility
from models.source import Source, SourceType
from traversal.relationship_calculator import describe_relationship
from traversal.timeline import family_timeline, format_timeline, person_timeline


def cmd_init(args: argparse.Namespace) -> None:
    path = init_db()
    print(f"Database initialized at {path}")


def cmd_add_person(args: argparse.Namespace) -> None:
    person = Person(
        id=args.id,
        given_name=args.given,
        surname=args.surname,
        gender=Gender(args.gender) if args.gender else Gender.UNKNOWN,
        birth_date=args.birth_date,
        birth_place=args.birth_place,
        death_date=args.death_date,
        death_place=args.death_place,
        maiden_name=args.maiden_name,
        notes=args.notes or "",
    )
    repo = TreeRepository()
    repo.save_person(person)
    print(f"Added: {person}")


def cmd_add_parent(args: argparse.Namespace) -> None:
    rel_type = RelationshipType(args.type) if args.type else RelationshipType.BIOLOGICAL
    visibility = Visibility(args.visibility) if args.visibility else Visibility.EVERYONE
    rel = Relationship(
        parent_id=args.parent, child_id=args.child, rel_type=rel_type, visibility=visibility
    )
    repo = TreeRepository()
    repo.save_relationship(rel)
    print(
        f"Added relationship: {args.parent} -> {args.child} ({rel_type.value}, {visibility.value})"
    )


def cmd_add_union(args: argparse.Namespace) -> None:
    union = Union(
        partner1_id=args.partner1,
        partner2_id=args.partner2,
        union_date=args.date,
        union_place=args.place,
    )
    repo = TreeRepository()
    repo.save_union(union)
    print(f"Added union: {args.partner1} & {args.partner2}")


def cmd_add_event(args: argparse.Namespace) -> None:
    event = LifeEvent(
        person_id=args.person,
        event_type=EventType(args.type),
        date=args.date,
        end_date=args.end_date,
        place=args.place,
        description=args.description or "",
        source=args.source,
    )
    repo = TreeRepository()
    repo.save_event(event)
    print(f"Added event: {event}")


def cmd_relationship(args: argparse.Namespace) -> None:
    repo = TreeRepository()
    tree = repo.load_tree()
    person_a = tree.get_person(args.person_a)
    person_b = tree.get_person(args.person_b)
    if not person_a:
        print(f"Person not found: {args.person_a}", file=sys.stderr)
        sys.exit(1)
    if not person_b:
        print(f"Person not found: {args.person_b}", file=sys.stderr)
        sys.exit(1)
    label = describe_relationship(tree, args.person_a, args.person_b)
    print(f"{person_b.full_name} is {person_a.full_name}'s {label}")


def cmd_timeline(args: argparse.Namespace) -> None:
    repo = TreeRepository()
    tree = repo.load_tree()
    if args.all:
        entries = family_timeline(tree)
        print("=== Family Timeline ===\n")
    else:
        if not args.person_id:
            print("Specify a person ID or use --all", file=sys.stderr)
            sys.exit(1)
        person = tree.get_person(args.person_id)
        if not person:
            print(f"Person not found: {args.person_id}", file=sys.stderr)
            sys.exit(1)
        entries = person_timeline(tree, args.person_id)
        print(f"=== Timeline: {person.full_name} ===\n")
    if entries:
        print(format_timeline(entries))
    else:
        print("No events found.")


def cmd_list(args: argparse.Namespace) -> None:
    repo = TreeRepository()
    people = repo.list_people()
    if not people:
        print("No people in the database. Use 'add-person' or 'import' to add some.")
        return
    for p in people:
        status = "living" if p.is_living else f"d. {p.death_date or '?'}"
        born = f"b. {p.birth_date}" if p.birth_date else "b. ?"
        print(f"  {p.id:<20s} {p.full_name:<30s} ({born}, {status})")
    print(f"\n  Total: {len(people)} people")


def cmd_show(args: argparse.Namespace) -> None:
    repo = TreeRepository()
    tree = repo.load_tree()
    person = tree.get_person(args.person_id)
    if not person:
        print(f"Person not found: {args.person_id}", file=sys.stderr)
        sys.exit(1)

    # Build a map of field → [source_ids] for inline citations
    person_citations = tree.citations_for(EntityType.PERSON, person.id)
    field_sources: dict[str, list[str]] = {}
    general_sources: list[str] = []
    for c in person_citations:
        if c.field_name:
            field_sources.setdefault(c.field_name, []).append(c.source_id)
        else:
            general_sources.append(c.source_id)

    def _cite(field: str) -> str:
        """Return inline citation tag like ' [fan-chart-2016]'."""
        sids = field_sources.get(field, [])
        if sids:
            return f" [{', '.join(sids)}]"
        return ""

    print(f"\n  {person.full_name}")
    print(f"  {'=' * len(person.full_name)}")
    if person.birth_date:
        place = f" in {person.birth_place}" if person.birth_place else ""
        print(f"  Born: {person.birth_date}{place}{_cite('birth_date')}")
    if person.death_date:
        place = f" in {person.death_place}" if person.death_place else ""
        print(f"  Died: {person.death_date}{place}{_cite('death_date')}")
    if person.maiden_name:
        print(f"  Maiden name: {person.maiden_name}")
    if person.notes:
        print(f"  Notes: {person.notes}")

    parents = tree.parents_of(person.id)
    if parents:
        print(f"\n  Parents: {', '.join(p.full_name for p in parents)}")

    partners = tree.partners_of(person.id)
    if partners:
        print(f"  Partners: {', '.join(p.full_name for p in partners)}")

    siblings = tree.siblings_of(person.id)
    if siblings:
        print(f"  Siblings: {', '.join(p.full_name for p in siblings)}")

    children = tree.children_of(person.id)
    if children:
        print(f"  Children: {', '.join(p.full_name for p in children)}")

    events = tree.events_for(person.id)
    if events:
        print("\n  Life Events:")
        for e in events:
            date = e.date or "?"
            desc = e.description or e.event_type.value
            print(f"    {date}  {desc}")

    # Show sources cited
    all_source_ids = set(general_sources)
    for sids in field_sources.values():
        all_source_ids.update(sids)
    if all_source_ids:
        print("\n  Sources:")
        for sid in sorted(all_source_ids):
            src = tree.sources.get(sid)
            if src:
                n_cites = sum(1 for c in person_citations if c.source_id == sid)
                print(f"    [{sid}] {src.name} ({n_cites} citation{'s' if n_cites != 1 else ''})")
            else:
                print(f"    [{sid}]")
    print()


def cmd_search(args: argparse.Namespace) -> None:
    repo = TreeRepository()
    results = repo.search_people(args.query)
    if not results:
        print(f"No results for '{args.query}'")
        return
    for p in results:
        print(f"  {p.id:<20s} {p.full_name}")
    print(f"\n  {len(results)} result(s)")


def cmd_stats(args: argparse.Namespace) -> None:
    repo = TreeRepository()
    s = repo.stats()
    tree = repo.load_tree()
    gens = tree.num_generations if tree.people else 0
    print("\n  Family Tree Statistics")
    print("  =====================")
    print(f"  People:        {s['people']}")
    print(f"    Living:      {s['living']}")
    print(f"    Deceased:    {s['deceased']}")
    print(f"  Relationships: {s['relationships']}")
    print(f"  Unions:        {s['unions']}")
    print(f"  Life events:   {s['events']}")
    print(f"  Sources:       {s.get('sources', 0)}")
    print(f"  Citations:     {s.get('citations', 0)}")
    print(f"  Generations:   {gens}")
    print()


def cmd_add_source(args: argparse.Namespace) -> None:
    source = Source(
        id=args.id,
        name=args.name,
        source_type=SourceType(args.type) if args.type else SourceType.OTHER,
        author=args.author,
        date=args.date,
        description=args.description or "",
        url=args.url,
    )
    repo = TreeRepository()
    repo.save_source(source)
    print(f"Added source: {source}")


def cmd_cite(args: argparse.Namespace) -> None:
    citation = Citation(
        source_id=args.source,
        entity_type=EntityType(args.entity_type),
        entity_id=args.entity_id,
        field_name=args.field,
        excerpt=args.excerpt or "",
        confidence=Confidence(args.confidence) if args.confidence else Confidence.CONFIRMED,
        notes=args.notes or "",
    )
    repo = TreeRepository()
    repo.save_citation(citation)
    scope = f".{args.field}" if args.field else ""
    print(f"Cited: {args.source} -> {args.entity_type}:{args.entity_id}{scope}")


def cmd_sources(args: argparse.Namespace) -> None:
    repo = TreeRepository()
    sources = repo.list_sources()
    if not sources:
        print("No sources registered. Use 'add-source' to add one.")
        return
    for s in sources:
        cites = repo.citations_by_source(s.id)
        author = f" by {s.author}" if s.author else ""
        date = f" ({s.date})" if s.date else ""
        print(f"  {s.id:<20s} {s.name}{author}{date}  [{len(cites)} citations]")
    print(f"\n  Total: {len(sources)} sources")


def cmd_serve(args: argparse.Namespace) -> None:
    from web_server import serve

    serve(port=args.port)


def cmd_import(args: argparse.Namespace) -> None:
    tree = load_tree(args.file)
    repo = TreeRepository()
    repo.save_tree(tree)
    print(
        f"Imported {tree.num_people} people, "
        f"{len(tree.relationships)} relationships, "
        f"{len(tree.unions)} unions, "
        f"{len(tree.events)} events"
    )


def cmd_export(args: argparse.Namespace) -> None:
    repo = TreeRepository()
    tree = repo.load_tree()
    photos = repo.list_all_photos()
    save_tree(tree, args.file, photos=photos)
    print(f"Exported to {args.file}")


def _birth_year(person) -> int | None:
    import re

    d = getattr(person, "birth_date", None) or ""
    m = re.search(r"\d{4}", d)
    return int(m.group()) if m else None


def cmd_audit(args: argparse.Namespace) -> None:
    """Walk the tree and report structural data problems.

    Detects: self-loops (own parent), ancestor cycles, people with >2 parents
    (often grandparents wrongly linked as parents), duplicate edges, parent born
    after child, implausibly-young parents, unions between a parent and child,
    and disconnected/isolated people.

    --fix auto-corrects only the UNAMBIGUOUS issues (delete self-loops, swap
    parent-after-child edges). Over-parented and disconnected nodes are reported
    for manual review — picking the correct parent needs human judgement.
    """
    from collections import Counter, defaultdict

    from database.repository import _execute, _ph

    repo = TreeRepository()
    tree = repo.load_tree()
    people = tree.people  # id -> Person
    rels = tree.relationships
    unions = getattr(tree, "unions", [])

    def nm(i):
        p = people.get(i)
        return (f"{p.given_name or ''} {p.surname or ''}".strip() or i) if p else f"<{i}>"

    parents_of: dict[str, set] = defaultdict(set)
    for r in rels:
        parents_of[r.child_id].add(r.parent_id)

    self_loops = [(r.parent_id, r.child_id) for r in rels if r.parent_id == r.child_id]
    dup = [k for k, v in Counter((r.parent_id, r.child_id) for r in rels).items() if v > 1]
    over = {c: ps for c, ps in parents_of.items() if len(ps) > 2}

    cycles = set()
    for start in people:
        stack = list(parents_of.get(start, ()))
        seen: set = set()
        while stack:
            cur = stack.pop()
            if cur == start:
                cycles.add(start)
                break
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(parents_of.get(cur, ()))

    reversed_edges, implausible = [], []
    for r in rels:
        if r.parent_id == r.child_id:
            continue
        py, cy = _birth_year(people.get(r.parent_id)), _birth_year(people.get(r.child_id))
        if py is not None and cy is not None:
            if py > cy:
                reversed_edges.append((r.parent_id, r.child_id))
            elif cy - py < 13:
                implausible.append((r.parent_id, r.child_id, cy - py))

    pc_unions = [
        (u.partner1_id, u.partner2_id)
        for u in unions
        if u.partner1_id in parents_of.get(u.partner2_id, ())
        or u.partner2_id in parents_of.get(u.partner1_id, ())
    ]

    # Connected components over parent + union edges (undirected).
    adj: dict[str, set] = defaultdict(set)
    for r in rels:
        adj[r.parent_id].add(r.child_id)
        adj[r.child_id].add(r.parent_id)
    for u in unions:
        adj[u.partner1_id].add(u.partner2_id)
        adj[u.partner2_id].add(u.partner1_id)
    visited: set = set()
    comps = []
    for p in people:
        if p in visited:
            continue
        stack, size = [p], 0
        while stack:
            x = stack.pop()
            if x in visited:
                continue
            visited.add(x)
            size += 1
            stack.extend(a for a in adj.get(x, ()) if a not in visited)
        comps.append(size)
    comps.sort(reverse=True)
    isolated = [p for p in people if not adj.get(p)]

    any_issue = (
        self_loops
        or dup
        or over
        or cycles
        or reversed_edges
        or implausible
        or pc_unions
        or len(comps) > 1
    )
    if not any_issue:
        print(
            f"No issues found ({len(people)} people, {len(rels)} relationships, "
            f"{len(unions)} unions)."
        )
        return

    print(
        f"=== Tree audit: {len(people)} people, {len(rels)} relationships, {len(unions)} unions ==="
    )
    if self_loops:
        print(
            f"\nSELF-LOOPS — own parent ({len(self_loops)}): "
            + ", ".join(nm(p) for p, _ in self_loops)
        )
    if cycles:
        print(
            f"\nCYCLES — own ancestor ({len(cycles)}): " + ", ".join(nm(c) for c in sorted(cycles))
        )
    if dup:
        print(
            f"\nDUPLICATE edges ({len(dup)}): " + ", ".join(f"{nm(p)} -> {nm(c)}" for p, c in dup)
        )
    if reversed_edges:
        print(f"\nPARENT BORN AFTER CHILD ({len(reversed_edges)}):")
        for p, c in reversed_edges:
            print(f"  {nm(p)} -> {nm(c)}")
    if over:
        print(f"\nMORE THAN 2 PARENTS ({len(over)}):")
        for c, ps in over.items():
            gp = [nm(x) for x in ps if any(x in parents_of.get(o, ()) for o in ps if o != x)]
            extra = f"   (look like grandparents: {gp})" if gp else ""
            print(f"  {nm(c)}: {[nm(x) for x in ps]}{extra}")
    if implausible:
        print(f"\nPARENT < 13 YEARS OLDER THAN CHILD ({len(implausible)}):")
        for p, c, d in implausible:
            print(f"  {nm(p)} -> {nm(c)} ({d}y)")
    if pc_unions:
        print(f"\nUNION BETWEEN A PARENT AND CHILD ({len(pc_unions)}):")
        for a, b in pc_unions:
            print(f"  {nm(a)} & {nm(b)}")
    if len(comps) > 1:
        print(
            f"\nDISCONNECTED: {len(comps)} components (sizes {comps[:8]}); "
            f"{len(isolated)} fully isolated people"
        )
        if isolated:
            print("  isolated: " + ", ".join(nm(p) for p in isolated[:15]))

    if args.fix:
        conn = repo._conn()
        try:
            for p, c in self_loops:
                _execute(
                    conn,
                    f"DELETE FROM relationships WHERE parent_id = {_ph()} AND child_id = {_ph()}",
                    (p, c),
                )
            for p, c in reversed_edges:
                _execute(
                    conn,
                    f"UPDATE relationships SET parent_id = {_ph()}, child_id = {_ph()} "
                    f"WHERE parent_id = {_ph()} AND child_id = {_ph()}",
                    (c, p, p, c),
                )
            conn.commit()
        finally:
            conn.close()
        print(
            f"\nFixed {len(self_loops)} self-loop(s) and {len(reversed_edges)} reversed "
            "edge(s). Over-parented / disconnected nodes need manual review."
        )
    else:
        print(
            "\n--fix auto-corrects only the unambiguous issues (self-loops, "
            "parent-after-child). The rest need review."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="family-tree",
        description="Manage your family tree from the command line.",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # init
    sub.add_parser("init", help="Initialize the database")

    # add-person
    ap = sub.add_parser("add-person", help="Add a person")
    ap.add_argument("--id", required=True, help="Unique ID (e.g., 'grandma-alice')")
    ap.add_argument("--given", required=True, help="Given/first name")
    ap.add_argument("--surname", required=True, help="Surname")
    ap.add_argument("--gender", choices=["male", "female", "other", "unknown"])
    ap.add_argument("--birth-date", help="Birth date (YYYY-MM-DD)")
    ap.add_argument("--birth-place", help="Birth place")
    ap.add_argument("--death-date", help="Death date (YYYY-MM-DD)")
    ap.add_argument("--death-place", help="Death place")
    ap.add_argument("--maiden-name", help="Maiden name")
    ap.add_argument("--notes", help="Biographical notes")

    # add-parent
    ap2 = sub.add_parser("add-parent", help="Add a parent-child relationship")
    ap2.add_argument("--parent", required=True, help="Parent person ID")
    ap2.add_argument("--child", required=True, help="Child person ID")
    ap2.add_argument("--type", choices=["biological", "adoptive", "step", "foster"])
    ap2.add_argument("--visibility", choices=["everyone", "extended", "self_and_children"])

    # add-union
    ap3 = sub.add_parser("add-union", help="Add a marriage/partnership")
    ap3.add_argument("--partner1", required=True)
    ap3.add_argument("--partner2", required=True)
    ap3.add_argument("--date", help="Union date")
    ap3.add_argument("--place", help="Union place")

    # add-event
    ap4 = sub.add_parser("add-event", help="Add a life event")
    ap4.add_argument("--person", required=True, help="Person ID")
    ap4.add_argument(
        "--type",
        required=True,
        choices=[e.value for e in EventType],
        help="Event type",
    )
    ap4.add_argument("--date", help="Event date")
    ap4.add_argument("--end-date", help="End date (for spans)")
    ap4.add_argument("--place", help="Event place")
    ap4.add_argument("--description", help="Description")
    ap4.add_argument("--source", help="Source of information")

    # relationship
    ap5 = sub.add_parser("relationship", help="Describe how two people are related")
    ap5.add_argument("person_a", help="Person A ID")
    ap5.add_argument("person_b", help="Person B ID")

    # timeline
    ap6 = sub.add_parser("timeline", help="Show chronological timeline")
    ap6.add_argument("person_id", nargs="?", help="Person ID (or use --all)")
    ap6.add_argument("--all", action="store_true", help="Show entire family timeline")

    # list
    sub.add_parser("list", help="List all people")

    # show
    ap7 = sub.add_parser("show", help="Show details for a person")
    ap7.add_argument("person_id", help="Person ID")

    # search
    ap8 = sub.add_parser("search", help="Search people by name")
    ap8.add_argument("query", help="Search query")

    # stats
    sub.add_parser("stats", help="Show summary statistics")

    # import
    ap9 = sub.add_parser("import", help="Import from JSON file")
    ap9.add_argument("file", help="Path to JSON file")

    # export
    ap10 = sub.add_parser("export", help="Export to JSON file")
    ap10.add_argument("file", help="Output path for JSON file")

    # add-source
    ap11 = sub.add_parser("add-source", help="Register a source document")
    ap11.add_argument("--id", required=True, help="Unique ID (e.g., 'golden-book')")
    ap11.add_argument("--name", required=True, help="Human-readable name")
    ap11.add_argument(
        "--type",
        choices=[t.value for t in SourceType],
        help="Source type",
    )
    ap11.add_argument("--author", help="Author/provider")
    ap11.add_argument("--date", help="Date of source (free text)")
    ap11.add_argument("--description", help="Description")
    ap11.add_argument("--url", help="URL (for public sources)")

    # cite
    ap12 = sub.add_parser("cite", help="Attach a source citation to an entity")
    ap12.add_argument("--source", required=True, help="Source ID")
    ap12.add_argument(
        "--entity-type",
        required=True,
        choices=[t.value for t in EntityType],
        help="Entity type",
    )
    ap12.add_argument("--entity-id", required=True, help="Entity ID (person ID, etc.)")
    ap12.add_argument("--field", help="Specific field (e.g., 'birth_date')")
    ap12.add_argument("--excerpt", help="Relevant quote from source")
    ap12.add_argument(
        "--confidence",
        choices=[c.value for c in Confidence],
        help="Confidence level",
    )
    ap12.add_argument("--notes", help="Additional notes")

    # sources
    sub.add_parser("sources", help="List all registered sources")

    ap_audit = sub.add_parser(
        "audit", help="Flag likely-bad relationship data (reversed edges, cycles)"
    )
    ap_audit.add_argument(
        "--fix", action="store_true", help="Swap the likely-reversed parent-child edges"
    )

    # serve
    ap13 = sub.add_parser("serve", help="Start the web dashboard server")
    ap13.add_argument("--port", type=int, default=8000, help="Port to listen on")

    return parser


COMMANDS = {
    "init": cmd_init,
    "add-person": cmd_add_person,
    "add-parent": cmd_add_parent,
    "add-union": cmd_add_union,
    "add-event": cmd_add_event,
    "relationship": cmd_relationship,
    "timeline": cmd_timeline,
    "list": cmd_list,
    "show": cmd_show,
    "search": cmd_search,
    "stats": cmd_stats,
    "import": cmd_import,
    "export": cmd_export,
    "add-source": cmd_add_source,
    "cite": cmd_cite,
    "sources": cmd_sources,
    "serve": cmd_serve,
    "audit": cmd_audit,
}


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(1)
    handler = COMMANDS.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
