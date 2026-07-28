from uuid import uuid4
from unittest import skipUnless

from django.conf import settings
from django.core.cache import cache
from django.core.cache.backends.redis import RedisCache
from django.test import SimpleTestCase


@skipUnless(settings.REDIS_URL, "requires the CI Redis service")
class RedisCacheIntegrationTest(SimpleTestCase):
    def setUp(self):
        self.cache_key = f"pows:ratelimit:ci:{uuid4()}"

    def tearDown(self):
        cache.delete(self.cache_key)

    def test_throttle_history_is_visible_to_independent_redis_client(self):
        throttle_history = [1_700_000_000.0, 1_700_000_001.0]
        cache.set(self.cache_key, throttle_history, timeout=60)

        independent_client = RedisCache(settings.REDIS_URL, params={})

        assert independent_client.get(self.cache_key) == throttle_history
