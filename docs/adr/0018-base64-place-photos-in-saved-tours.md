# ADR 0018 - Store Place Photos in Saved Tour Snapshots

Status: Accepted
Date: 2026-11-05

## Context

The itinerary shows optional, credited Wikimedia Commons photos. Explicitly
saved tours currently retain the plan and source references but omit those
photos, so an archived tour cannot show the images found for its places.

## Decision

- On explicit save of a validated current plan, copy available place images
  into that saved snapshot as Base64 with their Commons file page, credit,
  license and alt text. Keep visual data keyed by schedule entry ID.
- Download only bounded image bytes from the trusted Commons image host over
  HTTPS. Reject unsupported types, oversized responses and unsafe redirects.
  Image retrieval remains optional: a failed image cannot change the plan or
  prevent the tour from being saved.
- Store the image data in the existing JSON snapshot text in PostgreSQL, with
  the same behavior in the local SQLite fallback. No table migration is needed.
  Existing snapshots without images remain readable. Repeated saves of one
  owner, plan ID and revision return the original immutable snapshot.
- Render archived images from the saved bytes. Reading an archive never
  refreshes Commons images or invokes plan research. Attribution stays visible.
  Live itinerary state and public photo lookup cache remain session-only or
  presentation data, separate from the saved archive.

## Consequences

- Base64 increases saved snapshot size. Bound image count and bytes per image;
  archive list queries continue to fetch metadata only.
- Saved photos reflect the image and attribution at save time. They may become
  stale; the Commons source page remains available for checking current terms.
- This amends ADR 0006's visual persistence boundary and ADR 0014/0015's
  saved snapshot content. Explicit-save, owner scope and read-only archive
  behavior remain in force.

## Alternatives Considered

- Store only photo URLs: archived images can disappear or change after saving.
- Add a separate image table: unnecessary for bounded images read only with one
  saved-tour detail; it would require a database migration in both backends.

## Review Triggers

- Typical snapshot size or save latency exceeds deployment limits.
- A new image provider or rights policy changes trusted hosts or attribution.
