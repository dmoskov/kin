// afterMutate is the single post-mutation refresh: it must rebuild every
// piece of derived state (data → visibility filter → lanes → views) in
// order, for the CURRENT center couple. The undo path once called
// autoComputeLanes() with no arguments and silently wiped S.LANES — this
// pins the contract so that class of bug can't come back.

import { describe, it, expect, beforeEach } from "vitest";
import { S } from "../../web/js/00-state.js";
import { afterMutate } from "../../web/js/04b-edit-core.js";

describe("afterMutate", () => {
  let calls;

  beforeEach(() => {
    calls = [];
    window.loadData = async () => calls.push("loadData");
    window.applyVisibilityFilter = () => calls.push("applyVisibilityFilter");
    window.autoComputeLanes = (a, b) => calls.push(`autoComputeLanes:${a},${b}`);
    window.refreshAllViews = () => calls.push("refreshAllViews");
    window.showPersonPanel = (id) => calls.push(`showPersonPanel:${id}`);
    S.CENTER_ID_A = "alice";
    S.CENTER_ID_B = "bob";
  });

  it("refreshes derived state in order and reshows the panel", async () => {
    await afterMutate("p1");
    expect(calls).toEqual([
      "loadData",
      "applyVisibilityFilter",
      "autoComputeLanes:alice,bob",
      "refreshAllViews",
      "showPersonPanel:p1",
    ]);
  });

  it("skips the person panel when personId is null (delete/undo flows)", async () => {
    await afterMutate(null);
    expect(calls).toEqual([
      "loadData",
      "applyVisibilityFilter",
      "autoComputeLanes:alice,bob",
      "refreshAllViews",
    ]);
  });
});
