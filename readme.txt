# PPGComp Lattes

Sistema de coleta, processamento e avaliação da produção científica do Programa de Pós-Graduação em Computação (PPGComp), a partir dos currículos Lattes de professores e alunos, considerando a classificação Qualis das publicações.

## Requisitos

- Python 3
- Ambiente virtual (`venv`)
- Dependências listadas em `requirements.txt`

## Instalação e execução

### 1. Ativar o ambiente virtual

```bash
source .venv/bin/activate
```

### 2. Executar o processamento

```bash
python3 -m app.runner
```

### 3. Executar a aplicação web

```bash
gunicorn --bind 127.0.0.1:5000 web.app:app
```

A aplicação ficará disponível localmente em:

```text
http://127.0.0.1:5000
```

## Persistência de overrides e flags (opcional)

Em produção (Render), o sistema de arquivos é efêmero. Para manter os
ajustes manuais de Qualis e as flags de aluno entre deploys, configure
um GitHub Gist **secreto** com os arquivos `qualis_overrides.json` e
`publication_flags.json`:

| Variável | Descrição |
|---|---|
| `GITHUB_TOKEN` | PAT com escopo `gist`. |
| `GIST_ID` | ID do Gist secreto. |
| `GIST_TIMEOUT_SECONDS` | Timeout de cada chamada ao GitHub (padrão: `5`). |
| `GIST_CACHE_TTL_SECONDS` | Validade do cache em memória (padrão: `30`). |

Sem essas variáveis, o sistema usa somente os arquivos em `output/`.
Se o Gist estiver configurado mas inacessível (token inválido, sem
rede etc.), a aplicação continua funcionando com o arquivo local e
registra um aviso no log — as rotas da API nunca deixam de responder
JSON por causa disso.

## Entradas do sistema (Inputs)

O sistema utiliza três conjuntos de dados como entrada:

| Entrada | Descrição |
|---|---|
| **Professores** | Lista de currículos Lattes dos professores do programa. |
| **Alunos** | Lista de alunos coautores das publicações. |
| **Qualis** | Arquivo JSON contendo a classificação Qualis das publicações. |

## Atualização do repositório

Após realizar alterações no código ou nos dados, execute:

```bash
git status
git add .
git commit -m "Atualiza dados do Lattes"
git push
```

## Tecnologias

- Python
- Flask
- Gunicorn
- Git / GitHub
- Currículo Lattes
- Qualis CAPES

---

**PPGComp – Programa de Pós-Graduação em Computação**  
Universidade Federal do Rio Grande (FURG)
