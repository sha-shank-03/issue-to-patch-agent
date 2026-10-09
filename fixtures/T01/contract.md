# API contract

Fresh A=5,B=1,orders=0,audit=0. Validate both positive quantities and both stock levels before any mutation. Success debits both lines and adds one order/audit entry. Every failure leaves the whole snapshot unchanged.
