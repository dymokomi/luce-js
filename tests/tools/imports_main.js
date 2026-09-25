/* ljsc test: a module whose imports ljsc follows (a module importing another one, a
   JSON module and the std system module), with import.meta and scriptArgs */
import * as std from "std";
import { area, describe } from "./imports_lib.js";
import msg from "./message.json";

std.printf("area=%d\n", area(3, 4));
console.log(describe([1, 2, 3]));
console.log("msg.tab:", msg.tab.join(","));
console.log("main:", import.meta.main, "url:", import.meta.url.slice(0, 7));
console.log("args:", scriptArgs.slice(1).join(" "));
