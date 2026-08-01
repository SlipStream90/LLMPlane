"""Business logic services.

Routes stay thin: validate input, call a service or repository, shape a
response. Anything that talks to a system outside Postgres — the gateway,
Docker (via workers), Langfuse, provider APIs — lives here, behind a class that
can be substituted in tests.
"""
