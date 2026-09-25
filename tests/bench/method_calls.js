// Method calls through the prototype chain, with `this` field access.
class Acc {
    constructor() { this.v = 0; }
    add(x) { this.v += x; return this; }
    get() { return this.v; }
}
var a = new Acc();
for (var i = 0; i < 3000000; i++) a.add(1).add(2);
if (a.get() !== 9000000) throw new Error("method");
