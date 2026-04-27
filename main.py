import serial
import serial.tools.list_ports
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque

def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if any(keyword in port.description.lower() for keyword in 
               ['arduino', 'usbmodem', 'usbserial', 'ch340', 'cp210']):
            return port.device
    return None

PORT = find_arduino_port()

if PORT is None:
    print("아두이노를 찾을 수 없습니다. 연결을 확인해주세요.")
    exit()

print(f"아두이노 감지됨: {PORT}")

ser = serial.Serial(PORT, 115200, timeout=1)
time.sleep(2)

# ── 영점 조절 ──────────────────────────────────────────
print("영점 조절 중... 5초간 아무것도 올려놓지 마세요!")

calibration_data1 = []
calibration_data2 = []
start_time = time.time()

while time.time() - start_time < 5:
    remaining = 5 - int(time.time() - start_time)
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8').strip()
        if ',' in line:
            values = line.split(',')
            calibration_data1.append(int(values[0]))
            calibration_data2.append(int(values[1]))
            print(f"\r영점 조절 중... {remaining}초 남음", end='', flush=True)

offset1 = sum(calibration_data1) / len(calibration_data1)
offset2 = sum(calibration_data2) / len(calibration_data2)

print(f"\n영점 완료! 기준값 → 로드셀1: {offset1:.0f} | 로드셀2: {offset2:.0f}")
print("그래프 시작...\n")
# ────────────────────────────────────────────────────────

# 최근 200개 데이터만 표시
MAX_POINTS = 200
data1 = deque([0] * MAX_POINTS, maxlen=MAX_POINTS)
data2 = deque([0] * MAX_POINTS, maxlen=MAX_POINTS)

# ── 그래프 설정 ────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
fig.suptitle('로드셀 실시간 데이터', fontsize=14, fontweight='bold')

line1, = ax1.plot(list(data1), color='royalblue', linewidth=1.5)
ax1.set_title('로드셀 1')
ax1.set_ylabel('값 (영점 기준)')
ax1.set_xlim(0, MAX_POINTS)
ax1.axhline(y=0, color='red', linestyle='--', linewidth=0.8)
ax1.grid(True, alpha=0.3)

line2, = ax2.plot(list(data2), color='tomato', linewidth=1.5)
ax2.set_title('로드셀 2')
ax2.set_ylabel('값 (영점 기준)')
ax2.set_xlim(0, MAX_POINTS)
ax2.axhline(y=0, color='red', linestyle='--', linewidth=0.8)
ax2.grid(True, alpha=0.3)

plt.tight_layout()

# ── 애니메이션 업데이트 ────────────────────────────────
def update(frame):
    while ser.in_waiting > 0:
        line = ser.readline().decode('utf-8').strip()
        if ',' in line:
            values = line.split(',')
            try:
                reading1 = int(values[0]) - offset1
                reading2 = int(values[1]) - offset2
                data1.append(reading1)
                data2.append(reading2)
            except ValueError:
                pass

    line1.set_ydata(list(data1))
    line2.set_ydata(list(data2))

    # y축 자동 범위 조정
    ax1.set_ylim(min(data1) - 100, max(data1) + 100)
    ax2.set_ylim(min(data2) - 100, max(data2) + 100)

    return line1, line2

ani = animation.FuncAnimation(fig, update, interval=50, blit=False)

try:
    plt.show()
except KeyboardInterrupt:
    print("\n종료합니다.")
finally:
    ser.close()