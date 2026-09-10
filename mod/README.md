# BlizzMod Telemetry Injector (version.dll)

Este diretório contém o binário pré-compilado e instruções do mod hook C++ injetado no **Marvel Contest of Champions** (MCoC) via Proton/Wine no Linux.

## 📋 Como Funciona

1. **Injeção de DLL (Proxy DLL)**:
   - Ao iniciar o jogo pela Steam, o Proton carrega o arquivo `version.dll` localizado na pasta raiz do jogo.
   - Esse binário executa os hooks IL2CPP do jogo (`libraries/pipeline/hooks/InitHooks.cpp`).

2. **Captura de Telemetria em Tempo Real**:
   - Extrai ponteiros da memória da engine:
     - Posição 3D dos lutadores (`Transform_get_position`)
     - HP normalizado e absoluto (`Health_get_resourceAttribute`)
     - Poder / Mana (`Mana_get_resourceAttribute`)
     - Distância precisa entre oponentes
     - Flags de estado (Bloqueio, Atacando, Especial, Atordoado/Stun, Esquiva)
   - Dispara pacotes binários UDP a cada frame para `127.0.0.1:5555`.

3. **Consumo pelo NovoAuto**:
   - O daemon Python (`main.py run`) escuta a porta UDP `5555` em loop assíncrono (< 5µs) e controla o teclado virtual `/dev/uinput`.

---

## 🚀 Instalação Rápida

Copie o arquivo `version.dll` deste diretório diretamente para a pasta do jogo na Steam:

```bash
cp version.dll ~/.local/share/Steam/steamapps/common/"Marvel Contest of Champions"/version.dll
```

Certifique-se de que a opção de inicialização do jogo na Steam inclui o override da DLL:
```bash
WINEDLLOVERRIDES="version=n,b" %command%
```

---

## 🛠️ Código-Fonte e Recompilação

O código-fonte completo do hook em C++ está versionado no repositório:
👉 [https://github.com/erickloyola/BlizzMod](https://github.com/erickloyola/BlizzMod) (branch `testes`)

Para recompilar a DLL localmente via Docker (Wine + MSVC) sem poluir o sistema:
```bash
cd /home/erickloyola/BlizzMod
./compilar_docker.sh
```
O script compilará a DLL com limites seguros de RAM/CPU e a copiará automaticamente para o jogo.
