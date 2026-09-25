@echo off
rem Teste sem o jogo: com o gravador JA ABERTO, envia 30 segundos de dados falsos.
rem O painel deve mudar para "Gravando". Depois apague o arquivo de teste
rem (pista "desconhecida") da pasta de gravacoes.
echo Enviando 30 s de dados de teste para o gravador...
"%~dp0F1Telemetria.exe" sintetico --minutos 0.5 --pista -1 --tipo 0 --plataforma 255
echo Pronto. Confira o painel no navegador.
pause
