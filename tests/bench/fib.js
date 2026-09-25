// Recursive calls, int compare and add: fib(30).
function fib(n) { return n < 2 ? n : fib(n - 1) + fib(n - 2); }
for (var k = 0; k < 5; k++) if (fib(30) !== 832040) throw new Error("fib");
