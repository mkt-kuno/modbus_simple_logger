import os, time, copy, json, platform, psutil, datetime, asyncio
import threading, queue
import tkinter as tk
import tkinter.ttk as ttk

import numpy as np

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from pymodbus import FramerType
import pymodbus.client as ModbusClient

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.schema import Column
from sqlalchemy.types import DateTime, Integer, Float, String

DEBUG = True

MODBUS_COM_PORT = 'COM11'
MODBUS_MODE = 'RTU'
MODBUS_BAUDRATE = 38400
MODBUS_SLAVE_ADDRESS = 1

WEB_PORT = 60080
WEB_HOST = 'localhost' if DEBUG else '0.0.0.0'

NUM_CH_AI = 16
NUM_CH_AI_LIMIT = 16
NUM_CH_AO = 8
NUM_CH_AO_LIMIT = 8
NUM_CH_PARAM = 16

APP_DATA_DIR_PATH = os.path.join(os.environ['APPDATA'], 'ModbusSimpleLogger')
TEMP_DATA_DIR_PATH = os.path.join(os.environ['TEMP'], 'ModbusSimpleLogger')

class AioDataTable(declarative_base()): # type: ignore
    __tablename__ = 'data'
    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime)
    ai_raw_0 = Column(Integer)
    ai_raw_1 = Column(Integer)
    ai_raw_2 = Column(Integer)
    ai_raw_3 = Column(Integer)
    ai_raw_4 = Column(Integer)
    ai_raw_5 = Column(Integer)
    ai_raw_6 = Column(Integer)
    ai_raw_7 = Column(Integer)
    ai_raw_8 = Column(Integer)
    ai_raw_9 = Column(Integer)
    ai_raw_10 = Column(Integer)
    ai_raw_11 = Column(Integer)
    ai_raw_12 = Column(Integer)
    ai_raw_13 = Column(Integer)
    ai_raw_14 = Column(Integer)
    ai_raw_15 = Column(Integer)
    ai_phy_0 = Column(Float)
    ai_phy_1 = Column(Float)
    ai_phy_2 = Column(Float)
    ai_phy_3 = Column(Float)
    ai_phy_4 = Column(Float)
    ai_phy_5 = Column(Float)
    ai_phy_6 = Column(Float)
    ai_phy_7 = Column(Float)
    ai_phy_8 = Column(Float)
    ai_phy_9 = Column(Float)
    ai_phy_10 = Column(Float)
    ai_phy_11 = Column(Float)
    ai_phy_12 = Column(Float)
    ai_phy_13 = Column(Float)
    ai_phy_14 = Column(Float)
    ai_phy_15 = Column(Float)
    ao_raw_0 = Column(Integer)
    ao_raw_1 = Column(Integer)
    ao_raw_2 = Column(Integer)
    ao_raw_3 = Column(Integer)
    ao_raw_4 = Column(Integer)
    ao_raw_5 = Column(Integer)
    ao_raw_6 = Column(Integer)
    ao_raw_7 = Column(Integer)
    ao_phy_0 = Column(Float)
    ao_phy_1 = Column(Float)
    ao_phy_2 = Column(Float)
    ao_phy_3 = Column(Float)
    ao_phy_4 = Column(Float)
    ao_phy_5 = Column(Float)
    ao_phy_6 = Column(Float)
    ao_phy_7 = Column(Float)
    param_phy_0 = Column(Float)
    param_phy_1 = Column(Float)
    param_phy_2 = Column(Float)
    param_phy_3 = Column(Float)
    param_phy_4 = Column(Float)
    param_phy_5 = Column(Float)
    param_phy_6 = Column(Float)
    param_phy_7 = Column(Float)
    param_phy_8 = Column(Float)
    param_phy_9 = Column(Float)
    param_phy_10 = Column(Float)
    param_phy_11 = Column(Float)
    param_phy_12 = Column(Float)
    param_phy_13 = Column(Float)
    param_phy_14 = Column(Float)
    param_phy_15 = Column(Float)

class ThreadSafeAioData():
    def __init__(self):
        self._lock = threading.Lock()
        self._ai = np.array([0]*NUM_CH_AI, dtype=np.int16)
        self._ao = np.array([0]*NUM_CH_AO, dtype=np.uint16)
        self._ai_calib_a = np.array([0.0]*NUM_CH_AI, dtype=np.float32)
        self._ai_calib_b = np.array([1.0]*NUM_CH_AI, dtype=np.float32)
        self._ai_calib_c = np.array([0.0]*NUM_CH_AI, dtype=np.float32)
        self._ao_calib_a = np.array([0.0]*NUM_CH_AO, dtype=np.float32)
        self._ao_calib_b = np.array([1.0]*NUM_CH_AO, dtype=np.float32)
        self._ao_calib_c = np.array([0.0]*NUM_CH_AO, dtype=np.float32)
        self._param = np.array([0.0]*NUM_CH_PARAM, dtype=np.float32)

    def get_param_phy(self, ch:int) -> float:
        if ch < 0 or ch >= NUM_CH_PARAM:
            raise ValueError('Invalid channel')
        with self._lock:
            return float(self._param[ch])

    def set_param_phy(self, value:float, ch:int):
        if ch < 0 or ch >= NUM_CH_PARAM:
            raise ValueError('Invalid channel')
        with self._lock:
            self._param[ch] = np.float32(value)

    def get_param_phy_all(self) -> float:
        with self._lock:
            return self._param.tolist()

    def set_param_phy_all(self, data:list[float]):
        if len(data) != NUM_CH_PARAM:
            raise ValueError('Invalid data shape')
        with self._lock:
            self._param = np.array(data)

    def get_ai_calib(self, ch:int) -> tuple[float, float, float]:
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            return (float(self._ai_calib_a[ch]), float(self._ai_calib_b[ch]), float(self._ai_calib_c[ch]))

    def set_ai_calib(self, a:float, b:float, c:float, ch:int):
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            self._ai_calib_a[ch] = np.float32(a)
            self._ai_calib_b[ch] = np.float32(b)
            self._ai_calib_c[ch] = np.float32(c)

    def get_ao_calib(self, ch:int) -> tuple[float, float, float]:
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            return (float(self._ao_calib_a[ch]), float(self._ao_calib_b[ch]), float(self._ao_calib_c[ch]))

    def set_ao_calib(self, a:float, b:float, c:float, ch:int):
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            self._ao_calib_a[ch] = np.float32(a)
            self._ao_calib_b[ch] = np.float32(b)
            self._ao_calib_c[ch] = np.float32(c)

    def get_ai_phy(self, ch:int) -> float:
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            _x = self._ai[ch]
            _a = self._ai_calib_a[ch]
            _b = self._ai_calib_b[ch]
            _c = self._ai_calib_c[ch]
            return float(_x * _a**2 + _x * _b + _c)

    def get_ai_phy_all(self) -> list[float]:
        with self._lock:
            _x = self._ai
            _a = self._ai_calib_a
            _b = self._ai_calib_b
            _c = self._ai_calib_c
            return (_x * _a**2 + _x * _b + _c).tolist()

    def get_ao_phy(self, ch:int) -> float:
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            _x = self._ao[ch]
            _a = self._ao_calib_a[ch]
            _b = self._ao_calib_b[ch]
            _c = self._ao_calib_c[ch]
            return float(_x * _a**2 + _x * _b + _c)
    
    def get_ao_phy_all(self) -> list[float]:
        with self._lock:
            _x = self._ao
            _a = self._ao_calib_a
            _b = self._ao_calib_b
            _c = self._ao_calib_c
            return (_x * _a**2 + _x * _b + _c).tolist()

    def get_ai_raw(self, ch:int) -> int:
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            return int(self._ai[ch])

    def get_ai_raw_all(self) -> list[int]:
        with self._lock:
            return self._ai.tolist()

    def set_ai_raw(self, data:int, ch:int):
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            self._ai[ch] = np.int16(data)

    def set_ai_raw_all(self, data:list[int]):
        if len(data) != NUM_CH_AI:
            raise ValueError('Invalid data shape')
        with self._lock:
            self._ai = np.array(data)

    def get_ao_raw(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            return int(self._ao[ch])

    def get_ao_raw_all(self) -> list[int]:
        with self._lock:
            return copy.deepcopy(self._ao).tolist()

    def set_ao_raw(self, data:int, ch:int):
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            self._ao[ch] = np.uint16(data)
        
    def set_ao_raw_all(self, data:list[int]):
        if len(data) != NUM_CH_AO:
            raise ValueError('Invalid data shape')
        with self._lock:
            self._ao = np.array(data)

class Application(tk.Frame):
    BG_CMD_MODBUS_START = 'modbus_start'
    BG_CMD_MODBUS_STOP = 'modbus_stop'
    BG_CMD_SQL_SAVE_START = 'sql_save_start'
    BG_CMD_SQL_SAVE_STOP = 'sql_save_stop'
    BG_CMD_SQL_SAVE = 'sql_save'
    BG_CMD_TERMINATE = 'terminate'
    BG_CMD_AO_SEND = 'ao_send'
    BG_CMD_AI_RECEIVE = 'ai_receive'
    BG_CMD_CHANGE_INTERVAL = 'change_interval'

    DEFALUT_CONFIG_JSON_NAME = 'config.json'

    HX711_VOLTAGE = 4.2
    FMT_STRING_FLOAT = '%.3f'
    FMT_STRING_CALIB_FLOAT = '%.6f'

    _display_update_interval_ms = 100

    _aio = ThreadSafeAioData()
    
    _sql_engine = None
    _sql_db_path = ""
    _sql_save_interval_ms = 100

    _webserver_url = "ws://%s:%d"%(WEB_HOST, WEB_PORT)
    _webserver_thread = None
    _fastapi_app = FastAPI()

    _modbus_thread = None
    _modbus_msg_queue: queue.Queue = queue.Queue()
    _modbus_client = None
    _modbus_client_lock = threading.Lock()
    _modbus_interval_ms = 100

    _pipe_is_wainting = False

    _label_ai_raw_list: list[tk.Label] = []
    _label_ai_vlt_list: list[tk.Label] = []
    _label_ai_ust_list: list[tk.Label] = []
    _label_ai_phy_list: list[tk.Label] = []
    _label_ao_raw_list: list[tk.Label] = []
    _label_ao_phy_list: list[tk.Label] = []
    _label_ao_vlt_list: list[tk.Label] = []
    _label_param_phy_list: list[tk.Label] = []

    _entry_ai_label_list: list[tk.Entry] = []
    _entry_ai_unit_list: list[tk.Entry] = []
    _entry_ao_label_list: list[tk.Entry] = []
    _entry_ao_unit_list: list[tk.Entry] = []
    _entry_param_label_list: list[tk.Entry] = []
    _entry_param_unit_list: list[tk.Entry] = []

    def __init__(self, master=None):
        super().__init__(master)
        self.pack()

        self.master = master
        self.master.title("Modbus Simple Logger")
        self.master.geometry("1920x1000")
        self.master.resizable(False, True)

        master.protocol("WM_DELETE_WINDOW", self._ui_on_closing)

        self._config_json = {}
        self._config_load_json_from_appdata()

        # restore calib values to AIO
        for ch in range(NUM_CH_AI):
            _a, _b, _c = self._config_json['ai'][ch]['calib']
            self._aio.set_ai_calib(_a, _b, _c, ch)
        for ch in range(NUM_CH_AO):
            _a, _b, _c = self._config_json['ao'][ch]['calib']
            self._aio.set_ao_calib(_a, _b, _c, ch)

        self._ui_create_widgets()
        self._ui_start_background_job()
        self.after(self._display_update_interval_ms, self._ui_update_display)

    def _ui_on_closing(self):
        self._ui_stop_background_job()
        self._config_save_json_to_appdata()
        self.master.destroy()

    def _ui_start_background_job(self):
        if not self._modbus_thread:
            self._modbus_thread = threading.Thread(target=self._bg_modbus_thread, daemon=True)
            self._modbus_thread.name = 'ModbusThread'
            self._modbus_thread.start()
            self._modbus_msg_queue.put(self.BG_CMD_MODBUS_START)
            self._modbus_msg_queue.put(self.BG_CMD_AO_SEND)
            self._modbus_msg_queue.put(self.BG_CMD_AI_RECEIVE)

        if not self._webserver_thread:
            self._webserver_thread = threading.Thread(target=self._bg_webserver_thread, daemon=True)
            self._webserver_thread.name = 'WebServerThread'
            self._webserver_thread.start()

    def _ui_stop_background_job(self):
        if self._modbus_thread:
            self._modbus_msg_queue.put(self.BG_CMD_MODBUS_STOP)
            self._modbus_msg_queue.put(self.BG_CMD_TERMINATE)
            self._modbus_thread.join()
            self._modbus_thread = None

    def _ui_update_display(self):
        _ao = self._aio.get_ao_raw_all()
        _ai = self._aio.get_ai_raw_all()
        _aic = self._aio.get_ai_phy_all()
        _aoc = self._aio.get_ao_phy_all()
        _par = self._aio.get_param_phy_all()

        for ch in range(NUM_CH_AI):
            self._label_ai_raw_list[ch].config(text="%d"% _ai[ch])
            _raw = _ai[ch]
            _phy = _aic[ch]
            if ch < int(NUM_CH_AI/2):
                _vlt = self._util_convert_hx711_raw2vlt(_raw)
                _ust = self._util_convert_hx711_raw2ust(_raw)
                self._label_ai_vlt_list[ch].config(text=self.FMT_STRING_FLOAT%_vlt)
                self._label_ai_ust_list[ch].config(text=self.FMT_STRING_FLOAT%_ust)
            else:
                _vlt = self._util_convert_ads1115_raw2vlt(_raw)
                self._label_ai_vlt_list[ch].config(text=self.FMT_STRING_FLOAT%_vlt)
            self._label_ai_phy_list[ch].config(text=self.FMT_STRING_FLOAT%_phy)
        
        for ch in range(NUM_CH_AO):
            _raw = int(_ao[ch])
            _phy = float(_aoc[ch])
            _vlt = self._util_convert_gp8403_raw2vlt(_ao[ch])
            self._label_ao_raw_list[ch].config(text=_raw)
            self._label_ao_phy_list[ch].config(text=self.FMT_STRING_FLOAT%_phy)
            self._label_ao_vlt_list[ch].config(text=self.FMT_STRING_FLOAT%_vlt)

        for ch in range(NUM_CH_PARAM):
            _phy = float(_par[ch])
            self._label_param_phy_list[ch].config(text=self.FMT_STRING_FLOAT%_phy)

        self.after(self._display_update_interval_ms, self._ui_update_display)

    def _ui_send_req_set_ao(self, ch, entry):
        try:
            _x = float(entry.get())
            _x = np.uint16(_x*1000)
            _x = 0 if _x < 0 else _x
            _x = 10000 if _x > 10000 else _x
            self._aio.set_ao_raw(_x, ch)
            self._modbus_msg_queue.put(self.BG_CMD_AO_SEND)
        except ValueError as e:
            pass

    def _ui_send_req_change_interval(self, interval_ms):
        try:
            _ms = 100
            if type(interval_ms) is str:
                if 'ms' in interval_ms:
                    _ms = int(interval_ms[:-2])
                elif 's' in interval_ms:
                    _ms = int(interval_ms[:-1])*1000
                elif 'min' in interval_ms:
                    _ms = int(interval_ms[:-3])*1000*60
            else:
                _ms = int(interval_ms)
            _ms = 100 if _ms < 100 else _ms
            print(_ms)
            self._sql_save_interval_ms = _ms
            self._modbus_msg_queue.put(self.BG_CMD_CHANGE_INTERVAL)
        except ValueError as e:
            print(e)

    def _ui_push_start_button(self):
        self.start_save_button.config(state='disabled')
        self._modbus_msg_queue.put('save_start')
        self.stop_save_button.config(state='normal')
    
    def _ui_push_stop_button(self):
        self.stop_save_button.config(state='disabled')
        self._modbus_msg_queue.put('save_stop')
        self.start_save_button.config(state='normal')

    def _ui_create_widgets(self):
        FONT_NAME = 'Consolas'

        WIDTH_OF_TYPE_LABEL = 4
        WIDTH_OF_DIGIT_LABEL = 12
        WIDTH_OF_UNIT_LABEL = 5
        WIDTH_OF_LABEL_LABEL = 21

        FONT_SIZE_NORMAL = 14
        FONT_SIZE_LARGE = 20

        FONT_TINY = (FONT_NAME, FONT_SIZE_NORMAL-3)
        FONT_SMALL = (FONT_NAME, FONT_SIZE_NORMAL-2)
        FONT_NORMAL = (FONT_NAME, FONT_SIZE_NORMAL)
        FONT_BOLD = (FONT_NAME, FONT_SIZE_NORMAL, 'bold')
        FONT_LARGE = (FONT_NAME, FONT_SIZE_LARGE, 'bold')
        FONT_LARGE_BOLD = (FONT_NAME, FONT_SIZE_LARGE, 'bold')

        _make_digit_label =   lambda p: _make_digit_label_s(p, 'normal')
        _make_digit_label_s = lambda p, s: tk.Label(p, width=WIDTH_OF_DIGIT_LABEL, background='white', font=FONT_BOLD, anchor="e", borderwidth=2, relief="groove", state=s)
        _make_normal_label =  lambda p, t, w, r, c: tk.Label(p, text=t, font=FONT_NORMAL, width=w).grid(row=r, column=c)
        _make_type_label =    lambda p, t, r, c: _make_normal_label(p, t, WIDTH_OF_TYPE_LABEL, r, c)
        _make_unit_label =    lambda p, t, r, c: _make_normal_label(p, t, WIDTH_OF_UNIT_LABEL, r, c)
        _make_label_label  =   lambda p, t, r, c:  tk.Label(p, text=t, font=FONT_NORMAL, width=WIDTH_OF_LABEL_LABEL).grid(row=r, column=c, columnspan=3)

        def _make_label_entry(p, t, r, c):
            tke = tk.Entry(p, font=FONT_NORMAL, width=WIDTH_OF_LABEL_LABEL, background="white", justify='center')
            tke.insert(0, t)
            tke.grid(row=r, column=c, columnspan=3, pady=1)
            return tke
        def _make_unit_entry(p, t, r, c, s='normal'):
            tke = tk.Entry(p, font=FONT_NORMAL, width=WIDTH_OF_UNIT_LABEL, background="white", justify='center', state=s)
            tke.insert(0, t)
            tke.grid(row=r, column=c, pady=1)
            return tke

        # Analog Input Frame
        _parent_frame = tk.LabelFrame(self, text='AnalogInput %d ch'%NUM_CH_AI, font=FONT_LARGE_BOLD)
        for ch in range(NUM_CH_AI):
            _text = 'CH %d (HX711-%d)'% (ch, ch) if ch < int(NUM_CH_AI/2) else 'CH %d (ADS1115-%d)'% (ch, (ch-8)//4)
            _config = self._config_json['ai'][ch]

            _lframe = tk.LabelFrame(_parent_frame, text=_text, font=FONT_BOLD)
            _lframe.grid(row=ch//int(NUM_CH_AI/2), column=ch%int(NUM_CH_AI/2), padx=3, pady=5, sticky='w')
            
            # Label for Channel
            _row = 0
            self._entry_ai_label_list.append(_make_label_entry(_lframe, _config['label'], _row, 0))
            # Raw Value
            _row += 1
            _make_type_label(_lframe, 'Raw', _row, 0)
            _label = _make_digit_label(_lframe)
            _label.grid(row=_row, column=1)
            self._label_ai_raw_list.append(_label)
            _make_unit_label(_lframe, 'i16', _row, 2)
            ## Physical Value
            _row += 1
            _make_type_label(_lframe, 'Phy', _row, 0)
            _label = _make_digit_label(_lframe)
            _label.grid(row=_row, column=1)
            self._label_ai_phy_list.append(_label)
            self._entry_ai_unit_list.append(_make_unit_entry(_lframe, _config['unit'], _row, 2))
            # Voltage Value
            _row += 1
            _make_type_label(_lframe, 'Vlt', _row, 0)
            _label = _make_digit_label(_lframe)
            _label.grid(row=_row, column=1)
            self._label_ai_vlt_list.append(_label)
            _text = 'mV/V' if ch < int(NUM_CH_AI/2) else 'V'
            _make_unit_label(_lframe, _text, _row, 2)
            # micro strain
            _row += 1
            if ch < int(NUM_CH_AI/2):
                _make_type_label(_lframe, 'μST', _row, 0)
                _label = _make_digit_label(_lframe)
                _label.grid(row=_row, column=1)
                self._label_ai_ust_list.append(_label)
                _make_unit_label(_lframe, 'με', _row, 2)
        _parent_frame.pack(side=tk.TOP, padx=5)

        # Analog Output Frame
        _parent_frame = tk.LabelFrame(self, text='AnalogOutput %d ch'%NUM_CH_AO, font=FONT_LARGE_BOLD)
        for ch in range(NUM_CH_AO):
            _state = 'disabled' if ch >= NUM_CH_AO_LIMIT else 'normal'
            _text = 'CH %d (GP8403-%d)'% (ch, ch//2)
            _config = self._config_json['ao'][ch]

            _lframe = tk.LabelFrame(_parent_frame, text=_text, font=FONT_BOLD)
            _lframe.grid(row=1, column=ch, padx=3, pady=5, sticky='w')

            # Label for Channel
            _row = 0
            self._entry_ao_label_list.append(_make_label_entry(_lframe, _config['label'], _row, 0))
            # Raw Value
            _row += 1
            _make_type_label(_lframe, 'Raw', _row, 0)
            _label = _make_digit_label_s(_lframe, _state)
            _label.grid(row=_row, column=1)
            self._label_ao_raw_list.append(_label)
            _make_unit_label(_lframe, 'u16', _row, 2)
            # Physical Value
            _row += 1
            _make_type_label(_lframe, 'Phy', _row, 0)
            _label = _make_digit_label_s(_lframe, _state)
            _label.grid(row=_row, column=1)
            self._label_ao_phy_list.append(_label) 
            self._entry_ao_unit_list.append(_make_unit_entry(_lframe, _config['unit'], _row, 2))
            # Voltage Value
            _row += 1
            _make_type_label(_lframe, 'Vlt', _row, 0)
            _label = _make_digit_label_s(_lframe, _state)
            _label.grid(row=_row, column=1)
            self._label_ao_vlt_list.append(_label)
            _make_unit_label(_lframe, 'V', _row, 2)
        _parent_frame.pack(side=tk.TOP, padx=5)

        # Parameter Frame
        _parent_frame = tk.LabelFrame(self, text='Parameter', font=FONT_LARGE_BOLD)
        for ch in range(NUM_CH_PARAM):
            _text = 'Param %d'% ch
            _config = self._config_json['param'][ch]

            _lframe = tk.LabelFrame(_parent_frame, text=_text, font=FONT_BOLD)
            _lframe.grid(row=ch//int(NUM_CH_PARAM/2), column=ch%int(NUM_CH_PARAM/2), padx=3, pady=5, sticky='w')
            # Label for Channel
            _row = 0
            self._entry_param_label_list.append(_make_label_entry(_lframe, _config['label'], _row, 0))
            # Physical Value
            _row += 1
            _make_type_label(_lframe, 'Phy', _row, 0)
            _label = _make_digit_label(_lframe)
            _label.grid(row=_row, column=1)
            self._label_param_phy_list.append(_label)
            self._entry_param_unit_list.append(_make_unit_entry(_lframe, _config['unit'],_row, 2))
        _parent_frame.pack(side=tk.TOP, padx=5)

        # Calibration Frame
        _parent_frame = tk.LabelFrame(self, text='Calibration', font=FONT_LARGE_BOLD)
        if _parent_frame:
            _row = 0
            _make_label_label(_parent_frame, 'Phy=A*Raw^2+B*Raw+C', _row, 0)
            _calib_cb_values = ["AI CH %d"%ch for ch in range(NUM_CH_AI)] + ["AO CH %d"%ch for ch in range(NUM_CH_AO)]
            # ComboBox
            _row += 1
            _calib_cb = ttk.Combobox(_parent_frame, values=_calib_cb_values, state='readonly', font=FONT_NORMAL)
            # if combobox is selected, update the entry
            def _update_entry(digit_label:tk.Label, cb:ttk.Combobox, entry_a:tk.Entry, entry_b:tk.Entry, entry_c:tk.Entry):
                _ch = cb.current()
                if _ch < NUM_CH_AI:
                    _a, _b, _c = self._aio.get_ai_calib(_ch)
                    _phy = self._aio.get_ai_phy(_ch)
                else:
                    _a, _b, _c = self._aio.get_ao_calib(_ch-NUM_CH_AI)
                    _phy = self._aio.get_ao_phy(_ch-NUM_CH_AI)
                entry_a.delete(0, tk.END)
                entry_a.insert(0, self.FMT_STRING_CALIB_FLOAT%_a)
                entry_b.delete(0, tk.END)
                entry_b.insert(0, self.FMT_STRING_CALIB_FLOAT%_b)
                entry_c.delete(0, tk.END)
                entry_c.insert(0, self.FMT_STRING_CALIB_FLOAT%_c)
                digit_label.config(text=self.FMT_STRING_FLOAT%_phy)
            #_calib_cb.bind('<<ComboboxSelected>>', lambda e: _update_entry(_digit, _calib_cb, _entry_a, _entry_b, _entry_c))
            _calib_cb.grid(row=_row, column=0, columnspan=3, padx=5)
            # A value
            _row += 1
            _make_type_label(_parent_frame, 'A', _row, 0)
            _entry_a = tk.Entry(_parent_frame, width=WIDTH_OF_DIGIT_LABEL, font=FONT_NORMAL, justify='right')
            _entry_a.grid(row=_row, column=1)
            _make_unit_label(_parent_frame, 'f32', _row, 2)
            # B value
            _row += 1
            _make_type_label(_parent_frame, 'B', _row, 0)
            _entry_b = tk.Entry(_parent_frame, width=WIDTH_OF_DIGIT_LABEL, font=FONT_NORMAL, justify='right')
            _entry_b.grid(row=_row, column=1)
            _make_unit_label(_parent_frame, 'f32', _row, 2)
            # C value
            _row += 1
            _make_type_label(_parent_frame, 'C', _row, 0)
            _entry_c = tk.Entry(_parent_frame, width=WIDTH_OF_DIGIT_LABEL, font=FONT_NORMAL, justify='right')
            _entry_c.grid(row=_row, column=1)
            _make_unit_label(_parent_frame, 'f32', _row, 2)
            # Phy Value
            _row += 1
            _make_type_label(_parent_frame, 'Phy', _row, 0)
            _digit = _make_digit_label(_parent_frame)
            _digit.grid(row=_row, column=1)
            _make_unit_label(_parent_frame, 'nan', _row, 2)

            _calib_cb.bind('<<ComboboxSelected>>', lambda e: _update_entry(_digit, _calib_cb, _entry_a, _entry_b, _entry_c))

            # Preview Button
            _row += 1
            def _update_phy(digit_label:tk.Label, cb:ttk.Combobox, entry_a:tk.Entry, entry_b:tk.Entry, entry_c:tk.Entry):
                _ch = cb.current()
                if _ch < 0:
                    return
                _a = float(entry_a.get())
                _b = float(entry_b.get())
                _c = float(entry_c.get())
                if _ch < NUM_CH_AI:
                    _x = self._aio.get_ai_raw(_ch)
                    _phy = _x * _a**2 + _x * _b + _c
                else:
                    _x = self._aio.get_ao_raw(_ch-NUM_CH_AI)
                    _phy = _x * _a**2 + _x * _b + _c
                digit_label.config(text=self.FMT_STRING_FLOAT%_phy)
            _btn = tk.Button(_parent_frame, text='Update', font=FONT_TINY, command=lambda: _update_phy(_digit, _calib_cb, _entry_a, _entry_b, _entry_c))
            _btn.grid(row=_row, column=0)
            # Offset Zero Button
            def _offset_zero_calib(digit_label:tk.Label, cb:ttk.Combobox, entry_a:tk.Entry, entry_b:tk.Entry, entry_c:tk.Entry):
                _ch = cb.current()
                if _ch < 0:
                    return
                _a = float(entry_a.get())
                _b = float(entry_b.get())
                if _ch < NUM_CH_AI:
                    _x = self._aio.get_ai_raw(_ch)
                    _phy = _x * _a**2 + _x * _b
                else:
                    _x = self._aio.get_ao_raw(_ch-NUM_CH_AI)
                    _phy = _x * _a**2 + _x * _b
                _c = -_phy
                _phy = _x * _a**2 + _x * _b + _c
                entry_c.delete(0, tk.END)
                entry_c.insert(0, self.FMT_STRING_CALIB_FLOAT%_c)
                digit_label.config(text=_phy)
            _btn = tk.Button(_parent_frame, text='Offset Zero', font=FONT_TINY, command=lambda: _offset_zero_calib(_label, _calib_cb, _entry_a, _entry_b, _entry_c))
            _btn.grid(row=_row, column=1)
            # Set Button
            def _set_calib(cb:ttk.Combobox, entry_a:tk.Entry, entry_b:tk.Entry, entry_c:tk.Entry):
                _ch = cb.current()
                if _ch < 0:
                    return
                _a = float(entry_a.get())
                _b = float(entry_b.get())
                _c = float(entry_c.get())
                if _ch < NUM_CH_AI:
                    self._aio.set_ai_calib(_a, _b, _c, _ch)
                else:
                    self._aio.set_ao_calib(_a, _b, _c, _ch-NUM_CH_AI)
            _btn = tk.Button(_parent_frame, text='Apply', font=FONT_TINY, command=lambda: _set_calib(_calib_cb, _entry_a, _entry_b, _entry_c))
            _btn.grid(row=_row, column=2)
        _parent_frame.pack(side=tk.LEFT, padx=5)

        # Analog output Frame
        _parent_frame = tk.LabelFrame(self, text='Set Analog Out', font=FONT_LARGE_BOLD)
        if _parent_frame:
            # select channnel combobox
            _row = 0
            _ao_cb_values = ["AO CH %d"%ch for ch in range(NUM_CH_AO)]
            _ao_cb = ttk.Combobox(_parent_frame, values=_ao_cb_values, state='readonly', font=FONT_NORMAL)
            _ao_cb.grid(row=_row, column=0, columnspan=3, padx=5)
            # Set Value Entry and Button
            _row += 1
            _make_type_label(_parent_frame, 'Vlt', _row, 0)
            _entry = tk.Entry(_parent_frame, width=WIDTH_OF_DIGIT_LABEL, font=FONT_NORMAL, justify='right')
            _entry.grid(row=_row, column=1, padx=5)
            _entry.insert(0, '0')
            _btn = tk.Button(_parent_frame, text='Set', font=FONT_SMALL, command=lambda: self._ui_send_req_set_ao(_ao_cb.current(), _entry))
            _btn.grid(row=_row, column=2, padx=5)

            _ao_cb.bind('<<ComboboxSelected>>', lambda e: _entry.delete(0, tk.END) or _entry.insert(0, self._util_convert_gp8403_raw2vlt(self._aio.get_ao_raw(_ao_cb.current()))))
        _parent_frame.pack(side=tk.LEFT, padx=5)

        # Information Frame
        _parent_frame = tk.LabelFrame(self, text='Information', font=FONT_LARGE_BOLD)
        if _parent_frame:
            # websocket url
            _row = 0
            _text = ""
            _text += "Websocket URL: %s"%self._webserver_url
            _text += "\n"
            _text += "Modbus Info: PORT:%s, Mode:%s, Baudrate:%d, Slave:%d"%(MODBUS_COM_PORT, MODBUS_MODE, MODBUS_BAUDRATE, MODBUS_SLAVE_ADDRESS)
            tk.Label(_parent_frame, text=_text, font=FONT_NORMAL, anchor="n").pack(side=tk.LEFT)
        _parent_frame.pack(side=tk.LEFT, padx=5)

        self.start_save_button = tk.Button(self, text='Start Save', font=FONT_NORMAL, command=self._ui_push_start_button)
        self.start_save_button.pack(side=tk.LEFT)
        self.stop_save_button = tk.Button(self, text='Stop Save', font=FONT_NORMAL, command=self._ui_push_stop_button, state='disabled')
        self.stop_save_button.pack(side=tk.LEFT)

    def _config_create_json(self):
        ret = {}
        _ai = []
        for ch in range(NUM_CH_AI):
            _ch_data = {}
            _ch_data['label'] = "AI CH %d LABEL"%ch if len(self._entry_ai_label_list)<=ch else self._entry_ai_label_list[ch].get()
            _ch_data['unit'] = "nan" if len(self._entry_ai_unit_list)<=ch else self._entry_ai_unit_list[ch].get()
            _ch_data['calib'] = self._aio.get_ai_calib(ch)
            _ai.append(_ch_data)
        ret['ai'] = _ai

        _ao = []
        for ch in range(NUM_CH_AO):
            _ch_data = {}
            _ch_data['label'] = "AO CH %d LABEL"%ch if len(self._entry_ao_label_list)<=ch else self._entry_ao_label_list[ch].get()
            _ch_data['unit'] = "nan" if len(self._entry_ao_unit_list)<=ch else self._entry_ao_unit_list[ch].get()
            _ch_data['calib'] =  self._aio.get_ao_calib(ch)
            _ao.append(_ch_data)
        ret['ao'] = _ao

        _param = []
        for ch in range(NUM_CH_PARAM):
            _ch_data = {}
            _ch_data['label'] = "Param CH %d LABEL"%ch if len(self._entry_param_label_list)<=ch else self._entry_param_label_list[ch].get()
            _ch_data['unit'] = "nan" if len(self._entry_param_unit_list)<=ch else self._entry_param_unit_list[ch].get()
            _param.append(_ch_data)
        ret['param'] = _param
        
        return ret

    def _config_save_json_to_appdata(self):
        self._config_json = self._config_create_json()
        with open(os.path.join(APP_DATA_DIR_PATH, self.DEFALUT_CONFIG_JSON_NAME), 'w') as f:
            json.dump(self._config_json, f)

    def _config_load_json_from_appdata(self):
        if not os.path.exists(os.path.join(APP_DATA_DIR_PATH, self.DEFALUT_CONFIG_JSON_NAME)):
            self._config_json = self._config_create_json()
            return
        try:
            with open(os.path.join(APP_DATA_DIR_PATH, self.DEFALUT_CONFIG_JSON_NAME), 'r') as f:
                self._config_json = json.load(f)
        except Exception as e:
            print('Failed to load config.json')
            print(e)
            self._config_json = self._config_create_json()

    def _bg_sql_save_stop(self):
        if not self._sql_engine:
            return
        
        self._sql_engine.clear_compiled_cache()
        self._sql_engine.dispose()
        self._sql_engine = None
        print('Background: Database closed: %s'%self._sql_db_path)
        self._sql_db_path = ""

    def _bg_sql_save_start(self):
        if self._sql_engine:
            self._bg_sql_save_stop()
        self._sql_db_path = os.path.join(TEMP_DATA_DIR_PATH, '%s.sqlite3'%datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
        self._sql_engine = create_engine('sqlite:///'+self._sql_db_path)
        Base.metadata.create_all(self._sql_engine)
        print('Background: Database created')
        print('Background: Database path: %s'%self._sql_db_path)

    def _bg_sql_save(self):
        if not self._sql_engine:
            return
        try:
            with Session(self._sql_engine) as session:
                data = AioDataTable()
                data.time = datetime.datetime.now()
                for ch in range(NUM_CH_AI):
                    setattr(data, 'ai_raw_%d'%ch, self._aio.get_ai_raw(ch))
                    setattr(data, 'ai_phy_%d'%ch, self._aio.get_ai_phy(ch))
                for ch in range(NUM_CH_AO):
                    setattr(data, 'ao_raw_%d'%ch, self._aio.get_ao_raw(ch))
                    setattr(data, 'ao_phy_%d'%ch, self._aio.get_ao_phy(ch))
                session.add(data)
                session.commit()
        except Exception as e:
            print('Background: Failed to save data')
            print(e)

    def _bg_modbus_calc_param(self):
        try:
            _previous = self._aio.get_param_phy_all()
            
            ########################################################################################################
            ## @todo implement your own calculation
            ########################################################################################################
            for ch in range(NUM_CH_PARAM):
                if ch < 4:
                    _previous[ch] = np.sin(time.time()/3.14)
                elif ch < 8:
                    _previous[ch] = np.abs(np.sin(time.time()/3.14))
                elif ch < 12:
                    _previous[ch] = 1.0 if np.sin(time.time()/3.14) > 0.0 else -1
                else:
                    _previous[ch] = _previous[ch] + 0.01 if _previous[ch]+0.01 < 1 else -1
            ########################################################################################################
            ########################################################################################################
            ########################################################################################################

            self._aio.set_param_phy_all(_previous)
        except Exception as e:
            print('Background: Failed to calc param')
            print(e)

    def _bg_modbus_thread(self):
        _base_time = time.time()
        _modbus_interval_ms = self._modbus_interval_ms
        _sql_save_interval_ms = self._sql_save_interval_ms

        while True:
            msg = self._modbus_msg_queue.get()
            match msg:
                case self.BG_CMD_TERMINATE:
                    break
                case self.BG_CMD_MODBUS_START:
                    framer = FramerType.RTU if MODBUS_MODE == 'RTU' else FramerType.ASCII
                    with self._modbus_client_lock:
                        self._modbus_client = ModbusClient.ModbusSerialClient(port=MODBUS_COM_PORT, framer=framer, baudrate=MODBUS_BAUDRATE, timeout=0.5)
                        if not self._modbus_client.connect():
                            print('Background: Modbus Failed to connect')
                    print('Background: Modbus Connected')
                case self.BG_CMD_MODBUS_STOP:
                    with self._modbus_client_lock:
                        self._modbus_client.close()
                    print('Background: Modbus Closed')
                case self.BG_CMD_SQL_SAVE_START:
                    self._bg_sql_save_start()
                    threading.Timer(next_time, lambda: self._modbus_msg_queue.put(self.BG_CMD_SQL_SAVE)).start()
                case self.BG_CMD_SQL_SAVE:
                    self._bg_sql_save()
                    next_time = ((_base_time - time.time()) % _sql_save_interval_ms/1000.0) or _sql_save_interval_ms/1000.0
                    threading.Timer(next_time, lambda: self._modbus_msg_queue.put(self.BG_CMD_SQL_SAVE)).start()
                case self.BG_CMD_SQL_SAVE_STOP:
                    self._bg_sql_save_stop()
                case self.BG_CMD_AO_SEND:
                    self._bg_modbus_sync_ao_all()
                case self.BG_CMD_AI_RECEIVE:
                    self._bg_modbus_sync_ai_all()
                    self._bg_modbus_calc_param()
                    next_time = ((_base_time - time.time()) % _modbus_interval_ms/1000.0) or _modbus_interval_ms/1000.0
                    threading.Timer(next_time, lambda: self._modbus_msg_queue.put(self.BG_CMD_AI_RECEIVE)).start()
                case self.BG_CMD_CHANGE_INTERVAL:
                    _sql_save_interval_ms = self._sql_save_interval_ms
                case _:
                    print('Background: Unknown message')

    def _bg_modbus_sync_ai_all(self):
        rr = None
        try:
            with self._modbus_client_lock:
                if self._modbus_client:
                    rr = self._modbus_client.read_input_registers(0, NUM_CH_AI_LIMIT, slave=MODBUS_SLAVE_ADDRESS)
        except Exception as e:
            print('sync_ai_all, Failed to write')
            print(e)
        if rr is not None and not rr.isError():
            if NUM_CH_AI_LIMIT < NUM_CH_AI:
                _temp = np.array(rr.registers, dtype=np.uint16).astype(np.int16)
                print(_temp)
                _temp = np.append(_temp, np.zeros(NUM_CH_AI-NUM_CH_AI_LIMIT, dtype=np.int16))
                print(_temp)
                # padding zero to _temp tail, same to NUM_CH_AI
                self._aio.set_ai_raw_all(_temp)
            else:
                self._aio.set_ai_raw_all(np.array(rr.registers, dtype=np.uint16).astype(np.int16))

    def _bg_modbus_sync_ao_all(self):
        data = self._aio.get_ao_raw_all()
        if NUM_CH_AO_LIMIT < NUM_CH_AO:
            data = data[:NUM_CH_AO_LIMIT]
        try:
            with self._modbus_client_lock:
                if self._modbus_client:
                    self._modbus_client.write_registers(0, data, slave=MODBUS_SLAVE_ADDRESS)
        except Exception as e:
            print('sync_ao_all, Failed to write')
            print(e)

    def _bg_webserver_create_json_response(self):
        json_env = {
            "version": "1.0",
            'num_ch_ai': NUM_CH_AI,
            'num_ch_ao': NUM_CH_AO,
            'num_ch_param': NUM_CH_PARAM,
            'modbus_com_port': MODBUS_COM_PORT,
            'modbus_mode': MODBUS_MODE,
            'modbus_baudrate': MODBUS_BAUDRATE,
            'modbus_slave_address': MODBUS_SLAVE_ADDRESS,
        }
        json_key =  ["index", "time"] + \
                    ["ai_raw_%d"%i for i in range(NUM_CH_AI)] + \
                    ["ai_phy_%d"%i for i in range(NUM_CH_AI)] + \
                    ["ao_raw_%d"%i for i in range(NUM_CH_AO)] + \
                    ["ao_phy_%d"%i for i in range(NUM_CH_AO)] + \
                    ["ao_vlt_%d"%i for i in range(NUM_CH_AO)] + \
                    ["param_phy_%d"%i for i in range(NUM_CH_PARAM)]
        json_label = {"time": "Time"}
        json_unit = {"time": None }
        json_data = {
            'index': -1, 
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
        }
        for ch in range(NUM_CH_AI):
            _label = self._entry_ai_label_list[ch].get()
            json_label['ai_raw_%d'%ch] = _label
            json_unit['ai_raw_%d'%ch] = 'i16'
            json_data['ai_raw_%d'%ch] = int(self._aio.get_ai_raw(ch))

            json_label['ai_phy_%d'%ch] = _label
            json_unit['ai_phy_%d'%ch] = self._entry_ai_unit_list[ch].get()
            json_data['ai_phy_%d'%ch] = float(self._aio.get_ai_phy(ch))

            json_label['ai_vlt_%d'%ch] = _label
            if ch < int(NUM_CH_AI/2):
                json_unit['ai_vlt_%d'%ch] = 'mV/V'
                json_data['ai_vlt_%d'%ch] = self._util_convert_hx711_raw2vlt(int(self._aio.get_ai_raw(ch)))
            else:
                json_unit['ai_vlt_%d'%ch] = 'V'
                json_data['ai_vlt_%d'%ch] = self._util_convert_ads1115_raw2vlt(int(self._aio.get_ai_raw(ch)))

        for ch in range(NUM_CH_AO):
            _label = self._entry_ao_label_list[ch].get()
            json_label['ao_raw_%d'%ch] = _label
            json_unit['ao_raw_%d'%ch] = 'i16'
            json_data['ao_raw_%d'%ch] = int(self._aio.get_ao_raw(ch))

            json_label['ao_phy_%d'%ch] = _label
            json_unit['ao_phy_%d'%ch] = self._entry_ao_unit_list[ch].get()
            json_data['ao_phy_%d'%ch] = float(self._aio.get_ao_phy(ch))

            json_label['ao_vlt_%d'%ch] = _label
            json_unit['ao_vlt_%d'%ch] = 'V'
            json_data['ao_vlt_%d'%ch] = self._util_convert_gp8403_raw2vlt(self._aio.get_ao_raw(ch))
        for ch in range(NUM_CH_PARAM):
            json_label['param_phy_%d'%ch] = self._entry_param_label_list[ch].get()
            json_unit['param_phy_%d'%ch] = self._entry_param_unit_list[ch].get()
            json_data['param_phy_%d'%ch] = float(self._aio.get_param_phy(ch))
        
        ret = {
            'env': json_env,
            'key': json_key,
            'label': json_label,
            'unit': json_unit,
            'data': [json_data],
        }
        return json.dumps(ret)
    
    async def _bg_webserver_websocket_handler(self, websocket: WebSocket):
        await websocket.accept()
        while True:
            try:
                msg = self._bg_webserver_create_json_response()
                await websocket.send_text(msg)
                await asyncio.sleep(1)
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(e)
                break

    def _bg_webserver_hello_world(self):
        return {"Hello": "World"}

    def _bg_webserver_thread(self):
        self._fastapi_app.add_api_route('/hello', self._bg_webserver_hello_world)
        self._fastapi_app.add_websocket_route('/ws', self._bg_webserver_websocket_handler)
        uvicorn.run(self._fastapi_app, host=WEB_HOST, port=WEB_PORT)

    def _util_convert_hx711_raw2vlt(self, raw:int):
        return float(raw)/32768.0/128.0/2*1E3
    
    def _util_convert_hx711_raw2ust(self, raw:int):
        return float(raw)/32768.0/128.0/2*1E3*2E3

    def _util_convert_ads1115_raw2vlt(self, raw:int):
        return float(raw)/32768.0*6.144
    
    def _util_convert_gp8403_raw2vlt(self, raw:int):
        return float(raw)/1000.0

def main():
    if not os.path.exists(TEMP_DATA_DIR_PATH):
        os.makedirs(TEMP_DATA_DIR_PATH)
    if not os.path.exists(APP_DATA_DIR_PATH):
        os.makedirs(APP_DATA_DIR_PATH)

    if platform.system() == 'Windows':
        proc = psutil.Process(os.getpid())
        proc.nice(psutil.REALTIME_PRIORITY_CLASS)

    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()

if __name__ == "__main__":
    main()

