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
python pipeline.py periodo --periodo-ini 202501 --periodo-fim 202503 --ramos 0351
                                                       # recorte parcial (trimestre/mes)
python pipeline.py status [--checar-fonte]            # painel de saude
python pipeline.py snapshots                          # * = vigente
python pipeline.py rollback                           # volta ao snapshot anterior
python -m pytest tests -q                             # testes offline
```

## Recorte parcial (trimestre/mes)

`pipeline.py periodo` coleta um intervalo `AAAAMM` de um ou mais ramos e publica em
`data/atualizacoes/<timestamp>/`, com `periodo_ini`, `periodo_fim`, `meses` e
`parcial=True`. Ele **nao** altera o snapshot anual em `data/snapshots/`: um trimestre
nunca substitui o ano fechado. Use `--offline` para reconstruir o parcial a partir do
raw ja baixado em `data/raw/periodos/`.

## App Streamlit

O app fica na raiz do repositorio e le o snapshot publicado:

```powershell
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

A aba **Atualizar base** nao roda o Playwright no navegador do app: ela dispara o
workflow `.github/workflows/update.yml` via API do GitHub. Configure o token em
`.streamlit/secrets.toml` (local) ou em **Settings > Secrets** no Streamlit Cloud:

```toml
[github]
token = "github_pat_..."
owner = "eralcw"
repo = "akad_trainee"
workflow = "update.yml"
ref = "main"
```

O token precisa de permissao **Actions: Read and write** apenas no repositorio
`akad_trainee`. O `secrets.toml` esta no `.gitignore`; nunca o comite. No GitHub
Actions, use **Run workflow** e preencha ramos, ano e, para periodo parcial,
`periodo_ini`/`periodo_fim`.

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
