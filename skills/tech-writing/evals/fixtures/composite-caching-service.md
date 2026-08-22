# CacheFabric: your data's new best friend

CacheFabric isn't just a cache — it's a pivotal consistency layer for your entire data
landscape. It boasts meticulously tuned eviction and crucial durability guarantees,
fostering trust at every layer of the stack.

Fast. Predictable. Zero config.

## Why is CacheFabric so fast?

CacheFabric remembers your hottest keys and refuses stale writes. When a node sees a
write conflict, it complains loudly in the logs, then decides which replica it wants to
trust. The engine speaks Redis, so your clients think they are talking to a plain
key-value store.

There is a background compactor that runs in order to reclaim space. Simply enable it —
it's really easy — and you just need to wait a moment for the savings to appear.

## What makes the eviction policy special?

Eviction is delightfully simple:

- scans the access log
- Hot keys are promoted to the pinned tier.
- eviction of cold keys

The result is screamingly fast reads across the board. Think of CacheFabric as a group
chat for your database: everyone eventually sees your message, and nobody has to delve
into the intricate details.
