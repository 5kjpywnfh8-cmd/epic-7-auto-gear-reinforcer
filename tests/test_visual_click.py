from __future__ import annotations

import math
import unittest

from src.e7_enhance.visual_click import (
    ClickAlreadyAttemptedError,
    ClickAuthorizationError,
    ClickResultUnknownError,
    ClickTargetError,
    NormalizedClickExecutor,
    NormalizedClickTarget,
)


class RecordingBackend:
    def __init__(self, viewport=(100, 200), error=None):
        self.viewport = viewport
        self.error = error
        self.viewport_calls = 0
        self.clicks = []

    def viewport_size(self):
        self.viewport_calls += 1
        return self.viewport

    def click(self, x, y):
        self.clicks.append((x, y))
        if self.error:
            raise self.error


class NormalizedClickExecutorTest(unittest.TestCase):
    def test_authorized_click_maps_normalized_point_to_current_viewport(self):
        backend = RecordingBackend()
        executor = NormalizedClickExecutor(
            backend,
            NormalizedClickTarget(0.25, 0.75),
            action_authorized=True,
        )

        executor.click_enhance()

        self.assertEqual(backend.clicks, [(25, 149)])
        self.assertEqual(executor.last_click.x, 25)
        self.assertEqual(executor.last_click.y, 149)
        self.assertTrue(executor.attempted)

    def test_unauthorized_action_fails_without_backend_access_and_cannot_retry(self):
        backend = RecordingBackend()
        executor = NormalizedClickExecutor(backend, NormalizedClickTarget(0.5, 0.5))

        with self.assertRaises(ClickAuthorizationError):
            executor.click_enhance()
        with self.assertRaises(ClickAlreadyAttemptedError):
            executor.click_enhance()

        self.assertEqual(backend.viewport_calls, 0)
        self.assertEqual(backend.clicks, [])

    def test_invalid_target_and_viewport_fail_closed_before_click(self):
        cases = (
            NormalizedClickTarget(-0.01, 0.5),
            NormalizedClickTarget(0.5, math.inf),
            NormalizedClickTarget(10**10000, 0.5),
        )
        for target in cases:
            with self.subTest(target=target):
                backend = RecordingBackend()
                executor = NormalizedClickExecutor(backend, target, action_authorized=True)
                with self.assertRaises(ClickTargetError):
                    executor.click_enhance()
                self.assertEqual(backend.clicks, [])

        backend = RecordingBackend(viewport=(0, 200))
        executor = NormalizedClickExecutor(
            backend,
            NormalizedClickTarget(0.5, 0.5),
            action_authorized=True,
        )
        with self.assertRaises(ClickTargetError):
            executor.click_enhance()
        self.assertEqual(backend.clicks, [])

    def test_backend_failure_is_unknown_and_never_retried(self):
        backend = RecordingBackend(error=OSError("backend unavailable"))
        executor = NormalizedClickExecutor(
            backend,
            NormalizedClickTarget(0.5, 0.5),
            action_authorized=True,
        )

        with self.assertRaises(ClickResultUnknownError):
            executor.click_enhance()
        with self.assertRaises(ClickAlreadyAttemptedError):
            executor.click_enhance()

        self.assertEqual(len(backend.clicks), 1)
        self.assertEqual(executor.last_click.viewport_width, 100)


if __name__ == "__main__":
    unittest.main()
