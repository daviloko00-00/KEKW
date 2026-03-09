🛡️ Educational Trojan Simulation

Projeto de simulação de trojan com finalidade estritamente educacional, criado para demonstrar como determinados tipos de malware funcionam internamente em ambientes controlados de laboratório.

Este projeto foi desenvolvido para estudo de cibersegurança ofensiva e defensiva, permitindo compreender técnicas utilizadas por malwares reais e, consequentemente, melhorar estratégias de detecção e mitigação.

🎯 Objetivo

Demonstrar, em um ambiente isolado e controlado, o comportamento típico de um malware, incluindo:

Persistência no sistema

Captura de entrada do teclado

Comunicação com servidor de comando e controle (C&C)

Sinais visuais/sonoros para validação durante testes

O propósito é educacional, permitindo analisar:

Técnicas de persistência

Métodos de coleta de dados

Funcionamento de canais de comunicação remota

Estratégias de defesa e detecção

⚠️ Este código nunca deve ser executado fora de ambientes controlados ou sem consentimento explícito.

📁 Estrutura do Projeto
Arquivo / Função	Descrição
main.py	Arquivo principal que integra todos os módulos do simulador
persist()	Copia o executável para %APPDATA%\msupdate.exe e cria persistência via registro do Windows
start_keylogger()	Implementa um hook de teclado para captura de digitações
listen(s)	Processa comandos remotos (/exit, /keys, comandos de shell e cd)
flash_desktop()	Pisca a tela do desktop para indicar ativação
beep_ok()	Emite som de confirmação
popup_ok()	Mostra mensagem visual para indicar que o trojan foi executado

Esses sinais visuais/sonoros facilitam a validação do funcionamento em ambiente de testes.

🧪 Ambiente de Teste Recomendado

Este projeto deve ser executado apenas em laboratório isolado.

Ambiente recomendado:

Máquina virtual

Rede isolada

Sistema descartável

Exemplos de virtualização:

VirtualBox

VMware

Hyper-V

⚙️ Como Executar
1️⃣ Criar ambiente isolado

Crie uma VM Windows dedicada para testes.

2️⃣ Preparar o ambiente

Alguns antivírus podem detectar o código como malware.
Para fins de estudo, pode ser necessário:

Desativar temporariamente o antivírus

Criar uma exceção para o diretório do projeto

3️⃣ Executar o simulador

No terminal da VM:

python main.py
4️⃣ Reiniciar o sistema

Após reiniciar a máquina virtual, o processo será iniciado automaticamente devido à persistência criada no registro.

5️⃣ Conectar ao canal de controle

Em outra máquina da rede virtual, execute:

ncat -lvp 443

Comandos disponíveis:

Comando	Função
/keys	Retorna as teclas capturadas
/exit	Encerra a conexão
dir, whoami, etc	Executa comandos de shell
cd	Altera diretório
🧹 Remoção do Simulador

Abra o PowerShell como Administrador e execute:

reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v msupdate /f
Remove-Item -Force "$env:APPDATA\msupdate.exe"
taskkill /im msupdate.exe /f

Isso remove:
Persistência no registro
Executável copiado
Processo em execução

⚖️ Aviso Legal

Este projeto foi criado exclusivamente para fins educacionais em segurança da informação.

O uso deste código para:
invasão de sistemas
espionagem
coleta de dados sem autorização
distribuição de malware
é ilegal em diversas jurisdições, incluindo:
Artigo 154-A do Código Penal Brasileiro
Computer Fraud and Abuse Act (CFAA) – EUA
Leis equivalentes em diversos países
O autor não se responsabiliza pelo uso indevido deste material.

Use apenas para:
estudo
pesquisa
treinamento em cibersegurança
laboratórios controlados
