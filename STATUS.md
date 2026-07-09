# Status do Prepara ENEM

Documento vivo: registra o que já existe (pra não redescobrir nada) e o roadmap de mudanças futuras, por prioridade. Atualizar aqui sempre que algo relevante mudar de plano.

Última atualização: 2026-07-09

## O que já temos (implementado e testado em produção)

**Infra**
- Django 5.2 + Postgres (Neon, região `sa-east-1`) + Cloud Run (deploy via Dockerfile, Python 3.12) + Gemini API
- Repositório: `github.com/PedroVNeves/prepara-enem`, produção em `https://prepara-enem-pw3vw6bmvq-rj.a.run.app`
- GitHub Action de keep-alive (ping a cada 10min, variável `APP_URL` configurada)
- ⚠️ **Deploy manual necessário**: o gatilho do Cloud Build constrói a imagem automaticamente a cada push, mas não cria uma revisão nova no Cloud Run sozinho — depois de cada push é preciso ir em Cloud Run → "Editar e implantar nova revisão" e confirmar manualmente, usando a imagem `southamerica-east1-docker.pkg.dev/prepara-enem-501721/cloud-run-source-deploy/pedrovneves-prepara-enem/prepara-enem:latest` (não a sugestão pré-preenchida do Container Registry legado, que aponta pra outro lugar). Não descobrimos a causa raiz ainda — fica como dívida técnica de infra.

**Dataset**
- 2757 questões do ENEM (2009–2023) importadas — texto, alternativas, gabarito, imagens
- Import otimizado (`exams/management/commands/import_enem_dataset.py`): upsert em lote, ~15s pro dataset inteiro (era horas com a versão ingênua de uma query por linha)
- Taxonomia de tópicos carregada (`exams/fixtures/topics.json`, 41 tópicos)
- Gap conhecido: questão 132 do ENEM 2023 tem 4 das 5 alternativas vazias — falha da fonte original (enem.dev), não do nosso import. Único caso em todo o dataset (0,04%). Não tratado — decisão pendente (deixar como está ou excluir a questão).

**TRI (Teoria de Resposta ao Item)**
- Bootstrap via Gemini (`irt/management/commands/classify_questions_llm.py`): classifica assunto + dificuldade inicial em lotes de 25 questões por chamada (respeita rate limit de 15 req/min do free tier). Todas as 2757 questões classificadas.
- Calibração real via `girth` (EM/máxima verossimilhança marginal) — `irt/services.py`, roda quando um item acumula respondentes suficientes.

**Login multi-perfil**
- Escolas (Professor/Escola/Turma), alunos vinculados a escola, alunos individuais (`AlunoProfile` com `escola=None`) — todos via `accounts` app, com seletor de contexto pós-login.

**Simulados — ESTADO ATUAL (vai mudar, ver Roadmap #1)**
- Dois modos hoje, nenhum dos dois é o que o produto deveria ser:
  1. **Prova fixa** (`simulados:start`, `SimuladoStartView`) — aluno escolhe uma prova histórica completa (ex: "ENEM 2023") e faz ela inteira, na ordem original.
  2. **Customizado** (`simulados:start_custom`, `SimuladoCustomStartView`) — aluno escolhe 1 disciplina + tópico opcional + quantidade, gera um pool filtrado aleatório dessa combinação específica.
- **Isso não é o que foi pedido** — ver Roadmap #1.

**Relatório do aluno**
- Dashboard interativo com D3.js (`reports/templates/reports/student_report.html` + `core/static/core/js/charts.js`): domínio por área (gráfico diverging azul/vermelho), domínio por assunto, erros por assunto, tempo por questão vs. média geral, impacto de erros na proficiência. Tooltips, legendas, alternância pra tabela em cada gráfico. Paleta validada pela skill de dataviz do projeto.
- Mesma view reaproveitada pelo professor pra ver o relatório de um aluno específico (`AlunoStatsView`).

**Redação**
- Modelos e views existem (`redacao` app): submissão, atribuição por professor, correção manual. Fixtures do corpus Essay-BR presentes pra validação futura do prompt.
- ⚠️ **Correção automática via IA ainda não está conectada de fato** — precisa verificar/implementar o fluxo real de chamada ao Gemini pra correção (`llm/client.py` existe como wrapper genérico, mas não confirmei se `redacao/services.py` já usa isso pra corrigir).

**Estilização**
- CSS básico próprio (`core/static/core/css/main.css`, sem framework externo), cabeçalho com troca de contexto e logout.

## Problemas / dívida técnica conhecida

1. Deploy manual necessário no Cloud Run (ver acima)
2. Redação: confirmar se a correção por IA está de fato implementada ou só a estrutura de dados existe
3. Questão 132/2023 com alternativas vazias — decidir o que fazer
4. Nunca testamos o fluxo completo de "professor cria turma, vincula aluno, atribui simulado/redação" ponta a ponta

## Roadmap — por prioridade

### 1. [PRIORIDADE MÁXIMA] Repensar geração de simulados

Feedback direto do usuário (2026-07-09): **o modelo atual não é o que foi pedido, nada do que existe hoje reflete a visão do produto.**

O que deve existir:
- **Um banco de questões único**, não provas históricas isoladas — todas as 2757 questões (todos os anos) formam um pool só.
- Cada simulado deve ser **gerado aleatoriamente respeitando a distribuição real de matérias do ENEM** (a proporção de questões por área — Linguagens, Ciências Humanas, Ciências da Natureza, Matemática — como no exame real), não uma prova histórica fixa nem uma escolha manual de 1 disciplina.
- **Nunca deve haver dois simulados idênticos** para o mesmo aluno (alta variabilidade — amostragem aleatória do pool a cada geração, evitando repetir o mesmo conjunto de questões).
- **Esse deve ser o fluxo padrão/principal**, não uma opção secundária — quando um aluno individual ("solo") entra pra fazer um simulado, é isso que ele deve ver primeiro. O usuário testou como aluno solo e "não viu nada disso".
- O modo "fazer uma prova histórica completa" pode continuar existindo como opção secundária (tipo "quero fazer o ENEM 2015 inteiro, como caiu de verdade"), mas não é mais o caminho principal.

Implicações técnicas a considerar quando for implementar:
- Provavelmente precisa de uma nova função em `simulados/services.py` (algo como `start_simulado_enem_completo` ou substituir o `start_fixed_simulado` atual) que amostra do pool inteiro respeitando proporções por `Discipline`.
- Pensar em como registrar/evitar repetição — talvez um histórico de `question_id`s já usados pelo aluno, com preferência por questões não vistas até esgotar o pool.
- Decidir a UI: a tela `simulados:start` (`start.html`) deixa de ser "escolha uma prova" e vira algo tipo "gerar simulado completo" com um botão único, movendo a escolha de prova histórica pra um lugar secundário.

### 2. Dashboards do banco de questões

Usuário mencionou "banco de questões dashboards" — a interpretação provável é um painel mostrando estatísticas do **banco de questões em si** (quantas questões por matéria/tópico/dificuldade, cobertura da taxonomia, distribuição de parâmetros TRI calibrados vs. estimados pelo LLM, etc.), não o relatório de desempenho do aluno (que já existe). **Confirmar com o usuário antes de implementar** — ficou ambíguo no pedido original.

## Convenções

- Sempre rodar a suíte de testes local antes de commitar (`python manage.py test`, com `.env` trocado temporariamente pra usar SQLite — ver histórico de sessões anteriores pro procedimento exato).
- Sempre validar visualmente mudanças de UI com Playwright antes de considerar pronto (screenshots + checagem de erros de console).
- Depois de todo push, lembrar do passo de implantação manual no Cloud Run (ver "Problemas conhecidos" #1).
