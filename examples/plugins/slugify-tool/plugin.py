import re
import unicodedata

from nexus_plugin import node


@node("com.nexus-examples.slugify-tool.slugify")
def slugify(request):
    text = unicodedata.normalize("NFKD", str(request["input"] or ""))
    ascii_text = text.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
