# API contract

Sort globally by createdAt then id before pagination, regardless of insertion order. Global IDs are [1,3,2,4,5,6]; adjacent pages must have no gaps or duplicates. Use zero-based pages, size 1..100, and overflow-safe offsets. Reject negative page or invalid size; an offset beyond the rows returns empty and a final partial page returns its remaining rows.
