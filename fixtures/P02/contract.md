# API contract

Calculate nonnegative page*size without integer overflow; any offset beyond six IDs returns empty. Size=1..100; negative pages/invalid sizes throw before returning a slice.
