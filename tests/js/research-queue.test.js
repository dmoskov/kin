// computeResearchGaps drives the research-queue worklist: which gaps count,
// when "death date" applies (only the probably-deceased), and the emptiest-
// first ordering.

import { describe, it, expect } from "vitest";
import { computeResearchGaps } from "../../web/js/19-research-queue.js";

const NOW = 2026;

function mapOf(people, photos = {}) {
  const m = {};
  for (const p of people) {
    m[p.id] = {
      ...p,
      fullName: [p.given_name, p.surname].filter(Boolean).join(" "),
      _profilePhotoPath: photos[p.id] || null,
    };
  }
  return m;
}

describe("computeResearchGaps", () => {
  it("flags missing fields and sorts the emptiest records first", () => {
    const people = [
      { id: "full", given_name: "Ada", surname: "Stone", birth_date: "1900-01-01", birth_place: "Boston", death_date: "1980", death_place: "Portland" },
      { id: "empty", given_name: "Ben", surname: "Stone" },
    ];
    const data = { people, events: [{ person_id: "full", event_type: "career", date: "1920" }] };
    const rows = computeResearchGaps(data, mapOf(people, { full: "photos/ada.jpg" }), NOW);
    expect(rows[0].id).toBe("empty");
    expect(rows[0].gaps).toEqual(["birth date", "birth place", "photo", "life events"]);
    // "full" has everything → not in the queue at all.
    expect(rows.find((r) => r.id === "full")).toBeUndefined();
  });

  it("asks for a death date only when the person is probably deceased", () => {
    const people = [
      { id: "old", given_name: "Eli", surname: "Gray", birth_date: "1880-01-01", birth_place: "x" },
      { id: "young", given_name: "Flo", surname: "Gray", birth_date: "1990-01-01", birth_place: "x" },
    ];
    const data = { people, events: [] };
    const rows = computeResearchGaps(data, mapOf(people), NOW);
    const gapsBy = Object.fromEntries(rows.map((r) => [r.id, r.gaps]));
    expect(gapsBy.old).toContain("death date");
    expect(gapsBy.young).not.toContain("death date");
  });

  it("flags death place only when a death date exists without one", () => {
    const people = [{ id: "p", given_name: "Ida", surname: "Lev", birth_date: "1880-01-01", birth_place: "x", death_date: "1950" }];
    const rows = computeResearchGaps({ people, events: [] }, mapOf(people), NOW);
    expect(rows[0].gaps).toContain("death place");
  });

  it("handles empty data", () => {
    expect(computeResearchGaps(null, {}, NOW)).toEqual([]);
    expect(computeResearchGaps({ people: [] }, {}, NOW)).toEqual([]);
  });
});
