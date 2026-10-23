# evalbox

Run a suite of checks against a language model and fail the build when it regresses.

A model that is right nine times out of ten is not the same as a model that is right.
evalbox runs each case several times, measures how often it holds up, and lets you say
how often it has to. A case with a threshold of 0.9 that comes back 8/10 is a failure,
and the report says which assertion broke and on which attempt.

No agent, no framework, no provider client. You give it a callable; it gives you a
verdict and an exit code.

## Install

```
pip install -e ".[schema]"
```

Python 3.10 or later. One dependency, PyYAML. The JSON Schema check pulls in
`jsonschema` as an optional extra; every other check uses the standard library.

## A suite

```yaml
name: invoice extraction
defaults:
  repeat: 10
  threshold: 0.9

cases:
  - name: reads the total from a clean invoice
    prompt: |
      Return JSON with the keys supplier, total and currency.
      Invoice: Nordvik Bygg AB, 12 450 SEK including VAT.
    checks:
      - json_valid
      - json_field: { path: supplier, equals: "Nordvik Bygg AB" }
      - json_field: { path: total, equals: 12450 }
      - max_latency_ms: 2500

  - name: says so instead of guessing when the total is missing
    prompt: |
      Return JSON with the keys supplier, total and currency.
      Invoice: Nordvik Bygg AB, amount illegible.
    tags: [safety]
    checks:
      - json_valid
      - json_field: { path: total, equals: null }
```

## The model

Anything callable that takes the prompt and returns a string, or a `Response` when you
want cost reported:

```python
from evalbox import Response


def answer(prompt: str) -> Response:
    completion = client.responses.create(model="...", input=prompt)
    return Response(text=completion.output_text, cost_usd=price_of(completion))
```

## Run it

```
evalbox examples/suite.yaml --model examples.fake_model:answer --workers 8
```

The example ships with a stand-in model so the command works with no API key. It is
wrong in the way a real one is wrong, which is the point:

```
case                                          pass       p50     p95     cost     note
--------------------------------------------  ---------  ------  ------  -------  ------------------------------------
reads the total from a clean invoice          ok 10/10   119 ms  170 ms  $0.0040
keeps the shape when the amount is written i  FAIL 5/10  118 ms  235 ms  $0.0040  json_schema: total: '12450' is not o
says so instead of guessing when the total i  ok 9/10    148 ms  218 ms  $0.0040

FAIL  2/3 cases, 30 calls, $0.0120, 0.7 s
```

Exit code 0 when every case clears its threshold, 1 when one does not, 2 when the suite
or the model could not be loaded. `--json report.json` writes the same run as data, so a
build can keep it and compare.

## Checks

| check | what it asserts |
| --- | --- |
| `equals` | the whole answer, trimmed unless you say `strip: false` |
| `contains`, `not_contains` | a substring is present, or is not |
| `regex` | a pattern matches, with `flags: ims` |
| `json_valid` | the answer parses as JSON |
| `json_schema` | the parsed answer satisfies a JSON Schema |
| `json_field` | a dotted path exists, and equals a value if you give one |
| `length` | the answer is between `min` and `max` characters |
| `max_latency_ms` | the call came back in time |
| `max_cost_usd` | the call stayed under a price, and fails when the model reports none |

## Two decisions worth knowing about

**The suite is validated before the first call.** Checks are built when the file is
read, so a misspelled check name or a broken regex fails in the first second rather
than after the run has spent ten minutes and real money.

**A model that raises fails one attempt, not the run.** The exception is recorded as
that attempt's reason and the suite carries on, because a provider that drops one call
in fifty is exactly the thing you are trying to measure.

## Tests

```
pytest -q
ruff check .
```

MIT licensed.
