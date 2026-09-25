@echo off
rem Abre o gravador e repassa uma copia de cada pacote para o F1 Laps (porta 20778).
rem No app do F1 Laps, mude a porta UDP para 20778 antes.
"%~dp0F1Telemetria.exe" gravar --repassar 127.0.0.1:20778
