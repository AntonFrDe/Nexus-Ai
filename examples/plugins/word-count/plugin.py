from nexus_plugin import node, route


@node("com.nexus-examples.word-count.count")
def count(request):
    words = len(str(request["input"] or "").split())
    limit = request["plugin_config"].get("long_after", 100)
    result = {"count": words, "unit": request["config"].get("unit", "words")}
    return route(result, "long" if words > limit else "short")
