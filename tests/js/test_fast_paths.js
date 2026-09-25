// The cases around the interpreter's fast paths (luce_js.engine interpreter.lucb): each
// fast path runs the common case of an opcode in the dispatch loop and leaves every other
// case to the opcode's full body, so both sides of each test are checked here. Not an
// upstream file.
import { assert, assertThrows } from "./assert.js";

// get_field, get_field2, get_length: own and inherited data properties, accessors, exotic
// objects on the prototype chain, primitives, missing properties
function test_get_field() {
    function P() { this.x = 1; }
    P.prototype.y = 2;
    Object.defineProperty(P.prototype, "z", { get() { return this.x + 10; } });
    var p = new P();
    assert(p.x, 1);
    assert(p.y, 2);
    assert(p.z, 11);
    assert(p.w, undefined);
    var o = Object.create([5, 6]);
    assert(o.length, 2);
    assert(o[1], 6);
    assert("abc".length, 3);
    assert((5).constructor, Number);
    assert([1, 2, 3].length, 3);
    var calls = { n: 0, f() { return this.n + 1; } };
    assert(calls.f(), 1);
    assertThrows(TypeError, () => { var u; return u.x; });
    var proxy = new Proxy({}, { get: (t, k) => k + "!" });
    assert(Object.create(proxy).foo, "foo!");
}

// put_field: writable data properties in place, read-only ones and setters by the full body
function test_put_field() {
    var o = { a: 1 };
    o.a = "s";
    assert(o.a, "s");
    o.b = 2;
    assert(o.b, 2);
    var ro = {};
    Object.defineProperty(ro, "c", { value: 1, writable: false });
    // a module is strict code; sloppy code ignores the write
    assertThrows(TypeError, () => { ro.c = 5; });
    new Function("o", "o.c = 5")(ro);
    assert(ro.c, 1);
    var seen;
    var s = { set d(v) { seen = v; } };
    s.d = 7;
    assert(seen, 7);
    var arr = [1, 2];
    arr.length = 1;
    assert(arr.length, 1);
    assert(arr[1], undefined);
}

// get_array_el, get_array_el2, get_array_el3 and put_array_el: fast array elements in
// place, anything else (holes, out of range, other objects and keys) by the full bodies
function test_array_elements() {
    var a = [1, 2, 3];
    a[0] += 10;
    a[1]++;
    assert(a.join(), "11,3,3");
    assert(a[5], undefined);
    a[3] = 4;
    assert(a.length, 4);
    var objs = [{ f() { return this.v; }, v: 7 }];
    assert(objs[0].f(), 7);
    var t = new Int8Array(2);
    t[0] += 5;
    t[1]++;
    assert(t.join(), "5,1");
    var o = { 0: "x", k: 1 };
    o[0] += "y";
    o["k"] += 1;
    assert(o[0] + o.k, "xy2");
    var s = "ab";
    assert(s[1], "b");
    (function () { arguments[0] += 1; assert(arguments[0], 2); })(1);
    var h = [1, , 3];
    Array.prototype[1] = "p";
    assert(h[1], "p");
    delete Array.prototype[1];
    assertThrows(TypeError, () => { var u; u[0] += 1; });
}

// add, sub, mul and the comparisons on numbers with a float, int overflow, -0 and NaN
function test_number_ops() {
    var big = 0x7fffffff, one = 1, half = 0.5, nan = NaN, mz = -0;
    assert(big + one, 2147483648);
    assert(-big - 2, -2147483649);
    assert(big * 2, 4294967294);
    assert(Object.is(0 * -1, -0));
    assert(Object.is(-0 + 0, 0));
    assert(Object.is(mz + mz, -0));
    assert(Object.is(mz - 0, -0));
    assert(one + half, 1.5);
    assert(half - one, -0.5);
    assert(half * 4, 2);
    assert(1.5 * 2 === 3, true);
    assert(nan < 1, false);
    assert(nan >= 1, false);
    assert(nan == nan, false);
    assert(nan != nan, true);
    assert(nan === nan, false);
    assert(1 < 1.5, true);
    assert(2 <= 2.0, true);
    assert(2.5 > 2, true);
    assert(3 >= 3.5, false);
    assert(1 == 1.0, true);
    assert(1 === 1.0, true);
    assert(1 !== 1.5, true);
    assert("1" == 1, true);
    assert("b" > "a", true);
    var s = 0.25;
    for (var i = 0; i < 4; i++) s += 0.25;
    assert(s, 1.25);
    var t = "a";
    t += "b";
    assert(t, "ab");
    assert(7 % 3, 1);
    assert(Object.is(-7 % 7, -0));
    assert(-7 % 3, -1);
    assert(7 % -3, 1);
    assert(isNaN(7 % 0), true);
    assert(Object.is((-2147483648) % -1, -0));
    assert(5.5 % 2, 1.5);
    assert((2.5 | 0), 2);
    assert((-2.5 | 0), -2);
    assert((4294967296.5 | 0), 0);
    assert((2147483648 | 0), -2147483648);
    assert(Math.abs(-3), 3);
    assert(Math.floor(2.5), 2);
    assert(Object.is(Math.round(-0.2), -0));
}

// push_this: an object this in place, the others converted in sloppy mode only
function test_push_this() {
    // a module is strict code
    var sloppy = new Function("return this");
    function strict() { return this; }
    assert(sloppy.call(undefined), globalThis);
    assert(typeof sloppy.call(5), "object");
    assert(strict.call(undefined), undefined);
    assert(strict.call(5), 5);
    var o = { m() { return this; } };
    assert(o.m(), o);
}

// closure variables written by put_var_ref, set_var_ref and their short forms
function test_var_refs() {
    var a = 1, b = 2, c = 3, d = 4, e = 5;
    function f() {
        a = a + 1; b += 2; c = d = e = "x";
        return a + b + c + d + e;
    }
    assert(f(), "6xxx");
    assert(a, 2);
    assert(e, "x");
    function counter() { var n = 0; return function () { return ++n; }; }
    var g = counter();
    g();
    assert(g(), 2);
}

// calls: C functions called before a frame is set up, missing arguments, deep recursion
function test_calls() {
    assertThrows(TypeError, () => { var x = {}; x.nope(); });
    assertThrows(TypeError, () => { var x = 1; x(); });
    function two(a, b) { return b; }
    assert(two(1), undefined);
    assert(Math.max(), -Infinity);
    assert([3, 1, 2].sort().join(), "1,2,3");
    // the depth a luce-js frame allows in the default 4 MB stack (C's qjs, with its
    // 1 MB, stops before)
    function depth(n) { return n ? depth(n - 1) + 1 : 0; }
    assert(depth(2500), 2500);
}

// a regular expression literal compiles once; its objects share the program and keep
// their own lastIndex, and compile() replaces only its object's program
function test_regexp_literals() {
    var objs = [];
    for (var i = 0; i < 3; i++)
        objs.push(/a(b)?/g);
    assert(objs[0] !== objs[1], true);
    objs[0].exec("xab");
    assert(objs[0].lastIndex, 3);
    assert(objs[1].lastIndex, 0);
    assert(objs[1].exec("ab")[1], "b");
    objs[2].compile("z", "i");
    assert(objs[2].test("Z"), true);
    assert(objs[1].source, "a(b)?");
    assert(objs[1].flags, "g");
    function f() { return /x/i; }
    assert(f().test("X") && f() !== f(), true);
    assert("a1b2".replace(/\d/g, (m) => /\d/.test(m) ? "#" : "?"), "a#b#");
}

test_get_field();
test_put_field();
test_array_elements();
test_number_ops();
test_push_this();
test_var_refs();
test_calls();
test_regexp_literals();
