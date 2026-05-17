# Aula 8 - exemplo para carregar no Streamlit

Este exemplo usa as equacoes de fluxo de potencia da Aula 8 em um sistema
didatico de 2 barras:

- barra 1: slack, `V1 = 1.0 pu` e `theta1 = 0`;
- barra 2: barra PQ, com variaveis `V2` e `t2`;
- linha 1-2: `z = 0.02 + j0.06 pu`;
- admitancia serie: `y = 1/z = 5 - j15 pu`;
- carga na barra 2: `Pload = 1.0 pu` e `Qload = 0.5 pu`;
- shunt da linha: `bsh = 0.0`.

## Variaveis

```text
V2, t2
```

## X0

```text
1.0, -0.05
```

## Tolerancia

```text
0.000001
```

## Equacoes

```python
-1.0 - (5.0*V2**2 - V2*(5.0*cos(t2) + (-15.0)*sin(t2)))
-0.5 - (-((-15.0) + 0.0)*V2**2 + V2*((-15.0)*cos(t2) - 5.0*sin(t2)))
```

## Resultado esperado

Com o solver atual, o resultado converge para aproximadamente:

```text
V2 = 0.94573237 pu
t2 = -0.05289374 rad
```

As equacoes representam:

```text
Pspec - Pcalc = 0
Qspec - Qcalc = 0
```

Como a barra 2 e uma carga PQ sem geracao local:

```text
Pspec = -Pload
Qspec = -Qload
```
