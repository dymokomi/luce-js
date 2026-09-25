// Regressions found by test262 (tests/test262.py): each case is a port bug fixed in
// luce_js.engine, reduced from the test262 test named beside it. Not an upstream file.
import { assert, assertThrows } from "./assert.js";

// built-ins/Object/defineProperties/15.2.3.7-6-a-164.js: a failed array length
// truncation still applies writable: false (define_property.lucb)
function test_array_length_writable() {
    var a = [0, 1, 2];
    Object.defineProperty(a, "1", { configurable: false });
    assertThrows(TypeError, () => Object.defineProperty(a, "length", { value: 0, writable: false }));
    var desc = Object.getOwnPropertyDescriptor(a, "length");
    assert(desc.value, 2);
    assert(desc.writable, false);
}

// staging/sm/String/normalize-parameter.js: the empty string normalizes to itself
// (string_normalize_iterator.lucb)
function test_normalize_empty() {
    assert("".normalize(), "");
    assert("".normalize("NFKD"), "");
}

// language/statements/function/S13.2.1_A1_T1.js: 32 nested function expressions parse
// (js_default_stack_size, compiler-issues/frame-slots-not-shared)
function test_nested_functions() {
    var src = "1";
    for (var i = 0; i < 32; i++)
        src = "(function(){ return " + src + " })()";
    assert((0, eval)(src), 1);
}

// language/comments/hashbang/module.js and every module without variables: linking
// a module whose function has no closure variables (module_link.lucb)
async function test_module_without_variables() {
    var ns = await import("./fixture_empty_module.js");
    assert(Object.keys(ns).length, 0);
}

test_array_length_writable();
test_normalize_empty();
test_nested_functions();
await test_module_without_variables();
