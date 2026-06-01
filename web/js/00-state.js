// Shared mutable application state for the family-tree web app.
// One object so it can be read AND written across ES modules without the
// `export let` live-binding restriction. Import as: import { S } from ...

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
  SHOW_TIMELINE_STREAM: localStorage.getItem("showTimelineStream") !== "false",
  MAP: null,
  _geocodeReady: Promise.resolve(),
  ALL_PHOTOS: null,
  PHOTO_PICKER_PERSON: null,
  AUTH_USER: null,
};
