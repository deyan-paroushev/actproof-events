# Bugfix bundle (May 19 sprint, after ChatGPT review)

Two related deliveries, packaged together because they fix the same set of bugs across two repositories.

## Apply order

1. Extract the four step bugfix zips into your respective working trees (actproof-events for the first three, quoruna for the fourth).
2. Rebuild the actproof-events wheel: `cd actproof-events && python -m build --wheel`.
3. Reinstall in the Quoruna venv: `pip install --force-reinstall --no-deps actproof-events/dist/actproof_events-1.4.0rc1-py3-none-any.whl`.
4. Run the mint script in draft mode to confirm: `python scripts/mint_standards_engagement_record.py --mode draft`. The summary should show maintainer = "Deyan Paroushev".

## What is fixed

See `EVENTS-BUGFIX-NOTES.md` and `STEP6_2-BUGFIX-NOTES.md` in this bundle for the per-zip detail. The headline is: ChatGPT's "minimal patch" 8-item list, applied surgically across both repos, with every dependent hash recomputed and the full mint pipeline re-verified end to end.

## What was deliberately not changed

The `op:` namespace prefix (ChatGPT explicitly said do not churn this tonight). The pre-existing test-vector schema-mismatch bug (non-blocking, scheduled for post-STS hygiene). The roadmap framing of "next regulatory profiles" (an application-document item, not a code item).
