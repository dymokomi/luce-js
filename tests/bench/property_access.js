// get_field/put_field on objects of one shape.
function Point(x, y) { this.x = x; this.y = y; }
var pts = [];
for (var i = 0; i < 100; i++) pts.push(new Point(i, 2 * i));
var s = 0;
for (var k = 0; k < 30000; k++) {
    for (var j = 0; j < 100; j++) { var p = pts[j]; s += p.x + p.y; p.x = p.y - p.x; p.y = p.y - p.x; }
}
if (typeof s !== "number") throw new Error("prop");
