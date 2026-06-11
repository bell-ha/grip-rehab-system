#define LEFT_DOUT   2
#define LEFT_SCK    3
#define RIGHT_DOUT  4
#define RIGHT_SCK   5

#define LEFT_VIB    9
#define RIGHT_VIB   10

#define BAUD_RATE        115200
#define SEND_INTERVAL_MS 10

long hx711_read(int dout, int sck) {
    while (digitalRead(dout) == HIGH);

    long value = 0;

    for (int i = 0; i < 24; i++) {
        digitalWrite(sck, HIGH);
        delayMicroseconds(1);
        value = (value << 1) | digitalRead(dout);
        digitalWrite(sck, LOW);
        delayMicroseconds(1);
    }

    digitalWrite(sck, HIGH);
    delayMicroseconds(1);
    digitalWrite(sck, LOW);
    delayMicroseconds(1);

    if (value & 0x800000) {
        value |= 0xFF000000;
    }

    return value;
}

bool hx711_ready(int dout) {
    return digitalRead(dout) == LOW;
}

long left_raw  = 0;
long right_raw = 0;
unsigned long last_send_ms = 0;

void setup() {
    Serial.begin(BAUD_RATE);

    pinMode(LEFT_DOUT,  INPUT);
    pinMode(LEFT_SCK,   OUTPUT);
    pinMode(RIGHT_DOUT, INPUT);
    pinMode(RIGHT_SCK,  OUTPUT);

    digitalWrite(LEFT_SCK,  LOW);
    digitalWrite(RIGHT_SCK, LOW);

    /* 진동 액츄에이터 핀 설정 */
    pinMode(LEFT_VIB,  OUTPUT);
    pinMode(RIGHT_VIB, OUTPUT);

    digitalWrite(LEFT_VIB,  LOW);
    digitalWrite(RIGHT_VIB, LOW);

    delay(400);
}

void loop() {
    /* 악력 센서 읽기 */
    if (hx711_ready(LEFT_DOUT)) {
        left_raw = hx711_read(LEFT_DOUT, LEFT_SCK);
    }
    if (hx711_ready(RIGHT_DOUT)) {
        right_raw = hx711_read(RIGHT_DOUT, RIGHT_SCK);
    }

    /* 시리얼 수신 — 라즈베리파이에서 진동 명령 받기
     * 포맷: "L1\n"  → 왼쪽 ON
     *       "L0\n"  → 왼쪽 OFF
     *       "R1\n"  → 오른쪽 ON
     *       "R0\n"  → 오른쪽 OFF
     */
    if (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();

        if      (cmd == "L1") digitalWrite(LEFT_VIB,  HIGH);
        else if (cmd == "L0") digitalWrite(LEFT_VIB,  LOW);
        else if (cmd == "R1") digitalWrite(RIGHT_VIB, HIGH);
        else if (cmd == "R0") digitalWrite(RIGHT_VIB, LOW);
    }

    /* 10ms마다 악력 데이터 전송 */
    unsigned long now = millis();
    if (now - last_send_ms >= SEND_INTERVAL_MS) {
        last_send_ms = now;
        Serial.print(left_raw);
        Serial.print(',');
        Serial.println(right_raw);
    }
}