# M3 generation smoke evaluation

This initial fixture covers two explicit launch intents and two requests that
should abstain. It is separate from the frozen M2.5 retrieval benchmark.
The expected argv and overrides for the launch cases are checked exactly,
along with verification status. The abstention cases check that Argus renders
no command.

Use a clean MPML checkout at `14ad36e3f70a10bb5781b88200e825a717ca402f` and
verify its interpreter can run both `mpml.spec` and `mpml.preflight`. Run from the
Argus root after building the hybrid index with `nomic-embed-text` and setting
`MPML_REPO` and `MPML_PYTHON`. Use an environment without MPML launch overrides
for comparable results. [Local setup and model instructions](../../README.md#ask-for-a-cited-mpml-recipe)

```bash
python eval/generation/smoke.py
```

The runner uses a 300-second generation timeout for CPU inference. It captures
structured outcomes and elapsed time and leaves every command as text. Use
`--case strategy-and-pair` to rerun the README example on its own.
