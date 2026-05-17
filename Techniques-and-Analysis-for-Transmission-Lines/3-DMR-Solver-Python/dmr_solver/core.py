"""Newton-Raphson nonlinear equation solver inspired by DMR-SOLVER."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


ArrayLike = np.ndarray | list[float] | tuple[float, ...]
Equation = Callable[[np.ndarray], ArrayLike]
Jacobian = Callable[[np.ndarray], ArrayLike]


@dataclass(frozen=True)
class DMRIteration:
    """State captured at one Newton-Raphson iteration."""

    iteration: int
    x: np.ndarray
    f: np.ndarray
    residual_norm: float
    step_norm: float | None


@dataclass(frozen=True)
class DMRResult:
    """Named result for callers that prefer attributes over tuple unpacking."""

    x: np.ndarray
    iter: int
    stat: int
    jac: np.ndarray
    history: tuple[DMRIteration, ...]

    def as_tuple(self) -> tuple[np.ndarray, int, int, np.ndarray]:
        return self.x, self.iter, self.stat, self.jac


def dmr_solver(
    equa: Equation,
    x0: ArrayLike,
    tol: float,
    *,
    max_iter: int = 100,
    jacobian: Jacobian | None = None,
    finite_diff_step: float | None = None,
    damping: bool = True,
    return_result: bool = False,
) -> tuple[np.ndarray, int, int, np.ndarray] | DMRResult:
    """Solve ``equa(x) = 0`` with Newton-Raphson iterations.

    The default return mirrors MATLAB's public DMR-SOLVER signature:
    ``X, ITER, STAT, JAC = dmr_solver(equa, X0, TOL)``.

    ``STAT`` follows the MATLAB documentation: ``1`` means convergence was
    reached, while ``2`` means the iteration stopped without convergence.
    """

    if tol <= 0:
        raise ValueError("tol must be positive.")
    if max_iter < 1:
        raise ValueError("max_iter must be at least 1.")

    x = _as_vector(x0, "x0")
    f = _evaluate_equation(equa, x)
    jac = _evaluate_jacobian(equa, x, f, jacobian, finite_diff_step)
    history: list[DMRIteration] = [
        _iteration_record(iteration=0, x=x, f=f, step_norm=None)
    ]

    stat = 1 if _residual_norm(f) <= tol else 2
    iterations = 0

    while stat != 1 and iterations < max_iter:
        step = _newton_step(jac, f)
        candidate = x + step

        if damping:
            candidate, next_f = _damped_candidate(equa, x, f, step)
        else:
            next_f = _evaluate_equation(equa, candidate)

        x = candidate
        f = next_f
        jac = _evaluate_jacobian(equa, x, f, jacobian, finite_diff_step)
        iterations += 1
        history.append(
            _iteration_record(
                iteration=iterations,
                x=x,
                f=f,
                step_norm=_residual_norm(step),
            )
        )

        if _residual_norm(f) <= tol:
            stat = 1
            break

    result = DMRResult(
        x=x,
        iter=iterations,
        stat=stat,
        jac=jac,
        history=tuple(history),
    )
    return result if return_result else result.as_tuple()


def _as_vector(values: ArrayLike, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=float).reshape(-1)
    if vector.size == 0:
        raise ValueError(f"{name} must contain at least one value.")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values.")
    return vector


def _evaluate_equation(equa: Equation, x: np.ndarray) -> np.ndarray:
    values = _as_vector(equa(x.copy()), "equa(x)")
    if not np.all(np.isfinite(values)):
        raise ValueError("equa(x) returned a non-finite value.")
    return values


def _evaluate_jacobian(
    equa: Equation,
    x: np.ndarray,
    f: np.ndarray,
    jacobian: Jacobian | None,
    finite_diff_step: float | None,
) -> np.ndarray:
    if jacobian is not None:
        jac = np.asarray(jacobian(x.copy()), dtype=float)
    else:
        jac = _finite_difference_jacobian(equa, x, f, finite_diff_step)

    expected_shape = (f.size, x.size)
    if jac.shape != expected_shape:
        raise ValueError(
            f"Jacobian shape must be {expected_shape}, got {jac.shape}."
        )
    if not np.all(np.isfinite(jac)):
        raise ValueError("Jacobian contains a non-finite value.")
    return jac


def _finite_difference_jacobian(
    equa: Equation,
    x: np.ndarray,
    f: np.ndarray,
    finite_diff_step: float | None,
) -> np.ndarray:
    if finite_diff_step is not None and finite_diff_step <= 0:
        raise ValueError("finite_diff_step must be positive.")

    base_step = finite_diff_step or np.sqrt(np.finfo(float).eps)
    jac = np.empty((f.size, x.size), dtype=float)

    for col in range(x.size):
        step_size = base_step * max(1.0, abs(x[col]))
        delta = np.zeros_like(x)
        delta[col] = step_size

        f_plus = _evaluate_equation(equa, x + delta)
        f_minus = _evaluate_equation(equa, x - delta)
        jac[:, col] = (f_plus - f_minus) / (2.0 * step_size)

    return jac


def _newton_step(jac: np.ndarray, f: np.ndarray) -> np.ndarray:
    rhs = -f
    if jac.shape[0] == jac.shape[1]:
        try:
            return np.linalg.solve(jac, rhs)
        except np.linalg.LinAlgError:
            pass

    step, *_ = np.linalg.lstsq(jac, rhs, rcond=None)
    return step


def _damped_candidate(
    equa: Equation,
    x: np.ndarray,
    f: np.ndarray,
    step: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    current_norm = _residual_norm(f)
    scale = 1.0
    best_x = x + step
    best_f = _evaluate_equation(equa, best_x)
    best_norm = _residual_norm(best_f)

    while best_norm > current_norm and scale > 1e-4:
        scale *= 0.5
        trial_x = x + scale * step
        trial_f = _evaluate_equation(equa, trial_x)
        trial_norm = _residual_norm(trial_f)
        if trial_norm < best_norm:
            best_x = trial_x
            best_f = trial_f
            best_norm = trial_norm

    return best_x, best_f


def _residual_norm(values: np.ndarray) -> float:
    return float(np.linalg.norm(values, ord=np.inf))


def _iteration_record(
    iteration: int,
    x: np.ndarray,
    f: np.ndarray,
    step_norm: float | None,
) -> DMRIteration:
    return DMRIteration(
        iteration=iteration,
        x=x.copy(),
        f=f.copy(),
        residual_norm=_residual_norm(f),
        step_norm=step_norm,
    )
