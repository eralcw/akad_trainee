"""Conteúdo didático do manual HTML (textos longos)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from dashboard import analise as A

ROOT = Path(__file__).resolve().parent.parent


def _manifest_exemplo() -> dict:
    for caminho in (ROOT / "data/raw/periodos/manifest.jsonl", ROOT / "data/raw/manifest.jsonl"):
        if not caminho.exists():
            continue
        for linha in reversed(caminho.read_text(encoding="utf-8").splitlines()):
            if not linha.strip():
                continue
            try:
                e = json.loads(linha)
            except Exception:
                continue
            if e.get("status") == "ok" and e.get("arquivo"):
                return e
    return {}


def sec_didatico() -> str:
    h1 = hashlib.sha256(b"akad").hexdigest()
    h2 = hashlib.sha256(b"akad ").hexdigest()
    e = _manifest_exemplo()
    exemplo = {
        "arquivo": e.get("arquivo", "ses_ramo0351_2025_1012_20261121T182744.xls"),
        "periodo": e.get("periodo", "202510-202512"),
        "sha256": e.get("sha256", "594e9bb43345dec42c0129f59eea8bad8bef9f24e9adbdc546596bc2dc710198"),
        "bytes": e.get("bytes", "62756"),
        "fonte": e.get("fonte", "export_xls"),
    }
    manifesto_html = (
        "{<br>"
        f'&nbsp;&nbsp;"tipo": "consulta", "status": "ok",<br>'
        f'&nbsp;&nbsp;"ramo": "0351", "ano": 2025,<br>'
        f'&nbsp;&nbsp;"periodo": "{exemplo["periodo"]}",<br>'
        f'&nbsp;&nbsp;"arquivo": "{exemplo["arquivo"]}",<br>'
        f'&nbsp;&nbsp;"bytes": {exemplo["bytes"]},<br>'
        f'&nbsp;&nbsp;"sha256": "{exemplo["sha256"]}"<br>'
        "}"
    )
    return f"""
    <section id="didatico">
      <div class="secnum">04 · automação sem jargão</div>
      <h2>O que é cada peça da automação, em linguagem simples</h2>
      <p>Antes de falar de gráfico, vale entender o caminho do dado. A automação é uma linha de montagem com quatro estações: <strong>coletar</strong>, <strong>conferir</strong>, <strong>guardar</strong> e <strong>publicar</strong>. Cada estação tem um nome técnico; abaixo explico com analogias.</p>

      <h3>O que é o raw?</h3>
      <p>É o arquivo exatamente como o SES entregou, sem edição. Pense no recibo original de uma compra: você pode tirar cópias, mas não rasura o recibo. O raw fica em <code>data/raw</code> e nunca é sobrescrito; cada coleta ganha um nome com data e hora.</p>

      <h3>O que é SHA-256?</h3>
      <p>É uma <strong>impressão digital do arquivo</strong>. O computador lê todos os bytes e calcula um código de 64 caracteres. Se um único espaço mudar, o código muda inteiro. Serve para provar que o arquivo usado na análise é exatamente o que foi baixado, e não uma versão editada por acidente ou por alguém.</p>
      <div class="chart">
        <table><thead><tr><th>Texto</th><th>SHA-256</th></tr></thead><tbody>
          <tr><td><code>akad</code></td><td class="num" style="font-size:10px">{h1}</td></tr>
          <tr><td><code>akad </code> (um espaço no fim)</td><td class="num" style="font-size:10px">{h2}</td></tr>
        </tbody></table>
      </div>
      <p class="caption">Um espaço muda a impressão digital inteira. É por isso que o pipeline compara o hash do arquivo com o hash registrado no manifesto.</p>

      <h3>O que é o manifesto?</h3>
      <p>É o <strong>caderno de registros</strong> da coleta. Para cada arquivo, ele anota: ramo, ano, período, nome do arquivo, tamanho, SHA-256, fonte e horário. Se o arquivo for alterado, o hash não bate e o contrato reprova. Um registro do manifesto se parece com isto:</p>
      <pre style="background:#F4F5FD;border:1px solid #E4E6F4;padding:12px;overflow:auto;font-family:'IBM Plex Mono',monospace;font-size:11px">{manifesto_html}</pre>

      <h3>O que é o contrato?</h3>
      <p>É a <strong>lista de conferência</strong> antes de publicar. Ele não olha se o gráfico é bonito; olha se o dado é confiável. As checagens principais são: todas as consultas foram lidas? a soma das seguradoras bate com a linha Totais do SES? o rodapé confere ramo e período? há duplicata? o prêmio é positivo por LOB/ano? a Akad aparece? o hash do arquivo bate? Se algo falha, o snapshot não é publicado.</p>

      <h3>O que é o snapshot?</h3>
      <p>É a <strong>foto validada</strong> da base em um momento. O raw é o recibo; o snapshot é a planilha organizada e conferida. Ele fica em <code>data/snapshots/&lt;data&gt;/</code> com <code>base.parquet</code>, <code>base.csv</code> e <code>meta.json</code>. O dashboard lê sempre o snapshot apontado por <code>latest.json</code>.</p>
      <div class="nota"><p><strong>Parquet x CSV.</strong> O CSV é texto, abre no Excel; o Parquet é binário e compacto, melhor para o Python. Os dois têm a mesma base. No Excel, importe o CSV como texto para não perder o zero à esquerda do ramo 0351.</p></div>

      <h3>O que é o staging?</h3>
      <p>É a <strong>área de rascunho</strong>. O snapshot é escrito primeiro em uma pasta temporária; só depois de completo ele é renomeado para a pasta final. Se algo der errado no meio, o rascunho é apagado e o snapshot anterior continua intacto. É como montar um móvel na garagem e só levar para a sala quando estiver pronto.</p>

      <h3>O que é o período parcial?</h3>
      <p>É um recorte de trimestre ou de meses. Ele fica em <code>data/atualizacoes</code> com <code>parcial=True</code> e não substitui o ano fechado. O ano fechado é a base do case; o parcial é monitoramento. Se você pedir janeiro a março, o SES devolve a soma do trimestre, não uma série mensal; por isso o recorte é tratado como parcial.</p>

      <h3>O que é o GitHub Actions?</h3>
      <p>É um <strong>robô que roda nos servidores do GitHub</strong>. Você deixa uma receita em <code>.github/workflows/update.yml</code>; ele instala Python e Chromium, abre o SES, coleta, valida e comita o resultado. O Streamlit não abre o navegador: ele só aperta o botão do robô via API. O token é a chave desse botão; fica nos secrets.</p>

      <h3>O que é o Streamlit?</h3>
      <p>É a biblioteca que transforma um script Python em site interativo. Cada visita executa o script; os filtros recalculam os gráficos. O app lê o snapshot, não o SES. A coleta é assíncrona: você dispara, o GitHub roda e o app mostra o status.</p>

      <h3>Dicionário de jargão</h3>
      <table><thead><tr><th>Termo</th><th>Em linguagem simples</th></tr></thead><tbody>
      <tr><td>Playwright</td><td>Robô que controla um navegador de verdade.</td></tr>
      <tr><td>Chromium</td><td>O navegador usado pelo robô.</td></tr>
      <tr><td>Headless</td><td>Navegador rodando sem janela visível.</td></tr>
      <tr><td>Raw</td><td>Arquivo original, intocado.</td></tr>
      <tr><td>Manifesto</td><td>Caderno de registros com hash e parâmetros de cada arquivo.</td></tr>
      <tr><td>SHA-256</td><td>Impressão digital do arquivo; muda se qualquer byte mudar.</td></tr>
      <tr><td>Parser</td><td>Trecho de código que lê a tabela e transforma em linhas e colunas.</td></tr>
      <tr><td>Contrato</td><td>Checklist que aprova ou reprova a publicação.</td></tr>
      <tr><td>Snapshot</td><td>Foto validada da base.</td></tr>
      <tr><td>Staging</td><td>Área de rascunho antes da publicação.</td></tr>
      <tr><td>Parquet</td><td>Arquivo de tabela binário e compacto.</td></tr>
      <tr><td>GitHub Actions</td><td>Robô que roda a coleta nos servidores do GitHub.</td></tr>
      <tr><td>Workflow</td><td>A receita que o robô executa.</td></tr>
      <tr><td>Token</td><td>Chave que autoriza o app a disparar o workflow.</td></tr>
      <tr><td>Commit / push</td><td>Salvar no histórico local / enviar para o GitHub.</td></tr>
      <tr><td>Streamlit</td><td>Biblioteca que transforma Python em site interativo.</td></tr>
      </tbody></table>
    </section>"""


def leitura(titulo: str, onde: str, mostra: str, observar: str, concluir: str, nao: str, fala: str) -> str:
    return f"""
    <div class="leitura">
      <div class="qnum">{onde}</div>
      <h3>{titulo}</h3>
      <p><strong>O que mostra.</strong> {mostra}</p>
      <p><strong>O que observar.</strong> {observar}</p>
      <p><strong>O que concluir.</strong> {concluir}</p>
      <p><strong>O que não concluir.</strong> {nao}</p>
      <div class="nota"><p><strong>Fala pronta:</strong> “{fala}”</p></div>
    </div>"""


def sec_leituras() -> str:
    blocos = [
        leitura(
            "Linha de prêmio por LOB e ano",
            "Visão geral",
            "Cinco linhas, uma por LOB; o eixo X é o ano e o eixo Y é o prêmio ganho em R$ bilhões. Cada ponto é a soma das seguradoras daquela LOB no ano.",
            "Transportes sai de R$ 3,3 bi em 2020 para R$ 5,8 bi em 2025; Empresarial de 2,6 para 4,6; Garantia de 2,6 para 4,3; RCG de 1,0 para 1,9; E&O de 0,4 para 0,9. Todas as linhas sobem; não há cruzamento.",
            "O mercado cresce em todas as cinco LOBs. Transportes é a maior em todos os anos; E&O é a menor, mas a que cresce mais em porcentagem. A distância entre Transportes e as demais aumenta em valor absoluto.",
            "Que o crescimento é real em termos de volume: os valores são nominais e incluem inflação. A linha não mostra margem nem sinistralidade; crescer não é necessariamente ganhar dinheiro.",
            "Todas as linhas crescem. Transportes é a maior LOB em todos os anos; E&O é a menor, mas a que cresce mais em porcentagem. Em valor absoluto, quem mais adiciona prêmio é Transportes.",
        ),
        leitura(
            "Mapa de calor da sinistralidade",
            "Visão geral",
            "Linhas são LOBs, colunas são anos e a cor representa a sinistralidade: quanto mais quente, maior a parcela do prêmio consumida por sinistro.",
            "Garantia fica entre 7,6% e 30,3%; RCG tem o ponto mais quente em 2023, com 92,4%; Empresarial esfria de 62,5% para 40,4%; Transportes fica entre 49,6% e 55,8%; E&O cai para 27,6% em 2024 e volta a 35,2% em 2025.",
            "O mapa mostra nível e trajetória ao mesmo tempo. Garantia é a mais confortável em nível; Empresarial é a que mais melhora; RCG é a mais instável; Transportes é estável, mas em patamar alto.",
            "Que a cor de um ano isolado é tendência. O pico de RCG em 2023 pode ser um ou poucos sinistros grandes; para dizer que piorou de forma estrutural, seria preciso olhar a causa e os anos seguintes.",
            "Garantia opera em outro patamar de sinistralidade. Empresarial melhora de forma consistente. RCG tem um pico em 2023 que exige leitura ano a ano. Transportes é estável, mas estável perto de 53%.",
        ),
        leitura(
            "Q1 — prêmio total por LOB",
            "Mercado",
            "Barras horizontais com o prêmio ganho acumulado de 2020 a 2025 por LOB. O comprimento é o valor; a ordem é do menor para o maior.",
            "Transportes R$ 29,3 bi; Empresarial R$ 20,9 bi; Garantia R$ 20,0 bi; RCG R$ 9,1 bi; E&O R$ 3,8 bi. Em participação: 35%, 25%, 24%, 11% e 5%.",
            "Transportes é o centro de gravidade do mercado; Empresarial e Garantia formam um segundo bloco; RCG e E&O são menores. A concentração de prêmio em Transportes explica por que a LOB aparece em quase toda a conversa.",
            "Que a maior LOB é a mais lucrativa. A Q6 mostra Transportes com a menor margem. Tamanho e rentabilidade são dimensões diferentes.",
            "Transportes concentra 35% do prêmio das cinco LOBs. Empresarial e Garantia vêm logo atrás, com cerca de 25% cada. E&O é a menor, com 5%.",
        ),
        leitura(
            "Q7 — crescimento 2020 → 2025",
            "Mercado",
            "Cada LOB é uma linha entre o prêmio de 2020 (ponto esquerdo) e o de 2025 (ponto direito). O comprimento mostra a variação absoluta; o texto na ponta direita mostra a variação percentual.",
            "E&O: +108,7% e +R$ 0,46 bi. RCG: +92,6% e +R$ 0,92 bi. Empresarial: +79,6% e +R$ 2,05 bi. Transportes: +74,4% e +R$ 2,48 bi. Garantia: +67,9% e +R$ 1,74 bi.",
            "As duas leituras contam histórias diferentes. E&O tem a maior taxa porque parte de uma base pequena; Transportes tem a maior adição absoluta porque já era grande. RCG cresce bem em % e em valor, mas com volatilidade.",
            "Que a maior porcentagem é a mais importante. Um crescimento de 900% sobre R$ 1 milhão é irrelevante em tamanho. Sempre leia % e absoluto juntos.",
            "Em porcentagem, E&O cresce mais, 108,7%. Em valor absoluto, Transportes adiciona mais, R$ 2,48 bi. São respostas diferentes para a mesma pergunta, e o case pede as duas.",
        ),
        leitura(
            "Q2 — seguradoras ativas",
            "Mercado",
            "Barras agrupadas por LOB, comparando 2020 e 2025. A contagem considera apenas seguradoras com prêmio ganho maior que zero no ano.",
            "Empresarial 47 → 51; RCG 45 → 47; Garantia 38 → 46; E&O 27 → 31; Transportes 25 → 25. Se contássemos toda linha do SES, RCG apareceria com 70 em 2020 e Empresarial com 71 em 2025.",
            "A maioria das LOBs ganhou concorrentes ativos no período; Transportes ficou estável. A contagem por presença de linha é muito maior e mede registro cadastral, não operação.",
            "Que mais seguradoras ativas significa mais competição acirrada. Para medir competição, olhe também a concentração (top 5, 80% acumulado, HHI).",
            "Com prêmio maior que zero, Empresarial lidera em 2020 e em 2025, com 47 e 51 seguradoras. Se eu contasse toda linha do SES, a resposta seria outra, porque o sistema lista empresas registradas mesmo sem operação.",
        ),
        leitura(
            "Q5 — resultado técnico por LOB",
            "Rentabilidade",
            "Barras horizontais com o resultado técnico acumulado de 2020 a 2025. Resultado técnico = prêmio + receita de resseguro − sinistro − despesa de resseguro − despesa comercial.",
            "Garantia R$ 5,34 bi; Transportes R$ 4,46 bi; Empresarial R$ 4,24 bi; RCG R$ 2,08 bi; E&O R$ 1,11 bi. Garantia é a terceira em prêmio e a primeira em resultado.",
            "Garantia converte prêmio em resultado com eficiência; Transportes tem escala, mas o resultado é menor do que o prêmio sugere; E&O tem o menor resultado absoluto, mas a maior margem.",
            "Que resultado técnico é lucro contábil. Não inclui despesa administrativa, imposto nem resultado financeiro. O nome correto é resultado técnico.",
            "Garantia gera o maior resultado técnico do período, R$ 5,34 bi, mesmo sendo a terceira em prêmio. Transportes tem o maior prêmio, mas fica atrás em resultado.",
        ),
        leitura(
            "Q6 — margem por LOB",
            "Rentabilidade",
            "Barras horizontais com a margem: resultado técnico dividido pelo prêmio ganho. É a eficiência de cada real de prêmio.",
            "E&O 29,4%; Garantia 26,7%; RCG 22,8%; Empresarial 20,3%; Transportes 15,2%. A ordem é quase inversa à do prêmio.",
            "E&O é a LOB mais eficiente, com o menor prêmio; Transportes é a maior e a menos eficiente. Garantia combina bom resultado absoluto e margem alta.",
            "Que margem alta resolve escala. Uma margem de 29% sobre R$ 3,8 bi ainda é menor em valor absoluto do que uma margem de 15% sobre R$ 29,3 bi. As duas leituras importam.",
            "E&O tem a maior margem, 29,4%; Transportes tem a menor, 15,2%. Tamanho não é margem.",
        ),
        leitura(
            "Q3 — sinistralidade agregada",
            "Sinistralidade",
            "Barras horizontais com a sinistralidade do período inteiro por LOB. O cálculo é soma dos sinistros dividida pela soma dos prêmios.",
            "RCG 52,7%; Transportes 52,6%; Empresarial 49,3%; E&O 39,5%; Garantia 19,6%. RCG e Transportes estão praticamente empatados.",
            "Duas LOBs operam perto de 53% de sinistralidade; Garantia opera abaixo de 20%. A diferença de 33 pontos entre Garantia e RCG é enorme para o mesmo mercado.",
            "Que sinistralidade alta significa prejuízo. A margem depende também de resseguro e despesa comercial; uma LOB com sinistralidade alta pode ter margem positiva.",
            "RCG e Transportes estão no mesmo patamar, perto de 53%. Garantia está em outro mundo, abaixo de 20%.",
        ),
        leitura(
            "Q9 — sinistralidade anual",
            "Sinistralidade",
            "Uma linha por LOB ao longo dos seis anos. O eixo Y é a sinistralidade anual; a direção da linha mostra melhora ou piora.",
            "Empresarial cai de 62,5% para 40,4%; E&O cai de 40,0% para 35,2%, com 27,6% em 2024; RCG tem o pico de 92,4% em 2023; Garantia fica entre 7,6% e 30,3%; Transportes fica entre 49,6% e 55,8%.",
            "Nível e tendência são coisas diferentes. Garantia é a mais confortável em nível, mas a linha sobe; Empresarial é a que mais melhora; RCG é a mais instável; Transportes é a mais estável, mas em patamar alto.",
            "Que um ano isolado é tendência. Use a inclinação e a volatilidade, não só o último ponto. O pico de RCG em 2023 não garante que 2026 será igual.",
            "Garantia é a mais confortável em nível; Empresarial é a que mais melhora; RCG é a mais volátil; Transportes é a mais estável, mas estável perto de 53%.",
        ),
        leitura(
            "Dispersão de volatilidade",
            "Sinistralidade",
            "Cada LOB é um ponto: eixo X é o desvio-padrão da sinistralidade anual; eixo Y é a média; o tamanho do ponto é o prêmio.",
            "Garantia tem média baixa e desvio moderado; Transportes tem média alta e o menor desvio; RCG tem média alta e o maior desvio; Empresarial tem média alta, mas tendência de queda; E&O tem média moderada.",
            "O quadrante bom é média baixa e desvio baixo. Garantia é a mais saudável em nível; Transportes é a mais previsível, mas em patamar alto; RCG é a mais perigosa.",
            "Que a média sozinha basta. Duas LOBs com a mesma média podem ter riscos muito diferentes; o desvio mostra a imprevisibilidade.",
            "Garantia é a mais saudável em nível; Transportes é a mais previsível; RCG é a mais imprevisível. Média e volatilidade contam histórias diferentes.",
        ),
        leitura(
            "Q4 — maior sinistralidade por seguradora",
            "Sinistralidade",
            "Tabela com as três maiores sinistralidades por LOB, exigindo share mínimo de 1% do prêmio da LOB. Sem o corte, empresas minúsculas dominam.",
            "Com 1%: Starr 71,9% em Transportes; HDI 74,3% em Empresarial; BTG 138,4% em Garantia; Generali 267,3% em RCG; Allianz 66,0% em E&O.",
            "Há outliers reais em todas as LOBs. O corte de materialidade separa o que é relevante do que é efeito de base pequena. Sinistralidade acima de 100% significa que o sinistro consumiu mais de um ano de prêmio.",
            "Que o ranking sem corte é útil. Empresas com prêmio quase zero aparecem com 1.000% e escondem as relevantes. Sinistralidade negativa é reversão de reserva, não erro.",
            "Com corte de 1% de share, os maiores casos são Starr em Transportes, HDI em Empresarial, BTG em Garantia, Generali em RCG e Allianz em E&O. Sem o corte, empresas minúsculas dominam o ranking.",
        ),
        leitura(
            "Q8 — concentração e relevantes",
            "Concorrência",
            "Três leituras juntas: barras do top 5 share por LOB; curva acumulada até 80%; tabela das relevantes com margem e sinistralidade contra o mercado.",
            "Top 5 concentra 45–54% em todas as LOBs; 11–14 seguradoras explicam 80%; as relevantes têm margem próxima do mercado, com exceções como Chubb e Fairfax em RCG.",
            "O mercado é moderadamente concentrado. “Relevante” é quem tem share material, não quem aparece na tabela. A cauda longa existe, mas não move o mercado.",
            "Que top 5 é o mercado inteiro. Em todas as LOBs, ainda há 11–14 seguradoras relevantes; a cauda tem papel, mas menor.",
            "O top 5 concentra entre 45% e 54% do prêmio. Cerca de 11 a 14 seguradoras explicam 80%. As relevantes têm margem perto do mercado, com algumas exceções.",
        ),
        leitura(
            "Q10 — share da Akad",
            "Akad",
            "Uma linha por LOB com a participação da Akad no prêmio da LOB ao longo dos anos. O eixo Y é o share; o X é o ano.",
            "E&O sai de 13,7% para 18,4%; Transportes de 5,1% para 10,2%; RCG de 0,5% para 2,2%; Garantia de 0,6% para 0,9%; Empresarial de 0,1% para 0,9%. A posição melhora em quatro das cinco LOBs.",
            "A Akad é relevante em E&O e Transportes. Em RCG o share ainda é pequeno, mas cresce; Garantia e Empresarial são subescala. Em Garantia o share sobe, mas o posto cai porque o mercado ganhou mais concorrentes.",
            "Que todo o crescimento é orgânico. 2020–2021 é a operação Argo; 2022 em diante é a Akad. O rebranding é uma quebra estrutural.",
            "A Akad é relevante em E&O, com 18,4% e primeiro lugar, e em Transportes, com 10,2% e terceiro. Em RCG o share é 2,2% e o posto 14º. Em Garantia e Empresarial é subescala.",
        ),
        leitura(
            "Q11 — Akad contra mercado",
            "Akad",
            "Barras agrupadas com a margem da Akad e a margem do mercado por LOB, mais a tabela com pares de porte e relevantes. A barra de vantagem mostra a margem da Akad menos a do mercado.",
            "E&O: Akad 37,5% vs mercado 29,4%; RCG: 38,1% vs 22,8%; Empresarial: 6,0% vs 20,3%; Garantia: 14,4% vs 26,7%; Transportes: 6,2% vs 15,2%. Na fase 2022–2025, E&O 41,2% vs 30,2% e Transportes 3,5% vs 14,6%.",
            "A vantagem clara está em E&O e RCG. Transportes tem escala, mas margem abaixo do mercado. Garantia e Empresarial são subescala e operam pior que o mercado.",
            "Que a Akad é melhor em todas as LOBs. Ela é melhor em E&O e RCG; em Transportes, Garantia e Empresarial fica atrás. Em RCG o share ainda é pequeno e o mercado é volátil.",
            "Em E&O e RCG a Akad tem margem acima do mercado e também supera os pares de porte e as relevantes. Em Transportes tem escala, mas margem abaixo. Garantia e Empresarial são subescala.",
        ),
        leitura(
            "Q12 — matriz de decisão",
            "Akad / Respostas",
            "Cada LOB é um círculo: eixo X é a atratividade do mercado (margem do mercado em 2022–2025); eixo Y é a vantagem da Akad (margem Akad menos margem do mercado, em pontos percentuais); tamanho é o prêmio.",
            "E&O e RCG ficam no topo direito: mercado atraente e Akad com vantagem. Transportes fica na parte de baixo: mercado grande, mas Akad com desvantagem. Garantia e Empresarial também ficam abaixo da linha do zero.",
            "E&O é o núcleo; RCG é aposta seletiva; Transportes é escala a corrigir; Garantia e Empresarial são opcionais. A matriz resume a recomendação, mas não substitui a análise de capital, canais e resseguro.",
            "Que a matriz é uma resposta automática. Ela é uma ferramenta de decisão; a recomendação final considera crescimento, lucratividade, canais, infraestrutura e risco.",
            "A matriz mostra E&O e RCG no quadrante de prioridade: mercado atraente e Akad com vantagem. Transportes é escala, mas com desvantagem de margem. Garantia e Empresarial ficam atrás.",
        ),
    ]
    return f"""
    <section id="leituras">
      <div class="secnum">07 · leitura detalhada</div>
      <h2>Cada gráfico, com o que mostrar, concluir e não concluir</h2>
      <p>Esta seção é o aprofundamento que faltava: para cada gráfico, o que ele mostra, o que observar, o que concluir, o que não concluir e uma fala pronta. Use como consulta antes da apresentação.</p>
      {''.join(blocos)}
    </section>"""


def sec_exemplo(base) -> str:
    r = base[(base["lob"] == "E&O") & (base["ano"] == 2025) & (base["codigo_susep"] == A.AKAD)]
    if r.empty:
        return ""
    r = r.iloc[0]
    receita_total = r.premio_ganho + r.receita_resseguro
    apos_sinistro = receita_total - r.sinistro_ocorrido
    apos_resseguro = apos_sinistro - r.despesa_resseguro
    resultado = apos_resseguro - r.despesa_comercial
    linhas = [
        ["Prêmio Ganho", A.f_mi(r.premio_ganho), "Receita de risco já decorrido. É o ponto de partida."],
        ["Sinistro Ocorrido", A.f_mi(r.sinistro_ocorrido), "O que a seguradora pagou ou reservou por sinistro."],
        ["Despesa com Resseguro", A.f_mi(r.despesa_resseguro), "Prêmio pago ao ressegurador para transferir risco."],
        ["Receita com Resseguro", A.f_mi(r.receita_resseguro), "O que a seguradora recupera do ressegurador."],
        ["Despesa Comercial", A.f_mi(r.despesa_comercial), "Comissão de corretagem e custo de aquisição."],
        ["Resultado técnico", A.f_mi(resultado), "Prêmio + receita de resseguro − sinistro − despesa de resseguro − despesa comercial."],
    ]
    tab = "<table><thead><tr><th>Coluna</th><th>Valor</th><th>O que significa</th></tr></thead><tbody>" + "".join(
        f'<tr><td>{a}</td><td class="num">{b}</td><td>{c}</td></tr>' for a, b, c in linhas
    ) + "</tbody></table>"
    return f"""
    <section id="exemplo">
      <div class="secnum">08 · exemplo real</div>
      <h2>Uma linha da base, coluna por coluna</h2>
      <p>Exemplo: <strong>AKAD SEGUROS S.A., E&amp;O (ramo 0378), 2025</strong>. É a mesma linha que aparece na base, sem média e sem agregação.</p>
      {tab}
      <p><strong>Passo a passo do resultado técnico:</strong> começa com {A.f_mi(r.premio_ganho)} de prêmio; soma {A.f_mi(r.receita_resseguro)} de receita com resseguro; subtrai {A.f_mi(r.sinistro_ocorrido)} de sinistro; subtrai {A.f_mi(r.despesa_resseguro)} de despesa com resseguro; subtrai {A.f_mi(r.despesa_comercial)} de despesa comercial. O resultado é {A.f_mi(resultado)}.</p>
      <p><strong>Sinistralidade:</strong> {A.f_mi(r.sinistro_ocorrido)} ÷ {A.f_mi(r.premio_ganho)} = {A.f_pct(r.sinistralidade)}. <strong>Margem:</strong> {A.f_mi(resultado)} ÷ {A.f_mi(r.premio_ganho)} = {A.f_pct(r.margem)}.</p>
      <div class="nota"><p><strong>Por que a margem é alta se a sinistralidade é 27%?</strong> Porque a receita com resseguro supera a despesa com resseguro e a despesa comercial é 23% do prêmio. O resultado técnico não é lucro contábil: ainda faltam despesa administrativa, imposto e resultado financeiro.</p></div>
    </section>"""


def sec_tour() -> str:
    return """
    <section id="tour">
      <div class="secnum">09 · tour do app</div>
      <h2>O que clicar em cada aba</h2>
      <p><strong>1. Painel → filtros.</strong> No topo, escolha as LOBs e o intervalo de anos. O padrão é 2020–2025 e todas as LOBs. Se filtrar um ano só, o app avisa que crescimento perde sentido.</p>
      <p><strong>2. Visão geral.</strong> Leia o ledger (prêmio, sinistralidade, resultado, margem), a linha de prêmio e o mapa de calor. É o resumo de 30 segundos.</p>
      <p><strong>3. Mercado.</strong> Use Q1 para tamanho, Q7 para crescimento e Q2 para número de ativas. Mostre o halter de crescimento quando alguém perguntar “quem cresceu mais”.</p>
      <p><strong>4. Rentabilidade.</strong> Q5 mostra resultado absoluto; Q6 mostra margem. Use os dois juntos para separar tamanho de eficiência.</p>
      <p><strong>5. Sinistralidade.</strong> Q3 dá o nível; Q9 dá a tendência; a dispersão dá o risco; Q4 dá os outliers. O slider de Q4 controla o corte de materialidade.</p>
      <p><strong>6. Concorrência.</strong> Escolha uma LOB no seletor. A tabela mostra as relevantes; a curva mostra a concentração; a dispersão mostra margem × sinistralidade com a Akad em estrela.</p>
      <p><strong>7. Akad.</strong> Q10 mostra posição e share; Q11 mostra a vantagem contra mercado, pares e relevantes. A nota de marca lembra: 2020–21 é Argo; 2022+ é Akad.</p>
      <p><strong>8. Respostas.</strong> As 12 respostas estão escritas e podem ser baixadas em Markdown. Use como apoio, não como script para ler.</p>
      <p><strong>9. Atualizar base.</strong> Escolha LOB/ramos, ano, trimestre ou intervalo, confirme e dispare. O GitHub Actions coleta; o app acompanha.</p>
      <p><strong>10. Status.</strong> Mostra snapshot anual, cobertura, totais conferidos e recortes parciais. É a prova de que a base está validada.</p>
      <p><strong>11. Método.</strong> Explica a fórmula, a definição de ativa e o caminho do botão. Tem o link para o EDA e para este roteiro.</p>
    </section>"""


def sec_transcricao() -> str:
    return """
    <section id="transcricao">
      <div class="secnum">10 · transcrição</div>
      <h2>Uma apresentação de 20 minutos, frase por frase</h2>
      <p><strong>Abertura.</strong> “Vou mostrar o que fiz em três camadas: a automação que coleta e valida os dados, o painel que transforma isso em leitura de mercado e a recomendação para a Akad. A base cobre 2020 a 2025, cinco LOBs, 14 ramos e 4.007 linhas. Cada consulta foi comparada com a linha Totais da própria SUSEP.”</p>
      <p><strong>Método.</strong> “O SES publica prêmio, sinistro e despesa por seguradora, ramo e período. O formulário é antigo e exige uma consulta por ramo e período; são 84 consultas. Eu automatizei com Playwright, gravei o arquivo original com SHA-256, transformei em base longa e só publiquei depois de passar no contrato de validação. A coleta roda no GitHub Actions; o app lê o snapshot validado.”</p>
      <p><strong>História da Akad.</strong> “Antes dos números, uma ressalva importante: a série de 2020–2025 tem dois capítulos. Até 2021, a operação era Argo. Em 2022, a Akad nasce como marca e estratégia. Para tamanho de mercado, os seis anos são úteis; para avaliar a Akad atual, eu olho 2022–2025.”</p>
      <p><strong>Mercado.</strong> “Transportes é a maior LOB, com R$ 29,3 bi, 35% do prêmio. Empresarial e Garantia vêm depois, com cerca de 25% cada. E&O é a menor, com 5%, mas é a que mais cresce em porcentagem: 108,7%. Em valor absoluto, Transportes adiciona mais: R$ 2,48 bi. São duas leituras diferentes, e o case pede as duas.”</p>
      <p><strong>Ativas.</strong> “Com o critério de prêmio maior que zero, Empresarial lidera em 2020 e em 2025, com 47 e 51 seguradoras. Se eu contasse toda linha do SES, RCG apareceria com 70 em 2020, mas isso é presença cadastral, não operação.”</p>
      <p><strong>Rentabilidade.</strong> “Garantia gera o maior resultado técnico, R$ 5,34 bi, mesmo sendo a terceira em prêmio. E&O tem a maior margem, 29,4%. Transportes tem o maior prêmio e a menor margem, 15,2%. Tamanho não é margem.”</p>
      <p><strong>Risco.</strong> “RCG e Transportes estão perto de 53% de sinistralidade; Garantia está abaixo de 20%. Na tendência, Empresarial melhora de 62,5% para 40,4%; RCG tem o pico de 92,4% em 2023; Transportes é estável, mas em patamar alto. A LOB mais saudável em nível é Garantia; a mais imprevisível é RCG.”</p>
      <p><strong>Concorrência.</strong> “O top 5 concentra 45–54% do prêmio e 11 a 14 seguradoras explicam 80%. Relevante é quem tem share material. As relevantes têm margem próxima do mercado, com exceções.”</p>
      <p><strong>Q4.</strong> “Com corte de 1% de share, os maiores casos são Starr em Transportes, HDI em Empresarial, BTG em Garantia, Generali em RCG e Allianz em E&O. Sem o corte, empresas minúsculas aparecem com 1.000% e escondem as relevantes. Sinistralidade negativa é reversão de reserva, não erro.”</p>
      <p><strong>Akad.</strong> “A Akad é relevante em E&O, com 18,4% e primeiro lugar, e em Transportes, com 10,2% e terceiro. Em RCG o share é 2,2% e o posto 14º. Na fase Akad, E&O vai de 15,2% para 18,4%, Transportes de 7,3% para 10,2% e RCG de 0,8% para 2,2%.”</p>
      <p><strong>Q11.</strong> “Em E&O e RCG a Akad tem margem acima do mercado e também supera os pares de porte e as relevantes. Em Transportes tem escala, mas margem abaixo. Garantia e Empresarial são subescala.”</p>
      <p><strong>Recomendação.</strong> “Minha recomendação é E&O como núcleo: liderança, margem e sinistralidade controlada. Transportes é escala a corrigir, com reprecificação, gestão de sinistros, resseguro e mix. RCG é aposta seletiva, com nicho e controle de acumulação. Garantia e Empresarial são opcionais. A estratégia usa a posição de 2022 como seguradora moderna e inovadora: canais de corretores, pricing e gestão de sinistros são a alavanca, não só preço.”</p>
      <p><strong>Fechamento.</strong> “O que ficou de fora: valores nominais, sem inflação; resultado técnico, sem despesa administrativa, imposto e resultado financeiro; 0645 sem dados; 2020–21 é Argo. O próximo passo é aprofundar a causa da queda de margem em Transportes e testar cenários de crescimento em E&amp;O e RCG.”</p>
    </section>"""
