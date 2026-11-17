// ==============================================================================
// FIRMWARE DE TESTE — ESP32 (Arduino / PlatformIO)
// Gera tráfego de rede real para estressar o IoT-IDS, em dois modos:
//   MODO_ATAQUE=0 -> Movimentação NORMAL (padrão esperado, periódico)
//   MODO_ATAQUE=1 -> Movimentação MALICIOSA (port scan estocástico, cada
//                    execução sorteia alvos/portas/tempos diferentes)
// O modo é definido em tempo de compilação via platformio.ini (-D MODO_ATAQUE=..)
// ==============================================================================
#include <WiFi.h>
#include <WiFiClient.h>

#define MODO_ATAQUE 1   // fallback: normal, caso platformio.ini não defina a flag

// ---------------------------- CONFIGURAÇÃO DE REDE ---------------------------
const char* WIFI_SSID  = "ssid";
const char* WIFI_SENHA = "pass";

// ------------------------------------------------------------------------------
// SERVIDOR_NORMAL: host FIXO na mesma rede Wi-Fi que o ESP32 contata repetida
// e previsivelmente no MODO NORMAL — simula o comportamento de um dispositivo
// IoT "bem comportado" que conversa sempre com o mesmo hub/broker/servidor.
//
// NÃO precisa ser nenhum serviço especial do projeto. Qualquer host da sua
// LAN que tenha algo escutando na porta abaixo serve. Caminho mais simples:
//   1) No PowerShell da sua máquina Windows: ipconfig  -> anote o IPv4 do
//      adaptador Wi-Fi (ex.: 192.168.1.1).
//   2) Nessa mesma máquina, rode: python -m http.server 8500
//      (não precisa ser admin; porta 8500 é só um endpoint HTTP descartável)
//   3) Preencha os dois campos abaixo com esse IP e essa porta.
// Se preferir, pode apontar para o IP do roteador (porta 80) — mas aí, se o
// roteador não responder na porta, as conexões vão falhar (S0) e o modo
// "normal" vai parecer uma varredura. Prefira sempre um host com um serviço
// realmente escutando.
// ------------------------------------------------------------------------------
IPAddress SERVIDOR_NORMAL(192, 168, 137, 1);
const uint16_t PORTA_SERVIDOR_NORMAL = 8500;

// Alvos do modo MALICIOSO
const IPAddress GATEWAY_HOTSPOT(192, 168, 137, 1);

const uint16_t PORTAS_COMUNS[] = {21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
                                   1883, 3306, 3389, 8080, 8883};
const int QTD_PORTAS_COMUNS = sizeof(PORTAS_COMUNS) / sizeof(PORTAS_COMUNS[0]);

// Sorteado uma vez por execução: 0 = scan horizontal/vertical misto,
// 1 = repetição numa única porta (padrão tipo brute-force)
int subTipoAtaqueEscolhido = 0;
uint16_t portaAlvoFixaBruteForce = 22;

void conectarWiFi() {
    Serial.printf("[WIFI] Conectando a '%s'...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_SENHA);
    while (WiFi.status() != WL_CONNECTED) {
        delay(300);
        Serial.print(".");
    }
    Serial.printf("\n[WIFI] Conectado! IP do ESP32: %s\n", WiFi.localIP().toString().c_str());
}

// Comportamento regular: mesmo servidor, mesma porta, intervalo quase fixo.
void executarPassoNormal() {
    WiFiClient client;
    Serial.printf("[NORMAL] GET http://%s:%u/ ...\n",
                   SERVIDOR_NORMAL.toString().c_str(), PORTA_SERVIDOR_NORMAL);

    if (client.connect(SERVIDOR_NORMAL, PORTA_SERVIDOR_NORMAL, 1000)) {
        client.print(String("GET / HTTP/1.1\r\nHost: ") +
                      SERVIDOR_NORMAL.toString() + "\r\nConnection: close\r\n\r\n");
        unsigned long t0 = millis();
        while (client.connected() && millis() - t0 < 500) {
            while (client.available()) client.read();
        }
    } else {
        Serial.println("[NORMAL] Falha de conexão (verifique se o http.server está rodando).");
    }
    client.stop();

    long jitter = (long)esp_random() % 1000 - 500; // ±500ms, padrão regular
    delay(4000 + jitter);
}

// Padrões suspeitos ALEATORIZADOS a cada execução do firmware.
void executarPassoMalicioso() {
    IPAddress alvo;
    // Sub-tipo 1 (brute-force): sempre o notebook. Sub-tipo 0: metade notebook,
    // metade um bloco fora da sub-rede, que obriga o pacote a passar pelo gateway.
    if (subTipoAtaqueEscolhido == 1 || esp_random() % 2 == 0) {
        alvo = GATEWAY_HOTSPOT;
    } else {
        alvo = IPAddress(10, 77, 0, 2 + (esp_random() % 250));
    }

    uint16_t porta;
    if (subTipoAtaqueEscolhido == 1) {
        porta = portaAlvoFixaBruteForce;
    } else if (esp_random() % 3 == 0) {
        porta = (uint16_t)(1024 + (esp_random() % 64000));
    } else {
        porta = PORTAS_COMUNS[esp_random() % QTD_PORTAS_COMUNS];
    }

    WiFiClient client;
    Serial.printf("[MALICIOSO][sub=%d] Tentando %s:%u ...\n",
                   subTipoAtaqueEscolhido, alvo.toString().c_str(), porta);

    bool conectou = client.connect(alvo, porta, 150); // timeout curto = scan
    if (conectou) client.stop();

    uint32_t espera = 50 + (esp_random() % 1450); // 50ms a 1500ms, aleatório
    delay(espera);
}

void setup() {
    Serial.begin(115200);
    delay(500);

    randomSeed(esp_random());
    subTipoAtaqueEscolhido = esp_random() % 2;
    portaAlvoFixaBruteForce = PORTAS_COMUNS[esp_random() % QTD_PORTAS_COMUNS];

#if MODO_ATAQUE == 1
    Serial.println("=== FIRMWARE EM MODO: MALICIOSO / ANÔMALO ===");
    Serial.printf("Sub-tipo sorteado nesta execução: %d\n", subTipoAtaqueEscolhido);
#else
    Serial.println("=== FIRMWARE EM MODO: NORMAL (tráfego regular) ===");
#endif

    conectarWiFi();
}

void loop() {
#if MODO_ATAQUE == 1
    executarPassoMalicioso();
#else
    executarPassoNormal();
#endif

    if (WiFi.status() != WL_CONNECTED) {
        conectarWiFi();
    }
}