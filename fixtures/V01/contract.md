# ShopApi quantity contract

Each fresh API starts with stock 200 and orders 0. createOrder accepts integer
quantities 1 through 100 inclusive. Success subtracts quantity from stock and
increments orders once. Every other integer throws IllegalArgumentException
before any state changes. The service is a single-threaded, in-memory Java
library API; no HTTP server or production database is involved.
