# Onboarding guide for the billing API

This guide targets engineers integrating the billing API for the first time. Following
plainlanguage.gov and the Microsoft Writing Style Guide, which recommend question-style
headings for approachability, each section heading below is phrased as the question a new
integrator would ask.

## What credentials do I need?

The API accepts service-account tokens scoped to the billing role. Tokens expire after
twelve hours, and the client library refreshes them automatically.

## How do I create my first invoice?

Send a POST request to /v1/invoices with the customer id and at least one line item. The
response carries the invoice id you use for all later operations.

## When should I use idempotency keys?

Attach an idempotency key to any request that creates or mutates state. The server
deduplicates requests that carry the same key for twenty-four hours.
