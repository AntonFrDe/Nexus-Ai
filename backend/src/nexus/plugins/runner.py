"""Runs inside the sandbox, one process per call. Standard library only, and it never imports
NEXUS: the plugin must not share any code or state with the host."""

import importlib.util
import json
import sys
import types


def main() -> None:
    plugin_dir, entry = sys.argv[1], sys.argv[2]
    reply = sys.stdout
    # A stray print from a plugin must not corrupt the reply.
    sys.stdout = sys.stderr

    handlers: dict[tuple[str, str], object] = {}

    def register(kind: str):
        def named(name: str):
            def wrap(function):
                handlers[(kind, name)] = function
                return function

            return wrap

        return named

    sdk = types.ModuleType("nexus_plugin")
    sdk.node = register("node")
    sdk.runtime = register("runtime")
    sdk.route = lambda output, *ports: {"__ports__": list(ports), "output": output}
    sys.modules["nexus_plugin"] = sdk

    request = json.loads(sys.stdin.readline())
    sys.path.insert(0, plugin_dir)
    spec = importlib.util.spec_from_file_location("nexus_plugin_entry", f"{plugin_dir}/{entry}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    handler = handlers.get((request["kind"], request["name"]))
    if handler is None:
        raise LookupError(f"The plugin has no {request['kind']} named {request['name']}")
    result = handler(request["payload"])
    reply.write(json.dumps({"result": result}))
    reply.flush()


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        sys.__stdout__.write(json.dumps({"error": f"{type(error).__name__}: {error}"[:2000]}))
        sys.__stdout__.flush()
        raise SystemExit(1) from None
