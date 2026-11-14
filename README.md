# Ava_14

API que consulta notícias de um jogo na Steam e uma pipeline que acompanha essas rotas. Quando uma rota fica atrás do catálogo público da Steam, ou quando a falha controlada acontece, o Cursor Agent escreve uma análise em português no pull request.

A aplicação em si devolve as notícias. Ela não gera texto para o usuário. A IA entra só na pipeline, para explicar um aviso de manutenção ou uma falha de teste. Essa análise não altera arquivos nem aplica correção.

## O que a aplicação faz

- Expõe uma API HTTP com FastAPI.
- Consulta `ISteamNews/GetNewsForApp` na Web API pública da Steam e devolve até 10 notícias, com o texto limitado a 300 caracteres.
- A rota principal usa a versão 2. A versão 1 continua no código para a pipeline comparar as duas com o catálogo da Steam.
- Na pipeline, compara as rotas usadas com `ISteamWebAPIUtil/GetSupportedAPIList`. Se a versão chamada for menor que a maior versão listada, publica um aviso. O teste continua passando.
- Pede ao Cursor Agent a explicação desse aviso e a análise da falha controlada. Os dois resultados viram comentário no pull request.

Cada notícia traz `gid`, `title`, `url`, `author` e `contents`. Autor e conteúdo podem vir vazios.

## Requisitos

- Python 3.12, a versão usada na pipeline.
- Git, para a análise incluir os commits recentes.
- Conexão com a internet para consultar a Steam.
- Uma chave do Cursor, somente para a análise do agente. A API de notícias não usa essa chave.

## Instalação

Na raiz do projeto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

No Linux ou no macOS, ative o ambiente com `source venv/bin/activate`.

## Configuração

Crie um arquivo `.env` na raiz, ao lado de `requirements.txt`:

```text
CURSOR_API_KEY=sua_chave
```

O arquivo está no `.gitignore`. A leitura acontece na hora da análise. Um valor já presente no ambiente tem prioridade sobre o `.env`.

Sem essa variável, a API de notícias continua funcionando. A análise do aviso ou da falha responde que não pôde ser feita porque a chave não está definida.

Na pipeline, o mesmo nome precisa existir como secret do repositório. O workflow declara `CURSOR_API_KEY` a partir de `secrets.CURSOR_API_KEY`. Guardar o secret no GitHub não basta: o job só enxerga o valor que o YAML mapeia.

## Como executar

Na raiz, com o ambiente virtual ativo:

```powershell
uvicorn app.main:app --reload
```

A API fica em `http://127.0.0.1:8000`. A documentação interativa fica em `http://127.0.0.1:8000/docs`.

### Rotas

| Método | Caminho | Resposta |
| --- | --- | --- |
| `GET` | `/` | `{"message": "Ava_14 API está funcionando!"}` |
| `GET` | `/health` | `{"status": "healthy"}` |
| `GET` | `/games/{app_id}/news` | Notícias pela versão 2 |
| `GET` | `/games/{app_id}/news/v1` | Notícias pela versão 1 |

`app_id` é o identificador numérico do jogo na Steam. Um exemplo usado nos testes é `730`:

```text
http://127.0.0.1:8000/games/730/news
```

Um `app_id` menor ou igual a zero, ou um corpo que não tenha o formato esperado, responde `400`. Uma falha ao consultar a Steam responde `502`.

## Testes e verificação local

Na raiz, com o ambiente ativo:

```powershell
pytest -v
ruff check .
ruff format --check .
mypy --strict app/
```

O Pytest ignora a falha controlada, a menos que `CI_CONTROLLED_FAILURE` seja `true`. Esse teste existe para deixar um job da pipeline vermelho de propósito. Para reproduzir só esse caso:

```powershell
$env:CI_CONTROLLED_FAILURE = "true"
pytest -v tests/test_controlled_failure.py
```

Esse comando chama o agente de verdade se `CURSOR_API_KEY` estiver definida e termina com falha. É o comportamento esperado.

Os testes de manutenção consultam o catálogo real da Steam. Se a versão guardada no código estiver atrás da versão listada, o Pytest passa e emite um aviso. Fora do GitHub Actions, esse aviso aparece no resumo do Pytest e o arquivo `maintenance-report.md` não é criado.

## Pipeline

O workflow em `.github/workflows/ci.yml` roda apenas quando um pull request é aberto ou atualizado. Um push direto não inicia os jobs.

O job `tests` instala as dependências, executa o Pytest, publica o relatório de manutenção e roda Ruff e MyPy. O aviso fixo da Steam aparece como anotação **Manutenção da Steam**. A explicação do agente fica no comentário marcado com `<!-- ava14-steam-maintenance -->`, na seção **Explicação**.

O job `Falha controlada` executa só `tests/test_controlled_failure.py`. O teste pede a análise ao agente e depois relança o `AssertionError`, então o check fica vermelho. A análise é publicada como anotação **Análise da falha** e como comentário marcado com `<!-- ava14-pipeline-failure -->`.

Os dois relatórios, `maintenance-report.md` e `failure-report.md`, são gerados na execução e estão no `.gitignore`.

## Estrutura

```text
app/
  main.py                 Rotas HTTP
  config.py               Leitura do .env e da CURSOR_API_KEY
  agents/
    failure_analyzer.py   Chamada ao Cursor Agent
  services/
    steam_service.py      Consulta de notícias
    steam_endpoints.py    Rotas e versões usadas
    steam_catalog.py      Comparação com o catálogo da Steam
  exceptions/
    error_messages.py     Mensagens exibidas pela API e pela análise
tests/                    Testes da API, do catálogo e do agente
.github/workflows/ci.yml  Pipeline do pull request
```
