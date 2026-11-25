"""Fluxogramas em SVG gerados em Python puro (sem Graphviz), usados na tela e no documento para impressão.

Cada passo é um dicionário:
  {"tipo": "ini" | "proc" | "dec" | "fim", "texto": "linha 1\\nlinha 2",
   "sim": "texto do bloco lateral opcional" (só em decisões de opção),
   "volta": índice do passo ao qual a seta volta (laço; numa decisão, é o ramo "sim"),
   "rotulo_volta": texto da seta de retorno, "sai": índice para onde vai o ramo "sim" de uma decisão (saída antecipada)}
Em toda decisão, a seta para baixo é o ramo "não".
"""
from html import escape

LARG, ALT, GAP, X0 = 360, 46, 26, 150
CORES = dict(ini="#1B6B82", fim="#1B6B82", proc="#EEF5F7", dec="#FFF4E0", opc="#F3EEF8")


def _texto(x, y, texto, cor="#22303a", tam=12.5, peso=400):
    linhas = texto.split("\n")
    y0 = y - (len(linhas) - 1) * 8
    return "".join(f'<text x="{x}" y="{y0 + 16 * i + 4}" text-anchor="middle" font-size="{tam}" font-weight="{peso}" '
                   f'fill="{cor}" font-family="Helvetica, Arial, sans-serif">{escape(l)}</text>' for i, l in enumerate(linhas))


def svg(passos, largura_total=820):
    """Desenha os passos em coluna. Laços voltam pela direita; saídas antecipadas descem pela esquerda."""
    cx = X0 + LARG / 2
    alturas = [ALT + 16 * max(0, p["texto"].count("\n")) + (18 if p["tipo"] == "dec" else 0) for p in passos]
    ys, y = [], 20
    for h in alturas:
        ys.append(y)
        y += h + GAP
    altura_total = y + 10
    partes = ['<defs><marker id="s" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
              '<path d="M0,0 L7,3 L0,6 z" fill="#5a6b75"/></marker></defs>']
    seta = 'stroke="#5a6b75" stroke-width="1.4" fill="none" marker-end="url(#s)"'
    voltas = 0
    for i, p in enumerate(passos):
        y, h = ys[i], alturas[i]
        meio = y + h / 2
        tipo = p["tipo"]
        if tipo in ("ini", "fim"):
            partes.append(f'<rect x="{X0}" y="{y}" width="{LARG}" height="{h}" rx="{h / 2}" fill="{CORES[tipo]}"/>')
            partes.append(_texto(cx, meio, p["texto"], "#fff", 12.5, 600))
        elif tipo == "proc":
            partes.append(f'<rect x="{X0}" y="{y}" width="{LARG}" height="{h}" rx="6" fill="{CORES[tipo]}" stroke="#9fc3cf"/>')
            partes.append(_texto(cx, meio, p["texto"]))
        else:  # decisão em losango
            pts = f"{cx},{y} {X0 + LARG + 10},{meio} {cx},{y + h} {X0 - 10},{meio}"
            partes.append(f'<polygon points="{pts}" fill="{CORES["dec"]}" stroke="#d9a84e"/>')
            partes.append(_texto(cx, meio, p["texto"], tam=12))
        # seta para o próximo passo (na decisão, é o ramo "não", salvo se houver bloco opcional "sim")
        # Um processo com "volta" fecha o laço: não desce para o passo seguinte.
        if i + 1 < len(passos) and tipo != "fim" and not (tipo == "proc" and "volta" in p):
            rot = _texto(cx + 16, y + h + 14, "não", "#8a6a2a", 11) if tipo == "dec" else ""
            partes.append(f'<line x1="{cx}" y1="{y + h}" x2="{cx}" y2="{ys[i + 1] - 2}" {seta}/>{rot}')
        if tipo == "dec" and "sim" in p:
            # bloco opcional à direita: entra pela direita e volta ao fluxo principal no passo seguinte
            bx, bw = X0 + LARG + 60, 200
            partes.append(f'<line x1="{X0 + LARG + 10}" y1="{meio}" x2="{bx - 2}" y2="{meio}" {seta}/>')
            partes.append(_texto(X0 + LARG + 34, meio - 6, "sim", "#2f6b3a", 11))
            partes.append(f'<rect x="{bx}" y="{meio - 22}" width="{bw}" height="44" rx="6" fill="{CORES["opc"]}" stroke="#b9a5d3"/>')
            partes.append(_texto(bx + bw / 2, meio, p["sim"], tam=11.5))
            ny = ys[i + 1] + 8
            partes.append(f'<polyline points="{bx + bw / 2},{meio + 22} {bx + bw / 2},{ny} {X0 + LARG + 2},{ny}" {seta}/>')
        if "volta" in p:
            # laço: sai pela direita e retorna ao topo do passo indicado
            voltas += 1
            xr = X0 + LARG + 30 + 26 * voltas
            yo = meio if tipo == "dec" else y + h / 2
            x_ini = X0 + LARG + (10 if tipo == "dec" else 0)
            yd = ys[p["volta"]] + alturas[p["volta"]] / 2
            partes.append(f'<polyline points="{x_ini},{yo} {xr},{yo} {xr},{yd} {X0 + LARG + 2},{yd}" {seta}/>')
            rot = p.get("rotulo_volta", "sim" if tipo == "dec" else "")
            if rot:
                partes.append(_texto(xr + 4 + 3.2 * len(rot), (yo + yd) / 2, rot, "#8a6a2a", 11))
        if "sai" in p and "volta" not in p:
            # saída antecipada pela esquerda até o passo indicado
            xl = X0 - 40
            yd = ys[p["sai"]] + alturas[p["sai"]] / 2
            partes.append(f'<polyline points="{X0 - 10},{meio} {xl},{meio} {xl},{yd} {X0 - 2},{yd}" {seta}/>')
            partes.append(_texto(xl - 16, meio - 6, "sim", "#2f6b3a", 11))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura_total} {altura_total}" '
            f'width="100%" style="max-width:{largura_total}px">' + "".join(partes) + "</svg>")
