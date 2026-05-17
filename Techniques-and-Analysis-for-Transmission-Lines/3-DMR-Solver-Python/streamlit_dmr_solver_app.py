from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from dmr_solver import dmr_solver


ALLOWED_FUNCTIONS = {
    "abs": np.abs,
    "arccos": np.arccos,
    "arcsin": np.arcsin,
    "arctan": np.arctan,
    "acos": np.arccos,
    "asin": np.arcsin,
    "atan": np.arctan,
    "ceil": np.ceil,
    "cos": np.cos,
    "cosh": np.cosh,
    "exp": np.exp,
    "floor": np.floor,
    "log": np.log,
    "log10": np.log10,
    "max": np.maximum,
    "min": np.minimum,
    "sin": np.sin,
    "sinh": np.sinh,
    "sqrt": np.sqrt,
    "tan": np.tan,
    "tanh": np.tanh,
}
ALLOWED_CONSTANTS = {"e": np.e, "pi": np.pi}
ALLOWED_NODE_TYPES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
)

EXAMPLES = {
    "DMR-SOLVER original": {
        "variables": "k, y, w, z",
        "x0": "5, 6, 1, 1",
        "tol": "0.001",
        "equations": "\n".join(
            [
                "k * sin(2*w) + y * sin(w) - 2*z",
                "k * sin(w) - z",
                "k**2 * cos(2*w) + k*y*cos(w)",
                "2*k + y - 24",
            ]
        ),
    },
    "Aula 8 - fluxo de potencia 2 barras": {
        "variables": "V2, t2",
        "x0": "1.0, -0.05",
        "tol": "0.000001",
        "equations": "\n".join(
            [
                "-1.0 - (5.0*V2**2 - V2*(5.0*cos(t2) + (-15.0)*sin(t2)))",
                "-0.5 - (-((-15.0) + 0.0)*V2**2 + V2*((-15.0)*cos(t2) - 5.0*sin(t2)))",
            ]
        ),
    },
}


@dataclass(frozen=True)
class CompiledEquation:
    display: str
    code: Any


def main() -> None:
    st.set_page_config(page_title="DMR-SOLVER Python", layout="wide")
    st.title("DMR-SOLVER Python")

    _load_example_if_needed()

    with st.sidebar:
        st.header("Entradas")
        example_name = st.selectbox("Exemplo", list(EXAMPLES))
        if st.button("Carregar exemplo", use_container_width=True):
            _set_example(example_name)
            st.rerun()

        variables_text = st.text_input(
            "Variaveis",
            value=st.session_state["variables"],
            help="Separe por virgula, na mesma ordem de X0.",
        )
        x0_text = st.text_input(
            "X0",
            value=st.session_state["x0"],
            help="Valores iniciais separados por virgula.",
        )
        tol = st.number_input(
            "Tolerancia",
            value=float(st.session_state["tol"]),
            format="%.10f",
            min_value=1e-12,
        )
        max_iter = st.number_input(
            "Maximo de iteracoes",
            value=100,
            min_value=1,
            max_value=10000,
            step=1,
        )
        damping = st.checkbox("Usar damping", value=True)

    equations_text = st.text_area(
        "Equacoes",
        value=st.session_state["equations"],
        height=190,
        help=(
            "Digite uma equacao por linha. Use expressoes que devem ser iguais "
            "a zero, ou escreva no formato lhs = rhs."
        ),
    )

    run = st.button("Executar solver", type="primary")
    if not run:
        _show_input_help()
        return

    try:
        variables = _parse_variables(variables_text)
        x0 = _parse_x0(x0_text, len(variables))
        compiled = _compile_equations(equations_text, variables)

        result = dmr_solver(
            _build_equation_function(compiled, variables),
            x0,
            tol,
            max_iter=int(max_iter),
            damping=damping,
            return_result=True,
        )
    except Exception as exc:
        st.error(f"Nao foi possivel executar o solver: {exc}")
        return

    if len(compiled) != len(variables):
        st.warning(
            "O numero de equacoes e diferente do numero de variaveis. "
            "O solver usou minimos quadrados para o passo de Newton."
        )

    _show_results(result, variables, compiled)


def _load_example_if_needed() -> None:
    if "variables" not in st.session_state:
        _set_example("DMR-SOLVER original")


def _set_example(example_name: str) -> None:
    example = EXAMPLES[example_name]
    st.session_state["variables"] = example["variables"]
    st.session_state["x0"] = example["x0"]
    st.session_state["tol"] = example["tol"]
    st.session_state["equations"] = example["equations"]


def _show_input_help() -> None:
    st.info(
        "Preencha as entradas e clique em **Executar solver**. "
        "Funcoes aceitas: sin, cos, tan, exp, log, sqrt, abs e constantes pi/e."
    )
    st.code(
        "\n".join(
            [
                "k * sin(2*w) + y * sin(w) - 2*z",
                "k * sin(w) - z",
                "k**2 * cos(2*w) + k*y*cos(w)",
                "2*k + y - 24",
            ]
        ),
        language="python",
    )


def _parse_variables(text: str) -> list[str]:
    variables = [item.strip() for item in text.split(",") if item.strip()]
    if not variables:
        raise ValueError("informe pelo menos uma variavel.")
    if len(set(variables)) != len(variables):
        raise ValueError("os nomes das variaveis devem ser unicos.")
    for name in variables:
        if not name.isidentifier():
            raise ValueError(f"nome de variavel invalido: {name!r}.")
        if name in ALLOWED_FUNCTIONS or name in ALLOWED_CONSTANTS:
            raise ValueError(f"{name!r} e reservado para funcao ou constante.")
    return variables


def _parse_x0(text: str, expected_size: int) -> np.ndarray:
    try:
        values = [float(item.strip()) for item in text.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError("X0 deve conter apenas numeros separados por virgula.") from exc

    if len(values) != expected_size:
        raise ValueError(
            f"X0 deve ter {expected_size} valores, mas recebeu {len(values)}."
        )
    return np.array(values, dtype=float)


def _compile_equations(text: str, variables: list[str]) -> list[CompiledEquation]:
    equations = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip().rstrip(";")
        if not line:
            continue
        expression = _normalize_equation(line)
        parsed = ast.parse(expression, mode="eval")
        _validate_expression(parsed, set(variables))
        equations.append(
            CompiledEquation(display=line, code=compile(parsed, "<equation>", "eval"))
        )

    if not equations:
        raise ValueError("informe pelo menos uma equacao.")
    return equations


def _normalize_equation(line: str) -> str:
    if "=" not in line:
        return line
    if "==" in line:
        raise ValueError("use '=' para lhs = rhs, nao '=='.")
    lhs, rhs = line.split("=", maxsplit=1)
    return f"({lhs.strip()}) - ({rhs.strip()})"


def _validate_expression(parsed: ast.AST, variables: set[str]) -> None:
    allowed_names = variables | set(ALLOWED_FUNCTIONS) | set(ALLOWED_CONSTANTS)
    for node in ast.walk(parsed):
        if not isinstance(node, ALLOWED_NODE_TYPES):
            raise ValueError(f"expressao contem sintaxe nao permitida: {type(node).__name__}.")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"nome desconhecido na equacao: {node.id!r}.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
                raise ValueError("apenas chamadas de funcoes matematicas simples sao permitidas.")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("constantes nas equacoes devem ser numericas.")


def _build_equation_function(compiled: list[CompiledEquation], variables: list[str]):
    safe_globals = {"__builtins__": {}}
    shared_locals = {**ALLOWED_FUNCTIONS, **ALLOWED_CONSTANTS}

    def equa(x: np.ndarray) -> np.ndarray:
        local_env = dict(shared_locals)
        local_env.update(dict(zip(variables, x)))
        return np.array(
            [eval(equation.code, safe_globals, local_env) for equation in compiled],
            dtype=float,
        )

    return equa


def _show_results(result, variables: list[str], equations: list[CompiledEquation]) -> None:
    residual = result.history[-1].residual_norm
    status_label = "Convergiu" if result.stat == 1 else "Nao convergiu"

    metric_cols = st.columns(3)
    metric_cols[0].metric("Status", f"{result.stat} - {status_label}")
    metric_cols[1].metric("Iteracoes", result.iter)
    metric_cols[2].metric("Residuo final", f"{residual:.3e}")

    solution_df = pd.DataFrame({"variavel": variables, "valor": result.x})
    equations_df = pd.DataFrame(
        {"equacao": [item.display for item in equations], "f(X)": result.history[-1].f}
    )

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Solucao")
        st.dataframe(solution_df, hide_index=True, use_container_width=True)
    with right:
        st.subheader("Equacoes no ponto final")
        st.dataframe(equations_df, hide_index=True, use_container_width=True)

    history_df = _history_dataframe(result.history, variables)
    st.subheader("Convergencia")
    st.line_chart(history_df.set_index("iteracao")[["residuo_inf"]])

    st.subheader("Variaveis por iteracao")
    st.line_chart(history_df.set_index("iteracao")[variables])

    with st.expander("Historico numerico"):
        st.dataframe(history_df, hide_index=True, use_container_width=True)

    with st.expander("Jacobiano final"):
        jac_df = pd.DataFrame(result.jac, columns=variables)
        st.dataframe(jac_df, hide_index=True, use_container_width=True)


def _history_dataframe(history, variables: list[str]) -> pd.DataFrame:
    rows = []
    for item in history:
        row = {
            "iteracao": item.iteration,
            "residuo_inf": item.residual_norm,
            "passo_inf": item.step_norm,
        }
        row.update(dict(zip(variables, item.x)))
        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    main()
