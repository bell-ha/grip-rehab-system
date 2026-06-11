import serial
import time

ser = serial.Serial(
    port='/dev/cu.usbmodem141011',
    baudrate=115200,
    timeout=1
)

time.sleep(2)  # 아두이노 재시작 대기

def vib_left_on():
    ser.write(b'L1\n')

def vib_left_off():
    ser.write(b'L0\n')

def vib_right_on():
    ser.write(b'R1\n')

def vib_right_off():
    ser.write(b'R0\n')

def read_grip():
    line = ser.readline().decode('utf-8').strip()
    if ',' in line:
        left, right = line.split(',')
        return int(left), int(right)
    return None, None

print("시작! q로 종료, 1/2/3/4로 진동 제어")
print("1: 왼쪽 ON  2: 왼쪽 OFF  3: 오른쪽 ON  4: 오른쪽 OFF")

import sys
import select

while True:
    # 악력 읽기
    left, right = read_grip()
    if left is not None:
        print(f"왼손: {left}  오른손: {right}")

    # 키 입력 확인 (논블로킹)
    if select.select([sys.stdin], [], [], 0)[0]:
        key = sys.stdin.readline().strip()
        if key == 'q':
            print("종료")
            break
        elif key == '1':
            vib_left_on()
            print("왼쪽 진동 ON")
        elif key == '2':
            vib_left_off()
            print("왼쪽 진동 OFF")
        elif key == '3':
            vib_right_on()
            print("오른쪽 진동 ON")
        elif key == '4':
            vib_right_off()
            print("오른쪽 진동 OFF")

ser.close()