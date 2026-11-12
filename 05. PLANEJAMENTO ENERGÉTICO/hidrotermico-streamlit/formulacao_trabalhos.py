import streamlit as st


def formulacao_semana():
    with st.expander("Formulação matemática e metodologia · DESSEM semanal"):
        st.markdown("**1. Decisões.** O SCIP resolve um modelo linear inteiro misto. Para cada térmica $i$ e hora $h$, as variáveis binárias $u$, $y$ e $w$ indicam unidade ligada, início de partida e desligamento. A potência $P_{ik}$ é contínua em cada meia hora $k$, de duração $\\Delta=0{,}5$ h.")
        st.latex(r"\min\ \sum_k\left[\Delta\left(\sum_i c_iP_{ik}+c_D D_k\right)+0{,}01\,\kappa S_k\right]+\sum_{i,h}K_i y_{ih}+\alpha")
        st.markdown("**Objetivo em R$.** $c_i$ é o custo variável da térmica e $c_D$ a penalidade do déficit, ambos em R$/MWh. $D_k$ é a carga não atendida em MW, $K_i$ o custo de partida em R$ e $S_k$ a vazão vertida em m³/s. O coeficiente 0,01 penaliza cada hm³ vertido. O termo $\\alpha$ representa o custo futuro ao fim da semana.")
        st.markdown("**2. Compromisso e permanência.** Uma partida muda o estado para ligado. Um desligamento muda o estado para desligado. As somas contam os eventos recentes que ainda obrigam a unidade a permanecer nesse estado.")
        st.latex(r"u_{ih}-u_{i,h-1}=y_{ih}-w_{ih},\quad \sum_{j=h-T_i^{on}+1}^{h}y_{ij}\le u_{ih},\quad \sum_{j=h-T_i^{off}+1}^{h}w_{ij}\le 1-u_{ih}")
        st.markdown("Os somatórios começam, no mínimo, na primeira hora do estudo. O modelo lê o estado inicial, a potência inicial e o tempo já cumprido nesse estado. Impede novos eventos cujas obrigações ultrapassariam a última hora.")
        st.markdown("**3. Potência e rampas.** A curva cadastrada de partida começa na hora de acionamento. A de parada termina na hora do desligamento. Em cada meia hora de trajetória, o cadastro fixa a potência. Fora das trajetórias, uma unidade ligada opera entre seus limites.")
        st.latex(r"P_i^{min}\le P_{ik}\le P_i^{max},\qquad -R_i^\downarrow\Delta\le P_{ik}-P_{i,k-1}\le R_i^\uparrow\Delta")
        st.markdown("A desigualdade de variação vale entre dois intervalos consecutivos em regime normal. As rampas $R$ estão em MW/h. A primeira potência livre após a partida fica limitada ao mínimo mais uma rampa de meia hora. Antes da curva de parada, a potência deve chegar ao mínimo.")
        st.markdown("**4. Água, carga e custo terminal.** A hidrelétrica Batalha atende à carga junto com as térmicas.")
        st.latex(r"V_k=V_{k-1}+\kappa(A-Q_k-S_k),\qquad \rho Q_k+\sum_i P_{ik}+D_k=L_{h(k)}")
        st.markdown("O volume $V$ está em hm³. A afluência $A$, a vazão turbinada $Q$ e a vertida $S$ estão em m³/s. O fator $\\kappa=0{,}0018$ converte uma meia hora de vazão em hm³. A produtividade $\\rho$ converte vazão turbinada em MW. A carga horária $L$ vale para as duas meias horas. O reservatório e o turbinamento respeitam os limites físicos.")
        st.latex(r"\alpha=\max\{0,\ \max_j[\lambda_j(V_j^{alvo}-V_{final})]\}")
        st.markdown("Cada corte $j$ associa um volume-alvo a uma penalidade marginal $\\lambda_j$ em R$/hm³. Desmarcar **Aplicar custo futuro** fixa $\\alpha=0$.")


def formulacao_arvore():
    with st.expander("Formulação matemática e metodologia · PL em árvore"):
        st.markdown("**1. Informação disponível.** Cada nó $n$ corresponde a um histórico observado de afluências. A raiz tem probabilidade 1. A probabilidade $p_n$ é a do pai multiplicada pela probabilidade condicional do ramo. Uma única decisão por nó garante que trajetórias com o mesmo histórico compartilhem o despacho até a bifurcação.")
        st.latex(r"\min\ \sum_{n}p_n C_n+\sum_{n\in F}p_n\alpha_n,\qquad C_n=H\left(\sum_j c_j G_{jn}+c_D D_n\right)+0{,}01\sum_i S_{in}")
        st.markdown("**2. Custo esperado.** $F$ é o conjunto de folhas. $C_n$ soma geração térmica $G$ ao custo variável $c_j$, déficit $D$ à penalidade $c_D$ e vertimento $S$. No caso das usinas, $H=720$ h converte MW médios em MWh e os custos são em reais. O quadro usa uma etapa de duração unitária e custos didáticos.")
        st.latex(r"V_{in}=V_{i,pai(n)}+A_{in}+\sum_{m\in M(i)}(Q_{mn}+S_{mn})-Q_{in}-S_{in}")
        st.markdown("**3. Balanço hídrico.** $V_{in}$ é o volume final da UHE $i$. Na raiz entra o volume inicial. $A$ é a afluência local, $Q$ o volume turbinado e $S$ o volume vertido, em hm³ por estágio. $M(i)$ reúne as usinas imediatamente a montante. No caso em cascata, Serra do Facão recebe o turbinamento e o vertimento de Batalha.")
        st.latex(r"\sum_i \rho_i Q_{in}+\sum_j G_{jn}+D_n=L_n,\qquad V_i^{min}\le V_{in}\le V_i^{max},\quad 0\le Q_{in}\le Q_i^{max},\quad 0\le G_{jn}\le G_j^{max}")
        st.markdown("**4. Atendimento à carga.** A produtividade $\\rho_i$ converte volume turbinado no estágio em potência média. $L_n$ é a demanda. Geração, déficit e vertimento são não negativos. As térmicas têm despacho contínuo até a potência máxima.")
        st.latex(r"\alpha_n\ge 0,\qquad \alpha_n\ge b_\ell+\sum_i a_{\ell i}V_{in}\quad(n\in F)")
        st.markdown("**5. Custo após o horizonte.** Em cada folha, os cortes estimam quanto custará continuar a operação com o volume restante. O intercepto $b_\\ell$ e os coeficientes $a_{\\ell i}$ vêm do custo ótimo e dos duais dos balanços hídricos de um estágio auxiliar. O SCIP minimiza todas as decisões em um único PL e aplica os cortes somente no último mês escolhido.")

