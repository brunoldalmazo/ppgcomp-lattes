# PPGComp Lattes

Sistema para coleta e processamento de dados de produção científica a partir dos currículos Lattes, incluindo informações de professores, alunos coautores e classificação Qualis das publicações.

## Execução

### 1. Ativar o ambiente virtual

```bash
source .venv/bin/activate
```

### 2. Executar o sistema

```bash
python3 -m app.runner
```

## Atualização do repositório

Após realizar alterações no código ou nos dados:

```bash
git status
git add .
git commit -m "Atualiza dados do Lattes"
git push
```

## Entradas do sistema (Inputs)

O sistema utiliza três conjuntos de dados como entrada:

- **Professores:** lista de currículos Lattes dos professores do programa.
- **Alunos:** lista de alunos coautores das publicações.
- **Qualis:** arquivo JSON contendo a classificação Qualis das publicações.

gunicorn --bind 127.0.0.1:5000 web.app:app
