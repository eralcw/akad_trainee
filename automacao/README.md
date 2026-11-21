# Automacao SES/SUSEP - Case Akad 2027

```
SES (portal) --export .xls--> data/raw/ (imutavel + SHA-256 + manifest.jsonl)
                                   |  (processar: SEM rede)
                                   v
                   transform -> validate (contrato) -> publish
                                                          |
                                data/snapshots/<data>/base.parquet  + latest.json
                                                          |
                                          dashboard (Streamlit) le so o snapshot
```

## Comandos (dentro de `automacao/`)

```powershell
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt ; playwright install chromium

python pipeline.py coletar --anos 2025 --ramos 0351   # teste: 1 consulta
python pipeline.py atualizar                          # coleta o que falta + processa + publica
python pipeline.py atualizar --offline                # so reprocessa data/raw (sem rede)
python pipeline.py status [--checar-fonte]            # painel de saude
python pipeline.py snapshots                          # * = vigente
python pipeline.py rollback                           # volta ao snapshot anterior
python -m pytest tests -q                             # testes offline
```

Por padrao a coleta abre o navegador (como o `ses_coleta.py` original); `--headless` roda sem janela.
O portal do SES tem firewall: se ele recusar o acesso, a coleta **para** (sem insistir) e o
pipeline segue com o `data/raw` ja existente.

## Contrato de dados (validate.py)
Snapshot so e publicado se: todas as consultas (ramos x anos do `config.yaml`) foram lidas;
a soma das seguradoras bate com a linha **Totais** do proprio SES (5 colunas); o rodape do SES
confere com o ramo/periodo pedido; sem duplicatas; premio > 0 por LOB x ano; colunas
obrigatorias nao zeradas; Akad presente. Sinais negativos geram aviso.

## Atualizacao
`config.yaml > atualizacao.reextrair_anos` lista anos sempre re-extraidos (retificacoes).
Cada publicacao compara com o snapshot anterior e informa linhas retificadas (diff).
Agendamento: `.github/workflows/update.yml` (trimestral + manual).

## Uso no dashboard
```python
from ses.config import Config
from ses import publish
from ses.transform import agregar
base = publish.carregar_base(Config())
por_lob_ano = agregar(base, ["lob", "ano"])   # soma antes de dividir
```
