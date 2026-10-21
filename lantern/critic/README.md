# Literature critic

Commentary-only critic that sits after verification in `discover.answer(critic=...)`.

    claims_from_record -> retrieve (scholarbud BM25 over Crossref/ChemRxiv abstracts) -> judge (LLM, post-checked) -> policy

- Contract: it never writes or changes a number and never promotes a candidate. `contradicts` (confident, at or above
  `tau_review`) moves a protein behind the others and marks it `review`; `supports` only adds a `badge`.
- Lineage discount: evidence from papers the rules were derived from (DOIs found in the repo's docs plus
  `data/critic_lineage.json`) counts at `alpha_lineage` = 0.3 of an external source, and lineage-only support can never badge.
- Frozen parameters: `policy.FROZEN`. They are a pure function of a vector (`Params.to_vector/from_vector`, `PARAM_BOUNDS`,
  `objective`, `evaluate`) so a GP/Bayesian optimiser can tune them once a labelled claim set exists. Nothing is trained yet.
- Failure degrades to `keep`: no index, no client, a judge error or no matching literature leaves the record untouched.
- Offline by default. Use it: `answer(q, critic=partial(critique, client=make_client(), index=build_index([...], live=True)))`.
- Known limits: abstract-level evidence, preprint bias, lexical retrieval, same-family judge/narrator agreement.
Tests: `tests/test_critic_{policy,judge,pipeline}.py`, `tests/test_scholarbud.py`.
