# Especificação — Produção técnica (patentes, software e desenho industrial)

Status: **aprovada, pronta para implementação**
Repositório: `ppgcomp-lattes` (branch `main`)
Última atualização: 2026-11-11

---

## 1. Objetivo

Hoje o scraper coleta **apenas** artigos de periódico (`type: "journal"`) e
trabalhos em anais (`type: "conference"`). Esta especificação adiciona a
coleta e a pontuação de:

1. Patente de invenção ou modelo de utilidade **concedido** — **1,00 ponto**
2. Patente de invenção ou modelo de utilidade **depositado** — **0,15 ponto**
3. Programa de computador **registrado** — **0,05 ponto**
4. Desenho industrial **registrado** — **0,05 ponto**

Programas de computador **sem registro** e itens de produção técnica que não
se enquadrem nas 4 categorias acima **não entram** nesta fase.

---

## 2. Decisões aprovadas (não reabrir sem o utilizador)

| Código | Decisão |
|---|---|
| D1 | **A** — dividir os pontos entre os professores PPGComp que listam o item (mesma lógica de `individual_points` das publicações) |
| D2 | **A** — cada patente conta **uma vez**, com o melhor status (concedida > depositada) |
| D3 | **A** — filtro de período pelo **ano do evento**: concessão (se concedida), senão depósito; para software/desenho industrial, ano do registro |
| D4 | Coluna nova **“Produção técnica”** na tabela, **entre A4 e Alunos**, com o somatório de pontos da categoria |
| D5 | **A** — aba nova **“Produção Técnica”** no Excel |

O `Total` do professor passa a ser:

```
total = pontos de publicações (Qualis) + technical_points
```

O `status` (`ATENDE` / `NÃO ATENDE`) continua a ser calculado sobre o `total`.

---

## 3. Fontes no HTML do Lattes

Os HTMLs já estão salvos em `output/raw/*.html` (28 ficheiros). **Não é
necessário novo scrape nem acesso à rede.**

### 3.1 Secções relevantes

| Cabeçalho no Lattes | Categoria interna |
|---|---|
| `Patente` | patente (invenção ou modelo de utilidade) |
| `Programa de computador` | software registrado |
| `Programa de computador registrado` | software registrado |
| `Desenho industrial` | desenho industrial registrado |
| `Desenho industrial registrado` | desenho industrial registrado |

Ignorar explicitamente:

- `Programas de computador sem registro`
- `Programa de Computador sem registro de patente`
- `Produtos tecnológicos`, `Processos ou técnicas`, `Trabalhos técnicos`,
  `Demais tipos de produção técnica`

### 3.2 Como delimitar cada secção

NÃO usar o `name` do anchor (`a[name="..."]`): há anchors duplicados e alguns
apontam para blocos maiores que contêm outras subsecções.

Usar o **texto do cabeçalho** em elementos `div.inst_back` e
`div.cita-artigos`, na ordem do documento:

1. Para cada cabeçalho cujo texto (normalizado, removendo “Ordenar por ...”)
   esteja na tabela acima:
2. Coletar os `div.layout-cell-11` **irmãos seguintes** até encontrar o próximo
   `div.inst_back` ou `div.cita-artigos`.
3. O texto do item vem de `get_text(" ", strip=True)`, normalizado com
   `re.sub(r"\s+", " ", ...)`.

Este padrão já é usado com sucesso em `extract_conference_papers()`.

### 3.3 Campos dentro de cada item

Exemplos reais:

```
Borges, Eduardo N. ; ROSA, V. S. ; ... . Sistema e método para desligamento
seguro de computadores em veículos. 2024, Brasil. Patente: Privilégio de
Inovação. Número do registro: BR1020240245865, título: "...", Instituição de
registro: INPI - Instituto Nacional da Propriedade Industrial.
Depósito: 26/11/2024; Pedido do Exame: 29/05/2025.
```

```
... . VDDB-Assembly. 2021. Patente: Programa de Computador.
Número do registro: BR512024003904-0, data de registro: 30/09/2021, ...
```

```
... . Leitor de cartão RFID. 2024, Brasil. Patente: Desenho Industrial.
Número do registro: BR302024003304-4, data de registro: 09/09/2024, ...
```

Expressões regulares sugeridas:

| Campo | Regex |
|---|---|
| autores/título/ano | `^(.*?)\s+\.\s+(.*?)\.\s+(\d{4})` |
| número de registro | `Número do registro:\s*([^,\s]+)` |
| data de depósito | `Depósito:\s*(\d{2}/\d{2}/\d{4})` (não confundir com `Depósito PCT:`) |
| data de concessão | `Concessão:\s*(\d{2}/\d{2}/\d{4})` |
| data de registro (software/DI) | `data de registro:\s*(\d{2}/\d{2}/\d{4})` |
| tipo de patente | `Patente:\s*([^.]+?)\.` |

Regras de classificação:

- `Patente: Modelo de Utilidade` → `patent_kind = "utility_model"`
- `Patente: Privilégio de Inovação` → `patent_kind = "invention"`
- Se houver `Concessão:` → `status = "granted"`
- Senão, se houver `Depósito:` → `status = "deposited"`
- Software/DI com `Número do registro:` → `status = "registered"`

Guardar sempre o texto original em `raw`, para auditoria e fallback.

### 3.4 Números verificados (dry-run de referência)

Calculados sobre os 28 HTMLs, com deduplicação global por número de registro:

| Categoria | Itens únicos |
|---|---:|
| Patentes (invenção + modelo de utilidade) | **25** |
| — invenção (`Privilégio de Inovação`) | 19 |
| — modelo de utilidade | 6 |
| — concedidas | 5 |
| — depositadas | 20 |
| Programas de computador registrados | **132** |
| Desenhos industriais registrados | **10** |

Se a Fase 0 encontrar números diferentes, **não continuar** sem explicar a
diferença.

---

## 4. Modelo de dados

### 4.1 Por currículo (`lattes_data[i]`)

Adicionar a chave `technical_production` (lista). Cada item:

```json
{
  "type": "patent",                  // patent | software | industrial_design
  "patent_kind": "invention",        // invention | utility_model | null
  "status": "granted",               // granted | deposited | registered
  "title": "Sistema e método para desligamento seguro de computadores em veículos",
  "year": 2024,
  "authors": "Borges, Eduardo N. ; ROSA, V. S. ; ...",
  "country": "Brasil",
  "registry_number": "BR1020240245865",
  "registry_institution": "INPI - Instituto Nacional da Propriedade Industrial",
  "deposit_date": "2024-11-26",
  "grant_date": null,
  "source_section": "Patente",
  "raw": "texto original completo do item"
}
```

Notas:

- `year` é o **ano do evento** (D3).
- `deposit_date`/`grant_date` em ISO (`YYYY-MM-DD`).
- `country` só quando o texto tiver o padrão `, Brasil.` / `, <País>.`;
  caso contrário `null`.
- `patent_kind` é `null` para software e desenho industrial.

### 4.2 Por professor (`professors[<nome>]`)

Adicionar:

```json
"technical_counts": {
  "patent_granted": 1,
  "patent_deposited": 0,
  "software_registered": 2,
  "industrial_design": 0
},
"technical_points": 1.10
```

E `total` deve incluir `technical_points`.

**Não alterar**:

- `counts` (A1–A4)
- `points` (Qualis)
- `publications`
- `coauthored_publications`
- `student_author_publications`
- `pending`
- `coauthorships`

### 4.3 Topo do `dados.json`

Adicionar (opcional, mas recomendado) a lista agregada:

```json
"technical_production": [
  {
    "professor": "Nome do professor",
    "type": "patent",
    "status": "granted",
    "title": "...",
    "year": 2024,
    "registry_number": "...",
    "points": 1.0,
    "shared_with": ["Outro Professor"]
  }
]
```

---

## 5. Algoritmo de pontuação

Constantes (em `app/config.py` ou módulo novo):

```python
TECHNICAL_WEIGHTS = {
    ("patent", "granted"): 1.00,
    ("patent", "deposited"): 0.15,
    ("software", "registered"): 0.05,
    ("industrial_design", "registered"): 0.05,
}
```

Passos em `evaluate_professors()` (espelhar o que já existe para publicações):

1. Para cada professor, filtrar `technical_production` pelo período
   `start_year <= year <= end_year` (D3).
2. Deduplicar por professor usando `technical_key(item)`:
   - `registry_number` normalizado (maiúsculas, sem espaços), se existir;
   - fallback: `(type, normalize_title(title), year)`.
3. Construir `technical_index`: chave → lista de professores que a listam.
4. Deduplicar globalmente e resolver D2:
   - a mesma patente aparece em vários CVs e em várias vistas;
   - agrupar por chave;
   - se qualquer ocorrência tiver `grant_date`, o item é **concedido**;
   - caso contrário, **depositado**.
5. Pontos do item = `TECHNICAL_WEIGHTS[(type, status)]`.
6. Pontos do professor para o item = `pontos_do_item / len(technical_index[key])`
   (D1), contando apenas professores avaliados.
7. Somar em `technical_points` e nos respetivos `technical_counts`.
8. `total = total_publicacoes + technical_points`.

Arredondamento: manter precisão total no cálculo; arredondar só na
apresentação (3 casas decimais).

---

## 6. Ficheiros a alterar

| Ficheiro | Alteração |
|---|---|
| `app/lattes.py` | novo(s) extrator(es) de produção técnica; incluir `technical_production` no retorno de `collect_lattes()` (nos dois caminhos: cache e scrape) |
| `app/metrics.py` | índice, filtro por período, dedup, pontuação, `technical_counts`, `technical_points`, `total` |
| `app/export.py` | sem alteração obrigatória (`lattes_data` é gravado como está); se quiseres o agregado do ponto 4.3, adicionar aqui |
| `app/export_excel.py` | nova aba `Produção Técnica`; aceitar `lattes_data` opcional |
| `app/runner.py` | passar `lattes_data` para `export_excel()` |
| `web/templates/index.html` | coluna “Produção técnica” entre A4 e Alunos; atualizar `colspan` de 10 para 11 |
| `readme.txt` | documentar a nova categoria e a pontuação |

Não é necessário alterar `web/app.py`: os campos novos chegam ao frontend pelo
`/api/avaliacao` e pelo `dados.json` já existentes.

---

## 7. Interface (D4)

Na tabela de professores (`renderTable`), a ordem das colunas passa a ser:

```
# | Professor | Atualização Lattes | A1 | A2 | A3 | A4 | Produção técnica | Alunos | Total | Status
```

- Cabeçalho: **Produção técnica**
- Valor: `Number(professor.technical_points || 0).toFixed(3)`
- Atualizar **todos** os `colspan="10"` para `colspan="11"` (loading, vazio,
  erro e `loading` inicial).
- Não alterar as colunas existentes nem o modal nesta fase.

---

## 8. Excel (D5)

Nova folha **`Produção Técnica`** com as colunas:

| Professor | Tipo | Subtipo | Status | Título | Ano | Nº Registro | Instituição | Data depósito | Data concessão | Pontos |
|---|---|---|---|---|---|---|---|---|---|---|

- Uma linha por item/professor.
- Pontos já divididos (D1).
- Manter as folhas atuais intactas.

---

## 9. Fases e critérios de aceite

### Fase 0 — Dry-run (não altera `dados.json`)

Entregar um relatório com:

- contagem global por categoria;
- contagem por professor;
- patentes concedidas vs depositadas;
- duplicados removidos (chave e nº de ocorrências);
- itens com `Número do registro` não parseado;
- itens sem ano.

Critérios de aceite:

- Patentes únicas = 25 (19 invenção, 6 modelo de utilidade; 5 concedidas, 20 depositadas).
- Software registrado = 132.
- Desenho industrial = 10.
- Zero alterações no repositório além do script de dry-run (que pode ficar em
  `scripts/dry_run_producao_tecnica.py`).
- Qualquer divergência explicada.

### Fase 1 — Coleta + pontuação + JSON

- `python3 -m app.runner` sem acesso à rede (reutiliza `output/raw`).
- `dados.json` contém `technical_production`, `technical_counts` e
  `technical_points`.
- `total` inclui a produção técnica.
- `publications`, `pending`, `coauthorships` e `counts` inalterados.
- `python3 -m compileall app` sem erros.

### Fase 2 — UI

- Coluna presente entre A4 e Alunos, com 3 casas decimais.
- `colspan` correto em todos os estados.
- Sem erros de JavaScript no browser.

### Fase 3 — Excel

- Aba `Produção Técnica` criada.
- Folhas antigas inalteradas.
- Soma dos pontos da aba coincide com `technical_points` do JSON.

---

## 10. Garantias e restrições

- **Não** misturar produção técnica em `publications`.
- **Não** enviar produção técnica para `pending` (não depende de Qualis).
- **Não** alterar a lógica de Qualis nem os pesos A1–A8.
- **Não** fazer novo scrape; usar `output/raw`.
- Manter compatibilidade com `dados.json` antigo (campo ausente = lista vazia).
- Preservar estilo e estrutura atuais do projeto (sem novas dependências).

---

## 11. Comandos úteis

```bash
# dry-run (Fase 0)
python3 scripts/dry_run_producao_tecnica.py

# reprocessar tudo (Fase 1) — usa cache dos HTMLs
python3 -m app.runner

# app local
.venv/bin/gunicorn --bind 127.0.0.1:5000 web.app:app

# checagem rápida
python3 -m compileall app
```
