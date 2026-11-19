#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#ifndef MODO_ATAQUE
#define MODO_ATAQUE 0   // 0 = inicia normal (feliz), 1 = inicia malicioso (zangado)
#endif

// ---------------------------- CONFIGURAÇÃO DO OLED 0.42" --------------------
// ESP32-C3 + OLED 0.42" (72x40): SCL = GPIO 6, SDA = GPIO 5
U8G2_SSD1306_72X40_ER_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE, 6, 5);

constexpr int BOOT_BUTTON_PIN = 9;
constexpr unsigned long DEBOUNCE_MS = 180;

// ---------------------------- CONFIGURAÇÃO DE REDE ---------------------------
const char* WIFI_SSID  = "KAUA_LQ";
const char* WIFI_SENHA = "12345678";

IPAddress SERVIDOR_NORMAL(192, 168, 137, 1);
const uint16_t PORTA_SERVIDOR_NORMAL = 8500;
const IPAddress GATEWAY_HOTSPOT(192, 168, 137, 1);

const uint16_t PORTAS_COMUNS[] = {21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
                                   1883, 3306, 3389, 8080, 8883};
const int QTD_PORTAS_COMUNS = sizeof(PORTAS_COMUNS) / sizeof(PORTAS_COMUNS[0]);

// ---------------------------- ESTADO COMPARTILHADO (FREERTOS) ----------------
portMUX_TYPE stateMux = portMUX_INITIALIZER_UNLOCKED;

volatile bool modoMalicioso = (MODO_ATAQUE == 1);
int subTipoAtaqueEscolhido = 0;      // 0 misto | 1 brute-force | 2 horizontal
int perfilVelocidade = 0;            // 0 rápido | 1 médio | 2 lento
uint16_t portaAlvoFixa = 22;
uint8_t proximoHostHorizontal = 2;

// Flag para resetar a animação quando o modo muda
volatile bool resetAnimRequested = false;

void sortearParametrosAtaque() {
    int novoSub = (int)(esp_random() % 3);
    int novoVel = (int)(esp_random() % 3);
    uint16_t novaPorta = PORTAS_COMUNS[esp_random() % QTD_PORTAS_COMUNS];

    taskENTER_CRITICAL(&stateMux);
    subTipoAtaqueEscolhido = novoSub;
    perfilVelocidade = novoVel;
    portaAlvoFixa = novaPorta;
    proximoHostHorizontal = 2;
    taskEXIT_CRITICAL(&stateMux);

    Serial.printf("[ATAQUE SORTEADO] sub-tipo=%d | velocidade=%d | porta_fixa=%u\n",
                  novoSub, novoVel, novaPorta);
}

void setModoMalicioso(bool malicioso) {
    taskENTER_CRITICAL(&stateMux);
    modoMalicioso = malicioso;
    resetAnimRequested = true;
    taskEXIT_CRITICAL(&stateMux);

    if (malicioso) {
        sortearParametrosAtaque();
        Serial.println("=== MODO: MALICIOSO (rotule PortScan) ===");
    } else {
        Serial.println("=== MODO: NORMAL (rotule Benigno) ===");
    }
}

bool isModoMalicioso() {
    taskENTER_CRITICAL(&stateMux);
    bool val = modoMalicioso;
    taskEXIT_CRITICAL(&stateMux);
    return val;
}

// ---------------------------- ANIMAÇÃO OLED (72x40) -------------------------
enum AnimPhase {
    PHASE_RAMP_UP = 0,
    PHASE_PEAK_ACTION,
    PHASE_HOLD,
    PHASE_RAMP_DOWN,
    PHASE_PAUSE
};

static AnimPhase animPhase = PHASE_RAMP_UP;
static int animLevel = 0;
static int peakStep = 0;
static int shakeX = 0;
static int shakeY = 0;
static unsigned long lastStepMs = 0;

void resetAnimationState() {
    animPhase = PHASE_RAMP_UP;
    animLevel = 0;
    peakStep = 0;
    shakeX = 0;
    shakeY = 0;
    lastStepMs = millis();
}

void drawAngryFace(int level, int sx, int sy) {
    const int eyeW = 16;
    int eyeH = 14 - (level * 2);
    if (eyeH < 4) eyeH = 4;

    const int centerBaseY = 19;
    int eyeTopY = centerBaseY - (eyeH / 2) + sy;

    int leftEyeX = 12 + sx;
    int rightEyeX = 44 + sx;

    u8g2.drawRBox(leftEyeX, eyeTopY, eyeW, eyeH, 2);
    u8g2.drawRBox(rightEyeX, eyeTopY, eyeW, eyeH, 2);

    if (eyeH >= 8) {
        u8g2.setDrawColor(0);
        int pupilOffsetX = (level >= 4) ? 2 : 0;
        int pupilY = eyeTopY + (eyeH / 2);
        u8g2.drawDisc(leftEyeX + (eyeW / 2) + pupilOffsetX, pupilY, 2);
        u8g2.drawDisc(rightEyeX + (eyeW / 2) + pupilOffsetX, pupilY, 2);
        u8g2.setDrawColor(1);
    }

    int tilt = (level * 3) / 6;
    int browGap = 2;

    int lOuterY = eyeTopY - browGap - tilt;
    int lInnerY = eyeTopY - browGap + (tilt / 2);
    u8g2.drawLine(leftEyeX - 1, lOuterY, leftEyeX + eyeW + 1, lInnerY);
    u8g2.drawLine(leftEyeX - 1, lOuterY + 1, leftEyeX + eyeW + 1, lInnerY + 1);

    int rInnerY = eyeTopY - browGap + (tilt / 2);
    int rOuterY = eyeTopY - browGap - tilt;
    u8g2.drawLine(rightEyeX - 1, rInnerY, rightEyeX + eyeW + 1, rOuterY);
    u8g2.drawLine(rightEyeX - 1, rInnerY + 1, rightEyeX + eyeW + 1, rOuterY + 1);

    int mouthY = 35 + sy;
    u8g2.drawLine(28 + sx, mouthY + 2, 36 + sx, mouthY - 1);
    u8g2.drawLine(36 + sx, mouthY - 1, 44 + sx, mouthY + 2);
}

void drawHappyFace(int level, int sx, int sy) {
    const int eyeW = 16;
    int eyeH = 12 + (level / 3);
    const int centerBaseY = 18;
    int eyeTopY = centerBaseY - (eyeH / 2) + sy;

    int leftEyeX = 12 + sx;
    int rightEyeX = 44 + sx;

    u8g2.drawRBox(leftEyeX, eyeTopY, eyeW, eyeH, 4);
    u8g2.drawRBox(rightEyeX, eyeTopY, eyeW, eyeH, 4);

    int smileArcDrop = (level * 3) / 6;
    u8g2.setDrawColor(0);
    int eyeBottomY = eyeTopY + eyeH - 2;
    u8g2.drawLine(leftEyeX + 2, eyeBottomY, leftEyeX + (eyeW / 2), eyeBottomY - 2 - smileArcDrop);
    u8g2.drawLine(leftEyeX + (eyeW / 2), eyeBottomY - 2 - smileArcDrop, leftEyeX + eyeW - 2, eyeBottomY);

    u8g2.drawLine(rightEyeX + 2, eyeBottomY, rightEyeX + (eyeW / 2), eyeBottomY - 2 - smileArcDrop);
    u8g2.drawLine(rightEyeX + (eyeW / 2), eyeBottomY - 2 - smileArcDrop, rightEyeX + eyeW - 2, eyeBottomY);
    u8g2.setDrawColor(1);

    int arch = (level * 2) / 6;
    int browY = eyeTopY - 3;
    u8g2.drawLine(leftEyeX, browY, leftEyeX + (eyeW / 2), browY - arch);
    u8g2.drawLine(leftEyeX + (eyeW / 2), browY - arch, leftEyeX + eyeW, browY);

    u8g2.drawLine(rightEyeX, browY, rightEyeX + (eyeW / 2), browY - arch);
    u8g2.drawLine(rightEyeX + (eyeW / 2), browY - arch, rightEyeX + eyeW, browY);

    int mouthY = 33 + sy;
    int smileDepth = 2 + (level / 3);
    u8g2.drawLine(27 + sx, mouthY - smileDepth, 36 + sx, mouthY + 1);
    u8g2.drawLine(36 + sx, mouthY + 1, 45 + sx, mouthY - smileDepth);
    u8g2.drawLine(27 + sx, mouthY - smileDepth + 1, 36 + sx, mouthY + 2);
    u8g2.drawLine(36 + sx, mouthY + 2, 45 + sx, mouthY - smileDepth + 1);
}

void renderCurrentFace(bool malicioso) {
    u8g2.clearBuffer();
    if (malicioso) {
        drawAngryFace(animLevel, shakeX, shakeY);
    } else {
        drawHappyFace(animLevel, shakeX, shakeY);
    }
    u8g2.sendBuffer();
}

void stepAnimation(bool malicioso) {
    taskENTER_CRITICAL(&stateMux);
    bool shouldReset = resetAnimRequested;
    if (shouldReset) {
        resetAnimRequested = false;
    }
    taskEXIT_CRITICAL(&stateMux);

    if (shouldReset) {
        resetAnimationState();
        renderCurrentFace(malicioso);
        return;
    }

    unsigned long now = millis();
    unsigned long intervalMs = 70;

    switch (animPhase) {
        case PHASE_RAMP_UP:
            intervalMs = 70;
            if (now - lastStepMs >= intervalMs) {
                lastStepMs = now;
                shakeX = 0;
                shakeY = 0;
                renderCurrentFace(malicioso);
                if (animLevel < 6) {
                    animLevel++;
                } else {
                    animPhase = PHASE_PEAK_ACTION;
                    peakStep = 0;
                }
            }
            break;

        case PHASE_PEAK_ACTION:
            intervalMs = 55;
            if (now - lastStepMs >= intervalMs) {
                lastStepMs = now;
                animLevel = 6;
                if (malicioso) {
                    shakeX = (int)random(-1, 2);
                    shakeY = (int)random(-1, 2);
                } else {
                    shakeX = 0;
                    shakeY = (peakStep % 2 == 0) ? -1 : 0;
                }
                renderCurrentFace(malicioso);
                peakStep++;
                if (peakStep >= 14) {
                    shakeX = 0;
                    shakeY = 0;
                    animPhase = PHASE_HOLD;
                    lastStepMs = now;
                }
            }
            break;

        case PHASE_HOLD:
            if (now - lastStepMs >= 850) {
                animPhase = PHASE_RAMP_DOWN;
                lastStepMs = now;
            }
            break;

        case PHASE_RAMP_DOWN:
            intervalMs = 60;
            if (now - lastStepMs >= intervalMs) {
                lastStepMs = now;
                shakeX = 0;
                shakeY = 0;
                renderCurrentFace(malicioso);
                if (animLevel > 0) {
                    animLevel--;
                } else {
                    animPhase = PHASE_PAUSE;
                    lastStepMs = now;
                }
            }
            break;

        case PHASE_PAUSE:
            if (now - lastStepMs >= 450) {
                animPhase = PHASE_RAMP_UP;
                animLevel = 0;
                lastStepMs = now;
            }
            break;
    }
}

void pollBootButton() {
    static bool lastReading = HIGH;
    static unsigned long lastPressMs = 0;

    bool reading = digitalRead(BOOT_BUTTON_PIN);
    unsigned long now = millis();

    if (lastReading == HIGH && reading == LOW) {
        if (now - lastPressMs >= DEBOUNCE_MS) {
            lastPressMs = now;
            bool proximoEstado = !isModoMalicioso();
            setModoMalicioso(proximoEstado);
        }
    }
    lastReading = reading;
}

// ---------------------------- OPERAÇÃO DE REDE -------------------------------
void conectarWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;

    Serial.printf("[WIFI] Conectando a '%s'...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_SENHA);

    while (WiFi.status() != WL_CONNECTED) {
        vTaskDelay(pdMS_TO_TICKS(300));
        Serial.print(".");
    }
    Serial.printf("\n[WIFI] Conectado! IP do ESP32: %s  <-- use este IP na coleta\n",
                  WiFi.localIP().toString().c_str());
}

void executarPassoNormal() {
    WiFiClient client;
    if (client.connect(SERVIDOR_NORMAL, PORTA_SERVIDOR_NORMAL, 1000)) {
        client.print(String("GET / HTTP/1.1\r\nHost: ") +
                     SERVIDOR_NORMAL.toString() + "\r\nConnection: close\r\n\r\n");
        unsigned long t0 = millis();
        while (client.connected() && millis() - t0 < 500) {
            while (client.available()) client.read();
            vTaskDelay(pdMS_TO_TICKS(5));
        }
    } else {
        Serial.println("[NORMAL] Falha de conexão (o http.server está rodando?).");
    }
    client.stop();

    long jitter = (long)(esp_random() % 1000) - 500;
    long delayMs = 4000 + jitter;
    if (delayMs < 500) delayMs = 500;
    vTaskDelay(pdMS_TO_TICKS((uint32_t)delayMs));
}

uint32_t esperaEntreTentativas(int vel) {
    switch (vel) {
        case 0:  return 5 + (esp_random() % 45);      // 5-50 ms
        case 1:  return 50 + (esp_random() % 350);    // 50-400 ms
        default: return 300 + (esp_random() % 1700);  // 0.3-2 s
    }
}

void executarPassoMalicioso() {
    int sub;
    int vel;
    uint16_t portaFixa;
    uint8_t hostHoriz;

    taskENTER_CRITICAL(&stateMux);
    sub = subTipoAtaqueEscolhido;
    vel = perfilVelocidade;
    portaFixa = portaAlvoFixa;
    hostHoriz = proximoHostHorizontal;
    if (sub == 2) {
        proximoHostHorizontal = (proximoHostHorizontal >= 250) ? 2 : (proximoHostHorizontal + 1);
    }
    taskEXIT_CRITICAL(&stateMux);

    IPAddress alvo;
    uint16_t porta;

    if (sub == 1) {                                       // brute-force
        alvo = GATEWAY_HOTSPOT;
        porta = portaFixa;
    } else if (sub == 2) {                                // horizontal
        alvo = IPAddress(10, 77, 0, hostHoriz);
        porta = portaFixa;
    } else {                                              // misto
        alvo = (esp_random() % 2 == 0) ? GATEWAY_HOTSPOT : IPAddress(10, 77, 0, 2 + (esp_random() % 250));
        porta = (esp_random() % 3 == 0) ? (uint16_t)(1024 + (esp_random() % 64000)) : PORTAS_COMUNS[esp_random() % QTD_PORTAS_COMUNS];
    }

    WiFiClient client;
    bool conectou = client.connect(alvo, porta, 150);
    if (conectou) client.stop();

    vTaskDelay(pdMS_TO_TICKS(esperaEntreTentativas(vel)));
}

// ---------------------------- TAREFAS FREERTOS -------------------------------
void taskDisplay(void* pvParameters) {
    (void)pvParameters;
    pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
    u8g2.begin();
    u8g2.setContrast(255);
    resetAnimationState();
    renderCurrentFace(isModoMalicioso());

    for (;;) {
        pollBootButton();
        stepAnimation(isModoMalicioso());
        vTaskDelay(pdMS_TO_TICKS(15));
    }
}

void taskNetwork(void* pvParameters) {
    (void)pvParameters;
    conectarWiFi();

    for (;;) {
        conectarWiFi();
        if (isModoMalicioso()) {
            executarPassoMalicioso();
        } else {
            executarPassoNormal();
        }
    }
}

void setup() {
    Serial.begin(115200);
    delay(500);
    randomSeed(esp_random());

    bool iniciaMalicioso = (MODO_ATAQUE == 1);
    if (iniciaMalicioso) {
        sortearParametrosAtaque();
        Serial.println("=== MODO INICIAL: MALICIOSO (rotule PortScan) ===");
    } else {
        Serial.println("=== MODO INICIAL: NORMAL (rotule Benigno) ===");
    }

    xTaskCreate(taskDisplay, "DisplayTask", 4096, nullptr, 3, nullptr);
    xTaskCreate(taskNetwork, "NetworkTask", 6144, nullptr, 2, nullptr);
}

void loop() {
    // Tudo é gerenciado pelas tarefas FreeRTOS; libera o loop principal
    vTaskDelay(pdMS_TO_TICKS(1000));
}