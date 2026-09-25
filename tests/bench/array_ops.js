// Array push and indexed read/write.
var total = 0;
for (var k = 0; k < 30; k++) {
    var a = [];
    for (var i = 0; i < 100000; i++) a.push(i);
    for (var i = 0; i < a.length; i++) a[i] = a[i] * 2;
    var s = 0;
    for (var i = 0; i < a.length; i++) s += a[i];
    total += s;
}
if (total !== 30 * 100000 * 99999) throw new Error("array " + total);
