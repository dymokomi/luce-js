// A counted loop over locals: int add, compare, branch.
function sum(n) { var s = 0; for (var i = 0; i < n; i++) s = (s + i) | 0; return s; }
var r = 0;
for (var k = 0; k < 10; k++) r = sum(3000000);
if (r !== ((3000000 * 2999999 / 2) | 0)) throw new Error("sum " + r);
