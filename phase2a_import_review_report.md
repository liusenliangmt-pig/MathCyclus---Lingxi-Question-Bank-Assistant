# Phase 2A-1 Import Review Framework Report

## 1. Goals

Phase 2A-1 fixes the Streamlit sidebar usability issue and introduces a shared
Word/PDF import-review foundation:

- Import candidate creation.
- Candidate preview.
- Manual field correction.
- Manual review.
- Formal physics-bank write only after approval.

This phase does not implement real Word parsing, PDF parsing, OCR, AI
recognition, file upload, or batch formal import.

## 2. Candidate/Formal Bank Boundary

Import candidates are local staging records. They do not belong to
`chapters_physics/` and they are not scanned by the physics CSV index.

Formal question creation happens only through:

```python
approve_import_candidate(...)
```

That service validates the candidate and then calls:

```python
save_new_physics_question(...)
```

No second direct `.tex` writing path was added.

## 3. Staging Directory Structure

The fixed staging root is:

```text
data/import_staging/
```

Runtime layout:

```text
data/import_staging/
  <batch_id>/
    batch.json
    candidates/
      <candidate_id>.json
    assets/
```

Only `data/import_staging/README.md` and
`data/import_staging/.gitignore` should be tracked. Real candidate data,
source images, locks, and temporary files are local runtime data and are
ignored by Git.

Future PDF page images should be stored under the same batch's `assets/`
directory and referenced through `source_file` or `original_image_path`.

Batch IDs and candidate IDs are restricted to letters, digits, hyphens, and
underscores. Paths are resolved and checked with `relative_to()` so they remain
inside `data/import_staging/`.

## 4. Candidate Data Structure

Candidate JSON uses `schema_version: 1`.

Main field groups:

- Status fields: `candidate_id`, `discipline`, `review_status`,
  `review_notes`, `created_at`, `updated_at`.
- Source fields: `source_type`, `source_file`, `source_page`,
  `source_region`, `import_batch_id`, `recognition_method`,
  `ocr_confidence`, `original_image_path`.
- Question fields: `question_id`, `stage`, `grade`, `volume`,
  `knowledge_block`, `knowledge_point`, `question_type`, `difficulty`,
  `score`, `tags`, `source`, `remark`, `experiment_type`, `image_type`,
  `unit_requirement`, diagram flags, `enabled`, `problem`, `answer`,
  `solutions`.

Writes use same-directory temp files, flush, fsync, and `os.replace()`.

## 5. Review Status Flow

Supported status values:

- `pending_review`: 待审核
- `approved`: 已通过
- `rejected`: 已驳回

Allowed transitions:

- `pending_review -> approved`
- `pending_review -> rejected`
- `rejected -> pending_review` only through explicit restore

Approved candidates cannot be approved again. Rejected candidates cannot be
approved directly.

## 6. Formal Entry Mapping

Candidate fields map to formal physics metadata:

- `source_type -> 来源类型`
- `source_file -> 来源文件`
- `source_page -> 来源页码`
- `source_region -> 来源区域坐标`
- `import_batch_id -> 导入批次ID`
- `recognition_method -> 识别方式`
- `ocr_confidence -> OCR置信度`
- `review_status -> 审核状态`
- `review_notes -> 审核备注`
- `original_image_path -> 原始图片路径`

Formal入库时 `审核状态` is written as `已通过`, not `pending_review`.

## 7. Atomicity And Rollback

Approval order:

1. Re-read candidate JSON.
2. Acquire a per-candidate lock file.
3. Confirm candidate is still `pending_review`.
4. Check whether the formal question ID already exists.
5. Validate candidate fields.
6. Call `save_new_physics_question`.
7. Validate formal file and physics index through the existing physics save
   layer.
8. Atomically update candidate status to `approved`.
9. Record `approved_at`, `official_question_id`, and `official_file_path`.
10. Release lock.

If formal entry fails, the candidate remains `pending_review` and
`approval_error` is stored. If a formal question exists before approval, the
service reports that the question may already have entered the formal bank and
requires manual state recovery.

## 8. UI Entry

Physics mode adds:

```text
题库导入与审核
```

The page supports:

- Creating/loading a batch.
- Creating a manual candidate.
- Loading one built-in test candidate.
- Listing candidates.
- Filtering by review status.
- Previewing problem/answer/solutions and source fields.
- Editing candidate fields before approval.
- Rejecting a candidate.
- Restoring a rejected candidate to pending review.
- Approving and entering the formal physics bank with a required confirmation
  checkbox.

Mathematics mode does not expose the physics approval action.

## 9. Sidebar UI Fix

The sidebar width is no longer fixed at `110px`. It now uses a responsive range
around `280px` to `300px`, hides horizontal overflow, and lets Chinese text wrap
by words/phrases rather than being squeezed character by character.

Stable selectors are used, mainly Streamlit `data-testid` attributes and the
existing sidebar structure. Streamlit's native collapse/expand behavior is kept.

Manual browser checks:

- At 100% browser zoom, open the sidebar and confirm menu labels are not
  clipped.
- At 125% browser zoom, confirm subject selector, radio labels, and buttons
  remain readable.
- Collapse and reopen the sidebar.
- Switch between mathematics and physics.
- Open the physics import-review page.
- Confirm the main content area and advanced search page width are not broken.

## 10. Automatic Tests

Commands run in the Phase 2A temporary copy:

```powershell
python -m py_compile question_bank_app.py utils\import_review_ops.py tests\physics_phase2a_import_review_smoke.py tests\phase2a_sidebar_css_smoke.py tests\run_phase2a_regression.py
python tests\physics_phase2a_import_review_smoke.py --project-root <phase2a> --module-root <phase2a>
python tests\phase2a_sidebar_css_smoke.py
python tests\run_phase2a_regression.py --project-root <phase2a> --module-root <phase2a> --python-executable <python>
```

Final result: PASS.

Covered cases:

- Illegal `batch_id` and `candidate_id` rejected.
- Path traversal rejected.
- Corrupt JSON rejected.
- Candidate create/edit/reload.
- Candidate reject.
- Rejected candidate direct approval rejected.
- Approval creates one formal physics file.
- Approved candidate cannot approve twice.
- Duplicate formal question ID rejected.
- Simulated formal index-refresh failure keeps candidate pending and records
  `approval_error`.
- Cleanup restores physics count to 8 and math hash unchanged.
- Staging directory has no test data residuals.
- Phase 1E regression remains PASS.

## 11. Baseline And Final Counts

- Mathematics index rows: 70.
- Physics source questions: 8.
- Physics index rows: 8.
- Physics index columns: 44.
- Mathematics index SHA-256:
  `250092C5158BA3A2185253AC0F0A141E5AE74C5C668A4CC74B208309EDE84386`.
- Physics index SHA-256:
  `DC9D49F6639647162BB0A75F23890D6A05D46A456EEE72F90ABE0CFCD961DD17`.

## 12. Not Supported Yet

- Real PDF upload or parsing.
- Real Word upload or parsing.
- OCR.
- AI recognition.
- Batch approval into the formal bank.
- Deleting formal physics questions.
- Network question-bank collection.

## 13. Next Phase Suggestion

The next safe step is electronic PDF intake:

1. Save uploaded PDF files into staging batch assets.
2. Extract text/pages into candidate JSON only.
3. Display extracted candidates in the existing review UI.
4. Require manual approval before formal entry.
5. Continue using `approve_import_candidate` for formal writes.
