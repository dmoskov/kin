// Entry module. Imports every module (preserving side-effect order),
// bridges all their exports onto window so cross-file bare calls and
// inline onclick="fn(...)" handlers resolve, then bootstraps the app.

import { S } from "./00-state.js";
import * as m01 from "./01-core.js";
import * as mEdit from "./04b-edit-core.js";
import * as m02 from "./02-lanes.js";
import * as m03 from "./03-data-nav.js";
import * as m04 from "./04-tree.js";
import * as m05 from "./05-panel.js";
import * as m06 from "./06-timeline.js";
import * as m07 from "./07-relationship.js";
import * as m08 from "./08-map.js";
import * as m09 from "./09-init.js";
import * as m10 from "./10-lightbox.js";
import * as m11 from "./11-documents.js";
import * as m12 from "./12-photos.js";
import * as m13 from "./13-google-photos.js";
import * as m14 from "./14-hovercard.js";
import * as m15 from "./15-auth.js";
import * as m16 from "./16-gallery.js";

for (const m of [mEdit, m01, m02, m03, m04, m05, m06, m07, m08, m09, m10, m11, m12, m13, m14, m15, m16]) Object.assign(window, m);

// Expose shared state for debugging and the smoke test.
window.S = S;

// Enable JS-only image fade-in (no-JS degrades to fully visible images).
document.documentElement.classList.add("js-fade");

window.initTheme();
window.init();
