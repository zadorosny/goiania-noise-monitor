# Goiânia Noise 2026 — Monitor de Retirada de Ingressos

## Contexto

Quero ser notificado o mais rápido possível no instante em que a retirada de ingressos do **31º Goiânia Noise Festival** for aberta ao público.

**Dados do evento:**
- Datas: 7 a 10 de maio de 2026
- Local: Centro Cultural Oscar Niemeyer, Goiânia/GO
- Entrada: gratuita mediante doação de 1kg de alimento
- Produtora: Monstro Discos
- Edições anteriores (ex.: 2024) usaram retirada online gratuita para controle de lotação via plataformas como **Bilheteria Digital** e **Sympla** — ainda não se sabe qual será usada em 2026, nem se haverá retirada online.

Faltam cerca de 4 semanas para o festival, então a janela de execução é curta e o custo de falsos negativos (perder o anúncio) é muito maior que o de falsos positivos.

## O que eu quero de você, antes de escrever código

**Não assuma stack.** Antes de implementar qualquer coisa, quero discutir:

1. **Fontes a monitorar** — site oficial (`https://www.goianianoisefestival.com.br/`), Instagram (`@goianianoisefestival`), Bilheteria Digital, Sympla, e possivelmente outras que você identificar. Quais valem o esforço? Qual a probabilidade real de cada uma ser o canal primário do anúncio?
2. **Estratégia de detecção por fonte** — scraping HTML, API pública, RSS, monitor de mudanças genérico, serviços prontos (ex.: visualping, changedetection.io self-hosted), ou combinação. Prós e contras de cada abordagem considerando velocidade de detecção, robustez, custo e risco de bloqueio.
3. **Instagram especificamente** — é a fonte mais provável e a mais chata de monitorar. Quero entender as opções (scrapers pagos tipo Apify, bibliotecas self-hosted tipo instaloader, API oficial via conta business, RSS bridges, etc.) com trade-offs honestos de confiabilidade vs custo vs risco de ban.
4. **Infra de execução** — onde rodar (VPS que já tenho, serverless, GitHub Actions cron, serviço gerenciado), qual intervalo de polling faz sentido, como persistir estado.
5. **Canal de notificação** — Telegram, email, push, webhook, SMS. Qual tem menor latência real até eu ver no celular.
6. **Linguagem/stack** — só depois de definir o acima. Tenho familiaridade com Python, .NET/C#, TypeScript, Docker, PostgreSQL, SQLite. Sem preferência forçada — escolha a ferramenta certa pro problema.

## Restrições e preferências

- Soluções prontas (no-code/low-code) são bem-vindas se forem genuinamente melhores que construir do zero pra essa janela curta. Não quero over-engineering de um sistema que vai rodar por 4 semanas.
- Por outro lado, se construir do zero for mais confiável, tudo bem — tenho experiência e infra.
- Custo baixo é desejável mas não é a restrição principal. Confiabilidade vem primeiro.
- Precisa funcionar 24/7 sem babá.

## Formato da resposta que quero primeiro

1. **Panorama das fontes** — ranking das fontes por probabilidade de serem o canal primário do anúncio, com raciocínio
2. **Matriz de opções** — 2 ou 3 abordagens concretas de ponta a ponta (fonte → detecção → execução → notificação), cada uma com prós, contras, custo estimado e tempo de implementação
3. **Sua recomendação** — qual das abordagens você escolheria e por quê
4. **Perguntas abertas** — o que você precisa de mim pra avançar

Só depois que eu aprovar a direção, partimos pro código.
