import math
import unittest

import numpy as np

from dmr_solver import DMRResult, dmr_solver


def official_example(x):
    k, y, w, z = x
    return np.array(
        [
            k * np.sin(2 * w) + y * np.sin(w) - 2 * z,
            k * np.sin(w) - z,
            k**2 * np.cos(2 * w) + k * y * np.cos(w),
            2 * k + y - 24,
        ]
    )


class DmrSolverTest(unittest.TestCase):
    def test_solves_official_example(self):
        x, iterations, stat, jac = dmr_solver(
            official_example, [5.0, 6.0, 1.0, 1.0], 0.001
        )

        self.assertEqual(stat, 1)
        self.assertLess(iterations, 20)
        np.testing.assert_allclose(
            x, [8.0, 8.0, math.pi / 3.0, 4.0 * math.sqrt(3.0)], atol=1e-3
        )
        self.assertEqual(jac.shape, (4, 4))
        self.assertLessEqual(np.linalg.norm(official_example(x), ord=np.inf), 0.001)

    def test_accepts_user_jacobian(self):
        def equa(x):
            return np.array([x[0] ** 2 - 4.0])

        def jac(x):
            return np.array([[2.0 * x[0]]])

        x, _, stat, _ = dmr_solver(equa, [3.0], 1e-10, jacobian=jac)

        self.assertEqual(stat, 1)
        self.assertAlmostEqual(x[0], 2.0)

    def test_can_return_named_result(self):
        result = dmr_solver(
            lambda x: np.array([x[0] - 1.0]), [0.0], 1e-12, return_result=True
        )

        self.assertIsInstance(result, DMRResult)
        self.assertEqual(result.stat, 1)
        self.assertAlmostEqual(result.x[0], 1.0)
        self.assertGreaterEqual(len(result.history), 1)
        self.assertEqual(result.history[-1].iteration, result.iter)

    def test_reports_non_convergence(self):
        x, iterations, stat, jac = dmr_solver(
            lambda x: np.array([x[0] ** 2 + 1.0]),
            [0.0],
            1e-12,
            max_iter=1,
            damping=False,
        )

        self.assertEqual(stat, 2)
        self.assertEqual(iterations, 1)
        self.assertEqual(jac.shape, (1, 1))
        self.assertTrue(np.isfinite(x[0]))


if __name__ == "__main__":
    unittest.main()
