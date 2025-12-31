## 📌 Sobre este Repositório

Este repositório contém artefatos de um **projeto real desenvolvido para um cliente do setor de alimentação (restaurante)**, com o objetivo de **centralizar e automatizar a visualização de dados operacionais**, superando limitações do ERP utilizado, que **não disponibilizava API pública nem relatórios integrados**.

A solução foi utilizada em **ambiente produtivo**, permitindo uma gestão mais rápida, eficiente e orientada a dados, com atualização automática de dashboards no Power BI.

> ⚠️ **Observação importante**  
> Este repositório apresenta uma **versão sanitizada** do projeto real.  
> Nenhuma credencial, identificador real, URL produtiva ou dado sensível do cliente foi publicado.  
> Os artefatos aqui disponíveis têm **finalidade exclusivamente demonstrativa**, preservando a arquitetura, a lógica de automação e as decisões técnicas adotadas.

---

## 📦 O que este repositório contém

Os arquivos disponibilizados representam os **principais componentes técnicos da solução**, de forma genérica e segura:

- **Workflow N8N (JSON)**  
  Representa o fluxo de orquestração responsável por:

  - Autenticação via Azure AD (OAuth2)
  - Disparo de requisições HTTP
  - Atualização automática de datasets no Power BI  
    _(Identificadores, tokens e URLs reais foram removidos ou substituídos por placeholders)_

- **Script de automação em Python**  
  Responsável pelo processo de:

  - Acesso automatizado ao ERP via SeleniumBase
  - Aplicação de filtros conforme regras de negócio
  - Exportação de dados em CSV
  - Transformação dos dados para JSON consumível por outros serviços

- **API intermediária com FastAPI**  
  Implementa rotas responsáveis por:
  - Receber requisições disparadas pelo N8N
  - Executar os scripts de automação e tratamento
  - Servir os dados processados de forma padronizada

Essa separação permite **desacoplamento**, **facilidade de manutenção** e **escalabilidade da solução**, mesmo em cenários onde o sistema de origem não oferece integração nativa.

---

## 🔐 Segurança e Privacidade

- Nenhuma informação sensível foi versionada
- Tokens, `client_id`, `client_secret` e URLs reais foram removidos
- Uso recomendado de variáveis de ambiente
- Estrutura preparada para ambientes produtivos
- Publicação realizada exclusivamente para fins de **portfólio técnico**
