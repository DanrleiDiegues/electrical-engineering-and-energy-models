from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dmr_solver import dmr_solver


def equa(x):
    k, y, w, z = x
    return np.array(
        [
            k * np.sin(2 * w) + y * np.sin(w) - 2 * z,
            k * np.sin(w) - z,
            k**2 * np.cos(2 * w) + k * y * np.cos(w),
            2 * k + y - 24,
        ]
    )


if __name__ == "__main__":
    x0 = np.array([5.0, 6.0, 1.0, 1.0])
    x, iterations, stat, jac = dmr_solver(equa, x0, 0.001)

    print("X =", x)
    print("ITER =", iterations)
    print("STAT =", stat)
    print("JAC =")
    print(jac)
