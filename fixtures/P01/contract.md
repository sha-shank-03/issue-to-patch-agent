# API contract

Zero-based page index, size 1..100. Return the exact slice of IDs [1,2,3,4,5,6], including a short final page; offsets beyond the list return empty. Reject negative page or invalid size.
