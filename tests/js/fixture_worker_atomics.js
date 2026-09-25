// The worker of test_worker_atomics.js. Not an upstream file.
import * as os from "os";

var parent = os.Worker.parent;
var ia, ba, adds, result = { type: "done" };

parent.onmessage = function (e) {
    var ev = e.data;
    switch (ev.type) {
    case "start":
        ia = ev.ia;
        ba = ev.ba;
        adds = ev.adds;
        // a plain write is seen by the main thread through the shared buffer
        ia[2] = 7;
        result.timed_out = Atomics.wait(ia, 4, 0, 10);
        result.not_equal = Atomics.wait(ia, 2, 0);
        parent.postMessage({ type: "waiting32" });
        result.wait32 = Atomics.wait(ia, 0, 0);
        // the main thread stored ia[1] before notifying
        result.after_wake = Atomics.load(ia, 1);
        parent.postMessage({ type: "waiting64" });
        result.wait64 = Atomics.wait(ba, 0, 0n);
        parent.postMessage({ type: "adding" });
        for (var i = 0; i < adds; i++)
            Atomics.add(ia, 3, 1);
        break;
    case "added":
        parent.postMessage(result);
        parent.onmessage = null; /* terminate the worker */
        break;
    }
};
