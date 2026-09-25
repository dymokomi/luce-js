// Calls of closures that read and write a captured variable.
function counter() { var c = 0; return function (d) { c += d; return c; }; }
var f = counter();
var g = function (x) { return f(x) + 1; };
var r = 0;
for (var i = 0; i < 3000000; i++) r = g(1);
if (r !== 3000001) throw new Error("closure " + r);
