// The structured date input composes ISO partials (YYYY / YYYY-MM /
// YYYY-MM-DD) into the hidden field that _readField reads — segments unlock
// progressively so a partial date is always a valid partial.

import { describe, it, expect, beforeEach } from "vitest";
import { EditForm } from "../../web/js/04b-edit-core.js";

function openDateForm(value) {
  const mount = document.createElement("div");
  document.body.appendChild(mount);
  EditForm.open({
    fields: [{ key: "birth_date", type: "date", label: "Born" }],
    values: { birth_date: value },
    mount: { el: mount, mode: "remove" },
    onSave: async () => ({ ok: true, json: async () => ({}) }),
  });
  const group = mount.querySelector(".ef-date");
  return {
    mount,
    hidden: group?.querySelector('input[type="hidden"]'),
    y: group?.querySelector(".ef-date-y"),
    m: group?.querySelector(".ef-date-m"),
    d: group?.querySelector(".ef-date-d"),
  };
}

const fire = (el, type) => el.dispatchEvent(new Event(type, { bubbles: true }));

describe("EditForm date field", () => {
  beforeEach(() => { document.body.innerHTML = ""; });

  it("splits an existing full date into segments", () => {
    const f = openDateForm("1850-06-09");
    expect(f.y.value).toBe("1850");
    expect(f.m.value).toBe("06");
    expect(f.d.value).toBe("9");
    expect(f.hidden.value).toBe("1850-06-09");
  });

  it("composes progressively: year, then month, then padded day", () => {
    const f = openDateForm("");
    expect(f.m.disabled).toBe(true);
    f.y.value = "1900";
    fire(f.y, "input");
    expect(f.hidden.value).toBe("1900");
    expect(f.m.disabled).toBe(false);

    f.m.value = "02";
    fire(f.m, "change");
    expect(f.hidden.value).toBe("1900-02");
    expect(f.d.disabled).toBe(false);

    f.d.value = "5";
    fire(f.d, "input");
    expect(f.hidden.value).toBe("1900-02-05");
  });

  it("drops month and day when the year becomes invalid", () => {
    const f = openDateForm("1900-02-05");
    f.y.value = "19";
    fire(f.y, "input");
    expect(f.hidden.value).toBe("");
    expect(f.m.disabled).toBe(true);
    expect(f.d.disabled).toBe(true);
  });

  it("falls back to a plain text input for non-ISO legacy values", () => {
    const f = openDateForm("c. 1920");
    expect(f.hidden).toBeFalsy();
    const plain = f.mount.querySelector("input.add-relative-input");
    expect(plain.value).toBe("c. 1920");
  });
});
