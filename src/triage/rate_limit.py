import redis.asyncio as redis


class RateLimiter:
    """Redis fixed-window limiter suitable for one-process or multi-replica API deployments."""

    def __init__(self, url: str, limit: int):
        self.client = redis.from_url(url, decode_responses=True)
        self.limit = limit

    async def allow(self, identity: str) -> bool:
        """Atomically increment a short-lived counter for the authenticated caller."""
        key = f"rate:{identity}"
        async with self.client.pipeline(transaction=True) as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, 60, nx=True)
            count, _ = await pipeline.execute()
        return int(count) <= self.limit

    async def healthy(self) -> bool:
        """Report whether Redis can accept commands."""
        try:
            return bool(await self.client.ping())
        except redis.RedisError:
            return False

    async def close(self) -> None:
        """Close the Redis connection pool."""
        await self.client.aclose()

