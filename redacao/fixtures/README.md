# Fixtures de validação da correção por IA

`essay_br_sample.csv` — amostra de 20 redações do corpus público **Essay-BR**
(https://github.com/rafaelanchieta/essay, licença MIT), com o tema, o texto
motivador e as notas por competência (0-200, já na escala oficial do ENEM)
atribuídas por corretores humanos. Usada pelo comando
`validate_essay_prompt` para medir a proximidade entre a nota do modelo e a
nota humana antes de habilitar a correção por IA para alunos reais.

Não é redação oficial do ENEM (o INEP não libera isso por privacidade) — é um
corpus corrigido por especialistas usando os mesmos critérios. Amostra
pequena de propósito (apenas para validação de desenvolvimento); para uma
validação estatisticamente robusta, baixe o corpus completo (~4.570
redações) do repositório original.
