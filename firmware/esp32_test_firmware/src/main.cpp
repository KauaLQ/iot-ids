// ==============================================================================
// FIRMWARE DE TESTE — ESP32 (Arduino / PlatformIO)
// Gera tráfego REAL para coletar sessões rotuladas para o IoT-IDS.
//   MODO_ATAQUE=0 -> tráfego normal (HTTP periódico)           => rotule "Benigno"
//   MODO_ATAQUE=1 -> varreduras, sorteadas a cada boot         => rotule "PortScan"
//       sub 0: scan misto (portas comuns/aleatórias, alvos variados)
//       sub 1: brute-force (uma porta fixa no gateway)
//       sub 2: scan HORIZONTAL (mesma porta, muitos IPs) — o padrão do IoT-23
//   Perfil de velocidade (sorteado): 0 rápido (~20-100 conn/s), 1 médio, 2 lento.
// IMPORTANTE: o modelo NÃO deve depender deste firmware. Este código só serve para
// gerar dados variados; para robustez, também colete tráfego de outras fontes
// (celular, notebook, nmap) — veja o roteiro no README.
// O modo é definido em tempo de compilação (platformio.ini: -D MODO_ATAQUE=..).
// ==============================================================================
#include <WiFi.h>
#include <WiFiClient.h>

#define MODO_ATAQUE 0   // padrão: normal

// ---------------------------- CONFIGURAÇÃO DE REDE ---------------------------
const char* WIFI_SSID  = "KAUA_LQ";
const char* WIFI_SENHA = "12345678";

// Host fixo contatado no modo normal. Na máquina Windows (hotspot 192.168.137.1):
// python -m http.server 8500
IPAddress SERVIDOR_NORMAL(192, 168, 137, 1);
const uint16_t PORTA_SERVIDOR_NORMAL = 8500;

const IPAddress GATEWAY_HOTSPOT(192, 168, 137, 1);

const uint16_t PORTAS_COMUNS[] = {21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
                                   1883, 3306, 3389, 8080, 8883};
const int QTD_PORTAS_COMUNS = sizeof(PORTAS_COMUNS) / sizeof(PORTAS_COMUNS[0]);

int subTipoAtaqueEscolhido = 0;      // 0 misto | 1 brute-force | 2 horizontal
int perfilVelocidade = 0;            // 0 rápido | 1 médio | 2 lento
uint16_t portaAlvoFixa = 22;
uint8_t proximoHostHorizontal = 2;

void conectarWiFi() {
    Serial.printf("[WIFI] Conectando a '%s'...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_SENHA);
    while (WiFi.status() != WL_CONNECTED) {
        delay(300);
        Serial.print(".");
    }
    Serial.printf("\n[WIFI] Conectado! IP do ESP32: %s  <-- use este IP na coleta\n",
                  WiFi.localIP().toString().c_str());
}

// Comportamento regular: mesmo servidor, mesma porta, intervalo quase fixo.
void executarPassoNormal() {
    WiFiClient client;
    if (client.connect(SERVIDOR_NORMAL, PORTA_SERVIDOR_NORMAL, 1000)) {
        client.print(String("GET / HTTP/1.1\r\nHost: ") +
                      SERVIDOR_NORMAL.toString() + "\r\nConnection: close\r\n\r\n");
        unsigned long t0 = millis();
        while (client.connected() && millis() - t0 < 500) {
            while (client.available()) client.read();
        }
    } else {
        Serial.println("[NORMAL] Falha de conexão (o http.server está rodando?).");
    }
    client.stop();
    long jitter = (long)(esp_random() % 1000) - 500;
    delay(4000 + jitter);
}

uint32_t esperaEntreTentativas() {
    switch (perfilVelocidade) {
        case 0:  return 5 + (esp_random() % 45);      // 5-50 ms   (rápido, como no IoT-23)
        case 1:  return 50 + (esp_random() % 350);    // 50-400 ms
        default: return 300 + (esp_random() % 1700);  // 0.3-2 s   (lento / "stealth")
    }
}

void executarPassoMalicioso() {
    IPAddress alvo;
    uint16_t porta;

    if (subTipoAtaqueEscolhido == 1) {                    // brute-force
        alvo = GATEWAY_HOTSPOT;
        porta = portaAlvoFixa;
    } else if (subTipoAtaqueEscolhido == 2) {             // horizontal: mesma porta, muitos IPs
        alvo = IPAddress(10, 77, 0, proximoHostHorizontal);
        proximoHostHorizontal = (proximoHostHorizontal >= 250) ? 2 : proximoHostHorizontal + 1;
        porta = portaAlvoFixa;
    } else {                                              // misto
        alvo = (esp_random() % 2 == 0) ? GATEWAY_HOTSPOT
                                       : IPAddress(10, 77, 0, 2 + (esp_random() % 250));
        porta = (esp_random() % 3 == 0) ? (uint16_t)(1024 + (esp_random() % 64000))
                                        : PORTAS_COMUNS[esp_random() % QTD_PORTAS_COMUNS];
    }

    WiFiClient client;
    bool conectou = client.connect(alvo, porta, 150);     // timeout curto = scan
    if (conectou) client.stop();
    delay(esperaEntreTentativas());
}

void setup() {
    Serial.begin(115200);
    delay(500);
    randomSeed(esp_random());
    subTipoAtaqueEscolhido = esp_random() % 3;
    perfilVelocidade = esp_random() % 3;
    portaAlvoFixa = PORTAS_COMUNS[esp_random() % QTD_PORTAS_COMUNS];

#if MODO_ATAQUE == 1
    Serial.println("=== MODO: MALICIOSO (rotule PortScan) ===");
    Serial.printf("sub-tipo=%d  velocidade=%d  porta fixa=%u\n",
                  subTipoAtaqueEscolhido, perfilVelocidade, portaAlvoFixa);
#else
    Serial.println("=== MODO: NORMAL (rotule Benigno) ===");
#endif
    conectarWiFi();
}

void loop() {
#if MODO_ATAQUE == 1
    executarPassoMalicioso();
#else
    executarPassoNormal();
#endif
    if (WiFi.status() != WL_CONNECTED) conectarWiFi();
}