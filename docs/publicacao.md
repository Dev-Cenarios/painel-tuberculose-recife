# O painel no ar, no nosso servidor

Além de ser entregue como imagem Docker (veja o `README.md`), o painel está **no ar no servidor (VM) dos painéis desde 18/set/2026**. Ele entrou no lugar do "Dashboard TB | Recife" antigo.

| | |
|---|---|
| **Endereço público** | `https://painel.cenarios.unb.br/cenarios/tbrecife/` |
| **Acesso direto** (para testar, por túnel SSH) | `ssh -L 8511:127.0.0.1:8511 cenarios-vm` e depois abrir `http://localhost:8511/cenarios/tbrecife/`. A porta só aceita conexão de dentro da própria VM (`127.0.0.1`) |
| **Container** | `recifetb`, com a imagem `recifetb:latest`, construída na própria VM |
| **Pasta na VM** | `~/recifetb`. É uma cópia do GitHub, baixada com uma chave que **só tem permissão de leitura** (`~/.ssh/id_recifetb_deploy`) |
| **Configuração** | `~/recifetb/.env`: `PORTA=8511` e `BASE_URL_PATH=cenarios/tbrecife` |
| **Dados** | `~/recifetb/data` (uns 3,6 MB em out/2026). Enviados à parte, com `tar`, porque **não ficam no git** |

## Atualizar o código

```bash
ssh cenarios-vm 'cd ~/recifetb && git pull && docker build -q -t recifetb:latest . && docker compose up -d'
```

O passo a passo: baixa o código novo (`git pull`), **reconstrói a imagem** e sobe o container de novo.

**Por que precisa reconstruir a imagem:** o código e os dados ficam **dentro** dela. É a mesma imagem que vai para a outra equipe.

**É seguro:** o `&&` faz cada passo só rodar se o anterior deu certo. Se a reconstrução falhar, o container antigo continua no ar.

## Trocar os dados

Da máquina de trabalho, dentro da pasta `paineis/RecifeTB`:

```bash
tar -C data --exclude='parquet/dashboard/popsvs' --exclude='parquet/dashboard/dim_geo' \
    --exclude='*.csv' --exclude='*.gz' -cf - parquet geo \
  | ssh cenarios-vm 'tar -C ~/recifetb/data -xf -'
```

Depois, rode o comando de **atualizar o código** acima, para reconstruir a imagem com os dados novos.

**O que esse comando faz:** empacota só as pastas `parquet` e `geo` e manda direto para a VM. Ele **deixa de fora**:
- `popsvs` e `dim_geo`, que o painel não usa;
- **todo arquivo `.csv`**. Essa é a **rede de segurança**: o arquivo com nome de paciente fica em `data/origem/` e nem está entre as pastas enviadas, mas, se um CSV aparecer por engano em outro lugar, ele também não vai.

## nginx

- O bloco é o `location /cenarios/tbrecife`, no arquivo `/etc/nginx/sites-enabled/telessaude`.
- Ele aponta para `proxy_pass http://localhost:8511`, **sem barra no final nos dois lados**. O container espera receber o caminho completo, com o `/cenarios/tbrecife` na frente.
- **Era o bloco do painel antigo.** Só o `proxy_pass` mudou, da porta 8503 para a 8511. Quem fez a troca foi o script `~/aplicar-rota-recifetb.sh`, na VM, que guardou uma cópia do arquivo antigo em `~/telessaude.bak-*`.

**O cartão da página inicial** (`/var/www/frontpage/index.html`) passou a se chamar "Monitoramento da Tuberculose | Recife". Cópia do arquivo antigo em `~/frontpage-index.bak-*`.

## O painel antigo, que saiu

O painel antigo ficava em `~/dashboard-tb-recife` (repositório `Mcardosor/dashboard-tb-recife`, porta 8503). Ele foi desligado com `docker compose down` em 18/set/2026.

**Em 21/out/2026, a pasta `~/dashboard-tb-recife` já não estava mais na VM.**

> ⚠️ **O endereço do repositório desse painel antigo tinha um token do GitHub escrito dentro dele.** Apagar a pasta não invalida o token. Se ele ainda não foi revogado no GitHub (Settings → Developer settings → Tokens), **precisa ser**.
