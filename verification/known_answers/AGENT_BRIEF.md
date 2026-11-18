# Brief for the known-answer test

Give this brief to a fresh agent that has never seen this project. Give it read access to the `ontology/`
folder and to `verification/known_answers/questions.yml` and `questions_reworded.yml`, and nothing else: no other repo files, no database,
no chat history.

> You are answering business questions about the Olist e-commerce warehouse (DuckDB). Read only the files in
> `ontology/` and `questions.yml`. For each question, write ONE DuckDB SQL query that returns a single value
> (one row, one column) and answers it. Use the tables and columns named in `ontology/ontology.yml`, and follow
> its definition cards (population, numerator, denominator, time rule, counterexamples). Do not hard-code
> numbers you see in the files; the query must compute the answer from the tables. You cannot run the queries.
> Reply with YAML only, mapping each question id to its query, for example:
> `q01: "select ..."`

Score the reply (after `make build`):

```sh
.venv/bin/python verification/known_answers/score.py answers.yml            # questions.yml
.venv/bin/python verification/known_answers/score.py answers_reworded.yml   # questions_reworded.yml
.venv/bin/python verification/known_answers/selftest.py                      # proves the scorer first
```
A question may forbid some tables (`forbidden_tables`); an answer that reads one is scored wrong. A reply of `CANNOT_ANSWER` is scored as an abstain, so a gap in the ontology shows up as a gap.

`answer_key.sql` holds the hand-written answers. Keep it away from the agent.
