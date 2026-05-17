# DMR-SOLVER Python

Python implementation of the public MATLAB DMR-SOLVER interface from
[`gopt-ufjf/DMR-solver`](https://github.com/gopt-ufjf/DMR-solver).

The upstream repository exposes the solver body only as `DMR_SOLVER.p`
(MATLAB P-code), so this project reproduces the documented API and behavior:
Newton-Raphson iterations for nonlinear systems, numerical Jacobian by default,
and the same convergence status convention.

## Install locally

```bash
python -m pip install -e .
```

## Usage

MATLAB:

```matlab
[X,ITER,STAT,JAC] = DMR_SOLVER(@EQUA,X0,TOL)
```

Python:

```python
import numpy as np
from dmr_solver import dmr_solver


def equa(x):
    k, y, w, z = x
    return np.array([
        k * np.sin(2 * w) + y * np.sin(w) - 2 * z,
        k * np.sin(w) - z,
        k**2 * np.cos(2 * w) + k * y * np.cos(w),
        2 * k + y - 24,
    ])


x0 = np.array([5.0, 6.0, 1.0, 1.0])
x, iterations, stat, jac = dmr_solver(equa, x0, 0.001)
```

`stat == 1` means convergence was reached. `stat == 2` means the maximum number
of iterations was reached without convergence.

Run the bundled example:

```bash
python examples/equa_example.py
```

Run tests:

```bash
python -m unittest discover -s tests
```

## Streamlit app

The Streamlit interface is available in `streamlit_app.py`. It lets users enter:

- variable names;
- initial point `X0`;
- tolerance and maximum iterations;
- one equation per line.

Equations can be written as expressions equal to zero:

```python
k * sin(2*w) + y * sin(w) - 2*z
```

or as `lhs = rhs`:

```python
k * sin(w) = z
```

Run locally after installing the requirements:

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

For Streamlit Cloud, upload this folder and set the main file to
`streamlit_app.py` or `app.py`.
