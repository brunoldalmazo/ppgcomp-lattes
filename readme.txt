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
