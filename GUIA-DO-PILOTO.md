# Guia do piloto: gravador de telemetria do F1 25

O programa roda **no PC** e grava tudo o que o F1 25 manda, com o jogo **no Xbox ou no próprio PC**. Não precisa escolher nada: ele reconhece sozinho.

## 1. Instalar (uma vez)
1. Coloque `F1Telemetria.exe` numa pasta sua (ex.: `Documentos\F1 Telemetria`).
2. Dê dois cliques. O Windows pode avisar "O Windows protegeu o computador" (o programa não tem assinatura digital ainda): clique em **Mais informações → Executar assim mesmo**.
3. Na janela do **firewall**, marque **só "Redes privadas"** e clique em Permitir. Nunca marque "Redes públicas".
4. O navegador abre o painel (`http://127.0.0.1:8750`). Ele mostra o **IP deste computador**: anote.

> A rede do PC precisa estar como **Privada** (Configurações → Rede e Internet → sua rede → Perfil de rede: Privada). Se estiver como Pública, o painel avisa.

## 2. Ligar a telemetria no jogo (uma vez)
No F1 25: **Configurações → Configurações de telemetria**
| Opção | Xbox | Jogo no PC |
|---|---|---|
| Telemetria UDP | Ligada | Ligada |
| Modo Broadcast UDP | Desligado | Desligado |
| Endereço IP UDP | **o IP que o painel mostra** | `127.0.0.1` |
| Porta UDP | 20777 | 20777 |
| Taxa de envio UDP | **60 Hz** | **60 Hz** |
| Formato UDP | deixe o padrão | deixe o padrão |

Se o Xbox não conectar mesmo com o IP certo, ligue o **Modo Broadcast**: ele manda para todos os aparelhos da rede.

## 3. Usar no dia a dia
1. Abra o `F1Telemetria.exe` **antes** de ir para a pista.
2. Jogue normalmente. O painel muda para **Gravando** e mostra, por exemplo, `F1 25 · Xbox · 192.168.0.23`, a pista e a sessão.
3. Cada sessão (treino, classificação, corrida, time trial) vira um arquivo em `Documentos\F1 Telemetria\gravacoes`, com data, pista e tipo no nome. O botão **Abrir pasta** leva direto até ela.
4. Para fechar: `Ctrl+C` na janela preta, ou feche a janela. Se o PC desligar no meio, a sessão fica salva até cerca de 1 segundo antes (aparece como `_interrompida`).

## 4. Usar junto com o F1 Laps
Só um programa pode receber o jogo diretamente. Deixe o jogo mandando para **este gravador** e ele repassa uma cópia idêntica para o F1 Laps:
1. No app do F1 Laps, mude a porta UDP para **20778**.
2. Abra o gravador pelo atalho com repasse: crie um atalho do `.exe` e, em **Destino**, acrescente no final:
   `gravar --repassar 127.0.0.1:20778`
3. O painel mostra "Repassando cada pacote para 127.0.0.1:20778".

## 5. Se não aparecer nada
Depois de 30 segundos sem sinal, o painel mostra um checklist. Os casos mais comuns:
- telemetria desligada no jogo, ou IP digitado errado;
- Xbox no **Wi-Fi de convidado** (isola os aparelhos). Use a mesma rede do PC, de preferência o Xbox no cabo;
- rede do Windows como **Pública**;
- outro programa (F1 Laps, SimHub) aberto na porta 20777: a janela preta avisa "Não consegui ouvir a porta 20777".

## 6. O que mandar para análise
Os arquivos `.f1rec` da pasta `gravacoes`. São dados seus: não publique.
