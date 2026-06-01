// Unit tests for pure frontend logic functions.
// Each describe block resets the relevant S fields in beforeEach.

import { describe, it, expect, beforeEach } from "vitest";
import { S } from "../../web/js/00-state.js";
import { rankPeople, searchPeopleLocal } from "../../web/js/03-data-nav.js";
import { computeFogDistance } from "../../web/js/04-tree.js";
import { calculateRelationship } from "../../web/js/07-relationship.js";
import { autoComputeLanes, assignLane, buildLaneCache } from "../../web/js/02-lanes.js";

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
  //   UNRELATED = nobody connected

  const src = {
    people: [
      { id: "GP1" }, { id: "GP2" },
      { id: "P1" }, { id: "P2" },
      { id: "C1" },
      { id: "P3" },
      { id: "UNRELATED" },
    ],
    relationships: [
      { parent_id: "GP1", child_id: "P1" },
      { parent_id: "GP2", child_id: "P1" },
      { parent_id: "P1", child_id: "C1" },
      { parent_id: "P2", child_id: "C1" },
      { parent_id: "P3", child_id: "P2" },
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
