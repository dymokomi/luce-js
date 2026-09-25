// String building by += and joining short pieces.
var total = 0;
for (var k = 0; k < 60; k++) {
    var s = "";
    for (var i = 0; i < 50000; i++) s += "ab" + (i % 10);
    total += s.length;
}
if (total !== 60 * 50000 * 3) throw new Error("concat");
