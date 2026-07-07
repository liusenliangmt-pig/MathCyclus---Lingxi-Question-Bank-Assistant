# Phase 1E Stable Release Report

## 1. Scope

Phase 1E validates the current dual-discipline stable baseline for mathematics and physics. This phase only adds regression coverage and this release report in the `phase1e` temporary copy. It does not implement Word import, PDF import, OCR, AI question generation, physics delete, batch modification, or new formal question content.

## 2. Architecture Summary

The app uses explicit discipline runtime configuration instead of a mutable global current-discipline object. Mathematics and physics are separated by runtime config, source root, CSV index path, Streamlit state keys, and cache inputs.

Mathematics continues to use `chapters/` and `utils/题库索引表.csv`. Physics uses `chapters_physics/` and `utils/物理题库索引表.csv`.

Physics write/edit behavior is centralized in `utils/physics_question_ops.py`. Future Word/PDF/OCR import workflows must reuse its validation, safe path construction, atomic save/edit, index refresh, rollback, and math-index protection interfaces.

## 3. Directory And Index State

- Mathematics formal indexed questions: 70.
- Physics formal source questions: 8.
- Mathematics index rows: 70.
- Physics index rows: 8.
- Physics index columns: 44.
- Mathematics index SHA-256: `250092C5158BA3A2185253AC0F0A141E5AE74C5C668A4CC74B208309EDE84386`.
- Physics index SHA-256: `DC9D49F6639647162BB0A75F23890D6A05D46A456EEE72F90ABE0CFCD961DD17`.

## 4. Implemented Stable Features

- Discipline switch between mathematics and physics.
- Isolated math/physics reading from source directories and CSV indexes.
- Isolated Streamlit state for browsing, filtering, advanced search, selected questions, random selection, and basic exam selection.
- Mathematics remains at the existing 70-question baseline.
- Physics supports browsing, search, details, random selection, basic exam selection, single-question entry, and single-question edit.
- Physics edit across directories uses a transaction-style flow with rollback on index-refresh failure.
- Physics difficulty display reads both the legacy difficulty-star field and the newer difficulty field.

## 5. Features Still Closed

- Word import.
- PDF import.
- OCR.
- AI question generation or AI write-back.
- Physics delete.
- Physics batch modification.
- Mixed mathematics/physics writing.

## 6. Unified Regression Entry

The unified regression script is:

```powershell
tests\run_phase1e_regression.py
```

For this temporary copy it was executed with the F-drive project virtual environment as a read-only interpreter and with both roots pointing to `phase1e`:

```powershell
F:\AI project\MathCyclus---Lingxi-Question-Bank-Assistant\MathCyclus---Lingxi-Question-Bank-Assistant\.venv\Scripts\python.exe tests\run_phase1e_regression.py --project-root C:\Users\17585\Documents\Codex\2026-07-08\ni\work\phase1e --module-root C:\Users\17585\Documents\Codex\2026-07-08\ni\work\phase1e --python-executable F:\AI project\MathCyclus---Lingxi-Question-Bank-Assistant\MathCyclus---Lingxi-Question-Bank-Assistant\.venv\Scripts\python.exe
```

Final status: PASS.

## 7. Automatic Test Results

- `py_compile`: PASS.
- `physics_phase1_smoke.py`: PASS.
- `physics_phase1d2_write_smoke.py`: PASS.
- `physics_phase1d2_move_smoke.py`: PASS.
- Index integrity checks: PASS.
- Streamlit AppTest advanced-search/session isolation checks: PASS.
- Duplicate physics ID rejection: PASS.
- Missing answer rejection: PASS.
- Illegal path rejection: PASS.
- Index-refresh failure rollback: PASS.
- Cross-directory move rollback: PASS.
- Mathematics-index hash mismatch blocks physics write: PASS.
- Final cleanup and residual-file check: PASS.

## 8. AppTest Coverage

- Mathematics default load shows the 70-question baseline.
- Physics advanced search field selections persist after rerun.
- Physics advanced search field selections persist after pressing search.
- Physics ID search returns exactly one result for a known physics ID.
- Mathematics advanced search defaults remain isolated from physics choices.

Long-running browser service was not started in this phase. A final manual browser check is still recommended before syncing.

## 9. Mathematics 99-Tex Finding

A raw scan of `chapters/` finds 99 `.tex` files, while the formal mathematics index contains 70 question records. The formal count remains 70 because the CSV index is the authoritative source for formal math questions.

The remaining 29 unindexed `.tex` files were only inspected, not modified, deleted, or added to the index:

- 23 files are chapter aggregate files named like `content_*.tex`.
- 6 files are auxiliary LaTeX figure/source files under related-image directories.
- None of the 29 unindexed files contained a complete formal single-question structure with formal ID plus `problem`/`answer`/`solutions`.

Any ambiguous future use of those files should be reviewed manually before indexing.

## 10. Physics Index Hash Difference

The previous Phase 1D-2 physics-index hash was:

`FFF1FB76256AFCF7A695EB1F5BDB2427CAED97A42B5AAB4814A569D38E1FD32C`

The current Phase 1E baseline is:

`DC9D49F6639647162BB0A75F23890D6A05D46A456EEE72F90ABE0CFCD961DD17`

The current physics index still has 44 columns, 8 rows, and the same physics question ID/path set. The hash difference came from index rebuild serialization, especially generated time fields, rather than a structural change or a formal question-content change. The current F-drive-derived Phase 1E baseline is therefore accepted as the physics-index baseline. The mathematics index hash remains the strict stability guard.

## 11. Cleanup And Data Safety

- Final mathematics question count: 70.
- Final physics question count: 8.
- No `PHY-TEMP-*` files remain.
- No `.tmp` files remain.
- No `.movebak` files remain.
- Test output directories created by the smoke tests were removed by cleanup.
- Formal mathematics and physics source question files were not modified by Phase 1E.

## 12. Rollback And Backup Method

Before syncing Phase 1E results to the formal F-drive project, create a timestamped backup of every file to be overwritten. If rollback is needed, copy those backed-up files back to their original paths and rerun:

```powershell
tests\run_phase1e_regression.py
```

Expected Phase 1E sync candidates are the unified regression script, the lightly adjusted smoke scripts, and this report. Business-code files should only be synced if a separately confirmed regression fix requires them.

## 13. Future Word/PDF Import Contract

Future import workflows must reuse:

- `validate_physics_question_payload`
- `build_target_path`
- `save_new_physics_question`
- `save_existing_physics_question_edit`
- `validate_physics_index_integrity`

PDF/OCR recognition output must first enter a review workflow. It must not write directly into the formal physics bank.

## 14. Recommendation

Phase 1E is suitable for sync review after manual confirmation. The next safe phase is Word/PDF import design, starting with a pending-review data model and only then adding parser/OCR dependencies.
