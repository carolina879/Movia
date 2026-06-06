# Movia 🚗

Sistema inteligente de navegação e roteamento urbano baseado em dados reais do OpenStreetMap.

O Movia utiliza algoritmos de busca heurística (A*) para calcular rotas rápidas, gerar caminhos alternativos e simular condições de trânsito em tempo real, oferecendo uma experiência semelhante a aplicativos de navegação modernos.

---

## Funcionalidades

### Navegação Inteligente
- Cálculo de rotas utilizando algoritmo A*
- Até 3 rotas alternativas
- Tempo estimado de viagem
- Distância total da rota
- Seleção visual da melhor rota

### Modos de Transporte
- Carro
- Bicicleta
- Caminhada

### Simulação de Trânsito
- Ajuste automático de tráfego conforme o horário
- Horários de pico com maior tempo estimado
- Visualização do fator de trânsito

### Busca de Endereços
- Geocodificação via OpenStreetMap
- Busca por bairros, avenidas e pontos de interesse
- Conversão automática de coordenadas em endereços

### Histórico e Favoritos
- Histórico das últimas rotas pesquisadas
- Salvar locais favoritos
- Acesso rápido aos destinos mais utilizados

### Interface Interativa
- Mapa em tempo real com Leaflet
- Definição de origem e destino por clique
- Uso da localização atual do usuário
- Visualização simultânea de múltiplas rotas

---

## Tecnologias Utilizadas

### Backend
- Python
- FastAPI
- OpenStreetMap (OSMnx)
- NetworkX
- SQLite
- AioSQLite
- HTTPX

### Frontend
- HTML5
- CSS3
- JavaScript
- Leaflet.js

---

## Arquitetura

```text
Movia
│
├── Backend (FastAPI)
│   ├── API REST
│   ├── Algoritmo A*
│   ├── Gerador de rotas alternativas
│   ├── Simulação de trânsito
│   ├── Geocodificação
│   └── Banco SQLite
│
└── Frontend (Leaflet)
    ├── Mapa interativo
    ├── Visualização das rotas
    ├── Histórico
    ├── Favoritos
    └── Painel de trânsito
```

---

## Como Executar

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Iniciar servidor

```bash
uvicorn main:app --reload
```



## Como Funciona

O sistema utiliza um grafo viário obtido diretamente do OpenStreetMap.

Cada cruzamento é representado por um nó e cada rua por uma aresta.

O algoritmo A* busca o caminho de menor custo utilizando:

f(n) = g(n) + h(n)

Onde:

- g(n) = custo acumulado da rota
- h(n) = distância estimada até o destino (Haversine)

Isso permite encontrar rotas muito rapidamente mesmo em mapas com centenas de milhares de nós.

---

## Diferenciais

- Algoritmo A* implementado manualmente
- Rotas alternativas inteligentes
- Simulação de trânsito baseada em horário
- Histórico persistente em SQLite
- Favoritos personalizados
- Dados reais do OpenStreetMap
- Interface semelhante a aplicativos de navegação comerciais

---

## Próximas Evoluções

- Trânsito em tempo real via API externa
- Detecção de acidentes
- Navegação curva a curva por voz
- Rotas colaborativas
- Aplicativo mobile
- Suporte a múltiplas cidades

---

## Autor

Carol Deschamps

Projeto desenvolvido para estudo de:
- Estruturas de Dados
- Grafos
- Algoritmos de Busca
- Sistemas Distribuídos
- Geolocalização
- Desenvolvimento Full Stack