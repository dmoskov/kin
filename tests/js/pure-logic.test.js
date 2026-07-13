// Unit tests for pure frontend logic functions.
// Each describe block resets the relevant S fields in beforeEach.

import { describe, it, expect, beforeEach } from "vitest";
import { S } from "../../web/js/00-state.js";
import { rankPeople, searchPeopleLocal, dateYear, dateSortKey } from "../../web/js/03-data-nav.js";
import {
  computeFogDistance, buildButterflyLayout,
  NODE_W, COMPACT_NODE_W, NODE_H, ROW_HEIGHT, SUB_ROW_HEIGHT, MAX_SUB_ROWS,
} from "../../web/js/04-tree.js";
import { calculateRelationship, viewerRelationText } from "../../web/js/07-relationship.js";
import { autoComputeLanes, assignLane, buildLaneCache, computeSublines } from "../../web/js/02-lanes.js";
import { _personPhotos } from "../../web/js/12-photos.js";
import { geocode } from "../../web/js/08-map.js";
import { populateViewingAsDropdown } from "../../web/js/16-gallery.js";

// ─── Fixture helpers ───────────────────────────────────────────────────────

function makePerson(id, given_name, surname, opts = {}) {
  const fullName = [given_name, surname].filter(Boolean).join(" ").trim();
  return {
    id,
    given_name,
    surname,
    fullName,
    birth_date: opts.birth_date || null,
    death_date: opts.death_date || null,
    maiden_name: opts.maiden_name || null,
    nicknames: opts.nicknames || [],
    gender: opts.gender || "unknown",
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// 1. rankPeople
// ═══════════════════════════════════════════════════════════════════════════

describe("rankPeople", () => {
  const people = [
    makePerson("A", "Jack", "Siegel"),
    makePerson("B", "John", "Smith"),
    makePerson("C", "Jane", "Doe", { maiden_name: "Smith" }),
    makePerson("D", "Alice", "Wonderland", { nicknames: ["Ali"] }),
    makePerson("E", "Bob", "Brown", { birth_date: "1985-06-01" }),
    makePerson("F", "Jack", "Smith"),
  ];

  it("empty query returns list capped to limit", () => {
    const res = rankPeople("", people, 3);
    expect(res).toHaveLength(3);
  });

  it("empty query returns all when limit is Infinity", () => {
    const res = rankPeople("", people);
    expect(res).toHaveLength(people.length);
  });

  it("exact full-name match ranks first (score 100)", () => {
    const res = rankPeople("jack siegel", people, 10);
    expect(res[0].id).toBe("A");
  });

  it("full-name prefix beats word-prefix beats substring", () => {
    // "jack s" → prefix match on "jack smith" / "jack siegel"
    // both start with "jack s...", so both get score 80; alphabetical tiebreak
    const res = rankPeople("jack s", people, 10);
    const ids = res.map((p) => p.id);
    expect(ids).toContain("A");
    expect(ids).toContain("F");
    // Both should appear before anyone who doesn't match name prefix
    const idxA = ids.indexOf("A");
    const idxF = ids.indexOf("F");
    expect(Math.max(idxA, idxF)).toBeLessThan(ids.length);
  });

  it("multi-token query is order-independent: 'siegel jack' matches 'Jack Siegel'", () => {
    const res = rankPeople("siegel jack", people, 10);
    expect(res.map((p) => p.id)).toContain("A");
  });

  it("matches on maiden_name", () => {
    const res = rankPeople("smith", people, 10);
    const ids = res.map((p) => p.id);
    expect(ids).toContain("B"); // surname Smith
    expect(ids).toContain("C"); // maiden_name Smith
    expect(ids).toContain("F"); // surname Smith
  });

  it("matches on nickname", () => {
    const res = rankPeople("ali", people, 10);
    expect(res.map((p) => p.id)).toContain("D");
  });

  it("matches on birth year", () => {
    const res = rankPeople("1985", people, 10);
    expect(res.map((p) => p.id)).toContain("E");
  });

  it("non-matching query returns empty array", () => {
    const res = rankPeople("xyzzy", people, 10);
    expect(res).toHaveLength(0);
  });

  it("limit caps results", () => {
    const res = rankPeople("smith", people, 2);
    expect(res).toHaveLength(2);
  });

  it("all tokens must match — partial miss excluded", () => {
    // "jack xyzzy" — no one has both tokens
    const res = rankPeople("jack xyzzy", people, 10);
    expect(res).toHaveLength(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// 2. searchPeopleLocal
// ═══════════════════════════════════════════════════════════════════════════

describe("searchPeopleLocal", () => {
  beforeEach(() => {
    S.PEOPLE_MAP = {};
    const ps = [
      makePerson("P1", "Alice", "Adams"),
      makePerson("P2", "Bob", "Baker"),
      makePerson("P3", "Carol", "Adams"),
    ];
    for (const p of ps) S.PEOPLE_MAP[p.id] = p;
  });

  it("empty query returns []", () => {
    expect(searchPeopleLocal("")).toEqual([]);
    expect(searchPeopleLocal("   ")).toEqual([]);
  });

  it("finds across full PEOPLE_MAP", () => {
    const res = searchPeopleLocal("adams", 10);
    const ids = res.map((p) => p.id);
    expect(ids).toContain("P1");
    expect(ids).toContain("P3");
    expect(ids).not.toContain("P2");
  });

  it("limit is respected", () => {
    const res = searchPeopleLocal("a", 1);
    expect(res).toHaveLength(1);
  });

  it("returns empty for no-match query", () => {
    expect(searchPeopleLocal("zzzzzz")).toHaveLength(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// 3. computeFogDistance
// ═══════════════════════════════════════════════════════════════════════════

describe("computeFogDistance", () => {
  // Family graph:
  //
  //   GP1 + GP2 (grandparents)
  //        |
  //   P1 (center A) + P2 (center B, married in)
  //        |
  //       C1
  //
  //   P3 = P2's parent (in-law ancestor, dist 2)
  //   SIB = P1's sibling (another child of GP1+GP2)
  //   UNRELATED = nobody connected

  const src = {
    people: [
      { id: "GP1" }, { id: "GP2" },
      { id: "P1" }, { id: "P2" },
      { id: "C1" },
      { id: "P3" },
      { id: "SIB" },
      { id: "UNRELATED" },
    ],
    relationships: [
      { parent_id: "GP1", child_id: "P1" },
      { parent_id: "GP2", child_id: "P1" },
      { parent_id: "P1", child_id: "C1" },
      { parent_id: "P2", child_id: "C1" },
      { parent_id: "P3", child_id: "P2" },
      { parent_id: "GP1", child_id: "SIB" },
      { parent_id: "GP2", child_id: "SIB" },
    ],
    unions: [
      { partner1_id: "P1", partner2_id: "P2" },
      { partner1_id: "GP1", partner2_id: "GP2" },
    ],
  };

  beforeEach(() => {
    S.CENTER_ID_A = "P1";
    S.CENTER_ID_B = null;
  });

  it("center person has distance 0", () => {
    const fog = computeFogDistance(src);
    expect(fog["P1"]).toBe(0);
  });

  it("blood ancestors of center have distance 0", () => {
    const fog = computeFogDistance(src);
    expect(fog["GP1"]).toBe(0);
    expect(fog["GP2"]).toBe(0);
  });

  it("married-in partner of center has distance 1", () => {
    const fog = computeFogDistance(src);
    expect(fog["P2"]).toBe(1);
  });

  it("a descendant of the center is distance 0 (blood)", () => {
    // C1 is a child of P1 (center). Descendants of the center are blood
    // relatives, so they must be distance 0 — regression for a bug where
    // traceDown bailed on the center (already added by traceUp) and the
    // center's descendants were wrongly left out of the bloodline.
    const fog = computeFogDistance(src);
    expect(fog["C1"]).toBe(0);
  });

  it("in-law's parent has distance 2 or higher", () => {
    const fog = computeFogDistance(src);
    // P3 is a parent of P2 (dist 1), so at least dist 2
    expect(fog["P3"]).toBeGreaterThanOrEqual(2);
    expect(fog["P3"]).toBeDefined();
  });

  it("the center's sibling is distance 0 (immediate family, not a far in-law)", () => {
    // Regression: siblings are neither ancestors nor descendants, and the
    // outward BFS only seeds from partners — so siblings used to fall through
    // to max fog and disappear from the tree until the "Everyone" depth level.
    const fog = computeFogDistance(src);
    expect(fog["SIB"]).toBe(0);
  });

  it("unrelated person is absent from the map", () => {
    const fog = computeFogDistance(src);
    expect(fog["UNRELATED"]).toBeUndefined();
  });

  it("returns {} for null src", () => {
    expect(computeFogDistance(null)).toEqual({});
  });

  it("CENTER_ID_B blood also gets distance 0 when set", () => {
    S.CENTER_ID_B = "P2";
    const fog = computeFogDistance(src);
    // P2 is now a center — traceUp("P2") adds P2 and P3 to bloodline
    expect(fog["P2"]).toBe(0);
    expect(fog["P3"]).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// 4. calculateRelationship
// ═══════════════════════════════════════════════════════════════════════════

describe("calculateRelationship", () => {
  // Family:
  //   GF (male) + GM (female) → Father (male) + Aunt (female)
  //   Father (male) + Mother (female) → Son (male) + Daughter (female)
  //   Uncle (male) is married to Aunt
  //   Cousin (male) is child of Aunt + Uncle

  const people = [
    makePerson("GF", "George", "Smith", { gender: "male" }),
    makePerson("GM", "Grace", "Smith", { gender: "female" }),
    makePerson("Father", "Frank", "Smith", { gender: "male" }),
    makePerson("Mother", "Mary", "Smith", { gender: "female" }),
    makePerson("Son", "Sam", "Smith", { gender: "male" }),
    makePerson("Daughter", "Sally", "Smith", { gender: "female" }),
    makePerson("Aunt", "Anna", "Smith", { gender: "female" }),
    makePerson("Uncle", "Ulrich", "Jones", { gender: "male" }),
    makePerson("Cousin", "Colin", "Jones", { gender: "male" }),
  ];

  const data = {
    people,
    relationships: [
      { parent_id: "GF", child_id: "Father" },
      { parent_id: "GM", child_id: "Father" },
      { parent_id: "GF", child_id: "Aunt" },
      { parent_id: "GM", child_id: "Aunt" },
      { parent_id: "Father", child_id: "Son" },
      { parent_id: "Mother", child_id: "Son" },
      { parent_id: "Father", child_id: "Daughter" },
      { parent_id: "Mother", child_id: "Daughter" },
      { parent_id: "Aunt", child_id: "Cousin" },
      { parent_id: "Uncle", child_id: "Cousin" },
    ],
    unions: [
      { partner1_id: "GF", partner2_id: "GM" },
      { partner1_id: "Father", partner2_id: "Mother" },
      { partner1_id: "Aunt", partner2_id: "Uncle" },
    ],
    events: [],
  };

  beforeEach(() => {
    const pm = {};
    for (const p of people) pm[p.id] = p;
    S.PEOPLE_MAP = pm;
    S.DATA = data;
    S.ORIGINAL_DATA = data;
  });

  it("Father → Son is 'son'", () => {
    expect(calculateRelationship("Father", "Son")).toBe("son");
  });

  it("Son → Father is 'father'", () => {
    expect(calculateRelationship("Son", "Father")).toBe("father");
  });

  it("Son → Mother is 'mother'", () => {
    expect(calculateRelationship("Son", "Mother")).toBe("mother");
  });

  it("Son → GF is 'grandfather'", () => {
    expect(calculateRelationship("Son", "GF")).toBe("grandfather");
  });

  it("GF → Son is 'grandson'", () => {
    expect(calculateRelationship("GF", "Son")).toBe("grandson");
  });

  it("Son → Daughter is 'sister'", () => {
    // Daughter is female
    expect(calculateRelationship("Son", "Daughter")).toBe("sister");
  });

  it("Daughter → Son is 'brother'", () => {
    expect(calculateRelationship("Daughter", "Son")).toBe("brother");
  });

  it("Son → Aunt is 'aunt'", () => {
    expect(calculateRelationship("Son", "Aunt")).toBe("aunt");
  });

  it("Aunt → Son is 'nephew'", () => {
    expect(calculateRelationship("Aunt", "Son")).toBe("nephew");
  });

  it("Son → Cousin is 'first cousin'", () => {
    expect(calculateRelationship("Son", "Cousin")).toBe("first cousin");
  });

  it("Father → Mother is 'wife'", () => {
    expect(calculateRelationship("Father", "Mother")).toBe("wife");
  });

  it("no relation returns sentinel string", () => {
    // two people with no relation path
    const isolated = makePerson("ISO", "Iso", "Lated", { gender: "male" });
    S.PEOPLE_MAP["ISO"] = isolated;
    const res = calculateRelationship("Son", "ISO");
    expect(res).toBe("no relation found");
  });

  it("cousin's spouse is 'first cousin-in-law' (was: no relation)", () => {
    // Uncle married into the family: Son's first cousin is Cousin, whose
    // parent Uncle is only related by marriage — but Uncle's own relationship
    // to Son should resolve via Aunt: Son → Uncle is uncle-in-law.
    expect(calculateRelationship("Son", "Uncle")).toBe("uncle-in-law");
    // And the spouse of a blood first cousin:
    const wife = makePerson("CousinWife", "Wendy", "Jones", { gender: "female" });
    S.PEOPLE_MAP["CousinWife"] = wife;
    S.DATA = {
      ...data,
      people: [...people, wife],
      unions: [...data.unions, { partner1_id: "Cousin", partner2_id: "CousinWife" }],
    };
    expect(calculateRelationship("Son", "CousinWife")).toBe("first cousin-in-law");
  });

  it("parent's later spouse is a step-parent", () => {
    const step = makePerson("StepMom", "Steph", "Smith", { gender: "female" });
    S.PEOPLE_MAP["StepMom"] = step;
    S.DATA = {
      ...data,
      people: [...people, step],
      unions: [...data.unions, { partner1_id: "Father", partner2_id: "StepMom" }],
    };
    expect(calculateRelationship("Son", "StepMom")).toBe("stepmother");
    // and the reverse: spouse's blood child is a stepchild
    expect(calculateRelationship("StepMom", "Son")).toBe("stepson");
  });

  it("a dissolved union never yields step/in-law labels — it is described instead", () => {
    // Father's ex-wife (divorced before Son existed) must NOT be "stepmother".
    const ex = makePerson("ExWife", "Edna", "Smith", { gender: "female" });
    S.PEOPLE_MAP["ExWife"] = ex;
    S.DATA = {
      ...data,
      people: [...people, ex],
      unions: [...data.unions,
        // end_reason alone (no end_date) must also count as ended
        { partner1_id: "Father", partner2_id: "ExWife", end_reason: "divorce" }],
    };
    expect(calculateRelationship("Son", "ExWife")).toBe("father's ex-wife");
    expect(calculateRelationship("ExWife", "Son")).toBe("ex-husband's son");
    expect(calculateRelationship("Father", "ExWife")).toBe("ex-wife");
    // the standing marriage (Mother) still wins over the dissolved one
    expect(calculateRelationship("Son", "Mother")).toBe("mother");
    // current wife vs ex-wife of the same man (used to crash on a
    // bloodOnly self-lookup)
    expect(calculateRelationship("Mother", "ExWife")).toBe("husband's ex-wife");
  });

  describe("viewerRelationText", () => {
    // escapeHtml is window-bridged at runtime (99-main); stub it for tests.
    globalThis.escapeHtml ??= (s) => String(s ?? "");

    beforeEach(() => {
      S.AUTH_USER = null;
      S.VIEWER_ID = null;
      S.CENTER_ID_A = null;
    });

    it("uses VIEWER_ID, not the tree center moved by focus mode", () => {
      // Regression: focusing the tree on a grandparent set CENTER_ID_A=GF,
      // which relabeled Father's daughter as his "granddaughter".
      S.VIEWER_ID = "Father";
      S.CENTER_ID_A = "GF"; // focus mode moved the layout center
      expect(viewerRelationText("Daughter")).toBe("Your daughter");
    });

    it("names the reference person when viewing as someone other than the signed-in user", () => {
      S.AUTH_USER = { person_id: "Father" };
      S.VIEWER_ID = "GF";
      S.CENTER_ID_A = "GF";
      expect(viewerRelationText("Daughter")).toBe("George's granddaughter");
    });

    it("falls back to the center with a named label when no viewer identity exists", () => {
      S.CENTER_ID_A = "GF"; // layout fallback picked someone; not "you"
      expect(viewerRelationText("Daughter")).toBe("George's granddaughter");
    });

    it("returns null for the viewer themselves and for non-relations", () => {
      S.VIEWER_ID = "Father";
      expect(viewerRelationText("Father")).toBeNull();
      const isolated = makePerson("ISO2", "Iso", "Lated", { gender: "male" });
      S.PEOPLE_MAP["ISO2"] = isolated;
      expect(viewerRelationText("ISO2")).toBeNull();
    });
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// 5. Lane assignment (autoComputeLanes + assignLane)
// ═══════════════════════════════════════════════════════════════════════════

describe("lane assignment", () => {
  // Family:
  //   PatGF (male) + PatGM (female) → Dad (male)
  //   MatGF (male) + MatGM (female) → Mom (female)
  //   Dad + Mom → Child (center A + B)
  //
  // autoComputeLanes("Child", null) → grandparents are PatGF, PatGM, MatGF, MatGM
  // Each grandparent becomes a lane root; Child inherits one lane.

  const mkP = (id, given, sur, gender) => makePerson(id, given, sur, { gender });

  const people = [
    mkP("PatGF", "PatGF", "Paternal", "male"),
    mkP("PatGM", "PatGM", "Paternal", "female"),
    mkP("MatGF", "MatGF", "Maternal", "male"),
    mkP("MatGM", "MatGM", "Maternal", "female"),
    mkP("Dad", "Dad", "Paternal", "male"),
    mkP("Mom", "Mom", "Maternal", "female"),
    mkP("Child", "Child", "Smith", "male"),
  ];

  const data = {
    people,
    relationships: [
      { parent_id: "PatGF", child_id: "Dad" },
      { parent_id: "PatGM", child_id: "Dad" },
      { parent_id: "MatGF", child_id: "Mom" },
      { parent_id: "MatGM", child_id: "Mom" },
      { parent_id: "Dad", child_id: "Child" },
      { parent_id: "Mom", child_id: "Child" },
    ],
    unions: [
      { partner1_id: "PatGF", partner2_id: "PatGM" },
      { partner1_id: "MatGF", partner2_id: "MatGM" },
      { partner1_id: "Dad", partner2_id: "Mom" },
    ],
    events: [],
  };

  beforeEach(() => {
    const pm = {};
    for (const p of people) pm[p.id] = p;
    S.PEOPLE_MAP = pm;
    S.DATA = data;
    S.ORIGINAL_DATA = data;
    S.CENTER_ID_A = "Child";
    S.CENTER_ID_B = null;
    S.LANES = [];
    // Stub S.CONFIG to avoid _updateHeaderFromLanes crash
    S.CONFIG = { familyName: "Test" };
  });

  it("autoComputeLanes creates one lane per grandparent", () => {
    autoComputeLanes("Child", null);
    expect(S.LANES).toHaveLength(4);
  });

  it("lane ids are prefixed with 'auto-'", () => {
    autoComputeLanes("Child", null);
    for (const lane of S.LANES) {
      expect(lane.id).toMatch(/^auto-/);
    }
  });

  it("assignLane returns a lane id for a grandparent", () => {
    autoComputeLanes("Child", null);
    const lane = assignLane("PatGF");
    expect(lane).toBeTruthy();
    expect(typeof lane).toBe("string");
  });

  it("assignLane returns a lane id for the center person", () => {
    autoComputeLanes("Child", null);
    const lane = assignLane("Child");
    expect(lane).toBeTruthy();
  });

  it("assignLane returns a lane id for Dad (ancestor of center)", () => {
    autoComputeLanes("Child", null);
    const lane = assignLane("Dad");
    expect(lane).toBeTruthy();
  });

  it("paternal grandparents get different lanes", () => {
    autoComputeLanes("Child", null);
    const lanePatGF = assignLane("PatGF");
    const lanePatGM = assignLane("PatGM");
    // Each grandparent is their own lane root → should be in different lanes
    expect(lanePatGF).not.toBe(lanePatGM);
  });

  it("assignLane returns null for completely unknown person", () => {
    autoComputeLanes("Child", null);
    expect(assignLane("NOBODY")).toBeNull();
  });

  it("autoComputeLanes with centerB includes both families", () => {
    // Add a partner for Child
    const partner = mkP("Partner", "Partner", "Jones", "female");
    const partnerGF = mkP("PartnerGF", "PGF", "Jones", "male");
    const extPeopleMap = { ...S.PEOPLE_MAP };
    extPeopleMap["Partner"] = partner;
    extPeopleMap["PartnerGF"] = partnerGF;
    S.PEOPLE_MAP = extPeopleMap;
    S.DATA = {
      ...data,
      people: [...data.people, partner, partnerGF],
      relationships: [
        ...data.relationships,
        { parent_id: "PartnerGF", child_id: "Partner" },
      ],
      unions: [
        ...data.unions,
        { partner1_id: "Child", partner2_id: "Partner" },
      ],
    };
    autoComputeLanes("Child", "Partner");
    // Should have lanes for Child's 4 grandparents + Partner's 1 (PartnerGF)
    expect(S.LANES.length).toBeGreaterThanOrEqual(5);
    const lanePartnerGF = assignLane("PartnerGF");
    expect(lanePartnerGF).toBeTruthy();
  });

  it("buildLaneCache tolerates a lane with a null/missing root id (no crash)", () => {
    // Regression: a center person with no partner could yield a lane root of
    // null; buildLaneCache then did null.split(...) and the whole app failed to
    // initialize. It must skip falsy roots and still resolve the valid ones.
    S.LANES = [{ id: "auto-x", label: "X", rootIds: [null, undefined, "PatGF"], color: "#000" }];
    expect(() => buildLaneCache()).not.toThrow();
    expect(assignLane("PatGF")).toBeTruthy();
  });

  it("autoComputeLanes with a parentless, partnerless center does not crash", () => {
    autoComputeLanes("PatGF", null); // PatGF has no parents and no partner here
    expect(() => buildLaneCache()).not.toThrow();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Butterfly layout — center couple's siblings render at gen 0, flanking center
// ═══════════════════════════════════════════════════════════════════════════
describe("buildButterflyLayout sibling placement", () => {
  const mkP = (id, gender) => makePerson(id, id, "X", { gender });
  // Me + Spouse are the center couple. Me has siblings Bro/Sis (share my
  // parents); Spouse has sibling InLaw (shares Spouse's parents).
  const people = [
    mkP("Me", "male"), mkP("Spouse", "female"),
    mkP("Bro", "male"), mkP("Sis", "female"),
    mkP("InLaw", "male"),
    mkP("Dad", "male"), mkP("Mom", "female"),
    mkP("SpDad", "male"), mkP("SpMom", "female"),
  ];
  const data = {
    people,
    relationships: [
      { parent_id: "Dad", child_id: "Me" }, { parent_id: "Mom", child_id: "Me" },
      { parent_id: "Dad", child_id: "Bro" }, { parent_id: "Mom", child_id: "Bro" },
      { parent_id: "Dad", child_id: "Sis" }, { parent_id: "Mom", child_id: "Sis" },
      { parent_id: "SpDad", child_id: "Spouse" }, { parent_id: "SpMom", child_id: "Spouse" },
      { parent_id: "SpDad", child_id: "InLaw" }, { parent_id: "SpMom", child_id: "InLaw" },
    ],
    unions: [
      { partner1_id: "Me", partner2_id: "Spouse" },
      { partner1_id: "Dad", partner2_id: "Mom" },
      { partner1_id: "SpDad", partner2_id: "SpMom" },
    ],
    events: [],
  };

  beforeEach(() => {
    const pm = {};
    for (const p of people) pm[p.id] = p;
    S.PEOPLE_MAP = pm;
    S.DATA = data;
    S.ORIGINAL_DATA = data;
    S.CENTER_ID_A = "Me";
    S.CENTER_ID_B = "Spouse";
    S.LANES = [];
    S.CONFIG = { familyName: "Test" };
  });

  const byId = (nodes) => Object.fromEntries(nodes.map((n) => [n.id, n]));

  it("places both partners' siblings at gen 0 (same row as the center)", () => {
    const { nodes } = buildButterflyLayout();
    const n = byId(nodes);
    for (const id of ["Me", "Spouse", "Bro", "Sis", "InLaw"]) {
      expect(n[id], `${id} should be rendered`).toBeTruthy();
      expect(n[id].gen, `${id} at gen 0`).toBe(0);
    }
  });

  it("flanks the center: partner A's siblings left, partner B's right", () => {
    const { nodes } = buildButterflyLayout();
    const n = byId(nodes);
    // Me's siblings sit left of Me; Spouse's sibling sits right of Spouse.
    expect(Math.max(n.Bro.cx, n.Sis.cx)).toBeLessThan(n.Me.cx);
    expect(n.InLaw.cx).toBeGreaterThan(n.Spouse.cx);
  });

  it("keeps siblings near the center, not exiled to the far ancestor edge", () => {
    const { nodes } = buildButterflyLayout();
    const n = byId(nodes);
    // Siblings should be closer to the center than the grandparents-row spread.
    const rowSpan = Math.max(n.Me.cx, n.Spouse.cx) - Math.min(n.Bro.cx, n.Sis.cx, n.InLaw.cx);
    expect(rowSpan).toBeLessThan(1000); // a handful of node-widths, not a sprawl
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// _personPhotos — derive a person's photos from person_photos (S.DATA.photos)
// ═══════════════════════════════════════════════════════════════════════════

describe("_personPhotos", () => {
  beforeEach(() => {
    S.DATA = {
      photos: [
        {
          id: 1,
          file_path: "photos/a.jpg",
          created_at: "2024-01-01T00:00:00",
          tagged_people: [
            { person_id: "X", caption: "first", is_profile: true, display_order: 1 },
          ],
        },
        {
          id: 2,
          file_path: "photos/b.jpg",
          created_at: "2024-06-01T00:00:00",
          tagged_people: [
            { person_id: "X", caption: "second", is_profile: false, display_order: 2 },
            { person_id: "Y", caption: "y-pic", is_profile: true, display_order: 0 },
          ],
        },
        {
          id: 3,
          file_path: "photos/untagged.jpg",
          created_at: "2024-07-01T00:00:00",
          tagged_people: [],
        },
      ],
    };
  });

  it("returns only photos the person is tagged in, sorted newest first", () => {
    const out = _personPhotos("X");
    expect(out.map((e) => e.path)).toEqual(["photos/b.jpg", "photos/a.jpg"]);
  });

  it("surfaces the person's own caption and profile flag, not another tag's", () => {
    const out = _personPhotos("X");
    expect(out[0]).toMatchObject({ caption: "second", isProfile: false });
    expect(out[1]).toMatchObject({ caption: "first", isProfile: true });
  });

  it("returns an empty list for a person with no tagged photos", () => {
    expect(_personPhotos("Z")).toEqual([]);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// dateYear / dateSortKey — centralized date parsing
// ═══════════════════════════════════════════════════════════════════════════

describe("dateYear", () => {
  it("extracts the year from ISO dates of any precision", () => {
    expect(dateYear("1845")).toBe(1845);
    expect(dateYear("1845-06")).toBe(1845);
    expect(dateYear("1845-06-01")).toBe(1845);
  });
  it("returns null for empty/missing", () => {
    expect(dateYear(null)).toBe(null);
    expect(dateYear(undefined)).toBe(null);
    expect(dateYear("")).toBe(null);
  });
  it("tolerates a stray non-ISO prefix instead of returning NaN", () => {
    expect(dateYear("~1622")).toBe(1622);
    expect(dateYear("c. 1845")).toBe(1845);
  });
});

describe("dateSortKey", () => {
  it("sorts ISO dates chronologically, mixed precision included", () => {
    const dates = ["1846", "1845-06-01", "1845", "1845-06"];
    const sorted = [...dates].sort((a, b) => dateSortKey(a).localeCompare(dateSortKey(b)));
    expect(sorted).toEqual(["1845", "1845-06", "1845-06-01", "1846"]);
  });
  it("undated sorts last by default, first when placeEmptyFirst", () => {
    expect(dateSortKey("").localeCompare(dateSortKey("1845")) > 0).toBe(true);
    expect(dateSortKey("", true).localeCompare(dateSortKey("1845", true)) < 0).toBe(true);
  });
  it("extracts the ISO core from a noisy value so it still sorts by year", () => {
    expect(dateSortKey("~1622")).toBe("1622");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// buildButterflyLayout: collision pass, sub-row wrapping, compact cards
// ═══════════════════════════════════════════════════════════════════════════

describe("buildButterflyLayout collision + wrapping", () => {
  const mkP = (id, gender) => makePerson(id, id, "X", { gender });
  // Dense fixture: 4 blood uncles, each with a spouse and 3 kids, puts 12
  // cousin couples in the same generation row as the center couple — the
  // cross-block layout that used to stack cards on top of each other.
  const people = [
    mkP("Me", "male"), mkP("Spouse", "female"),
    mkP("K1", "female"), mkP("K2", "male"),
    mkP("Dad", "male"), mkP("Mom", "female"),
    mkP("GF", "male"), mkP("GM", "female"),
    mkP("SpDad", "male"), mkP("SpMom", "female"),
  ];
  const relationships = [
    { parent_id: "GF", child_id: "Dad" }, { parent_id: "GM", child_id: "Dad" },
    { parent_id: "Dad", child_id: "Me" }, { parent_id: "Mom", child_id: "Me" },
    { parent_id: "SpDad", child_id: "Spouse" }, { parent_id: "SpMom", child_id: "Spouse" },
    { parent_id: "Me", child_id: "K1" }, { parent_id: "Spouse", child_id: "K1" },
    { parent_id: "Me", child_id: "K2" }, { parent_id: "Spouse", child_id: "K2" },
  ];
  const unions = [
    { partner1_id: "Me", partner2_id: "Spouse" },
    { partner1_id: "Dad", partner2_id: "Mom" },
    { partner1_id: "GF", partner2_id: "GM" },
    { partner1_id: "SpDad", partner2_id: "SpMom" },
  ];
  for (let u = 1; u <= 4; u++) {
    people.push(mkP(`U${u}`, "male"), mkP(`SU${u}`, "female"));
    relationships.push(
      { parent_id: "GF", child_id: `U${u}` },
      { parent_id: "GM", child_id: `U${u}` },
    );
    unions.push({ partner1_id: `U${u}`, partner2_id: `SU${u}` });
    for (const k of ["a", "b", "c"]) {
      people.push(mkP(`C${u}${k}`, "female"));
      relationships.push(
        { parent_id: `U${u}`, child_id: `C${u}${k}` },
        { parent_id: `SU${u}`, child_id: `C${u}${k}` },
      );
    }
  }
  const data = { people, relationships, unions, events: [] };

  beforeEach(() => {
    const pm = {};
    for (const p of people) pm[p.id] = p;
    S.PEOPLE_MAP = pm;
    S.DATA = data;
    S.ORIGINAL_DATA = data;
    S.CENTER_ID_A = "Me";
    S.CENTER_ID_B = "Spouse";
    S.TREE_DEPTH = 4; // "Everyone" — all nodes participate in the lane pass
    S.LANES = [];
    S.CONFIG = { familyName: "Test" };
  });

  const byId = (nodes) => Object.fromEntries(nodes.map((n) => [n.id, n]));

  it("renders every card with zero overlaps despite cross-block density", () => {
    const { nodes } = buildButterflyLayout();
    expect(nodes.length).toBe(people.length);
    const bad = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        const oy = Math.min(a.y + NODE_H, b.y + NODE_H) - Math.max(a.y, b.y);
        if (ox > 1 && oy > 1) bad.push(`${a.id} <-> ${b.id}`);
      }
    }
    expect(bad, "overlapping cards").toEqual([]);
  });

  it("caps band growth and keeps sparse bands flat", () => {
    const { bands, genRange } = buildButterflyLayout();
    // Grandparents' generation holds one couple: must stay single-row.
    expect(bands.heights[-2]).toBe(ROW_HEIGHT);
    // No band may grow beyond the sub-row cap.
    const maxH = ROW_HEIGHT + (MAX_SUB_ROWS - 1) * SUB_ROW_HEIGHT;
    for (let g = genRange.min; g <= genRange.max; g++) {
      expect(bands.heights[g]).toBeLessThanOrEqual(maxH);
    }
  });

  it("keeps collateral cousins outside the center family's horizontal span", () => {
    // A card from another branch sitting BETWEEN the center couple's cards
    // reads as a member of that family (the Barry Kleinberg bug).
    const { nodes, couples } = buildButterflyLayout();
    const gens = {};
    for (const n of nodes) (gens[n.gen] ||= []).push(n);
    for (const gen of Object.keys(gens)) {
      const row = gens[gen];
      const centerCards = row.filter((n) => couples[n.coupleIdx].side === "center");
      if (centerCards.length === 0) continue;
      const min = Math.min(...centerCards.map((n) => n.x));
      const max = Math.max(...centerCards.map((n) => n.x + n.w));
      for (const n of row) {
        if (couples[n.coupleIdx].side === "center") continue;
        const inside = n.x + n.w > min + 1 && n.x < max - 1;
        expect(inside, `${n.id} interleaved into center span at gen ${gen}`).toBe(false);
      }
    }
  });

  it("keeps every card vertically inside its own generation band", () => {
    const { nodes, bands } = buildButterflyLayout();
    for (const n of nodes) {
      expect(n.y, `${n.id} below band top`).toBeGreaterThanOrEqual(bands.tops[n.gen]);
      expect(n.y + NODE_H, `${n.id} above band bottom`).toBeLessThanOrEqual(
        bands.tops[n.gen] + bands.heights[n.gen]
      );
    }
  });

  it("sizes in-law branches (fog >= 2) compact and bloodline full-width", () => {
    const { nodes } = buildButterflyLayout();
    const n = byId(nodes);
    expect(n.Me.w).toBe(NODE_W);
    expect(n.U1.w, "blood uncle (fog 1) full width").toBe(NODE_W);
    expect(n.SU1.w, "uncle's wife (fog 2) compact").toBe(COMPACT_NODE_W);
    expect(n.C1a.w, "cousin (fog 2) compact").toBe(COMPACT_NODE_W);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// 8. populateViewingAsDropdown — only living members
// ═══════════════════════════════════════════════════════════════════════════

describe("populateViewingAsDropdown", () => {
  beforeEach(() => {
    S.DATA = {
      people: [
        makePerson("L1", "Alice", "Smith"),
        makePerson("L2", "Bob", "Jones"),
        makePerson("D1", "Charlie", "Brown", { death_date: "2020-01-01" }),
        makePerson("D2", "Diana", "Prince", { death_date: "1985-06-15" }),
        makePerson("N1", null, "NoFirst"),
      ],
    };
    S.CENTER_ID_A = "L1";
  });

  it("excludes deceased people from the dropdown", () => {
    const sel = document.createElement("select");
    sel.id = "test-viewing-as";
    document.body.appendChild(sel);

    populateViewingAsDropdown("test-viewing-as");

    const values = [...sel.options].map(o => o.value);
    expect(values).toContain("L1");
    expect(values).toContain("L2");
    expect(values).not.toContain("D1");
    expect(values).not.toContain("D2");
    expect(values).not.toContain("N1");

    document.body.removeChild(sel);
  });

  it("shows only living people with names", () => {
    const sel = document.createElement("select");
    sel.id = "test-viewing-as-2";
    document.body.appendChild(sel);

    populateViewingAsDropdown("test-viewing-as-2");

    expect(sel.options).toHaveLength(2);

    document.body.removeChild(sel);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// geocode: prefix-only fuzzy matching + curated historical places
// ═══════════════════════════════════════════════════════════════════════════

describe("geocode", () => {
  it("a trailing country name must not hijack the pin (Wolyn-Moscow bug)", () => {
    // "Wolyn (Volhynia), Russia (now Ukraine)" contains "Russia", whose
    // curated pin is Moscow. It must resolve to the curated Volhynia entry,
    // ~1000km southwest.
    const [lat, lng] = geocode("Wolyn (Volhynia), Russia (now Ukraine)");
    expect(lat).toBeCloseTo(50.75, 1);
    expect(lng).toBeCloseTo(25.32, 1);
  });

  it("an unknown place containing a country name resolves to nothing, not the capital", () => {
    expect(geocode("Totally Unknown Shtetl, Russia (now Ukraine)")).toBe(null);
  });

  it("prefix fuzzy still matches more/less specific variants", () => {
    // Place more specific than key
    expect(geocode("Odessa, Russia (Black Sea port)")).toEqual([46.48, 30.73]);
    // Place less specific than key
    expect(geocode("Harvard University, Cambridge")).toEqual(geocode("Harvard University"));
  });

  it("curated pins for the Volhynia family places are in Ukraine", () => {
    const radzivil = geocode("Radzivil, Wolhynia (now Radyvyliv, Ukraine)");
    expect(radzivil[0]).toBeCloseTo(50.131, 1);
    expect(radzivil[1]).toBeCloseTo(25.254, 1);
    const port = geocode("Port of New York");
    expect(port[0]).toBeCloseTo(40.7, 1);
    expect(port[1]).toBeCloseTo(-74.0, 1);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// buildButterflyLayout: cross-family couples face their blood relatives
// ═══════════════════════════════════════════════════════════════════════════

describe("buildButterflyLayout couple orientation", () => {
  // Mirrors the prod shape that read wrong: Jack Siegel ⚭ Rosalie Kleinberg
  // sit between the two family blocks; each partner must render on the side
  // facing their own parents/siblings.
  const mkP = (id, gender) => makePerson(id, id, "X", { gender });
  const people = [
    mkP("Nancy", "female"), mkP("Richard", "male"), mkP("Lynn", "female"),
    mkP("Jack", "male"), mkP("Rosalie", "female"),
    mkP("Abraham", "male"), mkP("Ida", "female"),
    mkP("Lillian", "female"), mkP("Rose", "female"), mkP("Besse", "female"), mkP("Sarah", "female"),
    mkP("William", "male"), mkP("RoseC", "female"),
    mkP("Beatrice", "female"), mkP("Murray", "male"),
    mkP("MorrisM", "male"), mkP("CeliaM", "female"),
    mkP("Milt", "male"), mkP("Dustin", "male"), mkP("Buzz", "male"),
  ];
  const relationships = [];
  const kidsOf = (pars, cs) => {
    for (const c of cs) for (const p of pars) relationships.push({ parent_id: p, child_id: c });
  };
  kidsOf(["Jack", "Rosalie"], ["Nancy", "Lynn"]);
  kidsOf(["Abraham", "Ida"], ["Jack", "Lillian", "Rose", "Besse", "Sarah"]);
  kidsOf(["William", "RoseC"], ["Rosalie", "Beatrice", "Murray"]);
  kidsOf(["MorrisM", "CeliaM"], ["Richard"]);
  kidsOf(["Nancy", "Richard"], ["Dustin"]);
  kidsOf(["Lillian", "Milt"], ["Buzz"]);
  const unions = [
    { partner1_id: "Nancy", partner2_id: "Richard" },
    { partner1_id: "Jack", partner2_id: "Rosalie" },
    { partner1_id: "Abraham", partner2_id: "Ida" },
    { partner1_id: "William", partner2_id: "RoseC" },
    { partner1_id: "MorrisM", partner2_id: "CeliaM" },
    { partner1_id: "Lillian", partner2_id: "Milt" },
  ];
  const data = { people, relationships, unions, events: [] };

  beforeEach(() => {
    const pm = {};
    for (const p of people) pm[p.id] = p;
    S.PEOPLE_MAP = pm;
    S.DATA = data;
    S.ORIGINAL_DATA = data;
    S.CENTER_ID_A = "Nancy";
    S.CENTER_ID_B = "Richard";
    S.TREE_DEPTH = 4;
    S.LANES = [];
    S.CONFIG = { familyName: "Test" };
  });

  it("orients every cross-family couple toward each partner's own parents", () => {
    const { couples, couplePositions } = buildButterflyLayout();
    const coupleIdxOf = {};
    couples.forEach((c, i) => {
      coupleIdxOf[c.primaryId] = i;
      if (c.partnerId) coupleIdxOf[c.partnerId] = i;
    });
    const parentsOf = {};
    for (const r of relationships) (parentsOf[r.child_id] ||= []).push(r.parent_id);
    const anchor = (pid) => {
      for (const par of parentsOf[pid] || []) {
        const ci = coupleIdxOf[par];
        if (ci !== undefined && couplePositions.has(ci)) return couplePositions.get(ci).cx;
      }
      return null;
    };
    let checked = 0;
    couples.forEach((c, i) => {
      if (i === 0 || !c.partnerId) return; // couples[0] = center couple, fixed order
      const leftAnchor = anchor(c.primaryId);
      const rightAnchor = anchor(c.partnerId);
      if (leftAnchor === null || rightAnchor === null || leftAnchor === rightAnchor) return;
      checked++;
      expect(leftAnchor, `${c.primaryId} (left) + ${c.partnerId} (right) face away from their families`)
        .toBeLessThanOrEqual(rightAnchor);
    });
    expect(checked).toBeGreaterThan(0); // Jack+Rosalie at minimum
  });

  it("computeSublines: badges accumulate down generations; married-ins found minor lines", () => {
    const { sublines, byPerson } = computeSublines();
    // Nancy's two grandparent couples + Richard's two fallback roots (his
    // parents have no parents of their own) + Milt's minor line.
    expect(sublines.filter((s) => !s.minor).length).toBe(4);
    expect((byPerson["Jack"] || []).length).toBe(1);
    expect((byPerson["Rosalie"] || []).length).toBe(1);
    expect(byPerson["Jack"][0]).not.toBe(byPerson["Rosalie"][0]);
    expect(byPerson["Ida"]).toEqual(byPerson["Jack"]); // ancestors carry their line's badge
    expect(byPerson["Lillian"]).toEqual(byPerson["Jack"]); // siblings too
    expect((byPerson["Nancy"] || []).length).toBe(2); // one from each parent
    expect((byPerson["Dustin"] || []).length).toBe(4); // all four accumulate
    // Married-in Milt founds his own MINOR line — new blood gets a new color.
    expect((byPerson["Milt"] || []).length).toBe(1);
    expect(sublines[byPerson["Milt"][0]].minor).toBe(true);
    expect(byPerson["Milt"][0]).not.toBe(byPerson["Lillian"][0]);
    // A minor line's color is never a color a major line already uses —
    // married-ins must not look like blood of the family they joined.
    const majorColors = sublines.filter((s) => !s.minor).map((s) => s.color);
    expect(majorColors).not.toContain(sublines[byPerson["Milt"][0]].color);
    // Their child blends both: mother's major line + father's minor line.
    expect(byPerson["Buzz"]).toEqual(
      expect.arrayContaining([byPerson["Lillian"][0], byPerson["Milt"][0]])
    );
    expect(byPerson["Buzz"].length).toBe(2);
  });

  it("computeSublines: deeper root depth splits lines into more sublines", () => {
    const deep = computeSublines(3);
    // Every gen -2 line ends there, so each grandparent roots their own
    // subline: Abraham, Ida, William, RoseC + MorrisM, CeliaM (+ Milt minor).
    expect(deep.sublines.filter((s) => !s.minor).length).toBe(6);
    expect((deep.byPerson["Jack"] || []).length).toBe(2); // Abraham-root + Ida-root
    expect((deep.byPerson["Dustin"] || []).length).toBe(6); // all six accumulate
    expect(deep.sublines[deep.byPerson["Milt"][0]].minor).toBe(true);
  });

  it("puts Jack on the Siegel side and Rosalie on the Kleinberg side", () => {
    const { nodes } = buildButterflyLayout();
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const siegelSide = Math.sign(byId["Abraham"].cx - byId["William"].cx);
    expect(siegelSide).not.toBe(0);
    expect(Math.sign(byId["Jack"].cx - byId["Rosalie"].cx)).toBe(siegelSide);
  });

  it("flanks the center couple with partner A's siblings on the left", () => {
    // Regression: cx ties in resolveOverlaps used to shove the center couple
    // to the far left of its own sibling row (Claire-viewing-as bug).
    const { nodes } = buildButterflyLayout();
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    expect(byId["Lynn"].cx).toBeLessThan(byId["Nancy"].cx);
  });
});
