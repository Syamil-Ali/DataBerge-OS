# Messy Workbook Intelligence Implementation Plan

## Objective

Turn uploaded workbooks into a trustworthy data model before analysis by:

- Detecting actual table regions rather than assuming one worksheet equals one table.
- Profiling columns and explaining data-quality problems with concrete evidence.
- Inferring relationships conservatively and making every recommendation reviewable.
- Requiring user confirmation before relationships or high-impact transformations affect analysis.

## Current assessment

The existing product provides a credible foundation for clean, multi-sheet workbooks:

- Column profiling, missingness, duplicates, distributions, and semantic-role suggestions.
- Basic PK/FK, name-match, and value-coverage relationship inference.
- Review interfaces for relationships, previews, data dictionaries, and transformations.

The main limitation is that the relational importer currently treats each non-empty worksheet as one table. It does not yet reliably identify tables inside genuinely messy sheets containing titles, notes, multiple regions, repeated headers, totals, or merged cells.

Relationship inference also needs stricter validation. Incorrect relationships can silently corrupt joins, totals, and reports, so inference should prioritize precision over recall.

## Implementation sequence

### 1. Make relationship inference safe

This is the first priority because an incorrect relationship can produce incorrect analysis without an obvious error.

Extend each inferred relationship with evidence:

```python
{
    "parent_unique_ratio": 1.0,
    "child_match_ratio": 0.97,
    "orphan_count": 18,
    "null_count": 6,
    "type_compatible": True,
    "sample_matches": [["C-1001", "C-1001"]],
    "sample_orphans": ["C-9999"]
}
```

Implementation rules:

- Do not infer relationships from generic names such as `status`, `type`, `name`, `date`, or `description`.
- Normalize compatible identifiers before comparison, including safe equivalence between values such as `1`, `"1"`, and `"1.0"`.
- Require the proposed parent column to be sufficiently unique.
- Calculate match coverage using child rows rather than only distinct values.
- Treat null child values separately from unmatched non-null values.
- Flag explicit PK/FK annotations with poor coverage instead of trusting their labels automatically.
- Make inferred relationships inactive until the user confirms them.
- Store the inference method, validation evidence, and recommendation state.

Initial recommendation states:

- `recommended`
- `needs_review`
- `rejected`
- `confirmed`

Acceptance tests:

- Two unrelated `status` columns do not create a candidate relationship.
- An annotated foreign key with no matching parent values is rejected or prominently blocked.
- Integer `1` matches string `"1.0"` when normalization is unambiguous.
- Duplicate parent keys prevent a many-to-one recommendation.
- Null child values are not counted as orphan keys.
- Relationships are not active until explicitly confirmed.

Suggested test module:

```text
backend/tests/test_relationship_inference.py
```

### 2. Introduce a detected-table contract

Stop sending entire worksheets directly into profiling. First produce explicit table candidates:

```python
{
    "id": "sales__a5_h420",
    "sheet_name": "Sales",
    "cell_range": "A5:H420",
    "header_rows": [5],
    "data_start_row": 6,
    "row_count": 415,
    "column_count": 8,
    "confidence": 0.91,
    "detection_method": "blank_boundaries",
    "warnings": [
        "Three title rows were excluded",
        "A totals row was excluded"
    ]
}
```

Target workflow:

```text
Workbook upload
    -> Table detection
    -> User reviews ranges and headers
    -> Column profiling
    -> Relationship inference
    -> User confirms the model
    -> Analysis
```

Create a focused workbook-detection service and retain the existing Excel loader as a compatibility wrapper. Keep `.xls` on the existing limited path initially if the selected parser cannot preserve the metadata required for detection.

### 3. Build deterministic table detection v1

For `.xlsx` workbooks, inspect workbook structure before converting ranges into DataFrames.

Detection order:

1. Use native Excel Table definitions when available.
2. Inspect named ranges that resemble tabular data.
3. Calculate the occupied-cell grid for each visible worksheet.
4. Split regions using fully blank rows and columns.
5. Score potential header rows.
6. Exclude title and preamble rows above the selected header.
7. Detect likely totals, footnotes, and repeated headers.
8. Return multiple candidates when one worksheet contains multiple regions.

Header-scoring signals:

- Most cells in the row are populated.
- Values are predominantly text.
- Values are unique within the row.
- Following rows have a consistent width.
- Types below the row differ from the candidate header.
- Cells do not resemble notes, totals, or long prose.

For the first release, flag merged and multi-row headers for review instead of attempting to resolve every case automatically.

Suggested focused service:

```text
backend/app/services/workbook_detection.py
```

### 4. Add a table-boundary review screen

Before column profiling, show:

- Worksheet name and visibility.
- Detected cell range.
- Selected header row or rows.
- The first ten data rows.
- Excluded title and footer rows.
- Detection confidence and warnings.

Allow users to:

- Change the header row.
- Resize the detected range.
- Split one candidate into multiple tables.
- Merge adjacent candidates when appropriate.
- Ignore helper worksheets.
- Rename the resulting table.

Persist confirmed boundaries so reopening the project does not repeat detection or discard the user's decisions.

### 5. Replace warning strings with structured issues

Return stable, evidence-backed issue objects instead of only generic sentences:

```python
{
    "code": "DUPLICATE_PRIMARY_KEY",
    "severity": "high",
    "table": "Customers",
    "column": "customer_id",
    "affected_count": 14,
    "examples": ["C-1042", "C-1189"],
    "impact": "Joining orders may duplicate revenue.",
    "recommended_action": "Review or remove duplicate customer records.",
    "auto_fix_available": False
}
```

Initial issue detectors:

- Duplicate candidate keys.
- Orphan foreign keys.
- Mixed data types.
- Datetime parse failures.
- Constant and near-constant columns.
- Inconsistent category formatting.
- Repeated header rows.
- Totals embedded in data.
- Formula errors.
- High missingness.
- Unexpected identifier formats.
- Possible mixed currencies or units.

Do not silently fix high-impact issues. Present evidence and analytical impact before offering an action.

### 6. Surface relationship evidence in the UI

Extend the relationship review interface with an evidence panel:

```text
Orders.customer_id -> Customers.customer_id

Parent uniqueness        100%
Matching child rows       97%
Orphan rows               18
Null child values          6
Type compatibility        Compatible after normalization

Recommendation: Review before enabling
```

Users should be able to inspect sample matches and non-matches before enabling the relationship. Do not rely on a confidence percentage without explaining the evidence behind it.

### 7. Build a messy-workbook benchmark

Create a representative benchmark of generated or safely anonymized workbooks covering:

- A clean table beginning at `A1`.
- Titles and notes above the header.
- Multiple tables on one worksheet.
- Blank-row and blank-column separators.
- Hidden helper worksheets.
- Merged or multi-row headers.
- Repeated headers within the data.
- Subtotals and grand totals.
- Sparse formatting outside the real table.
- Mixed data types and malformed dates.
- Valid, invalid, and ambiguous relationships.

Track at least:

- Table-region precision and recall.
- Header-row accuracy.
- Relationship precision and recall.
- Orphan-count accuracy.
- False-positive rate for automatically recommended relationships.
- Percentage of user corrections required.

Relationship precision should be approximately 98% or higher before considering automatic activation. Until then, confirmation remains mandatory.

## Recommended first pull request

### Safe relationship inference with explainable evidence

Status: implemented as the first vertical slice. Inferred relationships now begin disabled, include row-level validation evidence, exclude generic name-only matches, and are covered by regression tests.

Scope:

- Add normalized key comparison.
- Add parent uniqueness, child-row coverage, null counts, and orphan counts.
- Block generic same-name columns.
- Stop activating inferred relationships automatically.
- Reject or prominently flag annotated PK/FK relationships with no matching values.
- Display the evidence in the relationship review interface.
- Add regression tests for known false positives and representation mismatches.

Likely files involved:

- `backend/app/services/relational.py`
- `backend/app/api/relational.py`
- `frontend/src/types/domain.ts`
- `frontend/src/components/relationship/RelationshipMap.tsx`
- `backend/tests/test_relationship_inference.py`

This first release improves trust immediately without requiring the workbook-ingestion pipeline to be rebuilt at the same time.

## Product copy during implementation

Until table-region detection and relationship validation are complete, use a narrower promise:

> Understand and validate multi-sheet workbooks before analysis.

After the acceptance criteria are met, the stronger positioning becomes credible:

> Turn messy workbooks into a trusted data model.

## Definition of done

The capability is ready to be marketed as messy workbook intelligence when:

- Multiple tables can be detected within one worksheet.
- Titles, notes, repeated headers, and total rows are excluded or clearly flagged.
- Users can review and correct every detected boundary.
- Relationship recommendations include visible validation evidence.
- Name-only relationship candidates are never silently activated.
- Data-quality issues identify affected locations, examples, impact, and recommended actions.
- Workbook and relationship decisions persist across navigation and future sessions.
- The benchmark meets the agreed precision targets.
- Backend tests, frontend tests, and the production build pass.
