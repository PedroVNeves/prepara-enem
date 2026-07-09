# Status do Prepara ENEM

Documento vivo: registra o que já existe (pra não redescobrir nada) e o roadmap de mudanças futuras, por prioridade. Atualizar aqui sempre que algo relevante mudar de plano.

Última atualização: 2026-07-09

## O que já temos (implementado e testado em produção)

**Infra**
- Django 5.2 + Postgres (Neon, região `sa-east-1`) + Cloud Run (deploy via Dockerfile, Python 3.12) + Gemini API
- Repositório: `github.com/PedroVNeves/prepara-enem`, produção em `https://prepara-enem-pw3vw6bmvq-rj.a.run.app`
- GitHub Action de keep-alive (ping a cada 10min, variável `APP_URL` configurada)
- ✅ **Deploy automático resolvido** (2026-07-09): o gatilho (tipo "Dockerfile") nunca tinha um passo de deploy — só construía a imagem e empurrava pro Artifact Registry, por isso toda revisão nova no Cloud Run exigia implantação manual. Corrigido trocando o gatilho pra tipo "Arquivo de configuração do Cloud Build" apontando pro `cloudbuild.yaml` (raiz do repo), que builda, dá push com tag `$COMMIT_SHA` + `latest`, e roda `gcloud run deploy` explicitamente. Precisou de uma conta de serviço gerenciada pelo usuário no gatilho (com permissão de Cloud Run Admin) e `options.logging: CLOUD_LOGGING_ONLY` no YAML (obrigatório sempre que uma conta de serviço customizada é usada — a UI simplificada de gatilho por Dockerfile não expõe esse campo, só o modo YAML). Confirmado funcionando: push → build → deploy, sem clique manual.

**Dataset**
- 2757 questões do ENEM (2009–2023) importadas — texto, alternativas, gabarito, imagens
- Import otimizado (`exams/management/commands/import_enem_dataset.py`): upsert em lote, ~15s pro dataset inteiro
- Taxonomia de tópicos carregada (`exams/fixtures/topics.json`, 41 tópicos)
- Gap conhecido: questão 132 do ENEM 2023 tem 4 das 5 alternativas vazias — falha da fonte original (enem.dev), não do nosso import. Único caso em todo o dataset (0,04%). Não tratado — decisão pendente.

**TRI (Teoria de Resposta ao Item)**
- Bootstrap via Gemini (`irt/management/commands/classify_questions_llm.py`): classifica assunto + dificuldade em lotes de 25 questões por chamada. Todas as 2757 questões classificadas.
- Calibração real via `girth` (EM/máxima verossimilhança marginal) — `irt/services.py`.

**Login multi-perfil**
- Escolas (Professor/Escola/Turma), alunos vinculados a escola, alunos individuais (`AlunoProfile` com `escola=None`) — `accounts` app, com seletor de contexto pós-login (`SelectContextView`) para quando um mesmo `User` tem mais de um papel (ex: professor em uma escola + aluno individual).
- O modelo de dados já suporta "mesmo e-mail, dois contextos" (individual + vinculado a escola) — **falta o fluxo de cadastro que permite isso na prática** (ver Roadmap #2).

**Simulados — ESTADO ATUAL (vai mudar, ver Roadmap #3)**
- Dois modos hoje, nenhum dos dois é o modelo principal desejado:
  1. **Prova fixa** (`simulados:start`) — aluno escolhe uma prova histórica completa e faz ela inteira, na ordem original.
  2. **Customizado** (`simulados:start_custom`) — aluno escolhe 1 disciplina + tópico opcional + quantidade.
- Seleção por banda de dificuldade relativa ao theta do aluno já existe (`select_by_difficulty_band`), inclusive excluindo questões já respondidas — é uma boa base pra reaproveitar na reformulação.

**Relatório do aluno**
- Dashboard interativo com D3.js (`/aluno/relatorio/`): domínio por área (gráfico diverging azul/vermelho), domínio por assunto, erros por assunto, tempo vs. média geral, impacto de erros na proficiência. Tooltips, legendas, tabela alternativa. Paleta validada pela skill de dataviz do projeto.
- Tela de resultado pós-simulado (`/aluno/simulados/<id>/resultado/`) também tem dashboard: hero figure do percentual, gráfico de acerto por área (só quando o simulado cobre mais de uma disciplina), tabela de revisão questão a questão.
- Mesma view de relatório reaproveitada pelo professor pra ver o relatório de um aluno específico (`AlunoStatsView`) e de uma turma (`TurmaStatsView`).

**Redação — MAIS COMPLETA DO QUE PARECIA, só não está exposta na navegação**
- Aluno individual pode escrever uma redação livre (tema à escolha ou tema de um banco pré-cadastrado, `EssayPrompt`) — `/aluno/redacao/nova/`. Aceita Markdown na escrita.
- Professor pode atribuir redação a turma/alunos (`EssayAssignmentCreateView`): escolhe tema próprio OU pede pra IA gerar um tema+texto motivador (`generate_essay_theme`); escolhe modo de correção (manual ou IA).
- Se o modo é IA, o envio só aceita texto digitado (força `SubmissionType.TEXT`, foto vira texto) — já é a regra que queríamos ("foto só quando for correção manual, IA só texto por ora").
- **Correção por IA está de fato funcionando**: `redacao/services.py::correct_essay` chama o Gemini com a rubrica das 5 competências do ENEM, salva nota + feedback por competência. Roda automaticamente via fila (`ops/scheduler.py`, APScheduler, a cada 5 minutos, `ENABLE_SCHEDULER=True` em produção) — não é preciso nenhuma ação manual, a correção acontece sozinha em até ~5min após o envio.
- Correção manual pelo professor: nota + feedback por competência (`ProfessorEssayGradingView`).
- Fixtures do corpus Essay-BR presentes pra validação futura do prompt (não usado ainda em produção, só disponível pra teste).
- Falta: **LaTeX** (Markdown já funciona, LaTeX não — adiado, ver Roadmap).

**Estilização**
- CSS básico próprio (`core/static/core/css/main.css`, sem framework externo), cabeçalho com troca de contexto e logout.

## Problemas / dívida técnica conhecida

1. ~~Deploy manual necessário no Cloud Run~~ — **resolvido 2026-07-09**, ver "Infra" acima
2. Questão 132/2023 com alternativas vazias — decidir o que fazer
3. Nunca testamos o fluxo completo de "professor cria turma, vincula aluno, atribui simulado/redação" ponta a ponta
4. ~~Não existe nenhuma navegação entre as áreas do site~~ — **resolvido 2026-07-09**, ver "Roadmap" (navegação + página inicial)

## Roadmap — por prioridade

Ordem confirmada com o usuário em 2026-07-09. Pagamento e e-mail configurado ficam de fora por enquanto (usuário confirmou que não são prioridade agora); LaTeX também adiado.

### 1. ✅ Navegação + página inicial — feito (2026-07-09)

Menu de navegação em `base.html` (via `accounts.context_processors.active_context`, contexto-aware: links diferentes pra aluno/professor) + páginas iniciais dedicadas (`core.views.AlunoHomeView`/`ProfessorHomeView`, em `/aluno/` e `/professor/`) com atalhos e lista de simulados recentes / turmas. Verificado em produção.

### 2. [PRÓXIMO] Cadastro (self-registration)

Hoje só um admin/professor consegue criar contas (via `/admin` ou shell). Precisa:
- Tela de cadastro pra aluno individual (cria `User` + `AlunoProfile` com `escola=None`)
- Fluxo de aluno se vincular a uma escola usando o **mesmo e-mail** de uma conta individual já existente (ou vice-versa) — like ao logar, se o `User` tiver mais de um contexto, `SelectContextView` já pergunta qual usar (isso já existe); falta só o cadastro permitir chegar nesse estado.
- Cadastro de escola/professor também (hoje só existe via admin).

### 3. Repensar geração de simulados

Feedback direto do usuário (2026-07-09): o modelo atual (prova histórica fixa OU escolha manual de 1 disciplina) não é o que foi pedido.

O que deve existir:
- **Um banco de questões único** — todas as 2757 questões (todos os anos) formam um pool só, não provas isoladas por ano.
- Cada simulado **gerado aleatoriamente respeitando a distribuição real de matérias do ENEM** (proporção por área: Linguagens, Ciências Humanas, Ciências da Natureza, Matemática, como no exame real).
- **Nunca dois simulados idênticos** pro mesmo aluno — alta variabilidade, evitar repetir o mesmo conjunto de questões (já existe uma base disso em `select_by_difficulty_band`, que exclui questões já respondidas).
- **Esse é o fluxo padrão** que o aluno solo vê ao querer fazer um simulado — a prova histórica fixa vira opção secundária.

Implicações técnicas:
- Nova função em `simulados/services.py` que amostra do pool inteiro respeitando proporções por `Discipline` (reaproveitar a lógica de amostragem ponderada já existente).
- `simulados:start` (`start.html`) deixa de ser "escolha uma prova" — vira "gerar simulado completo", com a prova histórica fixa como opção secundária/avançada.

### 4. Histórico de simulados (versão básica)

Lista simples dos simulados já feitos pelo aluno (data, tipo, percentual, link pro resultado). Sem filtros/paginação sofisticada por ora — só o básico funcionando.

### Adiado (confirmado com o usuário — não fazer agora)

- LaTeX na redação (Markdown já funciona)
- Pagamento / planos (individual paga e entra; escola escolhe plano por quantidade de alunos)
- E-mail transacional configurado (hoje cai no console backend em dev; produção nunca configurou SMTP real)
- Upload de foto pra correção por IA de redação (hoje IA só aceita texto; foto é só pra correção manual)
- Dashboard do banco de questões em si (estatísticas de cobertura por matéria/tópico/dificuldade) — ficou ambíguo se é isso mesmo que o usuário quis dizer, confirmar antes de implementar se voltar à tona

## Convenções

- Sempre rodar a suíte de testes local antes de commitar (`python manage.py test`, com `.env` trocado temporariamente pra usar SQLite).
- Sempre validar visualmente mudanças de UI com Playwright antes de considerar pronto (screenshots + checagem de erros de console).
- Depois de todo push, lembrar do passo de implantação manual no Cloud Run (ver "Problemas conhecidos" #1).
