const OFFICE_SHA = 'f99b62ccadd9d625c64c4b68f89eda544ea8cac5986970d0a21473d9fcb3fd76';
const TEST_PAIR = 'duplicate_opening_candidate|66076|108748';
const TEST_NOTE = 'Synthetic reference case: expected matching geometry and offset verified against the configured tolerance. Decision recorded to test review persistence.';

// Only this identified persistence-test record is migrated. Other judgements,
// even on the same public IFC, remain untouched. Prior data is retained.
export function migrateKnownTestReview(reviews, modelSha, at = new Date().toISOString()) {
  const existing = reviews?.[TEST_PAIR];
  if (modelSha !== OFFICE_SHA || existing?.review_status !== 'confirmed_duplicate' ||
      existing?.review_note !== TEST_NOTE) return {reviews, changed: false};
  const archived = {review_status: existing.review_status, review_note: existing.review_note,
    reviewed_at: existing.reviewed_at, archived_at: at, reason: 'Known persistence-test decision; not a real-model adjudication.'};
  return {changed: true, reviews: {...reviews, [TEST_PAIR]: {...existing,
    review_status: 'unresolved',
    review_note: 'Coincident openings reference different hosts. #66076 is at least 58.71 m from host #65997. Investigate the exported relationship before deciding duplication. Previous persistence-test confirmation archived.',
    reviewed_at: at, review_history: [...(existing.review_history || []), archived],
    migration_id: 'office-opening-test-review-v0715'}}};
}
