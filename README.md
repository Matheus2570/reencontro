# 🔎 Reencontro

Projeto acadêmico de achados e perdidos. O Reencontro permite cadastrar objetos perdidos ou encontrados, buscar possíveis correspondências e registrar a devolução após a conferência presencial pelo responsável do almoxarifado.

**Aplicação:** [Acessar o Reencontro](https://reencontro-fzsnosjepf6ayrk79bmwrc.streamlit.app/)

**Repositório:** [Matheus2570/reencontro](https://github.com/Matheus2570/reencontro)

## Equipe

| Integrante | RA | Responsabilidade |
| --- | --- | --- |
| Matheus de Carvalho | 2609724 | Gestor de Projeto e Desenvolvedor |
| Lucas Casagrande da Silva | 2609622 | Líder Técnico / Arquiteto e Desenvolvedor |
| Guilherme Azevedo | 2603109 | Desenvolvedor |
| Gustavo Silva Gomes | 2608687 | Desenvolvedor |
| Matheus Maiolo | 2600292 | Qualidade e Documentação / Produto e Comercial |

## Tecnologias

- **Python:** lógica da aplicação.
- **Streamlit:** interface web.
- **RapidFuzz:** comparação de textos e pontuação de semelhança.
- **Firebase Firestore:** banco de dados online.
- **Firebase Admin SDK:** conexão do servidor com o banco.
- **Streamlit Community Cloud:** hospedagem da aplicação.
- **Git e GitHub:** versionamento do código.

## Funcionalidades

- Login com RA e token.
- Cadastro de objetos perdidos pelos usuários.
- Cadastro de encontrados exclusivo do administrador, após confirmar o recebimento físico no almoxarifado e informar o RA de quem encontrou.
- Identificação separada de quem encontrou e de quem realizou o cadastro.
- Consulta dos próprios cadastros em aberto e seus códigos de identificação.
- Pesquisa independente em Meus objetos, almoxarifado, seleção do objeto para comparar, candidatos à devolução e histórico. A busca ignora acentos e maiúsculas e considera todas as palavras, independentemente da ordem. As listas de objetos, candidatos e histórico exibem dez registros por página, depois de aplicar o filtro.
- Consulta administrativa dos objetos encontrados em aberto no almoxarifado.
- Histórico pessoal de objetos recuperados e encontrados que já foram devolvidos; o administrador também pode consultar todas as devoluções.
- Busca de possíveis correspondências por categoria, nome, descrição, local, cor e data.
- Link opcional para visualizar uma foto no Google Drive.
- Área administrativa para localizar um cadastro perdido pelo código e consultar candidatos encontrados, priorizando compatibilidade das características antes da similaridade textual.
- Confirmação da devolução pelo administrador, resolvendo os dois cadastros e registrando a operação em uma transação.
- Troca de tokens por script administrativo.

## Como funciona a devolução

1. O proprietário cadastra o objeto como **Perdido**.
2. Quem encontrou entrega o objeto físico ao responsável do almoxarifado.
3. O administrador confirma o recebimento e cadastra o objeto como **Encontrado**, informando o RA de quem encontrou. Essa pessoa precisa ter um usuário cadastrado no Reencontro.
4. O proprietário consulta as possíveis correspondências e apresenta o código de seu cadastro ao responsável.
5. O responsável localiza o cadastro perdido na área administrativa, consulta os candidatos e confere o objeto físico e a propriedade.
6. Após entregar o objeto, o responsável confirma a devolução no sistema. Os cadastros perdido e encontrado passam para **resolvido** juntos, saem das listagens de objetos em aberto e ficam disponíveis no histórico do proprietário e de quem encontrou. O administrador pode consultar todas as devoluções.

A compatibilidade das características é avaliada separadamente da similaridade textual e de contexto. Informação ausente não conta como acordo nem como divergência. Qualquer divergência explícita coloca o candidato abaixo dos candidatos sem divergências, mesmo com texto quase idêntico; a interface mostra quais valores divergem. Dentro desses grupos, a ordenação considera a quantidade de características compatíveis, a quantidade de divergências, a nota textual/de contexto e o código para desempatar.

Novos cadastros aceitam marca e modelo opcionais, além de campos por categoria (capacidade e material para recipientes; rodinhas e tamanho para mochilas/acessórios; conexão e formato para fones/eletrônicos). Deixe em branco o que não souber. Os documentos antigos são interpretados apenas em memória, usando detalhes explícitos e inequívocos: cor identificável, capacidade com unidade, tipos reconhecidos, marca junto ao tipo do objeto ou rotulada e modelo rotulado. Valores ambíguos continuam ausentes; campos estruturados têm prioridade. Capacidades equivalentes, acentos e variações previstas são normalizados. Não há migração nem regravação dos registros existentes.

A nota textual/de contexto usa descrição (40%), nome (30%), local (20%) e data (10%). **Não é uma probabilidade e não comprova que os objetos são o mesmo.** A entrega depende de conferência humana. Um código de cadastro identifica um registro; ele não é uma senha nem comprova a propriedade do objeto.

## Requisitos para executar localmente

- Python instalado. A hospedagem do projeto foi configurada com Python 3.13.
- Git instalado.
- Acesso à internet para consultar o Firebase.
- Um arquivo privado de credenciais, conforme a seção seguinte.
- RA e token de um usuário ativo para entrar na aplicação.

Os comandos abaixo são para **Windows / PowerShell**.

## Arquivos privados de configuração

As credenciais são mantidas em armazenamento privado pelo responsável do projeto e fornecidas somente aos integrantes autorizados a desenvolver ou administrar o sistema. Elas não acompanham o repositório ou a entrega pública do trabalho.

| Arquivo | Finalidade | Necessário quando |
| --- | --- | --- |
| `.streamlit/secrets.toml` | Contém as credenciais do Firebase na seção `[firebase]`, para leitura pelo Streamlit. | É suficiente para executar o app localmente sem o arquivo JSON. |
| `.segredos/firebase-admin.json` | Contém a chave da conta de serviço do Firebase. | Pode ser usado pelo app e é necessário para os scripts administrativos atuais. |

Para **rodar somente o app**, basta um desses arquivos no caminho indicado. Na configuração atual, o app usa o JSON quando ele existe; caso contrário, utiliza os Secrets do Streamlit.

Para usar `trocar_token.py`, `cadastrar_grupo.py` ou `preparar_secrets.py`, coloque a chave JSON em `.segredos/firebase-admin.json`.

**Os dois arquivos contêm credenciais de servidor sensíveis.** Quem recebe qualquer um deles pode acessar o banco diretamente, dentro das permissões da conta de serviço. O `secrets.toml` não concede acesso menor por ser usado somente para iniciar o app. Compartilhe esses arquivos apenas com desenvolvedores ou administradores autorizados. Para apenas utilizar o site, cada pessoa precisa somente de seu RA e token.

Não publique credenciais no GitHub, no README, em prints, em chats públicos ou nos anexos da entrega. Não compartilhe tokens pessoais junto com o código. Se uma chave de serviço for exposta, revogue-a e substitua-a também na hospedagem.

## Instalação e execução

### 1. Clonar o projeto

```powershell
git clone https://github.com/Matheus2570/reencontro.git
cd reencontro
```

### 2. Criar o ambiente virtual

```powershell
py -m venv .venv
```

### 3. Instalar as dependências

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

O arquivo `requirements.txt` contém:

```text
streamlit
rapidfuzz
firebase-admin
```

### 4. Configurar as credenciais

Solicite ao responsável do projeto um dos arquivos privados descritos acima e coloque-o dentro de `reencontro`, mantendo o caminho exato:

- `reencontro/.streamlit/secrets.toml`; ou
- `reencontro/.segredos/firebase-admin.json`.

Crie a pasta correspondente se ela não existir. Não é necessário recriar o Firebase nem cadastrar novamente os usuários ao configurar outra máquina.

### 5. Iniciar o app

Execute na pasta `reencontro`:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abra o endereço indicado no terminal, normalmente `http://localhost:8501`, e entre com seu RA e token.

Para encerrar, pressione **Ctrl + C** no terminal.

**Atenção aos testes:** usando as mesmas credenciais, o app local acessa o mesmo banco do site publicado. Cadastros e devoluções feitos localmente também alteram os dados usados pelo site.

## Organização do projeto

| Arquivo | Responsabilidade |
| --- | --- |
| `app.py` | Configuração da interface, conexão com o Firebase, login e chamada dos módulos. |
| `objetos.py` | Cadastro com validação de acesso, identificação de quem encontrou e listagem dos objetos em aberto. |
| `acesso.py` | Validação de sessão e permissão nas operações de cadastro e devolução. |
| `pesquisa.py` | Normalização dos textos e pesquisa nos campos públicos dos registros. |
| `identificacao.py` | Exibição de RA e consulta dos vínculos antigos por UID, sem migração do banco. |
| `historico.py` | Histórico pessoal e consulta administrativa de todas as devoluções, com paginação. |
| `tests/test_fluxo.py` | Testes de permissões, devoluções, históricos e interface com banco simulado. |
| `correspondencias.py` | Normalização dos textos, pontuação e busca de correspondências. |
| `caracteristicas.py` | Campos opcionais por categoria, extração conservadora de legados e comparação de características. |
| `devolucoes.py` | Área administrativa, consulta de candidatos e confirmação da devolução. |
| `cadastrar_grupo.py` | Cadastro inicial dos cinco integrantes e geração de tokens. |
| `trocar_token.py` | Troca do token de um usuário cadastrado. |
| `preparar_secrets.py` | Conversão da chave JSON para o arquivo local de Secrets do Streamlit. |
| `requirements.txt` | Dependências do projeto. |
| `.gitignore` | Exclusão de credenciais, ambiente virtual e arquivos gerados do versionamento. |

A pasta `.venv` deve ser criada em cada máquina. O Python gera `__pycache__` automaticamente. Nenhuma das duas precisa ser copiada de outra máquina.

## Scripts administrativos

Estes comandos exigem `.segredos/firebase-admin.json` e devem ser executados apenas pelo responsável autorizado.

**Trocar o token de um usuário:**

```powershell
.\.venv\Scripts\python.exe trocar_token.py
```

Informe o RA solicitado. Guarde o novo token em local privado e entregue-o somente ao usuário correspondente. A troca invalida o token anterior e encerra as sessões antigas na próxima interação.

**Preparar os Secrets a partir do JSON:**

```powershell
.\.venv\Scripts\python.exe preparar_secrets.py
```

Esse comando gera `.streamlit/secrets.toml` localmente.

**Cadastro inicial do grupo:**

```powershell
.\.venv\Scripts\python.exe cadastrar_grupo.py
```

O grupo já foi cadastrado no banco atual. **Não execute esse comando novamente ao clonar o projeto.** Ele é destinado à configuração inicial de um banco sem esses usuários; não serve para atualizar usuários existentes.

## Banco de dados

O Firestore organiza os dados em **coleções e documentos**, em vez de tabelas SQL. As coleções são criadas quando os primeiros documentos são gravados.

| Coleção | Conteúdo |
| --- | --- |
| `usuarios` | Nome, RA, identificador interno, situação do acesso, permissão, hash e versão do token. |
| `itens` | Objetos perdidos e encontrados, características, autor do cadastro, identificação de quem encontrou, recebimento no almoxarifado e status. |
| `devolucoes` | Vínculo entre os cadastros, proprietário, pessoa que encontrou, responsáveis pelo cadastro e pela entrega, data e cópias dos dados dos objetos. |

## Acesso e limites da versão atual

- O login valida usuários cadastrados no projeto. Não consulta o sistema da faculdade nem comprova vínculo institucional.
- Os tokens individuais são gerados aleatoriamente e seus hashes são armazenados no banco. A aplicação não utiliza CPF como senha.
- O acesso administrativo no app depende da permissão do usuário registrada no banco. No cadastro inicial, Matheus de Carvalho possui essa permissão.
- As regras do Firestore bloqueiam o acesso direto de clientes. O servidor usa o Admin SDK e valida as permissões no código Python; as regras não restringem esse SDK.
- A listagem pessoal e a seleção para comparação consultam os cadastros em aberto autorizados ao usuário, sem limite de 50 registros, para que a pesquisa considere a lista inteira. A busca de correspondências parte apenas de cadastros perdidos em aberto do usuário. Aluno e administrador consultam os encontrados abertos da mesma categoria e usam a mesma função de ordenação. O aluno vê os cinco primeiros após classificar todos os candidatos, sem corte por nota textual; o administrador pode percorrer a lista completa.
- Na área administrativa, os candidatos abertos da mesma categoria são consultados e apresentados em páginas de dez opções. A paginação da interface não limita a consulta ao banco a dez registros.
- A comparação tolera variações de maiúsculas, minúsculas, acentos e ordem das palavras, conforme os critérios utilizados. Não garante reconhecimento de todos os sinônimos ou descrições incompletas.
- As fotos são links externos opcionais. Elas não são enviadas para o Firebase pelo app.
- Os participantes são exibidos pelo RA. Nos registros antigos, o app consulta o RA na coleção `usuarios` pelo UID, sem regravar o histórico. Se o usuário não for localizado e não houver RA salvo, aparece “RA não localizado”. Os novos registros também guardam o RA dos participantes; os UIDs continuam como vínculos internos. As datas de devolução são exibidas em formato brasileiro e no horário de Brasília (UTC−3).
- Os históricos consultam os registros de devolução e exibem dez por página. A paginação da interface não limita a leitura do banco a dez registros.
- Registros antigos continuam compatíveis: quando não há identificação separada de quem encontrou, o vínculo anterior com o autor do cadastro é preservado. Devoluções antigas sem cópias dos objetos consultam os cadastros originais. Não há migração automática dos dados antigos.
- A versão atual ainda não implementa limitação de tentativas de login ou notificações automáticas.

## Continuar o desenvolvimento em outra máquina

Siga a instalação acima e obtenha as credenciais por meio privado. Se o repositório já estiver clonado, atualize-o antes de começar:

```powershell
git pull
```

Após editar e testar, envie apenas os arquivos de código ou documentação que foram alterados. Exemplo para `app.py` e `README.md`:

```powershell
git add app.py README.md
git commit -m "Atualiza aplicativo e documentação"
git push
```

Adapte a lista de arquivos às alterações feitas. Os Secrets configurados na hospedagem são separados do repositório e continuam configurados ao atualizar o código.

O `.gitignore` deve manter, pelo menos:

```gitignore
.venv/
__pycache__/
.segredos/
.streamlit/secrets.toml
.env
*firebase-adminsdk*.json
```

Para verificar se os arquivos privados já estão rastreados pelo Git:

```powershell
git ls-files -- .segredos .streamlit/secrets.toml
```

O resultado esperado é vazio. O `.gitignore` não remove arquivos que já tenham sido versionados.

## Testes locais

Execute na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes usam um banco simulado em memória e o AppTest do Streamlit. Não precisam de credenciais e não acessam nem alteram o Firebase real.

## Documentação de referência

- [Secrets no Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [Configuração do Firebase Admin SDK](https://firebase.google.com/docs/admin/setup)

---

Projeto acadêmico em desenvolvimento. As correspondências sugeridas auxiliam a busca; a conferência presencial e a confirmação da propriedade continuam sob responsabilidade da pessoa que realiza a entrega.
