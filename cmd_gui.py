#!/usr/bin/env python3
"""
CMD GUI Tool - Windows 명령어 실행 GUI 프로그램
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import subprocess
import threading
import os
import sys
from datetime import datetime
import re

class CMDGui:
    def __init__(self, root):
        self.root = root
        self.root.title("FPK ADB CMD Sender 1.10")
        self.root.geometry("550x550")
        self.root.minsize(450, 450)
        
        # 스타일 설정
        self.setup_styles()
        
        # GUI 구성 요소 생성
        self.create_widgets()
        
        # 이벤트 바인딩
        self.bind_events()
        
        # 초기 설정
        self.current_directory = os.getcwd()
        self.dir_history = []  # 디렉토리 히스토리
        self.adb_folder = ""  # ADB 폴더 경로 (비어있으면 기본 PATH 사용)
        self.settings_file = os.path.join(self.current_directory, "adb_settings.txt")
        self.settings_window = None  # 환경설정 창 참조
        self.device_id = "ABC-0123456789"  # 고정 디바이스 ID

        # 저장된 ADB 폴더 설정 로드
        self.load_adb_settings()

        # 시작 시 ADB 상태 확인 (0.5초 후 실행)
        self.root.after(500, self.update_all_adb_status)
        
        # 주기적 전체 연결 상태 확인
        self.all_connected = False  # 전체 연결 상태 추적
        self.start_periodic_connection_check()
        
    def setup_styles(self):
        """GUI 스타일 설정"""
        style = ttk.Style()
        style.theme_use('winnative')
        
    def create_widgets(self):
        """GUI 위젯들을 생성합니다 - 키패드 레이아웃"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 상단 환경설정 버튼과 안내문구
        settings_frame = ttk.Frame(main_frame)
        settings_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

        # 환경설정 버튼 (높이 증가)
        settings_btn = ttk.Button(settings_frame, text="환경설정",
                                 command=self.open_settings)
        settings_btn.grid(row=0, column=0, pady=5, padx=(0, 10), ipady=8)

        # 연결 상태 메시지
        self.connection_status_label = ttk.Label(settings_frame, text="연결 상태 확인 중...",
                 foreground="orange", font=('Arial', 9, 'bold'))
        self.connection_status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

        # ADB Shell 상태 표시 (신호등)
        status_frame = ttk.Frame(settings_frame)
        status_frame.grid(row=0, column=2, sticky=tk.E, padx=5)
        
        ttk.Label(status_frame, text="ADB Shell:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_canvas = tk.Canvas(status_frame, width=20, height=20, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT)
        
        # 초기 상태: 회색 (Unknown)
        self.status_light = self.status_canvas.create_oval(2, 2, 18, 18, fill="gray", outline="gray")

        # 숨겨진 명령어 입력 필드 (키패드에서 명령어 설정용)
        self.cmd_entry = ttk.Entry(main_frame, width=1)
        self.cmd_entry.grid(row=1, column=0, sticky="w")
        self.cmd_entry.grid_remove()  # 화면에서 숨김

        # 키패드 스타일 버튼 프레임 (3x4 그리드)
        keypad_frame = ttk.Frame(main_frame)
        keypad_frame.grid(row=2, column=0, columnspan=3, pady=(10, 10))

        # 키패드 버튼 정의 (숫자 키패드 레이아웃)
        # 7 8 9
        # 4 5 6
        # 1 2 3
        # 0
        keypad_buttons = {
            # 첫 번째 행 (7, 8, 9)
            (0, 0): ("FAS\n7 (Home)", self.go_home),
            (0, 1): ("UP\n8 (▲)", self.move_up),
            (0, 2): ("사용안함\n9", None),  # 비활성화

            # 두 번째 행 (4, 5, 6)
            (1, 0): ("MENU UP\n4 (◀)", self.move_left),
            (1, 1): ("OK\n5 (Enter)", self.run_command),
            (1, 2): ("MENU DOWN\n6 (▶)", self.move_right),

            # 세 번째 행 (1, 2, 3)
            (2, 0): ("SIGNAL\n1", self.focus_signal_input),
            (2, 1): ("DOWN\n2 (▼)", self.move_down),
            (2, 2): ("VIEW\n3 (PgDn)", self.save_output),

            # 네 번째 행 (0)
            (3, 1): ("로그지우기\n0", self.clear_output)
        }

        # 키패드 버튼 생성 (1.3배 크게, 동작명을 위에 표시)
        self.keypad_btns = {}
        for (row, col), (text, command) in keypad_buttons.items():
            if command is None:  # 비활성화된 버튼
                btn = ttk.Button(keypad_frame, text=text, state=tk.DISABLED, width=16)
            else:
                btn = ttk.Button(keypad_frame, text=text, command=command, width=16)
            btn.grid(row=row, column=col, padx=8, pady=8, sticky=(tk.W, tk.E), ipady=8)
            self.keypad_btns[(row, col)] = btn

        # 사용자 Signal 전송 입력 (신호 이름 + 값)
        signal_frame = ttk.Frame(main_frame)
        signal_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(signal_frame, text="Signal:").grid(row=0, column=0, sticky=tk.W)

        self.signal_name_var = tk.StringVar()
        self.signal_value_var = tk.StringVar()

        self.signal_name_entry = ttk.Entry(signal_frame, textvariable=self.signal_name_var, width=28)
        self.signal_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(6, 6))
        self.signal_name_entry.insert(0, "DP_ID_")

        ttk.Label(signal_frame, text="Value:").grid(row=0, column=2, sticky=tk.W, padx=(6, 0))

        self.signal_value_entry = ttk.Entry(signal_frame, textvariable=self.signal_value_var, width=10)
        self.signal_value_entry.grid(row=0, column=3, sticky=tk.W, padx=(6, 6))
        self.signal_value_entry.bind('<Return>', lambda e: self.send_custom_signal())

        send_signal_btn = ttk.Button(signal_frame, text="Send", command=self.send_custom_signal)
        send_signal_btn.grid(row=0, column=4, sticky=tk.E, padx=(0, 0), ipady=4)

        # Preset signals (KBI view request)
        preset1_btn = ttk.Button(
            signal_frame,
            text="DP_ID_*_KBI_VIEW_REQUEST = 1",
            command=lambda: self.send_kbi_view_request(1),
        )
        preset1_btn.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=(0, 6), pady=(6, 0), ipady=2)

        preset3_btn = ttk.Button(
            signal_frame,
            text="DP_ID_*_KBI_VIEW_REQUEST = 3",
            command=lambda: self.send_kbi_view_request(3),
        )
        preset3_btn.grid(row=1, column=3, columnspan=2, sticky=(tk.W, tk.E), padx=(0, 0), pady=(6, 0), ipady=2)

        signal_frame.columnconfigure(1, weight=1)

        # 출력 결과 표시
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        ttk.Label(output_frame, text="실행 결과:").grid(row=0, column=0, sticky=tk.W)

        # 스크롤 가능한 텍스트 위젯 (높이를 반으로 줄임)
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            height=8,
            width=80,
            font=('Consolas', 9),
            wrap=tk.WORD
        )
        self.output_text.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))



        # 그리드 가중치 설정
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)  # 출력 프레임이 row=4
        settings_frame.columnconfigure(1, weight=1)  # 환경설정 버튼과 안내문구
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)
    
    def bind_events(self):
        """이벤트 바인딩 - 키패드 숫자키 포함"""
        # 기본 키 바인딩
        self.cmd_entry.bind('<Return>', lambda e: self.run_command())
        self.cmd_entry.bind('<Control-l>', lambda e: self.clear_command())
        self.root.bind('<Control-r>', lambda e: self.run_command())
        self.root.bind('<F5>', lambda e: self.run_command())


        # 키패드 숫자키 바인딩 (9번 제외)
        self.root.bind('<KeyPress-KP_7>', lambda e: self.go_home())
        self.root.bind('<KeyPress-KP_8>', lambda e: self.move_up())
        # KP_9는 비활성화
        self.root.bind('<KeyPress-KP_4>', lambda e: self.move_left())
        self.root.bind('<KeyPress-KP_5>', lambda e: self.run_command())
        self.root.bind('<KeyPress-KP_6>', lambda e: self.move_right())
        self.root.bind('<KeyPress-KP_1>', lambda e: self.focus_signal_input())
        self.root.bind('<KeyPress-KP_2>', lambda e: self.move_down())
        self.root.bind('<KeyPress-KP_3>', lambda e: self.save_output())
        self.root.bind('<KeyPress-KP_0>', lambda e: self.clear_output())

        # 일반 숫자키도 지원 (키패드가 없는 경우, 9번 제외)
        self.root.bind('<KeyPress-7>', lambda e: self.go_home())
        self.root.bind('<KeyPress-8>', lambda e: self.move_up())
        # 9는 비활성화
        self.root.bind('<KeyPress-4>', lambda e: self.move_left())
        self.root.bind('<KeyPress-5>', lambda e: self.run_command())
        self.root.bind('<KeyPress-6>', lambda e: self.move_right())
        self.root.bind('<KeyPress-1>', lambda e: self.focus_signal_input())
        self.root.bind('<KeyPress-2>', lambda e: self.move_down())
        self.root.bind('<KeyPress-3>', lambda e: self.save_output())
        self.root.bind('<KeyPress-0>', lambda e: self.clear_output())

        # 특수키 바인딩
        self.root.bind('<Home>', lambda e: self.go_home())          # 7번 - Home키
        self.root.bind('<Up>', lambda e: self.move_up())            # 8번 - 위쪽 화살표
        self.root.bind('<Left>', lambda e: self.move_left())        # 4번 - 왼쪽 화살표
        self.root.bind('<Return>', lambda e: self.run_command())    # 5번 - Enter키
        self.root.bind('<Right>', lambda e: self.move_right())      # 6번 - 오른쪽 화살표
        self.root.bind('<Down>', lambda e: self.move_down())        # 2번 - 아래쪽 화살표
        self.root.bind('<Next>', lambda e: self.save_output())      # 3번 - Page Down키
    
    def update_directory_label(self):
        """현재 디렉토리 상태 업데이트 (라벨 없이)"""
        # 출력창에 현재 디렉토리 표시
        pass

    def change_directory(self):
        """디렉토리 변경 (키패드 전용)"""
        from tkinter import filedialog
        directory = filedialog.askdirectory(initialdir=self.current_directory)
        if directory:
            self.current_directory = directory
            os.chdir(directory)
            self.output_text.insert(tk.END, f"디렉토리 변경: {directory}\n")
            self.output_text.see(tk.END)
    
    def set_command(self, command):
        """명령어 입력 필드에 명령어 설정"""
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.insert(0, command)
        self.cmd_entry.focus()
    
    def clear_command(self):
        """명령어 입력 필드 지우기"""
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.focus()

    def log_to_output(self, message):
        """출력창에 로그 메시지 추가"""
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)
        # GUI 업데이트를 위해 잠시 대기
        self.root.update_idletasks()

    def load_adb_settings(self):
        """저장된 ADB 설정 로드"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_folder = f.read().strip()
                    if saved_folder and os.path.exists(saved_folder):
                        self.adb_folder = saved_folder
                        self.log_to_output(f"[설정 로드] 저장된 ADB 폴더: {self.adb_folder}")
                    else:
                        self.log_to_output("[설정 로드] 저장된 ADB 폴더가 존재하지 않아 기본값 사용")
        except Exception as e:
            self.log_to_output(f"[설정 로드 오류] {str(e)}")

    def save_adb_settings(self):
        """ADB 설정 저장"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                f.write(self.adb_folder)
            self.log_to_output(f"[설정 저장] ADB 폴더 설정이 저장되었습니다: {self.adb_folder}")
        except Exception as e:
            self.log_to_output(f"[설정 저장 오류] {str(e)}")

    def get_adb_command(self, command=""):
        """ADB 명령어 생성 (폴더 지정 여부에 따라, 디바이스 ID 포함)"""
        # 기본 adb 경로 결정
        if self.adb_folder and os.path.exists(self.adb_folder):
            # 지정된 폴더의 adb.exe 사용
            adb_exe = os.path.join(self.adb_folder, "adb.exe")
            if os.path.exists(adb_exe):
                base_cmd = f'"{adb_exe}"'
            else:
                # adb.exe가 없으면 기본 명령어 사용
                self.log_to_output(f"[경고] 지정된 폴더에 adb.exe가 없습니다: {self.adb_folder}")
                base_cmd = "adb"
        else:
            # 기본 adb 명령어 사용 (PATH에서 찾기)
            base_cmd = "adb"
        
        # 디바이스 ID 추가
        if command:
            return f"{base_cmd} -s {self.device_id} {command}"
        else:
            return f"{base_cmd} -s {self.device_id}"

    def check_adb_installation(self):
        """ADB 설치 상태 확인"""
        try:
            # adb 명령어 실행하여 설치 상태 확인
            adb_cmd = self.get_adb_command()
            if self.adb_folder:
                self.log_to_output(f"[ADB 설치 확인] 지정된 ADB 폴더: {self.adb_folder}")
            else:
                self.log_to_output("[ADB 설치 확인] 기본 ADB 명령어 사용 (PATH에서 검색)")
            self.log_to_output(f"[ADB 설치 확인] 실행 명령어: {adb_cmd}")

            process = subprocess.Popen(
                adb_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=10)

            # 받은 값들을 출력창에 로그
            self.log_to_output(f"[ADB 설치 확인] 반환 코드: {process.returncode}")
            if stdout.strip():
                self.log_to_output(f"[ADB 설치 확인] STDOUT:\n{stdout}")
            if stderr.strip():
                self.log_to_output(f"[ADB 설치 확인] STDERR:\n{stderr}")

            # ADB 설치 여부 더 정확한 판단
            # 1. 반환 코드가 9009인 경우 = 명령어를 찾을 수 없음 (Windows)
            if process.returncode == 9009:
                self.log_to_output("[ADB 설치 확인] ❌ 명령어를 찾을 수 없음 (반환코드: 9009)")
                return False, "ADB 명령어를 찾을 수 없습니다. PATH에 등록되지 않았거나 설치되지 않았습니다."

            # 2. stderr에 특정 에러 메시지가 있는 경우
            if "'adb'은(는) 내부 또는 외부 명령" in stderr or "'adb' is not recognized" in stderr:
                self.log_to_output("[ADB 설치 확인] ❌ 명령어 인식 실패")
                return False, "ADB 명령어가 인식되지 않습니다. 설치되지 않았거나 PATH에 등록되지 않았습니다."

            # 3. Android Debug Bridge 문구가 있으면 설치됨
            if "Android Debug Bridge" in stdout or "Android Debug Bridge" in stderr:
                self.log_to_output("[ADB 설치 확인] ✅ ADB 설치 확인됨 (Android Debug Bridge 문구 발견)")
                return True, "ADB가 정상적으로 설치되어 있습니다."

            # 4. 반환 코드가 1이고 도움말이 표시되면 설치됨
            if process.returncode == 1 and ("usage:" in stdout.lower() or "usage:" in stderr.lower()):
                self.log_to_output("[ADB 설치 확인] ✅ ADB 설치 확인됨 (도움말 표시)")
                return True, "ADB가 정상적으로 설치되어 있습니다."

            # 5. adb version 명령어로 추가 확인
            self.log_to_output("[ADB 설치 확인] 추가 확인: adb version 명령어 실행...")
            try:
                version_cmd = self.get_adb_command("version")
                version_process = subprocess.Popen(
                    version_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='cp949',
                    cwd=self.current_directory
                )
                version_stdout, version_stderr = version_process.communicate(timeout=5)

                self.log_to_output(f"[ADB 설치 확인] adb version 반환 코드: {version_process.returncode}")
                if version_stdout.strip():
                    self.log_to_output(f"[ADB 설치 확인] adb version STDOUT:\n{version_stdout}")
                if version_stderr.strip():
                    self.log_to_output(f"[ADB 설치 확인] adb version STDERR:\n{version_stderr}")

                if version_process.returncode == 0 and ("Android Debug Bridge" in version_stdout or "version" in version_stdout.lower()):
                    self.log_to_output("[ADB 설치 확인] ✅ ADB 설치 확인됨 (adb version 성공)")
                    return True, "ADB가 정상적으로 설치되어 있습니다."

            except Exception as ve:
                self.log_to_output(f"[ADB 설치 확인] adb version 실행 실패: {str(ve)}")

            # 6. 그 외의 경우는 설치되지 않은 것으로 판단
            self.log_to_output(f"[ADB 설치 확인] ❌ ADB 설치 확인 실패 (반환코드: {process.returncode})")
            return False, f"ADB 설치 상태를 확인할 수 없습니다. (반환코드: {process.returncode})"

        except subprocess.TimeoutExpired:
            self.log_to_output("[ADB 설치 확인] ❌ 실행 시간 초과")
            return False, "ADB 명령어 실행 시간 초과"
        except FileNotFoundError:
            self.log_to_output("[ADB 설치 확인] ❌ 파일을 찾을 수 없음 (FileNotFoundError)")
            return False, "ADB가 설치되지 않았거나 PATH에 등록되지 않았습니다."
        except OSError as e:
            if e.errno == 2:  # No such file or directory
                self.log_to_output("[ADB 설치 확인] ❌ 파일을 찾을 수 없음 (OSError)")
                return False, "ADB 실행 파일을 찾을 수 없습니다."
            else:
                self.log_to_output(f"[ADB 설치 확인] ❌ OS 오류: {str(e)}")
                return False, f"시스템 오류: {str(e)}"
        except Exception as e:
            self.log_to_output(f"[ADB 설치 확인] ❌ 예외 발생: {str(e)}")
            return False, f"ADB 확인 중 오류 발생: {str(e)}"

    def check_adb_devices(self):
        """ADB 디바이스 연결 상태 확인"""
        try:
            # adb devices 명령어로 연결된 디바이스 확인
            self.log_to_output("[디바이스 확인] adb devices 명령어 실행 중...")

            devices_cmd = self.get_adb_command("devices")
            process = subprocess.Popen(
                devices_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=15)

            # 받은 값들을 출력창에 로그
            self.log_to_output(f"[디바이스 확인] 반환 코드: {process.returncode}")
            if stdout.strip():
                self.log_to_output(f"[디바이스 확인] STDOUT:\n{stdout}")
            if stderr.strip():
                self.log_to_output(f"[디바이스 확인] STDERR:\n{stderr}")

            if process.returncode == 0:
                lines = stdout.strip().split('\n')
                devices = []
                for line in lines[1:]:  # 첫 번째 줄은 "List of devices attached"
                    if line.strip() and '\t' in line:
                        device_info = line.strip().split('\t')
                        if len(device_info) >= 2:
                            devices.append((device_info[0], device_info[1]))

                if devices:
                    device_list = []
                    for device_id, status in devices:
                        device_list.append(f"{device_id} ({status})")
                    self.log_to_output(f"[디바이스 확인] ✅ 발견된 디바이스: {len(devices)}개")
                    return True, f"연결된 디바이스: {', '.join(device_list)}"
                else:
                    self.log_to_output("[디바이스 확인] ❌ 연결된 디바이스 없음")
                    return False, "연결된 디바이스가 없습니다."
            else:
                self.log_to_output("[디바이스 확인] ❌ adb devices 실행 실패")
                return False, f"adb devices 실행 실패: {stderr}"

        except subprocess.TimeoutExpired:
            self.log_to_output("[디바이스 확인] ❌ 실행 시간 초과")
            return False, "adb devices 명령어 실행 시간 초과"
        except Exception as e:
            self.log_to_output(f"[디바이스 확인] ❌ 예외 발생: {str(e)}")
            return False, f"디바이스 확인 중 오류 발생: {str(e)}"

    def check_adb_shell(self):
        """ADB shell 연결 테스트"""
        try:
            # adb shell echo 명령어로 shell 연결 테스트
            self.log_to_output('[Shell 테스트] adb shell echo "ADB Shell Test" 명령어 실행 중...')

            shell_cmd = self.get_adb_command('shell echo "ADB Shell Test"')
            process = subprocess.Popen(
                shell_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=15)

            # 받은 값들을 출력창에 로그
            self.log_to_output(f"[Shell 테스트] 반환 코드: {process.returncode}")
            if stdout.strip():
                self.log_to_output(f"[Shell 테스트] STDOUT:\n{stdout}")
            if stderr.strip():
                self.log_to_output(f"[Shell 테스트] STDERR:\n{stderr}")

            if process.returncode == 0 and "ADB Shell Test" in stdout:
                self.log_to_output("[Shell 테스트] ✅ Shell 연결 성공")
                return True, "ADB Shell 연결이 정상적으로 작동합니다."
            elif "no devices/emulators found" in stderr:
                self.log_to_output("[Shell 테스트] ❌ 디바이스 없음")
                return False, "연결된 디바이스가 없어 Shell 테스트를 할 수 없습니다."
            elif "device unauthorized" in stderr:
                self.log_to_output("[Shell 테스트] ❌ 디바이스 인증 실패")
                return False, "디바이스가 인증되지 않았습니다. USB 디버깅 허용을 확인하세요."
            elif "device offline" in stderr:
                self.log_to_output("[Shell 테스트] ❌ 디바이스 오프라인")
                return False, "디바이스가 오프라인 상태입니다."
            else:
                self.log_to_output("[Shell 테스트] ❌ Shell 연결 실패")
                return False, f"ADB Shell 연결 실패: {stderr}"

        except subprocess.TimeoutExpired:
            self.log_to_output("[Shell 테스트] ❌ 실행 시간 초과")
            return False, "ADB Shell 명령어 실행 시간 초과"
        except Exception as e:
            self.log_to_output(f"[Shell 테스트] ❌ 예외 발생: {str(e)}")
            return False, f"ADB Shell 테스트 중 오류 발생: {str(e)}"

    def open_settings(self):
        """환경설정 창 열기"""
        # 이미 환경설정 창이 열려있으면 포커스만 이동
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.focus()
            self.settings_window.lift()
            return
        
        settings_window = tk.Toplevel(self.root)
        self.settings_window = settings_window
        settings_window.title("환경설정 - ADB 상태 확인")
        settings_window.geometry("510x480")
        settings_window.resizable(False, False)

        # 창이 닫힐 때 참조 제거
        def on_close():
            self.settings_window = None
            settings_window.destroy()
        
        settings_window.protocol("WM_DELETE_WINDOW", on_close)

        # 설정 창을 메인 창 위에 위치
        settings_window.transient(self.root)
        settings_window.grab_set()

        # 메인 창의 위치를 기준으로 설정창 위치 조정
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()

        # 설정창을 메인창 중앙에 위치
        settings_x = main_x + (main_width - 510) // 2
        settings_y = main_y + (main_height - 480) // 2

        settings_window.geometry(f"510x480+{settings_x}+{settings_y}")

        # 설정 내용 프레임
        settings_frame = ttk.Frame(settings_window, padding="20")
        settings_frame.pack(fill=tk.BOTH, expand=True)

        # 제목
        ttk.Label(settings_frame, text="FPK ADB CMD Sender 설정",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        # ADB 폴더 설정 프레임
        path_frame = ttk.LabelFrame(settings_frame, text="ADB 폴더 설정", padding="10")
        path_frame.pack(fill=tk.X, pady=(0, 5))

        # 현재 ADB 폴더 표시
        current_path_frame = ttk.Frame(path_frame)
        current_path_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(current_path_frame, text="현재 ADB 폴더:").pack(side=tk.LEFT)
        current_folder_text = self.adb_folder if self.adb_folder else "기본값 (PATH에서 검색)"
        self.current_adb_folder_label = ttk.Label(current_path_frame, text=current_folder_text,
                                                 foreground="blue", font=('Consolas', 9))
        self.current_adb_folder_label.pack(side=tk.LEFT, padx=(5, 0))

        # ADB 폴더 선택 버튼
        path_buttons_frame = ttk.Frame(path_frame)
        path_buttons_frame.pack(fill=tk.X)

        ttk.Button(path_buttons_frame, text="폴더 선택",
                  command=self.browse_adb_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(path_buttons_frame, text="기본값으로",
                  command=self.reset_adb_folder).pack(side=tk.LEFT)

        # ADB 설치 상태 확인 프레임
        adb_frame = ttk.LabelFrame(settings_frame, text="ADB 설치 상태", padding="10")
        adb_frame.pack(fill=tk.X, pady=(0, 5))

        # ADB 설치 상태 표시 라벨
        self.adb_status_label = ttk.Label(adb_frame, text="ADB 상태를 확인하는 중...",
                                         font=('Arial', 10))
        self.adb_status_label.pack(pady=2)

        # 디바이스 연결 상태 확인 프레임
        device_frame = ttk.LabelFrame(settings_frame, text="디바이스 연결 상태", padding="10")
        device_frame.pack(fill=tk.X, pady=(0, 5))

        # 디바이스 상태 표시 라벨
        self.device_status_label = ttk.Label(device_frame, text="디바이스 상태를 확인하는 중...",
                                           font=('Arial', 10))
        self.device_status_label.pack(pady=2)

        # ADB Shell 테스트 프레임
        shell_frame = ttk.LabelFrame(settings_frame, text="ADB Shell 연결 테스트", padding="10")
        shell_frame.pack(fill=tk.X, pady=(0, 10))

        # Shell 테스트 상태 표시 라벨
        self.shell_status_label = ttk.Label(shell_frame, text="Shell 연결을 테스트하는 중...",
                                          font=('Arial', 10))
        self.shell_status_label.pack(pady=2)

        # 전체 상태 다시 확인 버튼
        ttk.Button(settings_frame, text="전체 상태 다시 확인",
                  command=lambda: self.update_all_adb_status()).pack(pady=5)

        # 닫기 버튼 (높이 증가)
        ttk.Button(settings_frame, text="닫기",
                  command=on_close).pack(pady=(10, 0), ipady=8)

        # 초기 전체 ADB 상태 확인
        self.update_all_adb_status()

    def start_periodic_connection_check(self):
        """주기적으로 전체 연결 상태 확인 (3초마다 지속 체크)"""
        self.last_shell_status = False  # 이전 상태 추적용
        
        def periodic_check():
            # 전체 연결 상태 조용히 확인
            def check_all_thread():
                # 1. ADB 설치 확인
                adb_installed = self.check_adb_installation_silent()
                
                if adb_installed:
                    # 2. 특정 디바이스 연결 확인 (ID: ABC-0123456789)
                    device_connected = self.check_adb_devices_silent()
                    
                    if device_connected:
                        # 3. ADB Shell 테스트
                        shell_working, _ = self.check_adb_shell_silent()
                        
                        if shell_working is not None:
                            # 전체 상태 업데이트
                            all_ok = shell_working
                            self.root.after(0, lambda: self.update_connection_status(adb_installed, device_connected, shell_working, all_ok))
                        else:
                            # Shell 체크 실패 시 이전 상태 유지
                            pass
                    else:
                        self.root.after(0, lambda: self.update_connection_status(adb_installed, device_connected, False, False))
                else:
                    self.root.after(0, lambda: self.update_connection_status(adb_installed, False, False, False))
            
            thread = threading.Thread(target=check_all_thread)
            thread.daemon = True
            thread.start()
            
            # 연결 여부와 관계없이 3초마다 계속 반복
            self.root.after(3000, periodic_check)
        
        # 첫 실행
        periodic_check()

    def check_adb_installation_silent(self):
        """ADB 설치 상태 확인 (조용히, 로그 없이)"""
        try:
            adb_cmd = self.get_adb_command("version")
            process = subprocess.Popen(
                adb_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=5)
            return process.returncode == 0 and ("Android Debug Bridge" in stdout or "version" in stdout.lower())
        except:
            return False

    def check_adb_devices_silent(self):
        """디바이스 연결 상태 확인 (조용히, 로그 없이) - 특정 ID만 확인"""
        try:
            devices_cmd = self.get_adb_command("devices")
            # -s 옵션 없이 전체 디바이스 목록 조회
            devices_cmd = devices_cmd.replace(f"-s {self.device_id} ", "")
            
            process = subprocess.Popen(
                devices_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=5)
            
            if process.returncode == 0:
                lines = stdout.strip().split('\n')
                for line in lines[1:]:  # 첫 번째 줄은 "List of devices attached"
                    if line.strip() and '\t' in line:
                        device_info = line.strip().split('\t')
                        if len(device_info) >= 2:
                            device_id = device_info[0]
                            device_status = device_info[1]
                            # 특정 디바이스 ID가 있고 상태가 'device'인지 확인
                            if device_id == self.device_id:
                                return device_status == 'device'
            return False
        except:
            return False

    def check_adb_shell_silent(self):
        """ADB shell 연결 테스트 (조용히, 로그 없이)"""
        try:
            shell_cmd = self.get_adb_command('shell echo "ADB Shell Test"')
            process = subprocess.Popen(
                shell_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            stdout, stderr = process.communicate(timeout=5)

            if process.returncode == 0 and "ADB Shell Test" in stdout:
                return True, "연결됨"
            else:
                return False, "연결 안됨"

        except subprocess.TimeoutExpired:
            # 타임아웃은 연결 실패로 간주
            return False, "타임아웃"
        except Exception as e:
            # 기타 예외는 이전 상태 유지 (None 반환)
            return None, str(e)

    def update_status_light(self, is_working):
        """신호등 색상만 업데이트 (조용히)"""
        if hasattr(self, 'status_canvas'):
            color = "#00FF00" if is_working else "#FF0000"
            self.status_canvas.itemconfig(self.status_light, fill=color, outline=color)

    def update_connection_status(self, adb_installed, device_connected, shell_working, all_ok):
        """전체 연결 상태 업데이트 (신호등 + 메시지)"""
        # 신호등 색상 업데이트
        self.update_status_light(shell_working)
        
        # 연결 상태 메시지 업데이트
        if hasattr(self, 'connection_status_label'):
            if not adb_installed:
                self.connection_status_label.config(text="❌ ADB 미설치", foreground="red")
            elif not device_connected:
                self.connection_status_label.config(text=f"❌ 디바이스 미연결 (ID: {self.device_id})", foreground="red")
            elif not shell_working:
                self.connection_status_label.config(text="❌ Shell 연결 실패", foreground="red")
            else:
                self.connection_status_label.config(text="✅ 사용 가능합니다", foreground="green")
        
        # 이전 연결 상태 저장
        previous_status = self.all_connected if hasattr(self, 'all_connected') else False
        
        # 전체 연결 상태 저장
        self.all_connected = all_ok
        
        # 상태가 변경되었고, 새로 연결된 경우에만 스크립트 업로드
        if hasattr(self, 'last_shell_status'):
            if not self.last_shell_status and shell_working:
                # 연결되지 않았다가 연결된 경우
                self.upload_mfl_script_silent()
            self.last_shell_status = shell_working
        
        # 연결이 끊어진 경우 로그 출력
        if previous_status and not all_ok:
            self.output_text.insert(tk.END, f"[연결 끊김] 디바이스 연결이 끊어졌습니다.\n")
            self.output_text.see(tk.END)

    def upload_mfl_script_silent(self):
        """mfl_total.sh 스크립트를 조용히 생성하고 업로드"""
        def upload_thread():
            try:
                script_path = os.path.join(self.current_directory, "mfl_total.sh")
                
                # 스크립트가 없으면 생성
                if not os.path.exists(script_path):
                    self.create_mfl_script_file_only(script_path)
                
                # 1. 업로드
                push_cmd = self.get_adb_command(f'push "{script_path}" /tmp/')
                push_process = subprocess.Popen(
                    push_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='cp949',
                    cwd=self.current_directory
                )
                push_stdout, push_stderr = push_process.communicate(timeout=30)
                
                if push_process.returncode != 0:
                    # 업로드 실패 시 종료
                    return
                
                # 2. 실행권한 부여 (업로드 성공 시에만)
                chmod_cmd = self.get_adb_command('shell chmod +x /tmp/mfl_total.sh')
                chmod_process = subprocess.Popen(
                    chmod_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='cp949',
                    cwd=self.current_directory
                )
                chmod_stdout, chmod_stderr = chmod_process.communicate(timeout=15)
                
                # chmod 결과는 무시 (일부 시스템에서는 권한 부여가 제한될 수 있음)
                    
            except subprocess.TimeoutExpired:
                # 타임아웃 발생 시에도 조용히 종료
                pass
            except Exception as e:
                # 기타 예외도 조용히 종료
                pass
        
        thread = threading.Thread(target=upload_thread)
        thread.daemon = True
        thread.start()

    def create_mfl_script_file_only(self, script_path):
        """mfl_total.sh 파일만 생성 (로그 없이)"""
        script_content = '''#!/bin/bash

if [ "$1" = "up" ]; then
    echo "up."
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "down" ]; then
    echo "down"
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menuup" ]; then
    echo "menuup"
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menudown" ]; then
    echo "menudown"
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "ok" ]; then
    echo "ok"
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "view" ]; then
    echo "view"
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "fas" ]; then
    echo "fas"
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "signal" ]; then
    dpid="$2"
    value="$3"
    if [ -z "$dpid" ] || [ -z "$value" ]; then
        echo "Usage: $0 signal <DPID_NAME> <VALUE>"
        exit 1
    fi
    echo "signal: $dpid = $value"
    IpcSender --dpid "$dpid" 0 "$value" > /dev/null 2>&1
else
    echo "Unknown Command."
fi
'''
        with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(script_content)
        
        try:
            import stat
            os.chmod(script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
        except:
            pass

    def update_all_adb_status(self):
        """전체 ADB 상태 업데이트"""
        # 메인 창에 확인 시작 메시지 표시
        self.output_text.insert(tk.END, "[설정] ADB 전체 상태 확인 시작...\n")
        self.output_text.see(tk.END)

        # 별도 스레드에서 모든 ADB 상태 확인
        def check_all_adb_thread():
            # 1. ADB 설치 상태 확인
            adb_installed, adb_message = self.check_adb_installation()
            self.root.after(0, lambda: self.show_adb_install_result(adb_installed, adb_message))

            if adb_installed:
                # 2. 디바이스 연결 상태 확인
                device_connected, device_message = self.check_adb_devices()
                self.root.after(0, lambda: self.show_device_result(device_connected, device_message))

                # 3. ADB Shell 테스트
                shell_working, shell_message = self.check_adb_shell()
                self.root.after(0, lambda: self.show_shell_result(shell_working, shell_message))
            else:
                # ADB가 설치되지 않은 경우 나머지 테스트 건너뛰기
                self.root.after(0, lambda: self.show_device_result(False, "ADB가 설치되지 않아 확인할 수 없습니다."))
                self.root.after(0, lambda: self.show_shell_result(False, "ADB가 설치되지 않아 테스트할 수 없습니다."))

        thread = threading.Thread(target=check_all_adb_thread)
        thread.daemon = True
        thread.start()

    def show_adb_install_result(self, is_installed, message):
        """ADB 설치 확인 결과 표시"""
        # 설정 창의 상태 라벨 업데이트
        if hasattr(self, 'adb_status_label'):
            if is_installed:
                self.adb_status_label.config(text=f"✅ {message}", foreground="green")
            else:
                self.adb_status_label.config(text=f"❌ {message}", foreground="red")

        # 메인 창 출력에도 결과 표시
        if is_installed:
            self.output_text.insert(tk.END, f"[설정] ✅ ADB 설치: {message}\n")
        else:
            self.output_text.insert(tk.END, f"[설정] ❌ ADB 설치: {message}\n")
            self.output_text.insert(tk.END, "[설정] ADB 설치 방법: Android SDK Platform Tools를 다운로드하여 PATH에 추가하세요.\n")

        self.output_text.see(tk.END)

    def show_device_result(self, is_connected, message):
        """디바이스 연결 확인 결과 표시"""
        # 설정 창의 상태 라벨 업데이트
        if hasattr(self, 'device_status_label'):
            if is_connected:
                self.device_status_label.config(text=f"✅ {message}", foreground="green")
            else:
                self.device_status_label.config(text=f"❌ {message}", foreground="red")

        # 메인 창 출력에도 결과 표시
        if is_connected:
            self.output_text.insert(tk.END, f"[설정] ✅ 디바이스 연결: {message}\n")
        else:
            self.output_text.insert(tk.END, f"[설정] ❌ 디바이스 연결: {message}\n")
            if "연결된 디바이스가 없습니다" in message:
                self.output_text.insert(tk.END, "[설정] 해결방법: USB 디버깅을 활성화하고 디바이스를 연결하세요.\n")

        self.output_text.see(tk.END)

    def show_shell_result(self, is_working, message):
        """ADB Shell 테스트 결과 표시"""
        # 설정 창의 상태 라벨 업데이트
        if hasattr(self, 'shell_status_label'):
            if is_working:
                self.shell_status_label.config(text=f"✅ {message}", foreground="green")
            else:
                self.shell_status_label.config(text=f"❌ {message}", foreground="red")

        # 메인 창 신호등 업데이트
        if hasattr(self, 'status_canvas'):
            color = "#00FF00" if is_working else "#FF0000"  # 밝은 녹색 또는 빨간색
            self.status_canvas.itemconfig(self.status_light, fill=color, outline=color)

        # 메인 창 출력에도 결과 표시
        if is_working:
            self.output_text.insert(tk.END, f"[설정] ✅ ADB Shell: {message}\n")
        else:
            self.output_text.insert(tk.END, f"[설정] ❌ ADB Shell: {message}\n")
            if "인증되지 않았습니다" in message:
                self.output_text.insert(tk.END, "[설정] 해결방법: 디바이스에서 USB 디버깅 허용 팝업을 승인하세요.\n")

        self.output_text.insert(tk.END, "="*60 + "\n")
        self.output_text.see(tk.END)

        # 모든 상태 확인이 완료되고 Shell 연결이 성공한 경우에만 스크립트 업로드
        if is_working:
            self.create_mfl_script()
        else:
            # 연결 실패 시 로컬에만 스크립트 생성
            self.create_mfl_script_local_only()

    def browse_adb_folder(self):
        """ADB 폴더 선택 및 자동 적용"""
        from tkinter import filedialog

        # 폴더 선택 대화상자
        folder_path = filedialog.askdirectory(
            title="ADB가 있는 폴더 선택",
            initialdir=self.adb_folder if self.adb_folder else os.getcwd()
        )

        if folder_path:
            # 폴더 유효성 검사
            if not os.path.exists(folder_path):
                messagebox.showerror("오류", f"지정한 폴더가 존재하지 않습니다:\n{folder_path}")
                return

            if not os.path.isdir(folder_path):
                messagebox.showerror("오류", f"지정한 경로가 폴더가 아닙니다:\n{folder_path}")
                return

            # adb.exe 파일 존재 확인
            adb_exe_path = os.path.join(folder_path, "adb.exe")
            if not os.path.exists(adb_exe_path):
                result = messagebox.askyesno("확인",
                    f"지정한 폴더에 adb.exe 파일이 없습니다:\n{folder_path}\n\n그래도 이 폴더를 사용하시겠습니까?")
                if not result:
                    return

            # 폴더 자동 적용
            old_folder = self.adb_folder
            self.adb_folder = folder_path

            # 설정 저장
            self.save_adb_settings()

            # UI 업데이트
            if hasattr(self, 'current_adb_folder_label'):
                self.current_adb_folder_label.config(text=self.adb_folder)

            # 메인 창에 로그
            self.log_to_output(f"[설정] ADB 폴더 변경: {old_folder or '기본값'} → {self.adb_folder}")

            # 새 폴더로 ADB 상태 재확인 (Alert 없이)
            self.update_all_adb_status()

    def reset_adb_folder(self):
        """ADB 폴더를 기본값으로 재설정"""
        old_folder = self.adb_folder
        self.adb_folder = ""

        # 설정 저장
        self.save_adb_settings()

        # UI 업데이트
        if hasattr(self, 'current_adb_folder_label'):
            self.current_adb_folder_label.config(text="기본값 (PATH에서 검색)")

        self.log_to_output(f"[설정] ADB 폴더 재설정: {old_folder or '기본값'} → 기본값 (PATH에서 검색)")
        self.update_all_adb_status()

    def create_mfl_script(self):
        """mfl_total.sh 쉘 스크립트 파일 생성"""
        try:
            script_path = os.path.join(self.current_directory, "mfl_total.sh")

            # 쉘 스크립트 내용 생성 (사용자 제공 내용)
            script_content = '''#!/bin/bash

if [ "$1" = "up" ]; then
    echo "up."
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "down" ]; then
    echo "down"
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menuup" ]; then
    echo "menuup"
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menudown" ]; then
    echo "menudown"
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "ok" ]; then
    echo "ok"
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "view" ]; then
    echo "view"
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "fas" ]; then
    echo "fas"
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "signal" ]; then
    dpid="$2"
    value="$3"
    if [ -z "$dpid" ] || [ -z "$value" ]; then
        echo "Usage: $0 signal <DPID_NAME> <VALUE>"
        exit 1
    fi
    echo "signal: $dpid = $value"
    IpcSender --dpid "$dpid" 0 "$value" > /dev/null 2>&1
else
    echo "Unknown Command."
fi
'''

            # 파일 저장
            with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(script_content)

            # 실행 권한 부여 (Unix 계열 시스템에서)
            try:
                import stat
                os.chmod(script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
            except:
                pass  # Windows에서는 chmod가 제한적으로 작동

            self.log_to_output(f"[스크립트 생성] mfl_total.sh 파일이 생성되었습니다: {script_path}")

            # ADB Shell 연결이 확인된 경우에만 디바이스로 업로드
            self.upload_script_to_device(script_path)

        except Exception as e:
            self.log_to_output(f"[스크립트 생성 오류] {str(e)}")

    def create_mfl_script_local_only(self):
        """mfl_total.sh 쉘 스크립트 파일 생성 (로컬에만, 업로드 안함)"""
        try:
            script_path = os.path.join(self.current_directory, "mfl_total.sh")

            # 이미 파일이 존재하면 생성하지 않음
            if os.path.exists(script_path):
                self.log_to_output(f"[스크립트] mfl_total.sh 파일이 이미 존재합니다: {script_path}")
                return

            # 스크립트 내용 생성
            script_content = '''#!/bin/bash

if [ "$1" = "up" ]; then
    echo "up."
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "down" ]; then
    echo "down"
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menuup" ]; then
    echo "menuup"
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_UP_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "menudown" ]; then
    echo "menudown"
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_MENU_DOWN_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "ok" ]; then
    echo "ok"
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_OK_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "view" ]; then
    echo "view"
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_VIEW_SHORT_PRESS_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "fas" ]; then
    echo "fas"
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_PRESS 0 0 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 1 > /dev/null 2>&1
    IpcSender --dpid DP_ID_HMI_FAS_TASTER_SHORT_RELEASE 0 0 > /dev/null 2>&1
elif [ "$1" = "signal" ]; then
    dpid="$2"
    value="$3"
    if [ -z "$dpid" ] || [ -z "$value" ]; then
        echo "Usage: $0 signal <DPID_NAME> <VALUE>"
        exit 1
    fi
    echo "signal: $dpid = $value"
    IpcSender --dpid "$dpid" 0 "$value" > /dev/null 2>&1
else
    echo "Unknown Command."
fi
'''

            # 파일 저장
            with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(script_content)

            # 실행 권한 부여
            try:
                import stat
                os.chmod(script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
            except:
                pass

            self.log_to_output(f"[스크립트] mfl_total.sh 파일이 생성되었습니다: {script_path}")
            self.log_to_output("[스크립트] 디바이스 연결 후 자동으로 업로드됩니다.")

        except Exception as e:
            self.log_to_output(f"[스크립트 생성 오류] {str(e)}")

    def upload_script_to_device(self, script_path):
        """스크립트를 디바이스로 업로드하고 실행권한 부여"""
        try:
            # 1. adb push로 스크립트 업로드
            self.log_to_output("[스크립트 업로드] 디바이스로 mfl_total.sh 업로드 중...")
            push_cmd = self.get_adb_command(f'push "{script_path}" /tmp/')

            push_process = subprocess.Popen(
                push_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            push_stdout, push_stderr = push_process.communicate(timeout=30)

            self.log_to_output(f"[스크립트 업로드] 반환 코드: {push_process.returncode}")
            if push_stdout.strip():
                self.log_to_output(f"[스크립트 업로드] STDOUT:\n{push_stdout}")
            if push_stderr.strip():
                self.log_to_output(f"[스크립트 업로드] STDERR:\n{push_stderr}")

            if push_process.returncode == 0:
                self.log_to_output("[스크립트 업로드] ✅ 스크립트 업로드 성공")
            else:
                self.log_to_output("[스크립트 업로드] ❌ 스크립트 업로드 실패")
                if "no devices/emulators found" in push_stderr:
                    self.log_to_output("[스크립트 업로드] 디바이스가 연결되지 않았습니다.")
                elif "device unauthorized" in push_stderr:
                    self.log_to_output("[스크립트 업로드] 디바이스 인증이 필요합니다.")
                # 업로드 실패 시에도 chmod는 시도 (파일이 이미 존재할 수 있음)

            # 2. chmod +x로 실행권한 부여 (업로드 성공/실패 무관하게 시도)
            self.log_to_output("[실행권한 부여] /tmp/mfl_total.sh에 실행권한 부여 중...")
            chmod_cmd = self.get_adb_command('shell chmod +x /tmp/mfl_total.sh')

            chmod_process = subprocess.Popen(
                chmod_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',
                cwd=self.current_directory
            )
            chmod_stdout, chmod_stderr = chmod_process.communicate(timeout=15)

            self.log_to_output(f"[실행권한 부여] 반환 코드: {chmod_process.returncode}")
            if chmod_stdout.strip():
                self.log_to_output(f"[실행권한 부여] STDOUT:\n{chmod_stdout}")
            if chmod_stderr.strip():
                self.log_to_output(f"[실행권한 부여] STDERR:\n{chmod_stderr}")

            if chmod_process.returncode == 0:
                self.log_to_output("[실행권한 부여] ✅ 실행권한 부여 성공")
                self.log_to_output("[스크립트 배포] ✅ mfl_total.sh 디바이스 배포 완료!")
                self.log_to_output("[사용법] 디바이스에서 다음과 같이 사용: /tmp/mfl_total.sh [up|down|menuup|menudown|ok|view|fas]")
            else:
                self.log_to_output("[실행권한 부여] ❌ 실행권한 부여 실패")

        except subprocess.TimeoutExpired:
            self.log_to_output("[스크립트 업로드] ❌ 업로드 시간 초과")
        except Exception as e:
            self.log_to_output(f"[스크립트 업로드 오류] {str(e)}")

    # 키패드 기능들
    def go_home(self):
        """FAS 버튼 실행 (키패드 7)"""
        self.output_text.insert(tk.END, f"[7] FAS 버튼 실행\n")
        self.execute_mfl_command("fas")

    def move_up(self):
        """UP 버튼 실행 (키패드 8)"""
        self.output_text.insert(tk.END, f"[8] UP 버튼 실행\n")
        self.execute_mfl_command("up")

    def refresh_dir(self):
        """현재 디렉토리 새로고침 (키패드 9)"""
        self.output_text.insert(tk.END, f"[9] 현재 디렉토리 새로고침: {self.current_directory}\n")
        self.set_command("dir")
        self.run_command()

    def move_left(self):
        """MENU UP 버튼 실행 (키패드 4)"""
        self.output_text.insert(tk.END, f"[4] MENU UP 버튼 실행\n")
        self.execute_mfl_command("menuup")

    def move_right(self):
        """MENU DOWN 버튼 실행 (키패드 6)"""
        self.output_text.insert(tk.END, f"[6] MENU DOWN 버튼 실행\n")
        self.execute_mfl_command("menudown")

    def move_down(self):
        """DOWN 버튼 실행 (키패드 2)"""
        self.output_text.insert(tk.END, f"[2] DOWN 버튼 실행\n")
        self.execute_mfl_command("down")

    def focus_signal_input(self):
        """SIGNAL 입력 필드로 포커스 이동 (키패드 1)"""
        try:
            if hasattr(self, 'signal_name_entry') and self.signal_name_entry.winfo_exists():
                self.signal_name_entry.focus_set()
                self.signal_name_entry.selection_range(0, tk.END)
        except Exception:
            pass

    def send_custom_signal(self):
        """사용자가 입력한 signal name/value를 IpcSender로 전송"""
        signal_name = (self.signal_name_var.get() if hasattr(self, 'signal_name_var') else "").strip()
        signal_value = (self.signal_value_var.get() if hasattr(self, 'signal_value_var') else "").strip()

        if not signal_name:
            messagebox.showwarning("입력 필요", "Signal name을 입력하세요.")
            self.focus_signal_input()
            return

        # 기본 안전 검증 (쉘 인젝션 방지 + IpcSender 파라미터 형태 맞춤)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", signal_name):
            messagebox.showwarning("형식 오류", "Signal name은 영문/숫자/_ 만 사용할 수 있습니다. (예: DP_ID_SOMETHING)")
            self.focus_signal_input()
            return

        if not signal_value:
            messagebox.showwarning("입력 필요", "Signal value를 입력하세요. (예: 0 또는 1)")
            try:
                self.signal_value_entry.focus_set()
                self.signal_value_entry.selection_range(0, tk.END)
            except Exception:
                pass
            return

        if not re.fullmatch(r"-?\d+", signal_value):
            messagebox.showwarning("형식 오류", "Signal value는 정수만 입력할 수 있습니다. (예: 0, 1, -1)")
            try:
                self.signal_value_entry.focus_set()
                self.signal_value_entry.selection_range(0, tk.END)
            except Exception:
                pass
            return

        # adb shell IpcSender --dpid <name> 0 <value>
        # NOTE: Do not use host-side redirection like `> /dev/null` on Windows.
        shell_cmd = f'shell IpcSender --dpid {signal_name} 0 {signal_value}'
        adb_cmd = self.get_adb_command(shell_cmd)

        self.output_text.insert(tk.END, f"[SIGNAL] {signal_name} = {signal_value}\n")
        self.output_text.insert(tk.END, f"실행 명령어: {adb_cmd}\n")
        self.output_text.see(tk.END)

        def execute_thread():
            try:
                process = subprocess.Popen(
                    adb_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='cp949',
                    cwd=self.current_directory
                )
                stdout, stderr = process.communicate(timeout=10)
                self.root.after(0, lambda: self.show_signal_result(signal_name, signal_value, stdout, stderr, process.returncode))
            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self.show_signal_error(signal_name, signal_value, "명령어 실행 시간 초과"))
            except Exception as e:
                self.root.after(0, lambda: self.show_signal_error(signal_name, signal_value, str(e)))

        thread = threading.Thread(target=execute_thread)
        thread.daemon = True
        thread.start()

    def send_kbi_view_request(self, value):
        """Preset: send both KBI view request DPIDs with the given value."""
        pairs = [
            ("DP_ID_HMI_AC_KBI_VIEW_REQUEST", str(value)),
            ("DP_ID_B_AC_KBI_VIEW_REQUEST", str(value)),
        ]
        self.output_text.insert(tk.END, f"[PRESET] KBI_VIEW_REQUEST = {value}\n")
        self.output_text.see(tk.END)

        def execute_thread():
            for signal_name, signal_value in pairs:
                try:
                    shell_cmd = f'shell IpcSender --dpid {signal_name} 0 {signal_value}'
                    adb_cmd = self.get_adb_command(shell_cmd)
                    process = subprocess.Popen(
                        adb_cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='cp949',
                        cwd=self.current_directory,
                    )
                    stdout, stderr = process.communicate(timeout=10)
                    self.root.after(
                        0,
                        lambda n=signal_name, v=signal_value, out=stdout, err=stderr, rc=process.returncode: self.show_signal_result(
                            n, v, out, err, rc
                        ),
                    )
                except subprocess.TimeoutExpired:
                    self.root.after(0, lambda n=signal_name, v=signal_value: self.show_signal_error(n, v, "명령어 실행 시간 초과"))
                except Exception as e:
                    self.root.after(0, lambda n=signal_name, v=signal_value, msg=str(e): self.show_signal_error(n, v, msg))

        thread = threading.Thread(target=execute_thread)
        thread.daemon = True
        thread.start()

    def show_signal_result(self, signal_name, signal_value, stdout, stderr, returncode):
        """사용자 signal 전송 결과 표시"""
        if returncode == 0:
            self.output_text.insert(tk.END, f"✅ SIGNAL 전송 성공: {signal_name} = {signal_value}\n")
            if stdout.strip():
                self.output_text.insert(tk.END, f"출력: {stdout.strip()}\n")
        else:
            self.output_text.insert(tk.END, f"❌ SIGNAL 전송 실패 (코드: {returncode}): {signal_name} = {signal_value}\n")
            if stderr.strip():
                self.output_text.insert(tk.END, f"오류: {stderr.strip()}\n")
            if "no devices" in stderr.lower() or "unauthorized" in stderr.lower() or "offline" in stderr.lower():
                self.output_text.insert(tk.END, "연결 상태를 확인하세요. (환경설정 버튼 클릭)\n")

        self.output_text.insert(tk.END, "-" * 40 + "\n")
        self.output_text.see(tk.END)

    def show_signal_error(self, signal_name, signal_value, error_msg):
        """사용자 signal 전송 에러 표시"""
        self.output_text.insert(tk.END, f"❌ SIGNAL 전송 오류: {signal_name} = {signal_value} / {error_msg}\n")
        if "timeout" in error_msg.lower() or "no devices" in error_msg.lower():
            self.output_text.insert(tk.END, "연결 상태를 확인하세요. (환경설정 버튼 클릭)\n")
        self.output_text.insert(tk.END, "-" * 40 + "\n")
        self.output_text.see(tk.END)
    
    def run_command(self):
        """OK 버튼 실행 (키패드 5)"""
        self.output_text.insert(tk.END, f"[5] OK 버튼 실행\n")
        self.execute_mfl_command("ok")
    
    def handle_cd_command(self, command):
        """cd 명령어 처리"""
        try:
            path = command[3:].strip()
            if not path:
                path = os.path.expanduser("~")
            
            if path == "..":
                path = os.path.dirname(self.current_directory)
            elif not os.path.isabs(path):
                path = os.path.join(self.current_directory, path)
            
            if os.path.exists(path) and os.path.isdir(path):
                self.current_directory = os.path.abspath(path)
                os.chdir(self.current_directory)
                self.update_directory_label()
                self.output_text.insert(tk.END, f"디렉토리 변경: {self.current_directory}\n")
            else:
                self.output_text.insert(tk.END, f"오류: 디렉토리를 찾을 수 없습니다: {path}\n")
            
            self.output_text.see(tk.END)
            
        except Exception as e:
            self.output_text.insert(tk.END, f"cd 명령어 오류: {str(e)}\n")
            self.output_text.see(tk.END)
    
    def execute_command(self, command):
        """명령어를 실행하고 결과를 표시"""
        try:
            # Windows 환경에서 명령어 실행
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp949',  # Windows 한글 지원
                cwd=self.current_directory,
                universal_newlines=True
            )
            
            # 실시간 출력 처리
            stdout, stderr = process.communicate()
            
            # 메인 스레드에서 UI 업데이트
            self.root.after(0, self.show_result, stdout, stderr, process.returncode)
            
        except Exception as e:
            self.root.after(0, self.show_error, str(e))
    
    def show_result(self, stdout, stderr, returncode):
        """명령어 실행 결과 표시"""
        if stdout:
            self.output_text.insert(tk.END, stdout)
        
        if stderr:
            self.output_text.insert(tk.END, f"\n오류 출력:\n{stderr}")
        
        if returncode != 0:
            self.output_text.insert(tk.END, f"\n종료 코드: {returncode}\n")
        
        self.output_text.insert(tk.END, "\n" + "="*60 + "\n")
        self.output_text.see(tk.END)
        
        # 실행 버튼 다시 활성화 (키패드 5번)
        if hasattr(self, 'keypad_btns') and (1, 1) in self.keypad_btns:
            self.keypad_btns[(1, 1)].config(state=tk.NORMAL)
        self.cmd_entry.focus()
    
    def show_error(self, error):
        """에러 메시지 표시"""
        self.output_text.insert(tk.END, f"\n실행 오류: {error}\n")
        self.output_text.insert(tk.END, "="*60 + "\n")
        self.output_text.see(tk.END)
        
        if hasattr(self, 'keypad_btns') and (1, 1) in self.keypad_btns:
            self.keypad_btns[(1, 1)].config(state=tk.NORMAL)
        self.cmd_entry.focus()
    
    def clear_output(self):
        """출력 창 지우기"""
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, "CMD GUI Tool - 출력 창이 지워졌습니다.\n")
        self.output_text.insert(tk.END, "="*60 + "\n")
    
    def save_output(self):
        """VIEW 버튼 실행 (키패드 3)"""
        self.output_text.insert(tk.END, f"[3] VIEW 버튼 실행\n")
        self.execute_mfl_command("view")

    def execute_mfl_command(self, button_name):
        """MFL 스크립트 명령어 실행"""
        try:
            # adb shell /tmp/mfl_total.sh [button_name] 명령어 생성
            mfl_cmd = self.get_adb_command(f'shell /tmp/mfl_total.sh {button_name}')
            self.output_text.insert(tk.END, f"실행 명령어: {mfl_cmd}\n")
            self.output_text.see(tk.END)

            # 별도 스레드에서 명령어 실행
            def execute_thread():
                try:
                    process = subprocess.Popen(
                        mfl_cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='cp949',
                        cwd=self.current_directory
                    )
                    stdout, stderr = process.communicate(timeout=10)

                    # 메인 스레드에서 결과 표시
                    self.root.after(0, lambda: self.show_mfl_result(button_name, stdout, stderr, process.returncode))

                except subprocess.TimeoutExpired:
                    self.root.after(0, lambda: self.show_mfl_error(button_name, "명령어 실행 시간 초과", True))
                except Exception as e:
                    self.root.after(0, lambda: self.show_mfl_error(button_name, str(e), True))

            thread = threading.Thread(target=execute_thread)
            thread.daemon = True
            thread.start()

        except Exception as e:
            self.output_text.insert(tk.END, f"MFL 명령어 실행 오류: {str(e)}\n")
            self.output_text.see(tk.END)

    def show_mfl_result(self, button_name, stdout, stderr, returncode):
        """MFL 명령어 실행 결과 표시"""
        if returncode == 0:
            self.output_text.insert(tk.END, f"✅ {button_name.upper()} 버튼 실행 성공\n")
            if stdout.strip():
                self.output_text.insert(tk.END, f"출력: {stdout.strip()}\n")
        else:
            self.output_text.insert(tk.END, f"❌ {button_name.upper()} 버튼 실행 실패 (코드: {returncode})\n")
            if stderr.strip():
                self.output_text.insert(tk.END, f"오류: {stderr.strip()}\n")
            
            # 연결 문제인 경우에만 안내 메시지
            if "no devices" in stderr or "unauthorized" in stderr or "offline" in stderr:
                self.output_text.insert(tk.END, "연결 상태를 확인하세요. (환경설정 버튼 클릭)\n")

        self.output_text.insert(tk.END, "-" * 40 + "\n")
        self.output_text.see(tk.END)

    def show_mfl_error(self, button_name, error_msg, open_settings=False):
        """MFL 명령어 실행 에러 표시"""
        self.output_text.insert(tk.END, f"❌ {button_name.upper()} 버튼 실행 오류: {error_msg}\n")

        # 타임아웃이나 연결 문제인 경우에만 안내
        if "timeout" in error_msg.lower() or "no devices" in error_msg.lower():
            self.output_text.insert(tk.END, "연결 상태를 확인하세요. (환경설정 버튼 클릭)\n")

        self.output_text.insert(tk.END, "-" * 40 + "\n")
        self.output_text.see(tk.END)

def main():
    """메인 함수"""
    # Tkinter 루트 윈도우 생성
    root = tk.Tk()
    
    # 아이콘 설정 (선택사항)
    try:
        # Windows에서 기본 아이콘 설정
        root.iconbitmap(default='')
    except:
        pass
    
    # 애플리케이션 시작
    app = CMDGui(root)
    
    # 시작 메시지
    app.output_text.insert(tk.END, "FPK ADB CMD Sender 시작 - HMI 버튼 제어\n")
    app.output_text.insert(tk.END, f"현재 디렉토리: {os.getcwd()}\n")
    app.output_text.insert(tk.END, "HMI 버튼 키패드 사용법:\n")
    app.output_text.insert(tk.END, "7(Home):FAS  8(▲):UP  [9:사용안함]\n")
    app.output_text.insert(tk.END, "4(◀):MENU UP  5(Enter):OK  6(▶):MENU DOWN\n")
    app.output_text.insert(tk.END, "1:SIGNAL 입력  2(▼):DOWN  3(PgDn):VIEW\n")
    app.output_text.insert(tk.END, "0:로그지우기\n")
    app.output_text.insert(tk.END, "="*60 + "\n")
    
    # 초기 포커스 설정
    app.cmd_entry.focus()
    
    # GUI 실행
    root.mainloop()

if __name__ == "__main__":
    main()
