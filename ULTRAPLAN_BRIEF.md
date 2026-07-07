# Briefing para o /ultraplan — Prepara ENEM

Este documento consolida tudo que foi definido/discutido antes da sessão de planejamento. Use como contexto de entrada do `/ultraplan`.

## 1. Visão do produto

Sistema preparatório para o ENEM com:
- **Simulados** gerados a partir de um banco de questões reais do ENEM
- **TRI (Teoria de Resposta ao Item)** para estimar proficiência do aluno, com estratégia de cold-start (ver seção 3)
- **Relatório personalizado por aluno**: questões erradas, o que mais afetou o TRI, tempo gasto por questão (para identificar em que assuntos/áreas o aluno perde mais tempo)
- **Correção de redação com IA** (feature futura, não é do MVP)
- **Login multi-perfil**: escolas (gestão de alunos/turmas), alunos vinculados a uma escola, alunos individuais (sem vínculo institucional)

## 2. Dataset de questões (já está no repositório)

Formato compatível com a API pública `enem.dev`, já commitado neste repo:
- `exams.json` — índice de todas as provas (2009–2023): título, ano, disciplinas, idiomas
- Uma pasta por ano (`2009/` a `2023/`), cada uma com:
  - `details.json` — metadados da prova + lista de questões (índice, disciplina, idioma)
  - `questions/<index[-idioma]>/details.json` — questão completa: `context` (enunciado), `alternatives` (A–E com texto e imagem opcional), `correctAlternative` (gabarito), `discipline`, `files` (imagens de apoio)
- **Totais confirmados**: 2.757 questões, 96MB, ~4.657 arquivos, 15 anos de provas
- 4 áreas: Ciências Humanas, Ciências da Natureza, Linguagens (com variantes Espanhol/Inglês), Matemática
- `broken-image.svg` é só um placeholder de imagem quebrada, não faz parte do dataset

**Ainda falta**: o banco de dados de redações (o usuário vai fornecer/definir a fonte à parte, ou usar os corpora públicos listados na seção 5).

## 3. Estratégia de TRI (cold-start → calibração real)

**Fase 1 — bootstrap (sem dados de resposta)**
- Classificar cada questão por assunto/tema e dificuldade estimada via Gemini API (Flash-Lite), lendo `context` + `alternatives`
- Parâmetros iniciais do modelo 3PL: `b` (dificuldade) = estimativa do Gemini; `a` (discriminação) fixo em ~1; `c` (acerto ao acaso) fixo em ~1/nº de alternativas (0.2 para 5 alternativas)
- Campo sugerido no schema: `difficulty_source` (`llm_estimate` vs `calibrated`)
- Custo: ~2.757 questões × ~600 tokens de entrada / ~80 de saída ≈ **$0,25 único**, ou **$0 se rodar dentro do free tier** (1.500 req/dia do Gemini Flash/Flash-Lite)

**Fase 2 — calibração real (conforme acumula respostas)**
- Job periódico server-side (sem custo de API) usando modelo 2PL/3PL via EM / máxima verossimilhança marginal
- Bibliotecas candidatas: `py-irt` ou `girth` (Python), `mirt` (R)
- Usar a estimativa do Gemini como *prior* bayesiano em vez de partir do zero — estabiliza a calibração com poucos dados
- Regra de bolso: calibração fica estatisticamente confiável a partir de ~200+ respondentes por item

## 4. Relatório personalizado + tracking de tempo

- Registrar por resposta: `student_id`, `question_id`, `alternativa_escolhida`, `correta` (bool), `tempo_gasto_ms`, `timestamp`, `simulado_id`
- Relatório é **agregação de dados** (SQL + fórmulas de TRI já calculadas) — não precisa de LLM, custo $0
- Conteúdo do relatório: questões erradas agrupadas por assunto/área, impacto de cada erro no `theta` (proficiência) do aluno, tempo médio por questão comparado à média geral (para identificar onde o aluno "trava")
- Opcional (custo baixo, não essencial): usar Gemini para gerar um parágrafo narrativo em cima dos dados agregados

## 5. Correção de redação com IA (feature futura)

**Datasets públicos para validar/calibrar o prompt de correção** (não são redações oficiais do ENEM — INEP não libera isso por privacidade; são corpora corrigidos por especialistas usando os mesmos critérios):
- [Essay-BR](https://github.com/rafaelanchieta/essay) — ~4.570 redações
- [Essay-BR estendido](https://github.com/lplnufpi/essay-br) — 6.563 redações, nota por competência + nota final
- [Banco de Redações UOL (XML)](https://github.com/gpassero/uol-redacoes-xml) — ~2.100 redações, 111 propostas temáticas, nota 0-2 por competência

**Abordagem recomendada**: não fazer fine-tuning (datasets pequenos demais pra isso). Usar como:
1. Conjunto de validação — rodar o prompt de correção (rubrica das 5 competências) contra essas redações já corrigidas por humanos e medir a proximidade da nota
2. Few-shot no prompt — incluir 2-3 exemplos de redação + nota + justificativa para calibrar a régua do modelo

**Custo estimado por redação**: ~$0,002 (Gemini Flash) a ~$0,009 (Gemini Pro, correção mais criteriosa). Free tier cobre até 1.500 correções/dia.

## 6. Estimativa de custo e capacidade (infra gratuita)

| Recurso | Free tier | Capacidade estimada aqui |
|---|---|---|
| Supabase DB | 500MB | Dataset de questões usa só ~5MB. Cada resposta de aluno (~250 bytes) → ~1,5-2M respostas cabem → **~1.700-2.000 alunos ativos** (5 simulados/aluno) antes de precisar upgrade |
| Supabase Storage | 1GB | Imagens das questões = ~90MB atuais, sobra espaço |
| Supabase MAU | 50.000 | Não é gargalo nessa escala |
| Render (backend) | 750h/mês (cobre 24/7) | Grátis, mas "dorme" após 15min sem tráfego (~1min pra acordar) — ok pra MVP |
| Gemini Flash | 1.500 req/dia, 10 req/min | Cobre classificação inicial + até 1.500 correções de redação/dia de graça |

**Resumo**: até ~1.500-2.000 alunos ativos com uso moderado, o sistema roda em **~$0/mês**. Acima disso, Supabase Pro entra em ~$25/mês (ao estourar 500MB), e o Gemini continua barato (~$20/mês para 10.000 redações/mês com Flash). O gargalo real é o banco de dados gratuito (500MB), não a API do Gemini.

⚠️ Preços e limites de free tier mudam com frequência — confirmar na doc oficial antes de travar decisões de arquitetura.

## 7. Em aberto para o /ultraplan decidir

- Stack tecnológica (linguagem/framework de backend, frontend, ORM)
- Modelagem exata do schema do banco (import do JSON de questões → tabelas relacionais)
- Desenho da autenticação multi-perfil (escola / aluno-de-escola / aluno-individual) — hierarquia de permissões, multi-tenancy por escola
- Design da API de simulados (geração adaptativa vs. fixa, quantas questões por simulado, seleção por TRI)
- Onde deixar o gancho para a futura correção de redação (schema de submissão de redação, fila de processamento assíncrono)
- Job scheduler para a recalibração periódica de TRI (cron, worker separado, etc.)
