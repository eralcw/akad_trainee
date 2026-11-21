# Roteiro de apresentação — Case Akad 2027

Este guia serve para a conversa de até 20 minutos. A ideia é que cada gráfico tenha uma frase de leitura, não uma lista de números. O material gráfico é o app Streamlit; o EDA em `analise/eda.html` aprofunda o tratamento.

---

## 0. A história da Akad (diga isso antes da Q10)

A Akad não tem seis anos de marca. Ela tem uma história em duas fases:

- **2012–2021: Argo no Brasil.** A operação começou em 2012, cresceu e aprendeu muito.
- **2022 em diante: Akad Seguros.** Em 2022 a empresa renasce como Akad, uma seguradora moderna e pronta para inovar.

A série do case vai de 2020 a 2025, então ela mistura os dois momentos. Para tamanho de mercado e tendência, os seis anos são úteis. Para julgar a Akad atual, a leitura principal é **2022–2025**. O código SUSEP da entidade continua o mesmo (02798), por isso o dado não se parte; o que muda é a marca e a estratégia.

Frase para usar:

> “A série de 2020–2025 tem dois capítulos. Até 2021, a operação era Argo. Em 2022, a Akad nasce como marca e estratégia. Por isso, para avaliar a Akad atual, eu olho 2022–2025; 2020–2021 serve de base histórica.”

Números da fase Akad (2022–2025), que ajudam a sustentar a recomendação:

| LOB | Share 2022 → 2025 | Margem Akad 2022–25 | Margem mercado 2022–25 | Sinistralidade Akad | Sinistralidade mercado |
|---|---:|---:|---:|---:|---:|
| E&O | 15,2% → 18,4% | 41,2% | 30,2% | 36,1% | 37,4% |
| Transportes | 7,3% → 10,2% | 3,5% | 14,6% | 63,0% | 52,7% |
| RCG | 0,8% → 2,2% | 38,2% | 24,0% | 38,2% | 54,3% |
| Garantia | 0,7% → 0,9% | 16,9% | 26,5% | 23,9% | 21,9% |
| Empresarial | 0,0% → 0,9% | 7,0% | 21,9% | 49,1% | 45,8% |

A leitura em uma frase: a Akad nasceu forte em E&O, cresceu em Transportes mas com margem baixa, e tem em RCG uma opção pequena e rentável.

---

## 1. Mercado de seguros 101

### O que é o SES
O SES é o Sistema de Estatísticas da SUSEP. Ele publica, por seguradora, ramo e período, os números de prêmios, sinistros e despesas. A consulta é um formulário antigo, uma combinação de ramo e período por vez. O case pede 14 códigos de ramo em 6 anos: 84 consultas. A automação abre o formulário, preenche, exporta o `.xls` e valida os totais.

### LOB e ramo
LOB é uma linha de negócio: um grupo de ramos parecidos. O case agrupa 14 códigos em 5 LOBs: RCG (0351), E&O (0378), Empresarial (0118), Transportes (9 códigos, mas o 0645 não tem movimento) e Garantia (0775 e 0776). O ramo é o código técnico; a LOB é a leitura de negócio.

### Prêmio ganho
É a parte do prêmio emitido que corresponde ao risco já decorrido. Não é caixa recebido; é a receita reconhecida no período. É o denominador natural de sinistralidade e margem.

### Sinistro ocorrido
É o sinistro do período, incluindo a variação de reservas. Pode ser negativo quando a seguradora reverte reservas de anos anteriores. Negativo não é erro; é ajuste. Por isso a análise mantém os negativos e agrega antes de dividir.

### Sinistralidade
É sinistro ocorrido dividido por prêmio ganho. Mostra quanto do prêmio foi consumido por sinistro. A regra de ouro: **soma dos sinistros ÷ soma dos prêmios**, nunca média das sinistralidades anuais. Média de razões dá peso igual a anos pequenos e distorce.

### Despesa e receita com resseguro
A despesa é o prêmio pago ao ressegurador para transferir risco. A receita é o que a seguradora recupera do ressegurador. As duas entram no resultado técnico; não são “detalhe”.

### Despesa comercial
É o custo de aquisição, principalmente comissão de corretagem. É o canal de venda aparecendo no número. Uma seguradora pode ter boa sinistralidade e margem ruim se a despesa comercial for alta.

### Resultado técnico (o que o case chama de lucro)
Fórmula acordada:

> prêmio ganho + receita com resseguro − sinistro ocorrido − despesa com resseguro − despesa comercial

Não é lucro contábil: fora da conta ficam despesa administrativa, imposto e resultado financeiro. Por isso o material chama de **resultado técnico**. A margem é esse resultado dividido pelo prêmio ganho.

### Seguradora ativa
É a que tem prêmio ganho maior que zero no ano. O SES lista empresas registradas mesmo sem operação; se você contar todas as linhas, conta registro, não atividade. No RCG, por exemplo, são 54 ativas em 78 cadastradas no período.

### Concentração
Top 5 é a soma do share das cinco maiores. “Até 80%” é quantas seguradoras explicam 80% do prêmio. HHI é a soma dos quadrados dos shares; quanto maior, mais concentrado. Nenhuma LOB do case é altamente concentrada, mas Transportes e Empresarial são as mais concentradas do grupo.

### Valores nominais
Os valores não estão corrigidos pela inflação. Crescimento de prêmio inclui inflação e crescimento real. Para o case, o número nominal é o que a SUSEP publica; se perguntarem, diga que não deflacionou.

### Por que recalcular a sinistralidade
A coluna Sinistralidade da SUSEP vem arredondada e não é aditiva entre ramos ou anos. A análise usa a coluna apenas como conferência e recalcula a razão a partir dos valores.

---

## 2. Como ler cada gráfico

### Painel → Visão geral

**Faixa de indicadores (ledger).** Mostra prêmio ganho, sinistralidade agregada, resultado técnico e margem do período filtrado. É o “tamanho da história”: R$ 83,1 bi de prêmio, 43,2% de sinistralidade, R$ 17,2 bi de resultado técnico e margem de 20,7%.

**Linha de prêmio por LOB e ano.** Cada linha é uma LOB; o eixo Y é R$ bilhões; o X é o ano. Leia assim: Transportes é a maior em todos os anos; Empresarial e Garantia vêm depois; E&O é a menor, mas a que mais cresce em porcentagem. Não há queda anual visível no agregado.

**Mapa de calor da sinistralidade.** Linhas = LOBs; colunas = anos; cor mais quente = sinistralidade maior. Leia assim: Garantia fica na faixa baixa; RCG tem o ponto vermelho de 2023 (92,4%); Empresarial esfria de 62,5% para 40,4%; Transportes fica estável perto de 50–55%; E&O cai para 27,6% em 2024 e volta a 35,2% em 2025.

**O que dizer:** “O mercado cresce em todas as linhas. A diferença está na qualidade do crescimento: Garantia cresce com sinistralidade baixa; RCG cresce com muita volatilidade; Transportes cresce com sinistralidade alta e estável.”

---

### Painel → Mercado

**Q1 — barras de prêmio total por LOB.** Eixo X = prêmio acumulado 2020–2025, em R$ bilhões. Ordem: Transportes 29,3; Empresarial 20,9; Garantia 20,0; RCG 9,1; E&O 3,8. Leia a barra, não a ordem alfabética. **Frase:** “Transportes é a maior LOB, com 35% do prêmio das cinco linhas; E&O é a menor, com 4,5%.”

**Q7 — halteres de crescimento.** Cada LOB tem uma linha ligando o prêmio de 2020 (ponto esquerdo) ao de 2025 (ponto direito); o texto na ponta direita é a variação percentual. Leia os dois eixos da história: E&O cresce 108,7% em porcentagem, mas adiciona R$ 0,46 bi; Transportes cresce 74,4% e adiciona R$ 2,48 bi. **Frase:** “Porcentagem e valor absoluto contam histórias diferentes. E&O é a maior taxa; Transportes é a maior adição de prêmio.”

**Q2 — barras agrupadas de seguradoras ativas.** Duas barras por LOB: 2020 e 2025, contando só prêmio > 0. Leia: Empresarial 47 → 51; RCG 45 → 47; Garantia 38 → 46; E&O 27 → 31; Transportes 25 → 25. **Cuidado:** a contagem por presença de linha seria outra (RCG 70 em 2020, Empresarial 71 em 2025). Diga que “ativa” é prêmio positivo, não registro.

---

### Painel → Rentabilidade

**Q5 — barras de resultado técnico.** Eixo X = R$ bilhões no período. Garantia 5,34; Transportes 4,46; Empresarial 4,24; RCG 2,08; E&O 1,11. **Frase:** “Garantia é a terceira em prêmio e a primeira em resultado técnico; Transportes é a primeira em prêmio e a quarta em margem.”

**Q6 — barras de margem.** Eixo X = margem (resultado técnico ÷ prêmio). E&O 29,4%; Garantia 26,7%; RCG 22,8%; Empresarial 20,3%; Transportes 15,2%. **Frase:** “Tamanho não é margem. E&O tem a maior margem com o menor prêmio; Transportes tem a maior escala e a menor margem.”

**Tabela.** Repete os números e inclui sinistralidade. Use a tabela quando alguém pedir o número exato; use o gráfico para a mensagem.

---

### Painel → Sinistralidade

**Q3 — barras de sinistralidade agregada.** RCG 52,7%; Transportes 52,6%; Empresarial 49,3%; E&O 39,5%; Garantia 19,6%. **Frase:** “RCG e Transportes estão no mesmo patamar de sinistralidade, perto de 53%; Garantia opera em outro mundo, abaixo de 20%.”

**Q9 — linhas de sinistralidade anual.** Cada linha é uma LOB ao longo dos seis anos. Leia a direção, não só o nível: Empresarial cai de 62,5% para 40,4%; E&O cai de 40,0% para 35,2%, com 27,6% em 2024; RCG tem o pico de 92,4% em 2023; Garantia fica entre 7,6% e 30,3%; Transportes fica entre 49,6% e 55,8%. **Frase:** “Garantia é a mais confortável em nível; Empresarial é a que mais melhora; RCG é a mais instável; Transportes é a mais estável, mas estável em patamar alto.”

**Dispersão de volatilidade.** Eixo X = desvio-padrão da sinistralidade; eixo Y = média; tamanho = prêmio. Leia os quadrantes: canto inferior esquerdo é o melhor (média baixa e vol baixa); canto superior direito é o pior (média alta e vol alta). Garantia fica em média baixa; Transportes em média alta e vol baixa; RCG em média alta e vol alta; Empresarial em média alta, mas com tendência de melhora. **Frase:** “A LOB mais saudável em nível é Garantia; a mais previsível é Transportes; a mais perigosa é RCG.”

**Q4 — tabela de maior sinistralidade por LOB.** O slider define o share mínimo para entrar no ranking. Com 1%: Transportes Starr 71,9%; Empresarial HDI 74,3%; Garantia BTG 138,4%; RCG Generali 267,3%; E&O Allianz 66,0%. **Cuidado:** sem o corte, empresas minúsculas aparecem com 1.000% e dominam. Diga que o corte é de materialidade, não de conveniência. Sinistralidade negativa é reversão de reserva, não erro.

---

### Painel → Concorrência

**Seletor de LOB.** Escolha uma LOB para ver as seguradoras relevantes. A tabela mostra as que explicam 80% do prêmio (top 80% acumulado), com share, prêmio, sinistralidade, margem e a diferença contra o mercado. **Frase:** “Relevante não é quem aparece na tabela; é quem tem share material. Em todas as LOBs, 11 a 14 seguradoras explicam 80%.”

**Curva acumulada.** Eixo X = seguradoras ordenadas por prêmio; eixo Y = share acumulado. A linha de 80% mostra quantas importam. Top 5 concentra 45–54%. **Frase:** “O mercado é moderadamente concentrado; não é duopólio, mas também não é pulverizado.”

**Dispersão sinistralidade × margem.** Cada ponto é uma seguradora; tamanho = prêmio; linha vertical = sinistralidade do mercado; linha horizontal = margem do mercado; estrela = Akad. O quadrante bom é o superior esquerdo (sinistralidade baixa, margem alta). **Frase:** “As líderes não são necessariamente as mais rentáveis. Há espaço para quem combina risco controlado e margem.”

---

### Painel → Akad

**Q10 — tabela de posição.** Mostra prêmio, share e rank em 2020 e 2025 por LOB. Leia com a ressalva de marca: 2020–2021 é Argo; 2022+ é Akad. **Frase:** “A Akad é relevante em E&O (18,4%, 1º) e Transportes (10,2%, 3º). Em RCG o share é 2,2% e o posto 14º; Garantia e Empresarial são subescala.”

**Linha de share da Akad.** Cada linha é a participação da Akad na LOB ao longo dos anos. E&O sai de 13,7% para 18,4%; Transportes de 5,1% para 10,2%; RCG de 0,5% para 2,2%; Garantia de 0,6% para 0,9%; Empresarial de 0,1% para 0,9%. **Frase:** “A posição melhora em quatro das cinco LOBs; em Garantia o share sobe, mas o posto cai porque o mercado ganhou mais concorrentes.”

**Q11 — tabela e barras de vantagem.** Compara Akad, mercado, pares de porte e relevantes em margem e sinistralidade. A barra mostra a margem da Akad menos a do mercado; rosa = melhor, cinza = pior. **Frase:** “E&O e RCG são as vantagens claras. Transportes tem escala, mas margem abaixo do mercado. Garantia e Empresarial são subescala.”

**Leitura de marca.** 2020–2021 é Argo; a Akad nasce em 2022. Na fase Akad, E&O vai de 15,2% para 18,4%, Transportes de 7,3% para 10,2% e RCG de 0,8% para 2,2%. Parte do movimento é reconstrução de marca e estratégia, não só crescimento orgânico.

---

### Painel → Respostas

A aba reúne Q1–Q12 com os números recalculados e um botão para baixar em Markdown. Use-a como apoio; na apresentação, mostre o gráfico e diga a frase, não leia o texto inteiro.

---

### Atualizar base / Status

Mostre que a automação é real: 84 consultas, 4.007 linhas, 84/84 lidas, 79 reconciliações com a linha Totais do SES, 5 consultas vazias (0645). Explique a separação: ano fechado vira snapshot anual; trimestre/mês vira `data/atualizacoes`, sem sobrescrever o ano. A coleta roda no GitHub Actions, com Playwright; o app só dispara e lê o resultado.

---

## 3. As 12 perguntas: resposta curta e gráfico

| # | Pergunta | Resposta curta | Onde mostrar | Cuidado |
|---|---|---|---|---|
| 01 | Maior prêmio no período | Transportes, R$ 29,3 bi | Mercado, barras Q1 | É prêmio nominal |
| 02 | Mais seguradoras ativas em 2020 e 2025 | Empresarial: 47 e 51 | Mercado, barras Q2 | Ativa = prêmio > 0; presença de linha dá outra resposta |
| 03 | Maior sinistralidade no período | RCG, 52,7% | Sinistralidade, barras Q3 | Empate técnico com Transportes (52,6%) |
| 04 | Maior sinistralidade por LOB | Starr 71,9% (Transp.), HDI 74,3% (Empr.), BTG 138,4% (Gar.), Generali 267,3% (RCG), Allianz 66,0% (E&O) | Sinistralidade, tabela Q4 | Use corte de 1%; sem corte, minúsculas dominam |
| 05 | Resultado técnico por LOB | Garantia R$ 5,34 bi; Transportes R$ 4,46 bi; Empresarial R$ 4,24 bi; RCG R$ 2,08 bi; E&O R$ 1,11 bi | Rentabilidade, Q5 | Não é lucro contábil |
| 06 | Margem por LOB | E&O 29,4%; Garantia 26,7%; RCG 22,8%; Empresarial 20,3%; Transportes 15,2% | Rentabilidade, Q6 | Resultado técnico ÷ prêmio |
| 07 | Maior crescimento | E&O +108,7% em %; Transportes +R$ 2,48 bi em absoluto | Mercado, Q7 | Sempre os dois juntos |
| 08 | Seguradoras relevantes | Top 5 45–54%; 11–14 até 80% | Concorrência, tabela/curva | Relevância = top 80% acumulado |
| 09 | Tendência e LOB mais saudável | Garantia em nível; Empresarial em melhora; RCG volátil; Transportes estável e alto | Sinistralidade, Q9/volatilidade | Média ≠ tendência |
| 10 | Onde a Akad é relevante | E&O 18,4% (1º) e Transportes 10,2% (3º); RCG 2,2% (14º) | Akad, Q10 | 2020–21 é Argo; 2022+ é Akad |
| 11 | Akad melhor que o mercado | E&O e RCG em margem; Transportes tem escala, mas margem baixa | Akad, Q11 | Olhe também pares e relevantes |
| 12 | Onde focar | E&O como núcleo; corrigir Transportes; RCG seletivo; Garantia/Empresarial opcionais | Akad/Respostas, Q12 | Recomendação, não resultado automático |

---

## 4. Roteiro de 20 minutos

**0:00–1:30 — Método e automação.**
“Coletei 84 consultas no SES, 14 ramos em 6 anos, e validei cada uma contra a linha Totais da própria SUSEP. A base tem 4.007 linhas. A automação roda no GitHub Actions; o app lê o snapshot validado.”
Mostre rapidamente a aba Atualizar/Status, sem se perder.

**1:30–5:00 — Mercado.**
Q1: Transportes é a maior. Q7: E&O cresce mais em %, Transportes em R$. Q2: Empresarial lidera em ativas com prêmio > 0. Mensagem: “o mercado cresce em todas as linhas; a diferença é qualidade do crescimento.”

**5:00–8:00 — Rentabilidade.**
Q5: Garantia lidera o resultado técnico. Q6: E&O lidera a margem. Mensagem: “tamanho não é margem; Transportes tem escala e a menor margem.”

**8:00–11:30 — Risco.**
Q3: RCG e Transportes perto de 53%; Garantia abaixo de 20%. Q9: Empresarial melhora; RCG tem o pico de 2023; Transportes é estável em patamar alto. Q4: com corte de 1%, os outliers por LOB. Mensagem: “a LOB mais saudável em nível é Garantia; a mais imprevisível é RCG.”

**11:30–14:00 — Concorrência.**
Q8: top 5 45–54%; 11–14 seguradoras explicam 80%; as relevantes têm margem próxima do mercado, com exceções. Mostre a curva e a dispersão. Mensagem: “relevante é quem tem share material, não quem aparece na tabela.”

**14:00–17:00 — Akad.**
Conte a história: 2012 Argo; até 2021; 2022 Akad. Q10: E&O 1º com 18,4%; Transportes 3º com 10,2%; RCG 14º com 2,2%. Q11: E&O e RCG acima do mercado em margem; Transportes escala, mas margem baixa. Mensagem: “a Akad atual é uma seguradora de 2022; a leitura de posição olha 2022–2025.”

**17:00–19:00 — Recomendação.**
Q12: E&O é o núcleo; Transportes é escala a corrigir; RCG é aposta seletiva; Garantia/Empresarial são opcionais. E&O combina liderança, margem e sinistralidade controlada; Transportes precisa de reprecificação, sinistros, resseguro e mix; RCG pede nicho e controle de acumulação.

**19:00–20:00 — Limitações e próximos passos.**
Diga o que ficou de fora: valores nominais, sem despesa administrativa/imposto/resultado financeiro; 0645 sem dados; 2020–21 é Argo. Próximo passo: aprofundar a causa da queda de margem em Transportes e testar cenários de crescimento em E&O/RCG.

---

## 5. Perguntas prováveis

**“Por que resultado técnico e não lucro?”**
Porque não inclui despesa administrativa, imposto nem resultado financeiro. Chamar de lucro convida a pergunta “o que ficou de fora”; resultado técnico é o nome honesto.

**“Por que ativa é prêmio > 0?”**
Porque o SES lista seguradoras registradas mesmo sem operação. No RCG, 54 de 78 têm prêmio positivo. Contar linha mede registro, não atividade.

**“Por que o 0645 não aparece?”**
Não tem tabela em 2020–2024 e, em 2025, aparece com seis linhas zeradas. Na prática, Transportes são oito ramos.

**“Por que sinistralidade negativa?”**
Reversão de reserva. Exemplo: Companhia de Seguros Aliança da Bahia, no RCG, com sinistro negativo em 2024; no agregado de seis anos, a razão fica em -202,8 vezes o prêmio. Não é erro; agregar antes de dividir dilui.

**“Por que RCG tem 92,4% em 2023?”**
Pico de sinistros no ano. Pode ser um ou poucos casos grandes; a série mostra o efeito, não a causa. É o principal argumento para tratar RCG como volátil.

**“Por que a margem de Transportes caiu?”**
Em 2025 a sinistralidade da Akad em Transportes ficou em 68,3% e a margem em 0,2%. A base não mostra a causa; as hipóteses são mix, sinistros grandes, reprecificação e resseguro.

**“O que mudou em 2022?”**
A marca e a estratégia. 2020–2021 é Argo; 2022+ é Akad. A série de seis anos tem uma quebra estrutural; para a Akad atual, olhe 2022–2025.

**“Por que valores nominais?”**
É o que a SUSEP publica. Não deflacionei; o crescimento inclui inflação. Se quiser, o próximo passo é deflacionar pelo IPCA.

**“Como você validou?”**
Cada consulta foi comparada com a linha Totais do SES; a maior diferença no snapshot foi R$ 5 em R$ 2,65 bi. Também conferi SHA-256 do raw, rodapé de ramo/período, duplicatas e prêmio positivo por LOB/ano.

**“O que é a automação?”**
Playwright abre o SES, preenche ramo/período, exporta o `.xls`, grava o raw imutável com SHA-256, transforma em base longa, valida o contrato e publica o snapshot. Roda no GitHub Actions; o app só lê e dispara.

---

## 6. Glossário curto

- **Prêmio ganho:** receita de risco decorrido.
- **Sinistro ocorrido:** sinistro do período, com reservas.
- **Sinistralidade:** sinistro ÷ prêmio ganho.
- **Resultado técnico:** prêmio + receita de resseguro − sinistro − despesa de resseguro − despesa comercial.
- **Margem:** resultado técnico ÷ prêmio.
- **Ativa:** prêmio ganho > 0.
- **Relevante:** top 80% do prêmio acumulado.
- **HHI:** soma dos quadrados dos shares.
- **LOB:** grupo de ramos semelhantes.
- **Ramo:** código técnico da SUSEP.

---

## 7. Checklist antes de apresentar

- Rodar o app com o período completo (2020–2025) e conferir o logo e as cores.
- Testar os filtros de LOB e ano; se filtrar um ano só, as perguntas de crescimento ficam sem sentido.
- Abrir a aba Respostas e baixar o Markdown.
- Ter o EDA aberto para quem pedir o tratamento dos dados.
- Saber de cor cinco números: R$ 83,1 bi de prêmio; 43,2% de sinistralidade; R$ 17,2 bi de resultado técnico; 20,7% de margem; E&O 18,4% de share e 41,2% de margem na fase Akad.
- Dizer a frase da marca: “2020–2021 é Argo; 2022 em diante é Akad.”
