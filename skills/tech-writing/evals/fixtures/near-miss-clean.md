# Retry configuration in the ingest client

This note covers the retry behavior of the ingest client for engineers who operate the
pipeline. It assumes you have read the client configuration reference.

The client retries on 429, 502, and 503 responses. Retries are configured per client, not
per request; a per-request reading overstates the retry budget by an order of magnitude.
Which backoff should you choose? The answer depends on how bursty your traffic is, and
the default exponential curve suits most deployments.

On startup, the service reads the config file and the program searches the retry table
for a matching policy. Each policy is held in a red-black tree, ordered by priority, so
lookups stay logarithmic under load. A process listens on port 8080 for health probes.

Fortran excels at numeric computation. Lisp excels at symbol manipulation. The retry
engine borrows from both traditions: numeric backoff curves, symbolic policy names.

The client accepts three tuning parameters:

- max_attempts: the ceiling on total tries, including the first
- base_delay: the starting backoff interval
- jitter: the random fraction added to each delay

## Frequently asked questions

Idempotency keys make retries safe: the server deduplicates any request that carries one.
If your handler mutates external state, attach a key before enabling retries.
