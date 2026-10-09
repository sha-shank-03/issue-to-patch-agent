# API contract

All lines refer to SKU A. Aggregate their positive quantities before validating against A=5. SKU B=8 is unrelated and unchanged. A valid request debits the aggregate once and adds one order/audit; failure changes nothing. Array inputs are nonempty, contain at most three lines and are not null.
