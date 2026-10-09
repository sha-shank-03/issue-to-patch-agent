# API contract

Fresh A=5,B=8,orders=0,audit=0. A valid request debits A and adds one order/audit. A deterministic audit failure or invalid quantity must leave every field unchanged. This models single-threaded in-memory atomicity only.
