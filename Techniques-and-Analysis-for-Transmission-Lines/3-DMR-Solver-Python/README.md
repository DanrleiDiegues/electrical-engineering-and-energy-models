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

### Changing variables and equations in Streamlit

The Streamlit app builds the solver input dynamically from the fields filled by
the user.

In the sidebar, write the variable names separated by commas:

```text
k, y, w, z
```

The order defines the internal vector `X`:

```python
X[0] = k
X[1] = y
X[2] = w
X[3] = z
```

Then write `X0` in the same order:

```text
5, 6, 1, 1
```

This means:

```text
k = 5
y = 6
w = 1
z = 1
```

The equations are written one per line in the `Equations` field. Each line can
be an expression equal to zero:

```python
k * sin(2*w) + y * sin(w) - 2*z
k * sin(w) - z
k**2 * cos(2*w) + k*y*cos(w)
2*k + y - 24
```

or in the natural `lhs = rhs` form:

```python
k * sin(w) = z
2*k + y = 24
```

The app converts these internally to expressions equal to zero:

```python
k * sin(w) - z
2*k + y - 24
```

When the user clicks `Run solver`, the app:

1. reads the variable names;
2. builds the initial vector `X0`;
3. compiles the typed equations;
4. creates the function `equa(x)`;
5. calls `dmr_solver`;
6. shows the solution, final residuals, final Jacobian, and convergence plots.

Supported functions in equations include:

```text
sin, cos, tan, exp, log, log10, sqrt, abs, sinh, cosh, tanh
```

Supported constants:

```text
pi, e
```

Important notes:

- `X0` must have the same number of values as the variable list.
- Ideally, the number of equations should match the number of variables.
- If the numbers are different, the solver still tries to compute the Newton
  step with least squares, but the result may be less predictable.