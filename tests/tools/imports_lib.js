/* imported by imports_main.js; imports imports_util.js in turn */
import { square, sum } from "./imports_util.js";

export function area(w, h) { return w * h; }
export function describe(a) { return "sum=" + sum(a) + " squares=" + a.map(square).join(","); }
