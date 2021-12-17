import asyncio
import time
from contextlib import asynccontextmanager


@asynccontextmanager
async def timeit():
    now = time.monotonic()
    try:
        yield
    finally:
        print(f"it took {time.monotonic() - now}s to run")


@timeit()
async def main() -> None:
    await asyncio.sleep(1)


asyncio.run(main())
