import os, time, copy, json, platform, psutil, datetime, asyncio
import tkinter as tk
import tkinter.ttk as ttk

import threading, queue

import numpy as np

from websockets.sync import server as WSServe

from pymodbus import FramerType
import pymodbus.client as ModbusClient

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.schema import Column
from sqlalchemy.types import DateTime, Integer, Float, String
Base = declarative_base()

DEBUG = True

MODBUS_COM_PORT = 'COM11'
MODBUS_MODE = 'RTU'
MODBUS_BAUDRATE = 38400
MODBUS_SLAVE_ADDRESS = 1

WEBSOCKET_PORT = 60080
WEBSOCKET_HOST = 'localhost' if DEBUG else '0.0.0.0'

NUM_CH_AI = 16
NUM_CH_AO = 8
NUM_CH_AO_LIMIT = 6
NUM_CH_PARAM = 16

APP_DATA_DIR_PATH = os.path.join(os.environ['APPDATA'], 'ModbusSimpleLogger')
TEMP_DATA_DIR_PATH = os.path.join(os.environ['TEMP'], 'ModbusSimpleLogger')

class TableAio(Base):
    __tablename__ = 'aio'
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
    ao_raw_0 = Column(Float)
    ao_phy_1 = Column(Float)
    ao_phy_2 = Column(Float)
    ao_phy_3 = Column(Float)
    ao_phy_4 = Column(Float)
    ao_phy_5 = Column(Float)
    ao_phy_6 = Column(Float)
    ao_phy_7 = Column(Float)
    param_0 = Column(Float)
    param_1 = Column(Float)
    param_2 = Column(Float)
    param_3 = Column(Float)
    param_4 = Column(Float)
    param_5 = Column(Float)
    param_6 = Column(Float)
    param_7 = Column(Float)
    param_8 = Column(Float)
    param_9 = Column(Float)
    param_10 = Column(Float)
    param_11 = Column(Float)
    param_12 = Column(Float)
    param_13 = Column(Float)
    param_14 = Column(Float)
    param_15 = Column(Float)

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

    def set_param_value(self, value:float, ch:int):
        if ch < 0 or ch >= NUM_CH_PARAM:
            raise ValueError('Invalid channel')
        with self._lock:
            self._param[ch] = value
    
    def get_param_value(self, ch:int):
        if ch < 0 or ch >= NUM_CH_PARAM:
            raise ValueError('Invalid channel')
        with self._lock:
            return self._param[ch]
    
    def set_param_value_all(self, data:np.ndarray):
        if data.shape != (NUM_CH_PARAM,):
            raise ValueError('Invalid data shape')
        with self._lock:
            self._param = copy.deepcopy(data)
    
    def get_param_value_all(self):
        with self._lock:
            return copy.deepcopy(self._param)

    def set_ai_calib_value(self, a:float, b:float, c:float, ch:int):
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            self._ai_calib_a[ch] = a
            self._ai_calib_b[ch] = b
            self._ai_calib_c[ch] = c

    def get_ai_calib_value(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            return (float(self._ai_calib_a[ch]), float(self._ai_calib_b[ch]), float(self._ai_calib_c[ch]))

    def set_ao_calib_value(self, a:float, b:float, c:float, ch:int):
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            self._ao_calib_a[ch] = a
            self._ao_calib_b[ch] = b
            self._ao_calib_c[ch] = c
    
    def get_ao_calib_value(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            return (float(self._ao_calib_a[ch]), float(self._ao_calib_b[ch]), float(self._ao_calib_c[ch]))

    def get_ai_data_calibed(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            _x = self._ai[ch]
            _a = self._ai_calib_a[ch]
            _b = self._ai_calib_b[ch]
            _c = self._ai_calib_c[ch]
            return (_x * _a**2 + _x * _b + _c)

    def get_ai_data_calibed_all(self):
        with self._lock:
            _x = self._ai
            _a = self._ai_calib_a
            _b = self._ai_calib_b
            _c = self._ai_calib_c
            return (_x * _a**2 + _x * _b + _c)

    def get_ao_data_calibed(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            _x = self._ao[ch]
            _a = self._ao_calib_a[ch]
            _b = self._ao_calib_b[ch]
            _c = self._ao_calib_c[ch]
            return (_x * _a**2 + _x * _b + _c)
    
    def get_ao_data_calibed_all(self):
        with self._lock:
            _x = self._ao
            _a = self._ao_calib_a
            _b = self._ao_calib_b
            _c = self._ao_calib_c
            return (_x * _a**2 + _x * _b + _c)

    def set_ao_data(self, data:np.uint16, ch:int):
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            self._ao[ch] = copy.deepcopy(np.uint16(data))

    def set_ai_data(self, data:np.int16, ch:int):
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            self._ai[ch] = copy.deepcopy(np.int16(data))

    def set_ai_data_all(self, data:np.ndarray):
        if data.shape != (NUM_CH_AI,):
            raise ValueError('Invalid data shape')
        with self._lock:
            self._ai = copy.deepcopy(data)

    def get_ao_data(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            return copy.deepcopy(self._ao[ch])

    def get_ao_data_all(self) -> np.uint16:
        with self._lock:
            return copy.deepcopy(self._ao)
    
    def get_ai_data_all(self):
        with self._lock:
            return copy.deepcopy(self._ai)
    
    def get_ai_data(self, ch:int) -> np.int16:
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            return copy.deepcopy(self._ai[ch])

# Create a new thread for ModbusRTU
class Application(tk.Frame):
    BG_CMD_MODBUS_START = 'modbus_start'
    BG_CMD_MODBUS_STOP = 'modbus_stop'
    BG_CMD_SAVE_START = 'save_start'
    BG_CMD_SAVE_STOP = 'save_stop'
    BG_CMD_TERMINATE = 'terminate'
    BG_CMD_AO_SEND = 'ao_send'
    BG_CMD_AI_RECEIVE = 'ai_receive'

    DEFALUT_CONFIG_JSON_NAME = 'config.json'

    HX711_VOLTAGE = 4.2
    FMT_STRING_FLOAT = '%.3f'
    FMT_STRING_CALIB_FLOAT = '%.6f'

    _aio = ThreadSafeAioData()
    
    _sql_engine = None
    _sql_db_path = ""

    _webserver_url = "ws://%s:%d"%(WEBSOCKET_HOST, WEBSOCKET_PORT)

    _modbus_thread = None
    _modbus_msg_queue = queue.Queue()
    _modbus_client = None
    _modbus_client_lock = threading.Lock()

    _pipe_is_wainting = False

    _label_ai_raw_list = []
    _label_ai_vlt_list = []
    _label_ai_ust_list = []
    _label_ai_phy_list = []
    _label_ao_raw_list = []
    _label_ao_phy_list = []
    _label_ao_vlt_list = []
    _label_param_list = []

    _entry_ai_label_list = []
    _entry_ai_unit_list = []
    _entry_ao_label_list = []
    _entry_ao_unit_list = []
    _entry_param_label_list = []
    _entry_param_unit_list = []

    def _on_closing(self):
        self._stop_background_job()
        self._save_config_json_to_appdata()
        self.master.destroy()

    def __init__(self, master=None):
        super().__init__(master)
        self.pack()

        self.master = master
        self.master.title("Modbus Simple Logger")
        self.master.geometry("1920x1000")
        self.master.resizable(False, True)

        master.protocol("WM_DELETE_WINDOW", self._on_closing)

        self._config_json = {}
        self._load_config_json_from_appdata()

        # restore calib values to AIO
        for ch in range(NUM_CH_AI):
            _a, _b, _c = self._config_json['ai'][ch]['calib']
            self._aio.set_ai_calib_value(_a, _b, _c, ch)
        for ch in range(NUM_CH_AO):
            _a, _b, _c = self._config_json['ao'][ch]['calib']
            self._aio.set_ao_calib_value(_a, _b, _c, ch)

        self._create_widgets()
        self._start_background_job()
        self.after(200, self._update_display)

    def _create_config_json(self):
        ret = {}
        _ai = []
        for ch in range(NUM_CH_AI):
            _ch_data = {}
            _ch_data['label'] = "AI CH %d LABEL"%ch if len(self._entry_ai_label_list)<=ch else self._entry_ai_label_list[ch].get()
            _ch_data['unit'] = "nan" if len(self._entry_ai_unit_list)<=ch else self._entry_ai_unit_list[ch].get()
            _ch_data['calib'] = self._aio.get_ai_calib_value(ch)
            _ai.append(_ch_data)
        ret['ai'] = _ai

        _ao = []
        for ch in range(NUM_CH_AO):
            _ch_data = {}
            _ch_data['label'] = "AO CH %d LABEL"%ch if len(self._entry_ao_label_list)<=ch else self._entry_ao_label_list[ch].get()
            _ch_data['unit'] = "nan" if len(self._entry_ao_unit_list)<=ch else self._entry_ao_unit_list[ch].get()
            _ch_data['calib'] =  self._aio.get_ao_calib_value(ch)
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

    def _save_config_json_to_appdata(self):
        self._config_json = self._create_config_json()
        with open(os.path.join(APP_DATA_DIR_PATH, self.DEFALUT_CONFIG_JSON_NAME), 'w') as f:
            json.dump(self._config_json, f)

    def _load_config_json_from_appdata(self):
        if not os.path.exists(os.path.join(APP_DATA_DIR_PATH, self.DEFALUT_CONFIG_JSON_NAME)):
            self._config_json = self._create_config_json()
            return
        try:
            with open(os.path.join(APP_DATA_DIR_PATH, self.DEFALUT_CONFIG_JSON_NAME), 'r') as f:
                self._config_json = json.load(f)
        except Exception as e:
            print('Failed to load config.json')
            print(e)
            self._config_json = self._create_config_json()

    def _start_background_job(self):
        if self._modbus_thread:
            # Already started
            return
        self._modbus_thread = threading.Thread(target=self._modbus_bg_thread, daemon=True)
        self._modbus_thread.start()
        self._modbus_msg_queue.put(self.BG_CMD_MODBUS_START)
        self._modbus_msg_queue.put(self.BG_CMD_AO_SEND)
        self._modbus_msg_queue.put(self.BG_CMD_AI_RECEIVE)

        threading.Thread(target=self._webserver_bg_thread, daemon=True).start()

    def _stop_background_job(self):
        if not self._modbus_thread:
            # Already stopped
            return
        self._modbus_msg_queue.put(self.BG_CMD_MODBUS_STOP)
        self._modbus_msg_queue.put(self.BG_CMD_TERMINATE)
        self._modbus_thread.join()

    def _save_data_to_db(self):
        if self._sql_engine:
            try:
                with Session(self._sql_engine) as session:
                    aio = TableAio()
                    aio.time = datetime.datetime.now()
                    for ch in range(NUM_CH_AI):
                        setattr(aio, 'ai_raw_%d'%ch, int(self._aio.get_ai_data(ch)))
                        setattr(aio, 'ai_phy_%d'%ch, float(self._aio.get_ai_data_calibed(ch)))
                    for ch in range(NUM_CH_AO):
                        setattr(aio, 'ao_raw_%d'%ch, int(self._aio.get_ao_data(ch)))
                        setattr(aio, 'ao_phy_%d'%ch, float(self._aio.get_ao_data_calibed(ch)))
                    session.add(aio)
                    session.commit()
            except Exception as e:
                print('Background: Failed to save data')
                print(e)

    def _modbus_bg_calc_param(self):
        try:
            _previous = self._aio.get_param_value_all()

            ## @todo implement your own calculation
            for ch in range(NUM_CH_PARAM):
                if ch < 4:
                    _previous[ch] = np.sin(time.time()/3.14)
                elif ch < 8:
                    _previous[ch] = np.abs(np.sin(time.time()/3.14))
                elif ch < 12:
                    _previous[ch] = 1.0 if np.sin(time.time()/3.14) > 0.0 else -1
                else:
                    _previous[ch] = _previous[ch] + 0.01 if _previous[ch]+0.01 < 1 else -1
            
            self._aio.set_param_value_all(_previous)
        except Exception as e:
            print('Background: Failed to calc param')
            print(e)

    def _webserver_handler(self, websocket):
        while True:
            ret = {
                'time': datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f'),
                'num_ch_ai': NUM_CH_AI, 'num_ch_ao': NUM_CH_AO, 'num_ch_param': NUM_CH_PARAM,
                'modbus': {
                    'com_port': MODBUS_COM_PORT,
                    'mode': MODBUS_MODE,
                    'baudrate': MODBUS_BAUDRATE,
                    'slave_address': MODBUS_SLAVE_ADDRESS,
                },
                'ai': [],
                'ao': [],
                'param': [],
            }
            for ch in range(NUM_CH_AI):
                _data = {
                    'raw': int(self._aio.get_ai_data(ch)),
                    'phy': float(self._aio.get_ai_data_calibed(ch)),
                    'label': self._entry_ai_label_list[ch].get(),
                    'unit': self._entry_ai_unit_list[ch].get(),
                }
                ret['ai'].append(_data)
            for ch in range(NUM_CH_AO):
                _data = {
                    'raw': int(self._aio.get_ao_data(ch)),
                    'phy': float(self._aio.get_ao_data_calibed(ch)),
                    'label': self._entry_ao_label_list[ch].get(),
                    'unit': self._entry_ao_unit_list[ch].get(),
                }
                ret['ao'].append(_data)
            for ch in range(NUM_CH_PARAM):
                _data = {
                    'phy': float(self._aio.get_param_value(ch)),
                    'label': self._entry_param_label_list[ch].get(),
                    'unit': self._entry_param_unit_list[ch].get(),
                }
                ret['param'].append(_data)
            
            websocket.send(json.dumps(ret))
            time.sleep(1)

    def _webserver_bg_thread(self):
        with WSServe.serve(self._webserver_handler, WEBSOCKET_HOST, WEBSOCKET_PORT) as server:
            server.serve_forever()

    def _modbus_bg_thread(self):
        base_time = time.time()
        next_time = 0
        interval = 0.100

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
                case self.BG_CMD_SAVE_START:
                    if not self._sql_engine:
                        self._sql_db_path = os.path.join(TEMP_DATA_DIR_PATH, '%s.sqlite3'%datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
                        self._sql_engine = create_engine('sqlite:///'+self._sql_db_path)
                        Base.metadata.create_all(self._sql_engine)
                        print('Background: Database created')
                        print('Background: Database path: %s'%self._sql_db_path)
                case self.BG_CMD_SAVE_STOP:
                    if self._sql_engine:
                        self._sql_engine.clear_compiled_cache()
                        self._sql_engine.dispose()
                        self._sql_engine = None
                        print('Background: Database closed: %s'%self._sql_db_path)
                        self._sql_db_path = ""
                case self.BG_CMD_AO_SEND:
                    self._sync_ao_all()
                case self.BG_CMD_AI_RECEIVE:
                    self._sync_ai_all()
                    self._save_data_to_db()
                    self._modbus_bg_calc_param()
                    next_time = ((base_time - time.time()) % interval) or interval
                    threading.Timer(next_time, lambda: self._modbus_msg_queue.put(self.BG_CMD_AI_RECEIVE)).start()
                case _:
                    print('Background: Unknown message')

    def _sync_ai_all(self):
        rr = None
        try:
            with self._modbus_client_lock:
                if self._modbus_client:
                    rr = self._modbus_client.read_input_registers(0, NUM_CH_AI, slave=MODBUS_SLAVE_ADDRESS)
        except Exception as e:
            print('sync_ai_all, Failed to write')
            print(e)
        if rr is not None and not rr.isError():
            self._aio.set_ai_data_all(np.array(rr.registers, dtype=np.uint16).astype(np.int16))

    def _sync_ao_all(self):
        data = self._aio.get_ao_data_all().tolist()
        try:
            with self._modbus_client_lock:
                if self._modbus_client:
                    self._modbus_client.write_registers(0, data, slave=MODBUS_SLAVE_ADDRESS)
        except Exception as e:
            print('sync_ao_all, Failed to write')
            print(e)

    def _update_display(self):
        ao = self._aio.get_ao_data_all()
        ai = self._aio.get_ai_data_all()
        aic = self._aio.get_ai_data_calibed_all()
        aoc = self._aio.get_ao_data_calibed_all()
        par = self._aio.get_param_value_all()

        for ch in range(NUM_CH_AI):
            self._label_ai_raw_list[ch].config(text="%d"% ai[ch])
            _raw = ai[ch]
            _phy = aic[ch]
            if ch < int(NUM_CH_AI/2):
                _vlt = float(_raw)/32768.0/128.0/2*1E3*self.HX711_VOLTAGE
                _ust = float(_raw)/32768.0/128.0/2*1E3*2E3
                self._label_ai_vlt_list[ch].config(text=self.FMT_STRING_FLOAT%_vlt)
                self._label_ai_ust_list[ch].config(text=self.FMT_STRING_FLOAT%_ust)
            else:
                _vlt = float(_raw)/32768.0*6.144
                self._label_ai_vlt_list[ch].config(text=self.FMT_STRING_FLOAT%_vlt)
            self._label_ai_phy_list[ch].config(text=self.FMT_STRING_FLOAT%_phy)
        
        for ch in range(NUM_CH_AO):
            _raw = int(ao[ch])
            _phy = float(aoc[ch])
            _vlt = float(ao[ch])/1000.0
            self._label_ao_raw_list[ch].config(text=_raw)
            self._label_ao_phy_list[ch].config(text=self.FMT_STRING_FLOAT%_phy)
            self._label_ao_vlt_list[ch].config(text=self.FMT_STRING_FLOAT%_vlt)

        for ch in range(NUM_CH_PARAM):
            _phy = float(par[ch])
            self._label_param_list[ch].config(text=self.FMT_STRING_FLOAT%_phy)

        self.after(200, self._update_display)

    # def _set_ao(self, ch, entry):
    #     try:
    #         _x = float(entry.get())
    #         _x = np.uint16(_x*1000)
    #         if _x < 0 or _x > 10000:
    #             raise ValueError('Invalid value')
    #         self._aio.set_ao_data(_x, ch)
    #         self._modbus_msg_queue.put(self.BG_CMD_AO_SEND)
    #     except ValueError as e:
    #         pass

    def _create_widgets(self):
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
            _text = 'mV' if ch < int(NUM_CH_AI/2) else 'V'
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
            # # Set Value Entry and Button
            # if DEBUG:
            #     _row += 1
            #     _make_type_label(_lframe, 'Vlt', _row, 0)
            #     _entry = tk.Entry(_lframe, width=WIDTH_OF_DIGIT_LABEL, font=FONT_NORMAL, justify='right', state=_state)
            #     _entry.grid(row=_row, column=1)
            #     _entry.insert(0, '0')
            #     tk.Button(_lframe, text='Set', font=FONT_SMALL, command=lambda ch=ch, entry=_entry: self.set_ao(ch, entry), state=_state).grid(row=_row, column=2)
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
            self._label_param_list.append(_label)
            self._entry_param_unit_list.append(_make_unit_entry(_lframe, _config['unit'],_row, 2))
        _parent_frame.pack(side=tk.TOP, padx=5)

        # Calibration Frame
        _parent_frame = tk.LabelFrame(self, text='Calibration', font=FONT_LARGE_BOLD)
        if _parent_frame:
            _row = 0
            _make_label_label(_parent_frame, 'Phy=A*Raw^2+B*Raw+C', _row, 0)
            _cb_values = ["AI CH %d"%ch for ch in range(NUM_CH_AI)] + ["AO CH %d"%ch for ch in range(NUM_CH_AO)]
            # ComboBox
            _row += 1
            _cb = ttk.Combobox(_parent_frame, values=_cb_values, state='readonly', font=FONT_NORMAL)
            # if combobox is selected, update the entry
            def _update_entry(digit_label:tk.Label, cb:ttk.Combobox, entry_a:tk.Entry, entry_b:tk.Entry, entry_c:tk.Entry):
                _ch = cb.current()
                if _ch < NUM_CH_AI:
                    _a, _b, _c = self._aio.get_ai_calib_value(_ch)
                    _phy = self._aio.get_ai_data_calibed(_ch)
                else:
                    _a, _b, _c = self._aio.get_ao_calib_value(_ch-NUM_CH_AI)
                    _phy = self._aio.get_ao_data_calibed(_ch-NUM_CH_AI)
                entry_a.delete(0, tk.END)
                entry_a.insert(0, self.FMT_STRING_CALIB_FLOAT%_a)
                entry_b.delete(0, tk.END)
                entry_b.insert(0, self.FMT_STRING_CALIB_FLOAT%_b)
                entry_c.delete(0, tk.END)
                entry_c.insert(0, self.FMT_STRING_CALIB_FLOAT%_c)
                digit_label.config(text=self.FMT_STRING_FLOAT%_phy)
            # _cb.bind('<<ComboboxSelected>>', lambda e: _update_entry(_digit, _cb, _entry_a, _entry_b, _entry_c))
            _cb.grid(row=_row, column=0, columnspan=3, padx=5)
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

            _cb.bind('<<ComboboxSelected>>', lambda e: _update_entry(_digit, _cb, _entry_a, _entry_b, _entry_c))

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
                    _x = self._aio.get_ai_data(_ch)
                    _phy = _x * _a**2 + _x * _b + _c
                else:
                    _x = self._aio.get_ao_data(_ch-NUM_CH_AI)
                    _phy = _x * _a**2 + _x * _b + _c
                digit_label.config(text=self.FMT_STRING_FLOAT%_phy)
            _btn = tk.Button(_parent_frame, text='Update', font=FONT_TINY, command=lambda: _update_phy(_digit, _cb, _entry_a, _entry_b, _entry_c))
            _btn.grid(row=_row, column=0)
            # Offset Zero Button
            def _offset_zero_calib(digit_label:tk.Label, cb:ttk.Combobox, entry_a:tk.Entry, entry_b:tk.Entry, entry_c:tk.Entry):
                _ch = cb.current()
                if _ch < 0:
                    return
                _a = float(entry_a.get())
                _b = float(entry_b.get())
                if _ch < NUM_CH_AI:
                    _x = self._aio.get_ai_data(_ch)
                    _phy = _x * _a**2 + _x * _b
                else:
                    _x = self._aio.get_ao_data(_ch-NUM_CH_AI)
                    _phy = _x * _a**2 + _x * _b
                _c = -_phy
                _phy = _x * _a**2 + _x * _b + _c
                entry_c.delete(0, tk.END)
                entry_c.insert(0, self.FMT_STRING_CALIB_FLOAT%_c)
                digit_label.config(text=_phy)
            _btn = tk.Button(_parent_frame, text='Offset Zero', font=FONT_TINY, command=lambda: _offset_zero_calib(_label, _cb, _entry_a, _entry_b, _entry_c))
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
                    self._aio.set_ai_calib_value(_a, _b, _c, _ch)
                else:
                    self._aio.set_ao_calib_value(_a, _b, _c, _ch-NUM_CH_AI)
            _btn = tk.Button(_parent_frame, text='Apply', font=FONT_TINY, command=lambda: _set_calib(_cb, _entry_a, _entry_b, _entry_c))
            _btn.grid(row=_row, column=2)
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

        # self.start_save_button = tk.Button(self, text='Start Save', font=FONT_NORMAL, command=self._push_start_button)
        # self.start_save_button.pack(side=tk.LEFT)
        # self.stop_save_button = tk.Button(self, text='Stop Save', font=FONT_NORMAL, command=self._push_stop_button, state='disabled')
        # self.stop_save_button.pack(side=tk.LEFT)

    def _push_start_button(self):
        self.start_save_button.config(state='disabled')
        self._modbus_msg_queue.put('save_start')
        self.stop_save_button.config(state='normal')
    
    def _push_stop_button(self):
        self.stop_save_button.config(state='disabled')
        self._modbus_msg_queue.put('save_stop')
        self.start_save_button.config(state='normal')

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

