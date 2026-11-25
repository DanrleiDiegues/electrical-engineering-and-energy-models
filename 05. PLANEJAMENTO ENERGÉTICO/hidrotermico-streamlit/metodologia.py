"""Texto de metodologia (modelo, métodos e algoritmos) como blocos, desenhados no Streamlit e exportados em HTML.

Seções 1 a 6 reproduzem o documento "Planejamento energético — Métodos e algoritmos" (02/11/2026).
Seções 7 em diante descrevem os métodos acrescentados depois (DESSEM, árvore, PDDD ampliada, PDDE, COBRE e dados PySDDP).
Para editar o texto, altere apenas a lista BLOCOS: a tela e o arquivo para impressão usam a mesma fonte.
"""
import html
import re


# ----------------------------------------------------------------------------- fluxogramas
FLUXO_PL = [
    dict(tipo="ini", texto="Ler trajetória de AFL, carga e dados das usinas"),
    dict(tipo="proc", texto="Criar o modelo SCIP; t ← 1"),
    dict(tipo="proc", texto="Criar v[t], q[t], s[t], g[t], déficit[t]\ncom limites de volume, turbina e geração"),
    dict(tipo="proc", texto="Mês t RECEBE do mês t−1: VI[t] = VF[t−1]\n(variável do mesmo PL; no mês 1, VI = v₀)\nBalanço hídrico, carga D[t] e custo[t]"),
    dict(tipo="dec", texto="t < T ?", volta=2, rotulo_volta="sim: t ← t+1"),
    dict(tipo="proc", texto="Objetivo: minimizar Σ custo[t]\nSCIP.optimize() — uma única chamada"),
    dict(tipo="dec", texto="Status ótimo?", sai=8),
    dict(tipo="fim", texto="Erro: modelo inviável — rever dados"),
    dict(tipo="fim", texto="Trajetória ótima e custo total (conferir balanços)"),
]

FLUXO_PDDD = [
    dict(tipo="ini", texto="Cortes vazios em todos os meses\nZsup ← ∞ ; Zinf ← −∞ ; n ← 1"),
    dict(tipo="proc", texto="FORWARD  t = 1 … T — o mês t RECEBE VIₜ = VFₜ₋₁\n(volume final do mês anterior; VI₁ = v₀)\nmin Cₜ + αₜ com os cortes de t; ENTREGA VFₜ a t+1"),
    dict(tipo="proc", texto="Zsup ← min(Zsup, Σ custos imediatos)\nZinf ← objetivo do mês 1"),
    dict(tipo="dec", texto="Zsup − Zinf ≤ τ\nou n = máximo?", sai=6),
    dict(tipo="proc", texto="BACKWARD  t = T … 2 — o mês t RECEBE v̄ = VFₜ₋₁\n(guardado no forward) e os cortes de t já atualizados"),
    dict(tipo="proc", texto="π ← duais do balanço ; b ← Q − π·v̄\nENTREGA ao mês t−1 o corte αₜ₋₁ ≥ b + π·VFₜ₋₁", volta=1,
         rotulo_volta="n ← n+1"),
    dict(tipo="fim", texto="Trajetória, CMO, CMA, cortes e gap"),
]

FLUXO_DESSEM = [
    dict(tipo="ini", texto="Ler deck DESSEM (termdat, operut, rampas)\ne HIDR.DAT com o PySDDP"),
    dict(tipo="proc", texto="Carga horária da semana → 336 meias horas"),
    dict(tipo="proc", texto="Térmicas: binárias u, y, w por hora\nTon/Toff, trajetórias de partida e parada"),
    dict(tipo="proc", texto="Meia hora k RECEBE de k−1: Vₖ₋₁ (volume),\npₖ₋₁ (potência, para a rampa) e uₕ₋₁ (estado da térmica)\nbalanço hídrico de Batalha e carga"),
    dict(tipo="dec", texto="Hidrelétrica flat?", sim="Qₖ = Q̄ em todas\nas meias horas"),
    dict(tipo="dec", texto="Custo futuro?", sim="α ≥ λ(V alvo − V final)\n(senão α = 0)"),
    dict(tipo="proc", texto="SCIP resolve o MILP\n(branch-and-bound nas binárias)"),
    dict(tipo="proc", texto="Fixar as binárias e resolver o PL\n→ duais: CMO e CMA"),
    dict(tipo="fim", texto="Despacho, partidas, custos, CMO e CMA"),
]

FLUXO_PDDE = [
    dict(tipo="ini", texto="Sortear |Ω| aberturas por mês (anos do histórico)\ncortes[t] vazios ; n ← 1"),
    dict(tipo="proc", texto="FORWARD: S sequências; em cada mês\nsorteia uma abertura (Monte Carlo)"),
    dict(tipo="proc", texto="Mês t RECEBE VIₜ = VFₜ₋₁ da mesma sequência\nresolve Cₜ + βₜ αₜ com os cortes de t\nguarda VIₜ (estado visitado) e ENTREGA VFₜ"),
    dict(tipo="proc", texto="BACKWARD t = T … 2: mês t RECEBE v̄ = VFₜ₋₁\nde cada sequência e resolve TODAS as aberturas"),
    dict(tipo="proc", texto="ENTREGA ao mês t−1 o corte médio (π̄, b̄)\nαₜ₋₁ ≥ b̄ + π̄·VFₜ₋₁ (descarta repetidos)"),
    dict(tipo="proc", texto="Zinf: média do mês 1 nas aberturas\nZsup: média dos forwards ± IC 95%"),
    dict(tipo="dec", texto="Zinf estável\nou n = máximo?", sai=8),
    dict(tipo="proc", texto="n ← n+1", volta=1, rotulo_volta="nova iteração"),
    dict(tipo="fim", texto="Política (cortes) → simulação de cenários"),
]

# Tipos de bloco: ("h1", título, subtítulo) · ("h2", título) · ("p", markdown) · ("eq", latex, número)
#                 ("code", legenda, texto) · ("tabela", cabeçalho, linhas) · ("fluxo", legenda, passos)
#                 ("lacunas", método anterior, [lacunas em vermelho], [ganhos e trade-offs em azul])
BLOCOS = [
    # ------------------------------------------------------------------ 1
    ("h1", "1. O problema que todos resolvem",
     "Objetivo: decidir quando usar a água, acionar as térmicas e, se necessário, admitir déficit."),
    ("h2", "1.1 Sistema físico, dados e decisões"),
    ("p", "Consideramos as UHEs **Batalha e Serra do Facão**, em cascata, e as UTEs BBF Baliza e ERB Candeias. Em cada mês, a água "
          "pode ser armazenada, turbinada ou vertida. A decisão de hoje altera a água disponível amanhã; esse é o acoplamento temporal do problema."),
    ("p", "**Índices:** t = 1, ..., T indica o mês; i, uma UHE; j, uma UTE. M(i) reúne as usinas imediatamente a montante de i. "
          "Batalha não tem montante modelada; Serra recebe a descarga de Batalha."),
    ("tabela", ["Tipo", "Símbolo e significado", "Unidade"], [
        ["Dados", "a: afluência local; D: carga; v₀: volume inicial", "hm³/mês; MWm; hm³"],
        ["Limites", "Vmin, Vmax; q̄: turbinamento máximo; ḡ: térmica máxima", "hm³; hm³/mês; MWm"],
        ["Custos", "c: custo térmico; cD: custo de déficit; h: duração", "R$/MWh; R$/MWh; h"],
        ["Decisões", "v: volume final; q: água turbinada; s: água vertida", "hm³; hm³/mês; hm³/mês"],
        ["Decisões", "g: geração térmica; d: déficit de atendimento", "MW médios (MWm)"]]),
    ("h2", "1.2 Custo imediato e restrições de cada mês"),
    ("p", "O custo imediato soma geração térmica, déficit e uma pequena penalização de vertimento. A água obedece ao balanço hídrico; "
          "geração e déficit devem atender à carga."),
    ("eq", r"C_t = h\Big(\sum_j c_j g_{jt} + c_D d_t\Big) + \varepsilon \sum_i s_{it}", "1"),
    ("eq", r"v_{it} = v_{i,t-1} + a_{it} + \sum_{m \in \mathcal{M}(i)} (q_{mt} + s_{mt}) - q_{it} - s_{it}", "2"),
    ("eq", r"\sum_i \rho_i q_{it} + \sum_j g_{jt} + d_t = D_t", "3"),
    ("eq", r"V_i^{\min} \le v_{it} \le V_i^{\max},\quad 0 \le q_{it} \le \bar q_i,\quad 0 \le g_{jt} \le \bar g_j,\quad s_{it}, d_t \ge 0", "4"),
    ("p", "Nas equações, ρ converte volume turbinado em geração média. A energia hídrica é ρq, e a cascata é contabilizada no mesmo mês. "
          "O limite de potência de Serra também é imposto: ρq ≤ 212,58 MW. O modelo atual não acrescenta um limite nominal separado para Batalha."),
    ("h2", "1.3 Convenções que permanecem nos quatro métodos"),
    ("p", "Usamos **h = 720 h**: uma vazão de 1 m³/s equivale a 2,592 hm³/mês. Assim, afluência e turbinamento entram em volume; "
          "ρ é a produtibilidade em MW/(m³/s) dividida por 2,592. A penalização de vertimento é ε = 0,01 R$/hm³."),
    ("p", "Os modelos são lineares, com produtibilidade constante, sem evaporação nem defluência ambiental mínima. O volume inicial é "
          "conhecido e o **custo após o último mês é zero**. Isso pode favorecer o esvaziamento no fim do horizonte. Chamaremos de "
          "Xₜ(v, a) o conjunto de decisões que satisfaz as restrições acima."),
    # ------------------------------------------------------------------ 2
    ("h1", "2. PDE Didática", "Programação Dinâmica Estocástica: construir uma regra de operação sob incerteza de afluências."),
    ("lacunas", 'Despachos isolados (mês a mês, sem custo futuro)', ['Cada mês é decidido sem olhar o futuro (miopia): a água não tem valor e o modelo esvazia os reservatórios.', 'O déficit e a térmica cara aparecem depois, nos meses secos, sem que a decisão de hoje considere isso.'], ['Dá valor à água com uma função de custo futuro por estado e considera a incerteza (cenários com probabilidade).', 'Trade-off: a grade de volumes introduz erro de discretização e exige |Ω|·T·kᴴ PLs — o tempo cresce exponencialmente com o número de UHEs.']),
    ("h2", "2.1 Ideia e informação disponível"),
    ("p", "A pergunta é: **quanto custa operar daqui até o fim, partindo de cada armazenamento possível?** O método responde do último "
          "mês para o primeiro. Na versão do projeto, cada mês tem dois cenários conjuntos: as duas UHEs com afluência alta ou as duas "
          "com afluência baixa, com probabilidade 0,5 cada. Os cenários de meses diferentes são independentes."),
    ("h2", "2.2 Recursão e representação do custo futuro"),
    ("p", "Fₜ(v) representa o custo esperado desde o mês t, antes de observar sua afluência. Após observar o cenário do mês, resolve-se "
          "um despacho. Por isso, a média dos cenários aparece **fora da minimização**. Ωₜ reúne os cenários e pₜω é sua probabilidade. "
          "A função de custo futuro (FCF) termina em $F_{T+1} = 0$."),
    ("eq", r"F_t(v) = \sum_{\omega \in \Omega_t} p_{t\omega} \min_{x \in X_t(v,\, a_t^{\omega})} \big\{ C_t(x) + \widehat F_{t+1}(v') \big\}", "5"),
    ("p", "O vetor v contém os volumes iniciais; v′ contém os finais. Avalia-se F em uma grade G de estados. Entre seus pontos, o "
          "despacho usa uma combinação convexa dos valores tabelados:"),
    ("eq", r"v' = \sum_r \lambda_r v^r,\quad \alpha = \sum_r \lambda_r F_{t+1}(v^r),\quad \sum_r \lambda_r = 1,\quad \lambda_r \ge 0", "6"),
    ("p", "O SCIP escolhe os pesos λ e minimiza Cₜ + α. Os pesos não são probabilidades. Eles permitem **volume final contínuo** dentro "
          "do domínio da grade e formam um envelope convexo dos valores; a aproximação não é uma interpolação bilinear prescrita."),
    ("h2", "2.3 Fluxo do código"),
    ("code", "Algoritmo 1 - Construção da política e simulação de uma trajetória.",
     "ler dados, probabilidades e k níveis de volume por UHE\nG <- produto cartesiano das grades das UHEs\nF[T+1, todos os estados] <- 0\n"
     "para t = T, ..., 1:\n    para cada volume inicial v em G:\n        para cada cenário conjunto w do mês t:\n"
     "            resolver PL: min C[t] + futuro(v_final)\n            usar AFL[t,w] e a combinação convexa (6)\n"
     "            Q[w] <- objetivo ótimo obtido pelo SCIP\n        F[t,v] <- soma de prob[w] * Q[w]\nv <- volume inicial real\n"
     "para t = 1, ..., T:\n    resolver PL com AFL observada e futuro F[t+1]\n    guardar despacho; v <- volume final obtido"),
    ("h2", "2.4 Resultado, ganho e limite"),
    ("p", "**Entrega:** custos esperados por estado e uma política sensível à água disponível. **Ganho:** considera a incerteza futura ao "
          "despachar hoje. **Limite:** a grade aproxima o valor da água; resolver cada PL até a otimalidade não elimina esse erro."),
    ("p", "Com H UHEs e k níveis por UHE, há $k^H$ estados e cerca de $|\\Omega|Tk^H$ PLs na construção da política. Para duas UHEs e dois "
          "cenários, são 2Tk² PLs. Alterar a trajetória simulada permite avaliar outra realização das afluências, usando a mesma política."),
    # ------------------------------------------------------------------ 3
    ("h1", "3. PL Único", "Programação Linear em um único modelo: otimizar conjuntamente todos os meses conhecidos."),
    ("lacunas", 'PDE Didática', ['O futuro é aproximado por uma grade: o valor da água tem erro de discretização.', 'Milhares de PLs pequenos; o esforço explode com o número de UHEs (maldição da dimensionalidade).'], ['Um único PL com todos os meses: ótimo exato, volumes contínuos, resolvido numa chamada (referência para validar os demais).', 'Trade-off: supõe o futuro conhecido (previsão perfeita), então o custo é otimista e não gera política; o modelo cresce com o horizonte.']),
    ("h2", "3.1 O que muda em relação à PDE Didática"),
    ("p", "Agora, fixamos uma trajetória de afluências e de carga para todo o horizonte. O futuro passa a ser **conhecido**. Em vez de "
          "calcular uma tabela de custo futuro, colocamos as variáveis e restrições de todos os meses no mesmo PL. Não há grade de "
          "armazenamentos nem média entre cenários."),
    ("h2", "3.2 Formulação do horizonte completo"),
    ("p", "O vetor xₜ reúne volumes, turbinamentos, vertimentos, gerações térmicas e déficit. O objetivo é o custo total de operação, "
          "sujeito às restrições (2) a (4) em todos os meses:"),
    ("eq", r"Z_{\mathrm{PL}} = \min_{x_1,\ldots,x_T} \sum_{t=1}^{T} C_t(x_t)", "7"),
    ("p", "O acoplamento entre meses é explícito: a decisão de volume final de um mês é o volume inicial do seguinte. Somente o primeiro "
          "volume inicial é um dado externo."),
    ("eq", r"VI_{i1} = v_{i0},\qquad VI_{it} = VF_{i,t-1}\quad (t = 2,\ldots,T)", "8"),
    ("p", "O futuro já está representado pelas variáveis dos próximos meses. Assim, **não é preciso acrescentar uma variável de custo "
          "futuro α**. A escolha de gerar ou guardar água resulta da minimização conjunta; o solver pode usar mais térmica hoje para "
          "evitar um custo maior depois."),
    ("h2", "3.3 Fluxo do código"),
    ("code", "Algoritmo 2 - Um modelo e uma chamada de otimização.",
     "ler e validar a trajetória de AFL e a carga mensal\nmodelo <- criar modelo SCIP\npara t = 1, ..., T:\n"
     "    criar v[t], q[t], s[t], g[t] e deficit[t]\n    aplicar limites de volume, turbina e geração\n"
     "    VI <- v_inicial, se t = 1; senão v[t-1]\n    adicionar balanço hídrico com VI e AFL[t]\n"
     "    adicionar atendimento à carga D[t]\n    custo[t] <- térmicas + déficit + vertimento\n"
     "definir objetivo: minimizar soma de custo[t]\nSCIP.optimize()\nexigir status ótimo; extrair a trajetória completa\n"
     "conferir balanços e somar os custos imediatos"),
    ("fluxo", "Fluxograma 2 - PL Único.", FLUXO_PL),
    ("p", "**O que cada mês recebe do anterior:** o volume inicial VIₜ é a própria **variável** VFₜ₋₁ do mês anterior, dentro do mesmo PL. Não há forward nem backward: o solver ajusta todos os meses ao mesmo tempo."),
    ("h2", "3.4 Resultado, ganho e limite"),
    ("p", "**Entrega:** a melhor trajetória contínua para as entradas determinísticas. **Ganho:** elimina a discretização dos volumes e "
          "fornece uma referência para validar PDD e PDDD. A solução é ótima para o modelo linear, dentro das tolerâncias numéricas do solver."),
    ("p", "**Dimensão:** com H UHEs e U UTEs, há T(3H + U + 1) variáveis contínuas. No nosso sistema, são 9T variáveis: 27 para três "
          "meses ou 108 para doze meses. Há 3T equações de balanço, além dos limites operativos."),
    ("p", "**Limite:** toda a trajetória futura é tratada como conhecida e o modelo cresce com o horizonte. Mudar a afluência exige "
          "resolver outro PL. Uma solução com previsão perfeita não tem o mesmo significado do custo esperado de uma política estocástica."),
    # ------------------------------------------------------------------ 4
    ("h1", "4. PDD", "Programação Dinâmica Determinística: resolver de trás para frente com volumes em uma grade."),
    ("lacunas", 'PL Único', ['Resolve tudo de uma vez: não mostra a recursão de Bellman nem o custo futuro de cada armazenamento.', 'Para horizontes longos o modelo único fica grande.'], ['Decompõe por mês e explicita Bellman: custo de cada estado e a melhor transição.', 'Trade-off: o VF fica preso à grade, então o custo é ≥ PL (ex.: 198,65 contra 22,14 R$ milhões) e são até T·k²ᴴ PLs — muito mais lento.']),
    ("h2", "4.1 O que muda em relação ao PL Único"),
    ("p", "Mantemos a mesma afluência conhecida, mas dividimos o problema por mês. Para cada volume inicial, testamos possíveis volumes "
          "finais e guardamos a melhor transição. **Nesta implementação, os volumes finais são pontos da grade**; turbinamento, "
          "vertimento, térmicas e déficit continuam contínuos."),
    ("h2", "4.2 Recursão de Bellman na grade"),
    ("p", "C*ₜ(v, v′; aₜ) é o menor custo imediato de um PL de um mês com volumes inicial e final fixados. Uma transição inviável recebe "
          "custo infinito. A recursão soma esse custo ao melhor custo dos meses seguintes:"),
    ("eq", r"J_t^{\mathcal G}(v) = \min_{v' \in \mathcal G} \big\{ C_t^{*}(v, v'; a_t) + J_{t+1}^{\mathcal G}(v') \big\}", "9"),
    ("p", "O custo terminal na grade é zero. Guardar apenas o custo não basta: também se armazena o volume final escolhido, para "
          "reconstruir o despacho do primeiro ao último mês. O volume inicial real é preservado; ele não é arredondado para a grade."),
    ("h2", "4.3 Fluxo do código"),
    ("code", "Algoritmo 3 - Enumerar transições, guardar escolhas e reconstruir.",
     "G <- produto das grades de volume das UHEs\nJ[T+1, todos os estados] <- 0\npara t = T, ..., 1:\n"
     "    para cada volume inicial v em G:\n        J[t,v] <- infinito\n        para cada volume final u em G:\n"
     "            r <- SCIP: min C[t], com VI=v e VF=u\n            se r for inviável: pular esta transição\n"
     "            total <- r.custo_imediato + J[t+1,u]\n            se total < J[t,v]:\n                J[t,v] <- total\n"
     "                escolha[t,v] <- (u, despacho de r)\nno mês 1, repetir a busca usando o VI real\n"
     "seguir as escolhas guardadas até o mês T\nretornar trajetória e soma dos custos imediatos"),
    ("h2", "4.4 Resultado, ganho e limite"),
    ("p", "**Entrega:** a trajetória de menor custo entre as transições viáveis permitidas pela grade. **Ganho:** explicita a lógica de "
          "Bellman e o custo de preservar água para depois. O problema completo é organizado em vários despachos de um mês."),
    ("p", "**Limite:** uma grade grossa pode excluir uma boa decisão contínua e produzir térmicas ou déficit artificiais. Quando há "
          "trajetória viável, seu custo não pode ser menor que o ótimo do PL Único com os mesmos dados. Refinar a grade reduz esse custo "
          "de forma garantida apenas se os pontos antigos forem mantidos."),
    ("p", "**Esforço:** $k^H$ volumes iniciais × $k^H$ volumes finais por mês, ou até $Tk^{2H}$ PLs, além da entrada com VI real. Com duas "
          "UHEs, a ordem é Tk⁴. A enumeração ocorre no código; o solver resolve PLs contínuos, não um problema inteiro misto."),
    # ------------------------------------------------------------------ 5
    ("h1", "5. PDDD", "Programação Dinâmica Dual Determinística: substituir a grade por cortes de custo futuro."),
    ("lacunas", 'PDD', ['Grade de volumes: erro de discretização, déficit artificial e explosão de transições (T·k⁴ com duas UHEs).'], ['Cortes gerados só nos estados visitados: VF contínuo, recupera o ótimo do PL e mede a qualidade pelo gap Zinf–Zsup.', 'Trade-off: exige iterações forward/backward, duais confiáveis e convexidade; cada corte aumenta os PLs de estágio.']),
    ("h2", "5.1 Ideia e modelo de cada estágio"),
    ("p", "A afluência continua conhecida, mas os volumes voltam a ser contínuos. Cada mês resolve **min Cₜ + α**, com as mesmas "
          "restrições físicas e α maior ou igual aos cortes do próximo mês. Esses cortes são planos que aproximam o custo futuro por baixo:"),
    ("eq", r"\widehat F_t(v) = \max\Big\{0,\ \max_{\ell \in \mathcal C_t} \big[b_t^{\ell} + (\pi_t^{\ell})^{\top} v\big]\Big\}", "10"),
    ("p", "O conjunto caligráfico reúne os cortes do mês t. No estado visitado v̄, o PL fornece Qₜ(v̄) e um subgradiente πₜ a partir dos "
          "duais do balanço hídrico. O novo corte é bₜ + πₜᵀv, com:"),
    ("eq", r"\pi_t \in \partial Q_t(\bar v),\qquad b_t = Q_t(\bar v) - \pi_t^{\top} \bar v", "11"),
    ("p", "∂Qₜ é o conjunto de subgradientes, permitindo pontos não diferenciáveis. Qₜ é o valor do PL com os cortes atuais. A validade "
          "do corte depende da linearidade e convexidade. Iniciamos a aproximação em zero, pois os custos desta aplicação são não negativos."),
    ("h2", "5.2 Fluxo do código: ida, limites e volta"),
    ("code", "Algoritmo 4 - Cortes gerados nos estados visitados, sem grade.",
     "cortes de todos os meses <- vazios; futuro terminal <- 0\nZsup <- infinito; Zinf <- -infinito\n"
     "para n = 1, ..., máximo de iterações:\n    v <- VI real; memória <- vazia\n    para t = 1, ..., T:                # FORWARD\n"
     "        r <- SCIP: min C[t] + futuro por cortes[t+1]\n        guardar r e seu VI; v <- r.volume_final\n"
     "    custo <- soma dos custos imediatos da memória\n    se custo < Zsup: Zsup <- custo; melhor <- memória\n"
     "    Zinf <- max(Zinf, objetivo do primeiro mês)\n    se gap atende (12): retornar melhor e convergência\n"
     "    se n é a última iteração: sair sem convergência\n    para t = T, ..., 2:                # BACKWARD\n"
     "        v_barra <- VI guardado do mês t\n        r <- SCIP com v_barra e cortes[t+1] atuais\n"
     "        pi <- duais hídricos convertidos para R$/hm³\n        b <- r.objetivo - produto(pi, v_barra)\n"
     "        adicionar (pi, b) a cortes[t]"),
    ("fluxo", "Fluxograma 4 - PDDD: forward, teste de convergência e backward.", FLUXO_PDDD),
    ("tabela", ["Passo", "O mês t recebe", "De onde vem", "O mês t entrega"], [
        ["Forward", "VIₜ (volume inicial de cada UHE)", "VFₜ₋₁, volume final ótimo do mês anterior (VI₁ = v₀)", "VFₜ ao mês t+1"],
        ["Forward", "Cortes de αₜ", "Backwards das iterações anteriores", "Custo imediato Cₜ (para o Zsup)"],
        ["Backward", "v̄ = VIₜ visitado", "Guardado no forward da mesma iteração", "Corte (π, b) ao mês t−1"],
        ["Backward", "Cortes de αₜ atualizados", "Backward do mês t+1, feito logo antes", "Q(v̄) e π, que formam o corte"]]),
    ("eq", r"Z_{\inf} \le Z^{*} \le Z_{\sup},\qquad Z_{\sup} - Z_{\inf} \le \tau_a + \tau_r \max(1, |Z_{\sup}|)", "12"),
    ("h2", "5.3 Resultado, parâmetros e cuidados de implementação"),
    ("p", "**Entrega:** uma trajetória viável, limites inferior e superior e o histórico do gap. **Ganho:** evita enumerar a grade e, com "
          "convergência, recupera o ótimo do PL determinístico. Mais cortes melhoram a aproximação, mas aumentam os PLs de estágio; não "
          "há garantia de ser mais rápido em todo caso."),
    ("p", "**Parâmetros atuais:** τa = R$ 1; τr = 10⁻⁸; máximo de 100 iterações. Chegar ao máximo não prova convergência. Zsup soma "
          "somente custos imediatos: somar objetivos com α contaria o futuro repetidamente."),
    ("p", "**Duais no SCIP:** o balanço é escrito como Ax = VI + AFL; seu dual é a sensibilidade ao VI, sem impor um sinal. Como o "
          "objetivo é dividido por 10⁶, o dual é multiplicado por 10⁶. O código desativa presolve, heurísticas e propagação para obter "
          "os duais do PL original [2]."),
    # ------------------------------------------------------------------ 6
    ("h1", "6. Como comparar e validar", "A evolução é de representação e estratégia de solução; a formulação física permanece a mesma."),
    ("h2", "6.1 Visão consolidada dos quatro métodos"),
    ("tabela", ["Método", "Informação futura", "Como representa o futuro", "Principal limite"], [
        ["PDE Didática", "Cenários e probabilidades", "Valores na grade + combinação convexa; VF contínuo", "Incerteza simplificada e aproximação pela grade"],
        ["PL Único", "Uma trajetória conhecida", "Todos os meses no mesmo PL; sem FCF explícita", "Exige trajetória futura fixada"],
        ["PDD", "Uma trajetória conhecida", "Tabela de Bellman; VF restrito à grade", "Explosão de transições e erro de discretização"],
        ["PDDD", "Uma trajetória conhecida", "Cortes de suporte; VF contínuo", "Depende de cortes válidos e fechamento do gap"]]),
    ("p", "PDDD é determinística. A extensão estocástica por cortes é a PDDE."),
    ("h2", "6.2 Exemplo registrado no nosso notebook"),
    ("p", "Para três meses (setembro a novembro), carga de 250 MWm e 720 h/mês: afluências locais de Batalha = [20, 25, 30] m³/s e de "
          "Serra = [24, 29, 20] m³/s. Mantidos os demais parâmetros do caso, os resultados salvos são:"),
    ("tabela", ["Método", "Custo total (R$ milhões)", "Déficit (MWh)"], [
        ["PL Único", "22,138228", "0"], ["PDD, k = 5", "198,652726", "43.804,499"], ["PDDD, 3 iterações", "22,138228", "0"]]),
    ("p", "O déficit adicional da PDD decorre da grade nesse caso. A coincidência entre PL e PDDD é uma verificação útil; ainda é preciso "
          "conferir gap e balanços."),
    ("eq", r"Z_{\mathrm{PL}} \le Z_{\mathrm{PDD}},\qquad Z_{\mathrm{PDDD}} \simeq Z_{\mathrm{PL}}\ \ (\text{gap atendido})", "13"),
    ("h2", "6.3 Ordem de conferência ao executar os códigos"),
    ("p", "**1. Igualar as entradas.** Mesmos meses, cargas, afluências locais, volumes iniciais, limites e custo terminal para isolar o "
          "efeito do algoritmo."),
    ("p", "**2. Conferir unidades e viabilidade.** Converter m³/s em hm³/mês; verificar balanços, limites e status do SCIP. Nos "
          "dicionários do código, os custos de térmica e déficit já incluem as 720 horas: não multiplicar duas vezes."),
    ("p", "**3. Ler a medida correta.** O custo realizado soma Cₜ ao longo da trajetória. O déficit em MWh soma h·dₜ. Na PDDD, verificar "
          "Zinf ≤ Zsup e o gap. Na PDE, distinguir custo esperado da política e custo realizado de uma trajetória; não comparar o "
          "esperado diretamente ao PL de um cenário."),
    ("h2", "6.4 Base do material"),
    ("p", "Base: *PLANEJAMENTO ENERGÉTICO - TODOS OS CÓDIGOS.ipynb* e PDE do Streamlit (02/11/2026). O pseudocódigo usa índices de 1 a T; "
          "o Python começa em zero."),
    ("p", "[1] André Marcato. Notebook de referência da disciplina (Colab). [2] PySCIPOpt. Constraints in SCIP - consulta e cuidados com "
          "duais. Equações deste material compostas em Computer Modern."),

    # ================================================================== novos métodos
    ("h1", "7. DESSEM semanal", "Compromisso térmico de uma semana em meias horas: quem liga, quando e quanto gera."),
    ("lacunas", 'Modelos mensais (MW médios)', ['Um mês em MW médios não enxerga o pico horário, partidas, rampas nem tempos mínimos das térmicas.'], ['Compromisso em meias horas com binárias, trajetórias de partida e parada e CMO a cada meia hora.', 'Trade-off: é um MILP (branch-and-bound), bem mais lento; a hidro é simplificada (afluência constante, FCF didática) e segue a carga, a menos que se imponha a opção flat.']),
    ("h2", "7.1 Ideia e escala de tempo"),
    ("p", "O horizonte passa a ser uma semana (168 h), discretizada em 336 meias horas. A binária u indica se a unidade térmica está "
          "ligada; partidas (y) e desligamentos (w) também são binários. O problema é um **PL inteiro misto (MILP)**. A hidro é Batalha, "
          "com afluência constante, e o valor da água no fim da semana vem de uma FCF didática com dois cortes."),
    ("eq", r"u_h - u_{h-1} = y_h - w_h,\quad \sum_{j=h-T_{on}+1}^{h} y_j \le u_h,\quad \sum_{j=h-T_{off}+1}^{h} w_j \le 1-u_h", "14"),
    ("eq", r"P^{\min}(u_h-e_k)+b_k \le p_k \le P^{\max}(u_h-e_k)+b_k,\qquad |p_k-p_{k-1}| \le R\,\Delta t", "15"),
    ("eq", r"V_k = V_{k-1} + 0{,}0018\,(A - Q_k - S_k),\qquad \rho Q_k + \sum_i p_{ik} + D_k = L_{h(k)}", "16"),
    ("eq", r"\min\ \sum_k \Delta t\Big(\sum_i c_i p_{ik} + c_D D_k\Big) + \sum_{i,h} K_i y_{ih} + \alpha,\qquad \alpha \ge \lambda_j\,(V^{alvo}_j - V_{336})", "17"),
    ("p", "As unidades, rampas, tempos mínimos e trajetórias de partida e parada são lidos do deck DESSEM (termdat.dat, operut.dat, "
          "rampas.dat) pelos leitores do PySDDP. Os limites e a produtibilidade de Batalha vêm do HIDR.DAT (seção 12)."),
    ("h2", "7.2 Fluxo do código"),
    ("code", "Algoritmo 6 - Compromisso térmico semanal (DESSEM didático).",
     "ler unidades do deck DESSEM e Batalha do HIDR.DAT (PySDDP)\ncarga[h] da semana; passos k = 1, ..., 336 (meia hora)\n"
     "para cada térmica i e hora h:\n    criar u[i,h], y[i,h], w[i,h] binárias\n    u[h] - u[h-1] = y[h] - w[h]; Ton e Toff (14)\n"
     "para cada meia hora k:\n    potência p[i,k] com trajetórias e rampas (15)\n    balanço hídrico de Batalha e atendimento à carga (16)\n"
     "    se HIDRO_FLAT: Q[k] = Q_barra\nse USAR_FCF: alfa >= cortes no volume final (17); senão alfa = 0\n"
     "objetivo: térmica + déficit + partidas + vertimento + alfa\nSCIP.optimize()  (MILP: branch-and-bound)\n"
     "fixar u, y, w e resolver o PL: CMO = dual da carga; CMA = -dual do balanço\nretornar despacho, custos, CMO e CMA"),
    ("fluxo", "Fluxograma 6 - DESSEM semanal.", FLUXO_DESSEM),
    ("tabela", ["Elo entre períodos", "A meia hora (ou hora) recebe", "Restrição"], [
        ["Volume de Batalha", "Vₖ₋₁, volume final da meia hora anterior", "Balanço hídrico (16)"],
        ["Potência térmica", "pₖ₋₁, potência da meia hora anterior", "Rampas de subida e descida (15)"],
        ["Estado da térmica", "uₕ₋₁ e as partidas/paradas das últimas Ton/Toff horas", "Partida, parada e tempos mínimos (14)"],
        ["Custo futuro", "Só o volume da última meia hora, V₃₃₆", "Cortes da FCF (17)"]]),
    ("h2", "7.3 Por que a hidrelétrica não fica flat?"),
    ("p", "Na operação real, uma UHE tende a ter uma contribuição horária mais estável. No modelo, nada a obriga a isso. Cinco trechos do "
          "código explicam o comportamento (marcados com **[POR QUE NÃO É FLAT]** em *modelo_semana.py* e no Colab):"),
    ("p", "**1. Uma vazão independente por meia hora.** `vazao[k] = m.addVar(lb=0, ub=Qmax)`: cada $Q_k$ só tem limites próprios. Não há "
          "rampa da hidro nem restrição entre $Q_k$ e $Q_{k-1}$."),
    ("p", "**2. O único elo entre meias horas é o volume.** No balanço (16), turbinar 1 m³/s agora ou dez horas depois retira a mesma "
          "água do reservatório: para a física do modelo, o horário é indiferente."),
    ("p", "**3. A carga fecha em cada meia hora.** As térmicas têm rampas, Ton/Toff e trajetórias de partida; a hidro não tem nenhuma "
          "dessas restrições. Ela é a única fonte flexível e passa a absorver a variação da carga."),
    ("p", "**4. O custo futuro só vê o volume final.** O corte $\\alpha \\ge \\lambda(V^{alvo} - V_{336})$ diz **quanta** água guardar, não **quando** "
          "usá-la. Por isso, desligar o custo futuro não deixa a hidro flat: ela continua seguindo a carga."),
    ("p", "**5. A água não tem custo direto.** O objetivo (17) cobra térmica, déficit e partidas. Com o mesmo volume semanal, o solver "
          "coloca a água nas meias horas em que ela evita a térmica mais cara, ou seja, no pico."),
    ("p", "Para forçar o comportamento flat, basta acrescentar uma vazão única para a semana (opção **Hidrelétrica flat**):"),
    ("eq", r"Q_k = \bar Q\quad \forall k,\qquad 0 \le \bar Q \le Q^{\max}", "18"),
    ("tabela", ["Caso (Baliza + Candeias, carga 100%)", "Custo total (R$)", "Geração de Batalha (MW)", "Déficit (MWh)"], [
        ["Hidro livre, com custo futuro", "547.237", "7,2 a 50,7", "0"],
        ["Hidro livre, sem custo futuro", "188.587", "20,5 a 50,7", "0"],
        ["Hidro flat, com custo futuro", "6.190.970", "20,5 constante", "1.224"]]),
    ("p", "Com a hidro flat, ela não pode passar da carga mínima (não há como descartar energia), e as duas térmicas somam só 26,6 MW: "
          "o pico deixa de ser atendido. No sistema real, a variação horária é absorvida por todo o SIN; neste recorte, só existem "
          "duas térmicas. A restrição de flat é, portanto, uma hipótese operativa que precisa vir acompanhada de flexibilidade em outro lugar."),

    ("h1", "8. PL Único em árvore", "O PL Único estendido a uma árvore de cenários: decisões que não antecipam o futuro."),
    ("lacunas", 'PL Único', ['Conhece toda a trajetória futura: as decisões antecipam afluências que ainda não ocorreram e o custo é otimista.'], ['Não antecipação: cada nó decide só com o que já foi observado, e o objetivo é o custo esperado.', 'Trade-off: a árvore tem 2ᵀ − 1 nós; por isso o horizonte fica limitado a cerca de 8 meses.']),
    ("h2", "8.1 Ideia"),
    ("p", "Cada nó n da árvore é um mês com uma afluência observada. Os filhos de n são as aberturas do mês seguinte, com probabilidade "
          "condicional. O volume inicial de um nó é o volume final do nó pai. Como cada nó tem suas próprias variáveis, a decisão de um "
          "mês depende só do que já foi observado (não antecipação)."),
    ("eq", r"\min \sum_{n} p_n\, C_{t(n)}(x_n) + \sum_{n \in \text{folhas}} p_n\, \alpha_n,\qquad VI_n = VF_{\text{pai}(n)},\qquad \alpha_n \ge b^\ell + a^{\ell\top} VF_n", "19"),
    ("p", "As folhas recebem cortes de continuação (um mês extra, resolvido à parte) para não esvaziar os reservatórios no fim. Com dados "
          "do PySDDP, o mês 1 usa a média histórica do mês inicial e cada mês seguinte tem duas aberturas equiprováveis: a média dos anos "
          "secos e a dos úmidos daquele mês do calendário (VAZOES.DAT)."),
    ("p", "**Tamanho:** com 2 aberturas por mês há $2^T - 1$ nós; por isso o horizonte fica limitado a 8 meses."),

    ("h1", "9. PDDD ampliada", "Dados de saída completos, estágios pós-horizonte, FCF em 3D e o Benders aninhado na árvore (degrau para a PDDE)."),
    ("lacunas", 'PDDD original (3 meses, dados fixos)', ['Horizonte curto com dados digitados; custo após o horizonte nulo (esvazia no fim); sem CMO, CMA nem visualização da FCF.'], ['Dados ao vivo do PySDDP, 24 meses, estágios pós-horizonte, CMO/CMA por estágio, FCF em 3D e, numa aba própria, o Benders aninhado na árvore, que iguala o PL em árvore.', 'Trade-off: na árvore percorre todos os nós (mesmo crescimento 2ᵀ) e cada estágio extra aumenta o tempo.']),
    ("h2", "9.1 Dados de saída do despacho"),
    ("p", "Para cada estágio: volume final, turbinado e vertido de cada UHE; geração de cada UTE; déficit; custo imediato e futuro; e os "
          "custos marginais. Os duais vêm do forward (resolvido com duais ativados):"),
    ("eq", r"\mathrm{CMO}_t = \frac{1}{h}\,\frac{\partial Q_t}{\partial D_t}\ \ [\text{R\$/MWh}],\qquad \mathrm{CMA}_{it} = -\frac{\partial Q_t}{\partial VI_{it}}\ \ [\text{R\$/hm}^3]", "20"),
    ("h2", "9.2 Estágios pós-horizonte (o 13º estágio)"),
    ("p", "Como o custo após o último mês é zero, o modelo tende a esvaziar os reservatórios no fim. Acrescentar estágios depois do "
          "horizonte (por exemplo, o 13º mês num estudo de 12) dá valor à água no fim do estudo: os cortes do estágio extra viram a FCF "
          "do último mês. Os resultados dos estágios extras são descartados da apresentação."),
    ("h2", "9.3 Função de custo futuro em 3D"),
    ("p", "Com duas UHEs, a FCF de cada mês é uma superfície $\\alpha(VF_{Bat}, VF_{Serra}) = \\max(0, \\max \\text{ dos cortes})$. O gráfico mostra, mês a mês, "
          "os planos acumulados e o volume final escolhido."),
    ("h2", "9.4 Benders aninhado na árvore (degrau entre a PDDD e a PDDE)"),
    ("p", "A comparação pedida pelo professor é PDDD × PL Único numa **trajetória** (uma afluência por mês), e é a que fica na aba PDDD. "
          "A versão em árvore está na aba **Benders na árvore**: não é a PDDD do trabalho, e sim o mesmo código percorrendo a árvore inteira. "
          "Ela mostra que os cortes funcionam com incerteza, mas também que a árvore cresce como nᵀ, o problema que a PDDE resolve."),
    ("p", "Se cada mês tem várias aberturas, o forward percorre todos os nós e o backward gera, para cada nó pai, um corte médio sobre os "
          "filhos. Com o gap fechado, o custo esperado iguala o do PL Único em árvore (seção 8):"),
    ("eq", r"\alpha_n \ge \sum_{c \in \text{filhos}(n)} \frac{p_c}{p_n}\Big[Q_c(\bar v_n) + \pi_c^{\top}(VF_n - \bar v_n)\Big]", "21"),
    ("tabela", ["Validação", "PL", "PDDD", "Iterações"], [
        ["Trajetória Set–Nov (caso do Colab)", "22.138.227,68", "22.138.227,68", "3"],
        ["Árvore de 3 meses (caso do Colab)", "211.217.723,11", "211.217.723,11", "3"],
        ["Árvore de 6 meses (caso do Colab)", "1.343.129.152,49", "1.343.129.152,49", "4"],
        ["24 meses PySDDP (Set/2015, 100 MWm)", "26.196.906", "26.196.906", "4"]]),

    ("h1", "10. PDDE", "Programação Dinâmica Dual Estocástica: cortes sob incerteza, sem enumerar a árvore."),
    ("lacunas", 'PDDD e PL em árvore', ['A PDDD ignora a incerteza; a árvore completa cresce como |Ω|ᵀ e fica impraticável para horizontes longos.'], ['Independência entre estágios: um conjunto de cortes por mês, forward por Monte Carlo, escala para muitos meses.', 'Trade-off: Zsup é estimativa estatística (intervalo de confiança), a convergência é lenta e depende das aberturas sorteadas; a independência ignora a persistência hidrológica (o NEWAVE usa PAR(p)).']),
    ("h2", "10.1 Ideia"),
    ("p", "A PDDE resolve um problema computacional: a árvore completa cresce como $|\\Omega|^T$. Supondo afluências **independentes entre "
          "estágios**, cada mês tem um conjunto Ωₜ de aberturas, e um único conjunto de cortes por mês vale para qualquer nó daquele mês. "
          "No trabalho: 3 aberturas por mês, sorteadas entre os anos do VAZOES.DAT (1931 em diante) para o mês do calendário, e 10 "
          "sequências forward por iteração. O NEWAVE usa 20 aberturas e 200 sequências. O mesmo código atende três casos: o 1dtoy do COBRE, "
          "**Batalha sozinha** (1 UHE, dados do PySDDP, no formato do 1dtoy: 4 meses, 2 térmicas, 10 aberturas, mesma folga de carga) e a "
          "cascata Batalha + Serra do Facão."),
    ("eq", r"Q_t(v, \omega) = \min_{x \in X_t(v, a_t^{\omega})} \big\{C_t(x) + \beta_t\,\alpha_t\big\},\qquad \alpha_t \ge \bar b^\ell + \bar\pi^{\ell\top} v'", "22"),
    ("eq", r"\bar\pi = \frac{1}{|\Omega_{t+1}|}\sum_{\omega} \pi_{t+1}^{\omega},\qquad \bar b = \frac{1}{|\Omega_{t+1}|}\sum_{\omega} Q_{t+1}(\bar v, \omega) - \bar\pi^{\top}\bar v", "23"),
    ("h2", "10.2 Fluxo do código"),
    ("code", "Algoritmo 5 - Forward amostrado, backward em todas as aberturas.",
     "sortear |Ω| aberturas por mês (anos do histórico)\ncortes[t] <- vazios\npara n = 1, ..., máximo de iterações:\n"
     "    para s = 1, ..., S:                    # FORWARD (S sequências)\n        v <- VI real\n"
     "        para t = 1, ..., T:\n            w <- sorteio entre as aberturas do mês t (Monte Carlo)\n"
     "            r <- SCIP: min C[t] + β·α, com cortes[t]\n            guardar v; custo[s] += C[t]; v <- r.volume_final\n"
     "    para t = T, ..., 2:                    # BACKWARD\n        para cada estado v_barra visitado no mês t:\n"
     "            resolver o mês t para TODAS as aberturas\n            pi, b <- médias dos duais e dos objetivos\n"
     "            adicionar (pi, b) a cortes[t-1]\n    Zinf <- média, nas aberturas do mês 1, do objetivo com VI real\n"
     "    Zsup <- média de custo[s] ± 1,96·desvio/√S\n    parar se Zinf estabilizar ou chegar ao máximo"),
    ("fluxo", "Fluxograma 5 - PDDE.", FLUXO_PDDE),
    ("tabela", ["Passo", "O mês t recebe", "De onde vem", "O mês t entrega"], [
        ["Forward", "VIₜ e uma abertura sorteada", "VFₜ₋₁ da mesma sequência; sorteio entre as |Ω| aberturas", "VFₜ ao mês t+1 e o custo Cₜ"],
        ["Backward", "v̄ = VIₜ de cada sequência", "Forward da mesma iteração", "Corte médio (π̄, b̄) ao mês t−1"],
        ["Backward", "Cortes de αₜ (únicos para o mês)", "Backward do mês t+1", "Média de Q e π nas aberturas"]]),
    ("h2", "10.3 Limites e parada"),
    ("p", "Zinf é determinístico e cresce a cada iteração. Zsup é uma **estimativa** (média dos forwards) com intervalo de confiança; a "
          "convergência estatística ocorre quando Zinf entra no intervalo de Zsup. A literatura traz vários critérios de parada; o do "
          "COBRE/ONS é arbitrário (por exemplo, um número fixo de iterações). Com uma só abertura por mês, a PDDE coincide com a PDDD e "
          "com o PL Único, o que serve de teste do código."),
    ("p", "**Cuidados:** com mudanças climáticas, sortear anos muito antigos pode perder representatividade. Cortes repetidos não "
          "acrescentam informação e degradam o LP; o código os descarta. Implementação: Colab (Trabalho 5) e aba PDDE do Streamlit."),

    ("h1", "11. COBRE / Novo Modelo: o caso 1dtoy", "O exemplo oficial mais simples do modelo aberto do setor elétrico."),
    ("lacunas", 'Nosso PDDE didático', ['Cada LP é reconstruído no SCIP, sem warm start, sem seleção de cortes e sem paralelismo: ~40× mais lento no 1dtoy.'], ['Novo Modelo: HiGHS com reaproveitamento de base, desconto, penalidades, entradas padronizadas e paralelismo.', 'Trade-off: muito mais complexo de entender e configurar; o 1dtoy para por número de iterações, sem prova de convergência.']),
    ("h2", "11.1 O que é"),
    ("p", "O Novo Modelo, que deve substituir NEWAVE e DECOMP, nasceu de um protótipo do ONS (o COBRE) e hoje é desenvolvido em conjunto "
          "por ONS, CCEE e EPE, com código aberto no GitHub (ons-ccee-epe/novomodelo). Ele resolve a PDDE com o solver HiGHS e lê os casos "
          "em JSON e Parquet."),
    ("h2", "11.2 Dados do 1dtoy"),
    ("tabela", ["Elemento", "Dado"], [
        ["Estágios", "jan a abr/2024, 1 patamar: 744, 696, 744 e 720 h"],
        ["UHE1", "0 a 1.000 hm³, VI = 83,222 hm³, turbinamento e defluência ≤ 50 m³/s, ρ = 1 MW/(m³/s), até 50 MW"],
        ["UTE1 e UTE2", "0 a 15 MW cada; 5 e 10 R$/MWh"],
        ["Carga", "75 MW, determinística"],
        ["Afluência", "Normal(40; 10) m³/s, ruído branco; 10 aberturas por estágio"],
        ["Penalidades", "déficit 7.500 R$/MWh; excesso 100 R$/MWh; vertimento 0,01 e turbinamento 0,05 R$/(m³/s·h)"],
        ["Desconto", "12% ao ano: β = 1,12^(−h/8.766)"],
        ["Cálculo da política e simulação", "128 iterações, 1 forward por iteração, semente 42; 100 cenários na simulação"]]),
    ("h2", "11.3 Teste à mão: o toy da documentação"),
    ("p", "A documentação do novomodelo (modelossetoreletrico.org.br, exemplo toy-single-reservoir) resolve à mão duas iterações de um "
          "caso ainda menor: 1 UHE de 0 a 100 com v₀ = 30, térmica sem limite a 50, carga 40, déficit 1000 e aberturas {20, 30, 40}. "
          "A nossa PDDE reproduz o ótimo 17000/27 ≈ 629,63 e o corte do estágio 3 da 1ª iteração (θ ≥ 500 − 100/3·v). Os cortes dos "
          "estágios 1 e 2 podem sair diferentes porque, com o reservatório exatamente vazio, o LP é degenerado: o dual pode ser 50 "
          "(térmica) ou 100/3 (valor da água). Ambos são subgradientes válidos; muda o caminho do Zinf, não o ótimo."),
    ("h2", "11.4 Resultado da comparação"),
    ("p", "Objetivo: avaliar como o COBRE se comporta diante de uma implementação independente (a nossa PDDE), com os mesmos dados. "
          "Usamos as **mesmas aberturas** do COBRE no cálculo da política e o **mesmo conjunto de teste** (2.000 cenários fora da amostra, semente 777) "
          "na simulação, o que permite uma comparação pareada. O ótimo exato vem do equivalente determinístico da árvore de aberturas."),
    ("tabela", ["Indicador", "Exemplo oficial (10 ab., 1 fw, 128 it.)", "Trabalho de PDDE (3 ab., 10 fw, 50 it.)"], [
        ["Ótimo exato da árvore (R$)", "20.617.794,45", "21.888.772,13"],
        ["Zinf COBRE (R$)", "20.616.141,78", "21.888.772,13"],
        ["Zinf nossa PDDE (R$)", "20.615.372,23", "21.888.772,13"],
        ["Custo no teste, COBRE (R$)", "20.806.731", "21.411.005"],
        ["Custo no teste, nossa PDDE (R$)", "20.806.735", "21.411.005"],
        ["Diferença pareada (R$)", "+3,79 ± 3,03", "−0,003 ± 0,07"],
        ["Tempo para calcular a política", "0,57 s (Rust/HiGHS) × 22 s (Python/SCIP)", "0,72 s × 24 s"]]),
    ("p", "As duas implementações chegam à mesma política: os volumes, o déficit e o custo por estágio coincidem; só o CMO e o valor da "
          "água diferem um pouco em cenários degenerados (há mais de um dual ótimo). O Zinf não coincide iteração a iteração porque os "
          "forwards sorteiam cenários diferentes. A diferença relevante é de **configuração**: com 3 aberturas a política custa cerca de "
          "R$ 600 mil a mais no teste (IC95% ± R$ 150 mil, comparação cenário a cenário), e o ótimo da árvore de 3 pontos é R$ 1,27 mi maior "
          "que o da árvore de 10, porque com 3 pontos o mês seco tem probabilidade 1/3. O Zinf de uma árvore pequena, portanto, não deve "
          "ser lido como limite inferior do problema real. O COBRE resolve o mesmo número de PLs dezenas de vezes mais rápido "
          "(Rust, HiGHS com warm start)."),

    ("h1", "12. Dados ao vivo com o PySDDP", "Os modelos leem os arquivos oficiais em vez de números digitados."),
    ("p", "**HIDR.DAT** (cadastro): volumes mínimo e máximo, máquinas, vazão e potência efetivas, produtibilidade específica e perdas. "
          "Engolimento = Σ máquinas × vazão efetiva; potência = Σ máquinas × potência efetiva."),
    ("eq", r"\rho_i = \text{prod\_esp}_i \times \big(H^{\text{nom}}_i - H^{\text{perda}}_i\big)\quad [\text{MW}/(\text{m}^3/\text{s})]", "24"),
    ("p", "**VAZOES.DAT** (histórico mensal desde 1931): vazões naturais. Em Serra usa-se a incremental (natural de Serra − natural de "
          "Batalha), porque o balanço já soma a descarga de Batalha. **Deck DESSEM** (termdat.dat, operut.dat, rampas.dat): Pmax, CVU, "
          "rampas e tempos mínimos das térmicas."),
    ("tabela", ["Usina", "Volume (hm³)", "Engolimento (m³/s)", "Potência (MW)", "ρ (MW/(m³/s))"], [
        ["Batalha", "430,05 a 1.781,61", "154", "52,50", "0,3294"],
        ["Serra do Facão", "1.752 a 5.199", "324", "212,58", "0,6410"]]),
    ("p", "Usam dados ao vivo: DESSEM semanal (térmicas e Batalha), PL Único em árvore (opção padrão), PDDD e PDDE. A PDE Didática e o "
          "PL Único mantêm o caso fixo do Colab para reproduzir os resultados registrados."),

    ("h1", "13. Visão consolidada ampliada", "Do despacho semanal à política estocástica."),
    ("tabela", ["Método", "Informação futura", "Como representa o futuro", "Onde está"], [
        ["DESSEM semanal", "Semana conhecida", "FCF didática no volume final", "Colab e Streamlit"],
        ["PL Único em árvore", "Árvore completa", "Um nó por cenário; cortes nas folhas", "Colab e Streamlit"],
        ["PDDD (trajetória ou árvore)", "Trajetória ou árvore", "Cortes por nó", "Colab e Streamlit"],
        ["PDDE", "Aberturas independentes", "Cortes por mês, médios nas aberturas", "Colab"],
        ["1dtoy (COBRE)", "Aberturas independentes", "Cortes por estágio, com desconto", "Colab"]]),
]


# ----------------------------------------------------------------------------- Streamlit
def mostrar_lacunas(st, bloco):
    """Vermelho: o que faltava no método anterior. Azul: o que o novo método resolve e o custo disso."""
    _, anterior, red, blue = bloco
    esc = lambda t: t.replace("R$", "R\\$")
    with st.container(border=True):
        st.markdown(f":red[**Lacuna do método anterior ({anterior})**]\n" + "\n".join(f"- :red[{esc(x)}]" for x in red))
        st.markdown(":blue[**O que este método resolve e seus trade-offs**]\n" + "\n".join(f"- :blue[{esc(x)}]" for x in blue))


def desenhar(st):
    """Desenha todos os blocos com componentes do Streamlit."""
    for bloco in BLOCOS:
        tipo = bloco[0]
        if tipo == "h1":
            st.header(bloco[1])
            st.caption(bloco[2])
        elif tipo == "h2":
            st.subheader(bloco[1])
        elif tipo == "p":
            # "R$" não pode abrir uma fórmula: escapa-se o cifrão de moeda; $...$ continua sendo matemática.
            st.markdown(bloco[1].replace("R$", "R\\$"))
        elif tipo == "eq":
            st.latex(bloco[1] + r"\tag{" + bloco[2] + "}")
        elif tipo == "code":
            st.caption(bloco[1])
            st.code(bloco[2], language=None, line_numbers=True)
        elif tipo == "tabela":
            import pandas as pd
            st.dataframe(pd.DataFrame(bloco[2], columns=bloco[1]), hide_index=True)
        elif tipo == "fluxo":
            from fluxograma import svg
            st.caption(bloco[1])
            st.image(svg(bloco[2]))
        elif tipo == "lacunas":
            mostrar_lacunas(st, bloco)


# ----------------------------------------------------------------------------- HTML para imprimir
def _inline(texto):
    """Markdown mínimo → HTML (negrito, itálico, código). As fórmulas ficam para o KaTeX."""
    t = html.escape(texto.replace("R$", "R\x00"), quote=False)
    t = re.sub(r"\$(.+?)\$", r"\\(\1\\)", t).replace("\x00", "$")
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def documento_html(titulo="Planejamento energético — Modelo, métodos e algoritmos"):
    """Documento completo e autônomo (KaTeX via CDN), pronto para imprimir ou salvar em PDF pelo navegador."""
    partes = []
    for bloco in BLOCOS:
        tipo = bloco[0]
        if tipo == "h1":
            partes.append(f'<h1>{html.escape(bloco[1])}</h1><p class="sub">{html.escape(bloco[2])}</p>')
        elif tipo == "h2":
            partes.append(f"<h2>{html.escape(bloco[1])}</h2>")
        elif tipo == "p":
            partes.append(f"<p>{_inline(bloco[1])}</p>")
        elif tipo == "eq":
            partes.append(f'<div class="eq"><span class="math">$${html.escape(bloco[1])}$$</span><span class="n">({bloco[2]})</span></div>')
        elif tipo == "code":
            linhas = "".join(f"<tr><td class='ln'>{i:02d}</td><td>{html.escape(l)}</td></tr>"
                             for i, l in enumerate(bloco[2].split("\n"), 1))
            partes.append(f'<p class="cap">{html.escape(bloco[1])}</p><table class="algo">{linhas}</table>')
        elif tipo == "lacunas":
            red = "".join(f"<li>{_inline(x)}</li>" for x in bloco[2])
            blue = "".join(f"<li>{_inline(x)}</li>" for x in bloco[3])
            partes.append(f'<div class="lac"><p class="r"><strong>Lacuna do método anterior ({html.escape(bloco[1])})</strong></p>'
                          f'<ul class="r">{red}</ul><p class="b"><strong>O que este método resolve e seus trade-offs</strong></p>'
                          f'<ul class="b">{blue}</ul></div>')
        elif tipo == "fluxo":
            from fluxograma import svg
            partes.append(f'<p class="cap">{html.escape(bloco[1])}</p><div class="fluxo">{svg(bloco[2])}</div>')
        elif tipo == "tabela":
            cab = "".join(f"<th>{html.escape(c)}</th>" for c in bloco[1])
            corpo = "".join("<tr>" + "".join(f"<td>{_inline(str(c))}</td>" for c in linha) + "</tr>" for linha in bloco[2])
            partes.append(f"<table class='dados'><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody></table>")
    corpo = "\n".join(partes)
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><title>{html.escape(titulo)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
 onload="renderMathInElement(document.body,{{delimiters:[{{left:'$$',right:'$$',display:true}},{{left:'\\\\(',right:'\\\\)',display:false}}]}});document.body.dataset.pronto=1"></script>
<style>
@page{{size:A4;margin:16mm 16mm 18mm}}
body{{font-family:'Source Serif 4','Georgia',serif;color:#22303a;max-width:820px;margin:28px auto;padding:0 18px;line-height:1.5;font-size:11pt}}
header{{display:flex;justify-content:space-between;font:9pt sans-serif;color:#6a7a85;border-bottom:1px solid #d9e2e6;padding-bottom:6px}}
h1{{font-weight:400;color:#1c4a5a;font-size:22pt;margin:34px 0 2px;break-before:page}} h1:first-of-type{{break-before:auto}}
.sub{{color:#6a7a85;margin-top:0}} h2{{font-weight:400;color:#1f6f86;font-size:14pt;margin:22px 0 6px}}
.eq{{display:flex;align-items:center;justify-content:center;margin:10px 0;break-inside:avoid}} .eq .math{{flex:1;text-align:center}}
.eq .n{{color:#6a7a85;font-size:10pt}} table{{border-collapse:collapse;width:100%;margin:10px 0;break-inside:avoid}}
.dados th{{background:#eef3f5;text-align:left;font:600 9.5pt sans-serif;padding:6px 8px}}
.dados td{{border-bottom:1px solid #e3eaed;padding:6px 8px;font-size:10pt;vertical-align:top}}
.algo{{font:9.5pt 'JetBrains Mono',Consolas,monospace;background:#f7fafb;border-left:3px solid #9fc3cf}}
.algo td{{padding:1px 8px;white-space:pre}} .algo .ln{{color:#9aa8b0;width:24px;text-align:right}}
.lac{{border:1px solid #e3eaed;border-radius:6px;padding:4px 14px;margin:8px 0 14px;break-inside:avoid}} .r{{color:#B3261E}} .b{{color:#1F5FA8}} .lac ul{{margin:2px 0 8px}} .fluxo{{text-align:center;break-inside:avoid;margin:6px 0 14px}} .cap{{font:9pt sans-serif;color:#6a7a85;margin-bottom:2px}} code{{background:#eef3f5;padding:0 3px;border-radius:3px;font-size:9.5pt}}
@media print{{body{{margin:0;max-width:none}} .noprint{{display:none}}}}
</style></head><body>
<header><span>UFJF | PLANEJAMENTO ENERGÉTICO</span><span>MODELO, MÉTODOS E ALGORITMOS</span></header>
{corpo}
</body></html>"""


def mostrar_algoritmo(st, secao):
    """Pseudocódigo e fluxograma de uma seção (ex.: "3." para o PL Único), num expansor da aba do método."""
    from fluxograma import svg
    inicio = next(i for i, b in enumerate(BLOCOS) if b[0] == "h1" and b[1].startswith(secao))
    fim = next((i for i, b in enumerate(BLOCOS[inicio + 1:], inicio + 1) if b[0] == "h1"), len(BLOCOS))
    blocos = [b for b in BLOCOS[inicio:fim] if b[0] in ("code", "fluxo")]
    with st.expander("Como o algoritmo funciona: pseudocódigo e fluxograma"):
        for b in BLOCOS[inicio:fim]:
            if b[0] == "lacunas":
                mostrar_lacunas(st, b)
        colunas = st.columns(2)
        for b in blocos:
            alvo = colunas[0] if b[0] == "code" else colunas[1]
            alvo.caption(b[1])
            if b[0] == "code":
                alvo.code(b[2], language=None, line_numbers=True)
            else:
                alvo.image(svg(b[2]))
        for b in BLOCOS[inicio:fim]:
            if b[0] == "tabela" and b[1][0] in ("Passo", "Elo entre períodos"):
                import pandas as pd
                st.caption("O que cada estágio recebe do anterior e o que entrega")
                st.dataframe(pd.DataFrame(b[2], columns=b[1]), hide_index=True)
        st.caption("Texto completo na aba Metodologia.")
