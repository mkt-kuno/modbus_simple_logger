import io, os, time, copy, platform, psutil, datetime
import tkinter as tk
import tkinter.ttk as ttk

import threading, queue
import multiprocessing as mp

import numpy as np
import matplotlib.pyplot as plt

from pymodbus import FramerType
import pymodbus.client as ModbusClient

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.schema import Column
from sqlalchemy.types import DateTime, Integer, Float, String
Base = declarative_base()

MODBUS_COM_PORT = 'COM11'
MODBUS_MODE = 'RTU'
MODBUS_BAUDRATE = 38400
MODBUS_SLAVE_ADDRESS = 1

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
        self._calib_a = np.array([0.0]*NUM_CH_AI, dtype=np.float32)
        self._calib_b = np.array([1.0]*NUM_CH_AI, dtype=np.float32)
        self._calib_c = np.array([0.0]*NUM_CH_AI, dtype=np.float32)
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
            self._calib_a[ch] = a
            self._calib_b[ch] = b
            self._calib_c[ch] = c

    def get_ai_calib_value(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            return (self._calib_a[ch], self._calib_b[ch], self._calib_c[ch])

    def get_ai_data_calibed(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            return (self._ai[ch] * self._calib_a[ch]**2 + self._ai[ch] * self._calib_b[ch] + self._calib_c[ch])

    def get_ai_data_calibed_all(self):
        with self._lock:
            _temp = self._ai.astype(np.float32)
            return (_temp * self._calib_a**2 + _temp * self._calib_b + self._calib_c)

    def get_ao_data_calibed(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AO:
            raise ValueError('Invalid channel')
        with self._lock:
            return (self._ao[ch] / 1000.0)
    
    def get_ao_data_calibed_all(self):
        with self._lock:
            return (self._ao / 1000.0)

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

    HX711_VOLTAGE = 4.2
    FMT_STRING_FLOAT = '%.3f'

    _aio = ThreadSafeAioData()
    _msg_queue = queue.Queue()
    _bg_thread = None
    _sql_engine = None
    _sql_db_path = ""

    _modbus_client = None
    _modbus_client_lock = threading.Lock()

    _pipe_is_wainting = False

    _label_ai_raw_list = []
    _label_ai_vlt_list = []
    _label_ai_ust_list = []
    _label_ai_phy_list = []
    _label_ao_raw_list = []
    _label_ao_phy_list = []
    _label_param_list = []

    def __init__(self, master=None):
        super().__init__(master)
        self.pack()
        self.create_widgets()

        self.master.title("Modbus Simple Logger")
        self.master.geometry("1920x1000")
        self.master.resizable(False, True)

        self.after(200, self.update)

    def start_background_job(self):
        self._bg_thread = threading.Thread(target=self.background_thread, daemon=True)
        self._bg_thread.start()
        self._msg_queue.put(self.BG_CMD_MODBUS_START)
        self._msg_queue.put(self.BG_CMD_AO_SEND)
        self._msg_queue.put(self.BG_CMD_AI_RECEIVE)

    def stop_background_job(self):
        self._msg_queue.put(self.BG_CMD_MODBUS_STOP)
        self._msg_queue.put(self.BG_CMD_TERMINATE)
        self._bg_thread.join()

    def save_data_to_db(self):
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

    def background_calc_param(self):
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

    def background_thread(self):
        base_time = time.time()
        next_time = 0
        interval = 0.100

        while True:
            msg = self._msg_queue.get()
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
                    self.sync_ao_all()
                case self.BG_CMD_AI_RECEIVE:
                    self.sync_ai_all()
                    self.save_data_to_db()
                    self.background_calc_param()
                    next_time = ((base_time - time.time()) % interval) or interval
                    threading.Timer(next_time, lambda: self._msg_queue.put(self.BG_CMD_AI_RECEIVE)).start()
                case _:
                    print('Background: Unknown message')

    def sync_ai_all(self):
        rr = None
        try:
            with self._modbus_client_lock:
                if self._modbus_client:
                    rr = self._modbus_client.read_input_registers(0, NUM_CH_AI, slave=MODBUS_SLAVE_ADDRESS)
        except Exception as e:
            print('sync_ai_all, Failed to write')
            print(e)
        if rr.isError():
            return
        self._aio.set_ai_data_all(np.array(rr.registers, dtype=np.uint16).astype(np.int16))

    def sync_ao_all(self):
        data = self._aio.get_ao_data_all().tolist()
        try:
            with self._modbus_client_lock:
                if self._modbus_client:
                    self._modbus_client.write_registers(0, data, slave=MODBUS_SLAVE_ADDRESS)
        except Exception as e:
            print('sync_ao_all, Failed to write')
            print(e)

    def update(self):
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
                _ust = float(_raw)/32768.0/128.0/2*1E6*2
                self._label_ai_vlt_list[ch].config(text=self.FMT_STRING_FLOAT%_vlt)
                self._label_ai_ust_list[ch].config(text=self.FMT_STRING_FLOAT%_ust)
            else:
                _vlt = float(_raw)/32768.0*6.144
                self._label_ai_vlt_list[ch].config(text=self.FMT_STRING_FLOAT%_vlt)
            self._label_ai_phy_list[ch].config(text=self.FMT_STRING_FLOAT%_phy)
        
        for ch in range(NUM_CH_AO):
            _raw = int(ao[ch])
            _phy = float(aoc[ch])
            self._label_ao_raw_list[ch].config(text=_raw)
            self._label_ao_phy_list[ch].config(text=self.FMT_STRING_FLOAT%_phy)

        for ch in range(NUM_CH_PARAM):
            _phy = float(par[ch])
            self._label_param_list[ch].config(text=self.FMT_STRING_FLOAT%_phy)

        if not self._pipe_is_wainting:
            x = 0.0
            y = 0.0
            _xa = self._x_axis_menu.get()
            _ya = self._y_axis_menu.get()
            match _xa.split('_')[0]:
                case 'time':
                    x = time.time()
                case 'phy':
                    x = aic[int(_xa.split('_')[1])]
                case 'param':
                    x = par[int(_xa.split('_')[1])]
            match _ya.split('_')[0]:
                case 'time':
                    y = time.time()
                case 'phy':
                    y = aic[int(_ya.split('_')[1])]
                case 'param':
                    y = par[int(_ya.split('_')[1])]
            self._pipe.send((x, y))
            #self._pipe.send((time.time(), self._aio.get_param_value(0)))
            self._pipe_is_wainting = True
        if self._pipe_is_wainting and self._pipe.poll():
            _bio = self._pipe.recv()
            _img = tk.PhotoImage(data=_bio)
            self._canvas_live.create_image(0, 0, image=_img, anchor='nw')
            self._canvas_live.image = _img
            self._pipe_is_wainting = False

        self.after(200, self.update)

    def set_ao(self, ch, entry):
        try:
            _x = float(entry.get())
            _x = np.uint16(_x*1000)
            if _x < 0 or _x > 10000:
                raise ValueError('Invalid value')
            self._aio.set_ao_data(_x, ch)
            self._msg_queue.put(self.BG_CMD_AO_SEND)
        except ValueError as e:
            print

    def set_calib_vlt_offset(self, ch):
        _x = self._aio.get_ai_data(ch)
        # self._calib_disp_offset_list[ch] = int((-1)*(_x))

    def create_widgets(self):
        FONT_NAME = 'Consolas'

        WIDTH_OF_TYPE_LABEL = 4
        WIDTH_OF_DIGIT_LABEL = 12
        WIDTH_OF_UNIT_LABEL = 5
        WIDTH_OF_INFO_LABEL = 20

        FONT_SIZE_NORMAL = 14
        FONT_SIZE_LARGE = 20

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
        _make_info_label  =   lambda p, t, r, c:  tk.Label(p, text=t, font=FONT_NORMAL, width=WIDTH_OF_INFO_LABEL).grid(row=r, column=c, columnspan=3)

        # Analog Input Frame
        _parent_frame = tk.LabelFrame(self, text='AnalogInput %d ch'%NUM_CH_AI, font=FONT_LARGE_BOLD)
        for ch in range(NUM_CH_AI):
            _text = 'CH %d (HX711-%d)'% (ch, ch) if ch < int(NUM_CH_AI/2) else 'CH %d (ADS1115-%d)'% (ch, (ch-8)//4)
            _lframe = tk.LabelFrame(_parent_frame, text=_text, font=FONT_BOLD)
            _lframe.grid(row=ch//int(NUM_CH_AI/2), column=ch%int(NUM_CH_AI/2), padx=3, pady=5, sticky='w')
            # Information
            _row = 0
            _make_info_label(_lframe, "CH Infomation Here", _row, 0)
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
            _make_unit_label(_lframe, '___', _row, 2)
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
            _lframe = tk.LabelFrame(_parent_frame, text=_text, font=FONT_BOLD)
            _lframe.grid(row=1, column=ch, padx=3, pady=5, sticky='w')
            # Information
            _row = 0
            _make_info_label(_lframe, "CH Infomation Here", _row, 0)
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
            _make_unit_label(_lframe, 'V', _row, 2)
            # Set Value Entry and Button
            _row += 1
            _make_type_label(_lframe, 'Vlt', _row, 0)
            _entry = tk.Entry(_lframe, width=WIDTH_OF_DIGIT_LABEL, font=FONT_NORMAL, justify='right', state=_state)
            _entry.grid(row=_row, column=1)
            _entry.insert(0, '0')
            tk.Button(_lframe, text='Set', font=FONT_SMALL, command=lambda ch=ch, entry=_entry: self.set_ao(ch, entry), state=_state).grid(row=_row, column=2)
        _parent_frame.pack(side=tk.TOP, padx=5)

        # Parameter Frame
        _parent_frame = tk.LabelFrame(self, text='Parameter', font=FONT_LARGE_BOLD)
        for ch in range(NUM_CH_PARAM):
            _text = 'Param %d'% ch
            _lframe = tk.LabelFrame(_parent_frame, text=_text, font=FONT_BOLD)
            _lframe.grid(row=ch//int(NUM_CH_PARAM/2), column=ch%int(NUM_CH_PARAM/2), padx=3, pady=5, sticky='w')
            # Information
            _row = 0
            _make_info_label(_lframe, "CH Infomation Here", _row, 0)
            # Physical Value
            _row += 1
            _make_type_label(_lframe, 'Phy', _row, 0)
            _label = _make_digit_label(_lframe)
            _label.grid(row=_row, column=1)
            self._label_param_list.append(_label)
            _make_unit_label(_lframe, '___',_row, 2)

        _parent_frame.pack(side=tk.TOP, padx=5)

        _frame = tk.Frame(self, width=1900, relief='raised')
        if _frame:
            self._canvas_live = tk.Canvas(_frame, width = 384, height = 216)
            self._canvas_live.create_rectangle(0, 0, 384+1, 216+1, fill = 'white')
            self._canvas_live.pack(side=tk.LEFT, padx=10, pady=8)

            _list = ['time']+['phy_%d'%i for i in range(NUM_CH_AI)]+['param_%d'%i for i in range(NUM_CH_PARAM)]
            self._x_axis_menu = ttk.Combobox(_frame, values=_list, state='readonly')
            self._x_axis_menu.current(0)
            self._x_axis_menu.pack(side=tk.LEFT, padx=10)
            self._x_axis_menu.bind('<<ComboboxSelected>>', lambda e: self._pipe.send('clear'))
            self._y_axis_menu = ttk.Combobox(_frame, values=_list, state='readonly')
            self._y_axis_menu.current(1)
            self._y_axis_menu.pack(side=tk.LEFT, padx=10)
            self._y_axis_menu.bind('<<ComboboxSelected>>', lambda e: self._pipe.send('clear'))
            # self._pulldown_menu = tk.Button(_frame, tearoff=0)
            # self._pulldown_menu.config(text='Menu')
            # self._pulldown_menu.add_command(label='Clear', command=lambda: self._msg_queue.put('clear'))
            # self._pulldown_menu.pack(side=tk.LEFT)

            self._canvas_whole = tk.Canvas(_frame, width = 384, height = 216)
            self._canvas_whole.create_rectangle(0, 0, 384+1, 216+1, fill = 'green')
            self._canvas_whole.pack(side=tk.LEFT, padx=10, pady=8)

            self._pipe, _pipe_for_child = mp.Pipe()
            self._plotter = ProcessPlotter()
            self._plot_process = mp.Process(target=self._plotter, args=(_pipe_for_child,), daemon=True)
            self._plot_process.start()
        _frame.pack(side='left')

        self.start_save_button = tk.Button(self, text='Start Save', font=FONT_NORMAL, command=self.push_start_button)
        self.start_save_button.pack(side='left')
        self.stop_save_button = tk.Button(self, text='Stop Save', font=FONT_NORMAL, command=self.push_stop_button, state='disabled')
        self.stop_save_button.pack(side='left')
        

    def push_start_button(self):
        self.start_save_button.config(state='disabled')
        self._msg_queue.put('save_start')
        self.stop_save_button.config(state='normal')
    
    def push_stop_button(self):
        self.stop_save_button.config(state='disabled')
        self._msg_queue.put('save_stop')
        self.start_save_button.config(state='normal')

class ProcessPlotter:
    def __init__(self):
        self.x = []
        self.y = []
        self.t0 = 0

    def terminate(self):
        plt.close('all')

    def __call__(self, pipe):
        self.pipe = pipe
        self.fig, self.ax = plt.subplots()
        
        while True:#self.pipe.poll():
            command = self.pipe.recv()
            if command is None:
                self.terminate()
                break
            if command == 'clear':
                #self.t0 = time.time()
                self.x = []
                self.y = []
                plt.cla()
                plt.clf()
                self.fig, self.ax = plt.subplots(figsize=(384,216), tight_layout=True)
                #self.fig = plt.figure()
            else:
                for i in range(0, len(command), 2):
                    self.x.append(command[i])
                    self.y.append(command[i+1])
                if len(self.x) > 2000:
                    self.x = self.x[1:]
                    self.y = self.y[1:]

                self.ax.clear()
                self.ax.plot(self.x, self.y)

                self.fig.set_size_inches(4.0, 2.15)
                self.fig.canvas.draw()
                self.fig.canvas.flush_events()
                _bio = io.BytesIO()
                plt.grid()
                plt.savefig(_bio, format='png')
                _bio.seek(0)

                self.pipe.send(_bio.read())
            #print('ProcessPlotter: done')

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
    app.start_background_job()
    app.mainloop()
    app.stop_background_job()

if __name__ == "__main__":
    main()

