// os.Worker with SharedArrayBuffer and Atomics across threads: Atomics.wait in a worker
// woken by Atomics.notify from the main thread, timed-out and not-equal waits, and
// concurrent Atomics.add from both threads. Not an upstream file; the worker side is
// fixture_worker_atomics.js.
import * as std from "std";
import * as os from "os";
import { assert, assertThrows } from "./assert.js";

const ADDS = 100000;

// a failure in a message handler is only printed, so every check exits on failure
function check(f) {
    try {
        f();
    } catch (e) {
        print(e);
        std.exit(1);
    }
}

function test_worker_atomics() {
    var sab = new SharedArrayBuffer(64);
    var ia = new Int32Array(sab, 0, 8);
    var ba = new BigInt64Array(sab, 32, 2);
    var worker = new os.Worker("./fixture_worker_atomics.js");
    var guard = os.setTimeout(() => {
        print("test_worker_atomics: timeout");
        std.exit(1);
    }, 60000);

    // the main thread of ljs cannot block, as in qjs
    assertThrows(TypeError, () => Atomics.wait(ia, 0, 0, 0));

    // wake the worker blocked on `index`: notify until it is found waiting
    function wake(array, index) {
        var n = Atomics.notify(array, index, 1);
        assert(n === 0 || n === 1);
        if (n === 0)
            os.setTimeout(() => check(() => wake(array, index)), 1);
    }

    worker.onmessage = function (e) {
        check(() => {
            var ev = e.data;
            switch (ev.type) {
            case "waiting32":
                Atomics.store(ia, 1, 1);
                wake(ia, 0);
                break;
            case "waiting64":
                wake(ba, 0);
                break;
            case "adding":
                for (var i = 0; i < ADDS; i++)
                    Atomics.add(ia, 3, 1);
                worker.postMessage({ type: "added" });
                break;
            case "done":
                assert(ev.wait32, "ok");
                assert(ev.wait64, "ok");
                assert(ev.timed_out, "timed-out");
                assert(ev.not_equal, "not-equal");
                assert(ev.after_wake, 1);
                assert(Atomics.load(ia, 3), 2 * ADDS);
                assert(ia[2], 7);
                assert(ev.buf === undefined);
                worker.onmessage = null;
                os.clearTimeout(guard);
                break;
            default:
                throw Error("unexpected message " + ev.type);
            }
        });
    };
    worker.postMessage({ type: "start", ia: ia, ba: ba, adds: ADDS });
}

test_worker_atomics();
