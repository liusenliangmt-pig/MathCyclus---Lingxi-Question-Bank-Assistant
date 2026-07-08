# Import Staging

This directory is the local staging root for Word/PDF import-review candidates.

Only this README and `.gitignore` should be tracked by Git. Real candidate
JSON files, batch metadata, source images, locks, and temporary files are local
runtime data and must not be committed.

Expected runtime layout:

```text
data/import_staging/
  <batch_id>/
    batch.json
    candidates/
      <candidate_id>.json
    assets/
```

Candidate data is reviewed manually before it can be written to the formal
physics question bank.
