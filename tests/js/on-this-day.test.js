// buildOnThisDayItems is the pure matcher behind the "On this day" card:
// only full YYYY-MM-DD dates participate, primary records win over
// duplicate events, and celebrations sort before remembrances.

import { describe, it, expect } from "vitest";
import { buildOnThisDayItems } from "../../web/js/18-on-this-day.js";

const PEOPLE_MAP = {
  p1: { id: "p1", fullName: "Ada Stone" },
  p2: { id: "p2", fullName: "Ben Stone" },
  p3: { id: "p3", fullName: "Cleo Stone" },
};

function data(overrides = {}) {
  return {
    people: [
      { id: "p1", birth_date: "1890-06-09", death_date: "1960-01-02" },
      { id: "p2", birth_date: "1892" }, // year-only: never matches
      { id: "p3", birth_date: "1900-06-09", death_date: "1980-06-09" },
    ],
    unions: [{ partner1_id: "p1", partner2_id: "p2", union_date: "1916-06-09" }],
    events: [
      { person_id: "p2", event_type: "immigration", date: "1903-06-09", place: "Boston" },
      // Duplicate of the primary birth record — must be skipped:
      { person_id: "p1", event_type: "birth", date: "1890-06-09" },
    ],
    ...overrides,
  };
}

describe("buildOnThisDayItems", () => {
  it("matches only full dates with today's month-day", () => {
    const items = buildOnThisDayItems(data(), PEOPLE_MAP, "06-09", 2026);
    const kinds = items.map((i) => i.kind);
    expect(kinds).toEqual(["birth", "birth", "marriage", "event", "death"]);
  });

  it("computes years-ago detail and sorts recent first within a kind", () => {
    const items = buildOnThisDayItems(data(), PEOPLE_MAP, "06-09", 2026);
    const births = items.filter((i) => i.kind === "birth");
    expect(births[0].year).toBe(1900); // more recent birth first
    expect(births[1].detail).toBe("136 years ago");
  });

  it("skips birth/death/marriage event rows (primary records cover them)", () => {
    const items = buildOnThisDayItems(data(), PEOPLE_MAP, "06-09", 2026);
    expect(items.filter((i) => i.kind === "birth")).toHaveLength(2);
  });

  it("uses a verb and place for life events", () => {
    const items = buildOnThisDayItems(data(), PEOPLE_MAP, "06-09", 2026);
    const ev = items.find((i) => i.kind === "event");
    expect(ev.text).toBe("Ben Stone arrived in Boston this day in 1903");
  });

  it("returns empty for a day with no matches and for missing data", () => {
    expect(buildOnThisDayItems(data(), PEOPLE_MAP, "12-25", 2026)).toEqual([]);
    expect(buildOnThisDayItems(null, PEOPLE_MAP, "06-09", 2026)).toEqual([]);
  });
});
