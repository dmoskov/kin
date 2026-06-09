// Shared mutable application state for the family-tree web app.
// One object so it can be read AND written across ES modules without the
// `export let` live-binding restriction. Import as: import { S } from ...
//
// Write ownership — everything else treats these as read-only:
//   S.DATA / S.ORIGINAL_DATA / S.PEOPLE_MAP / S.PHOTOS_MAP
//       loadData (03) builds them; applyVisibilityFilter (03) and
//       applyFocus (04) derive S.DATA from S.ORIGINAL_DATA.
//   S.CENTER_ID_A/B   setCenterPerson (16, viewer change), applyFocus (04,
//       focus mode), initViewingAs (02) + applyConfig (01) at startup.
//   S.LANES           autoComputeLanes (02) only.
// After any server write that changes tree data, call afterMutate (04b) —
// the single post-mutation refresh — rather than re-deriving these inline.

export const S = {
  DATA: null,
  PEOPLE_MAP: {},
  CONFIG: null,
  FOCUS_PERSON_ID: null,
  FOCUS_DEPTH: 1,
  ORIGINAL_DATA: null,
  ORIGINAL_CENTER_ID_A: null,
  ORIGINAL_CENTER_ID_B: null,
  PHOTOS_MAP: {},
  CENTER_ID_A: null,
  CENTER_ID_B: null,
  LANES: [],
  MAP: null,
  TREE_DEPTH: parseInt(localStorage.getItem("ft-tree-depth") || "2", 10),
  MAP_DEPTH: parseInt(localStorage.getItem("ft-map-depth") || "1", 10),
  _geocodeReady: Promise.resolve(),
  ALL_PHOTOS: null,
  PHOTO_PICKER_PERSON: null,
  AUTH_USER: null,
  // Views whose rendered DOM is out of date with S.DATA. refreshAllViews
  // (16) renders only the active view and marks the rest here; switchTab
  // (03) drains the flag via renderViewIfStale (16).
  _STALE_VIEWS: new Set(),
};
