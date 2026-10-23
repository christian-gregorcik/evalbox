"""A stand-in model, so the example runs without an API key.

It behaves the way a real one does on this task: right most of the time, wrong in a
particular way some of the time. That is the whole reason a case is repeated.
"""

from __future__ import annotations

import json
import random
import time

from evalbox import Response

_random = random.Random(7)


def answer(prompt: str) -> Response:
    time.sleep(_random.uniform(0.05, 0.25))
    cost = 0.0004

    if "illegible" in prompt:
        body = {"supplier": "Nordvik Bygg AB", "total": None, "currency": "SEK"}
        if _random.random() < 0.05:
            body["total"] = 0
    elif "twelve thousand" in prompt:
        body = {"supplier": "Sjöberg El", "total": 12450, "currency": "SEK"}
        if _random.random() < 0.4:
            body["total"] = "12450"
    else:
        body = {"supplier": "Nordvik Bygg AB", "total": 12450, "currency": "SEK"}
        if _random.random() < 0.03:
            body["total"] = 1245

    return Response(text=json.dumps(body, ensure_ascii=False), cost_usd=cost)
