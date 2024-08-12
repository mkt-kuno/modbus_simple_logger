import io, os, time, copy, platform, psutil, datetime
import tkinter as tk

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
HX711_VOLTAGE = 4.2

FMT_STRING_FLOAT = '%.3f'

APP_DATA_DIR_PATH = os.path.join(os.environ['APPDATA'], 'ModbusSimpleLogger')
TEMP_DATA_DIR_PATH = os.path.join(os.environ['TEMP'], 'ModbusSimpleLogger')
if not os.path.exists(TEMP_DATA_DIR_PATH):
    os.makedirs(TEMP_DATA_DIR_PATH)
if not os.path.exists(APP_DATA_DIR_PATH):
    os.makedirs(APP_DATA_DIR_PATH)

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
    param_0 = Column(Float)
    param_1 = Column(Float)
    param_2 = Column(Float)
    param_3 = Column(Float)
    param_4 = Column(Float)
    param_5 = Column(Float)
    param_6 = Column(Float)
    param_7 = Column(Float)

class ThreadSafeAioData():
    def __init__(self):
        self._lock = threading.Lock()
        self._ai = np.array([0]*NUM_CH_AI, dtype=np.int16)
        self._ao = np.array([0]*NUM_CH_AO, dtype=np.uint16)
        self._calib_a = np.array([0.0]*NUM_CH_AI, dtype=np.float32)
        self._calib_b = np.array([1.0]*NUM_CH_AI, dtype=np.float32)
        self._calib_c = np.array([0.0]*NUM_CH_AI, dtype=np.float32)

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
    _aio = ThreadSafeAioData()
    _msg_queue = queue.Queue()
    _bg_thread = None

    _modbus_client = None
    _modbus_client_lock = threading.Lock()

    _label_ai_raw_list = []
    _label_ai_vlt_list = []
    _label_ai_ust_list = []
    _label_ai_phy_list = []
    _label_ao_raw_list = []
    _label_ao_phy_list = []

    def start_background_job(self):
        self._bg_thread = threading.Thread(target=self.background_thread, daemon=True)
        self._bg_thread.start()
        self._msg_queue.put('modbus_start')
        self._msg_queue.put("receive")

    def stop_background_job(self):
        self._msg_queue.put('modbus_stop')
        self._msg_queue.put('terminate')
        self._bg_thread.join()

    def background_thread(self):
        base_time = time.time()
        next_time = 0
        interval = 0.100

        sql_engine = None

        while True:
            msg = msg = self._msg_queue.get()
            match msg:
                case 'terminate':
                    break
                case 'modbus_start':
                    framer = FramerType.RTU if MODBUS_MODE == 'RTU' else FramerType.ASCII
                    with self._modbus_client_lock:
                        self._modbus_client = ModbusClient.ModbusSerialClient(port=MODBUS_COM_PORT, framer=framer, baudrate=MODBUS_BAUDRATE, timeout=0.5)
                        if not self._modbus_client.connect():
                            print('Background: Modbus Failed to connect')
                    self.sync_ao_all()
                    self.sync_ai_all()  
                    print('Background: Modbus Connected')
                case 'modbus_stop':
                    with self._modbus_client_lock:
                        self._modbus_client.close()
                    print('Background: Modbus Closed')
                case 'save_start':
                    self._db_path = os.path.join(TEMP_DATA_DIR_PATH, '%s.sqlite3'%datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
                    sql_engine = create_engine('sqlite:///'+self._db_path)
                    Base.metadata.create_all(sql_engine)
                case 'save_stop':
                    sql_engine.clear_compiled_cache()
                    sql_engine.dispose()
                    sql_engine = None
                case 'receive':
                    if self._modbus_client:
                        self.sync_ai_all()
                    if sql_engine:
                        try:
                            with Session(sql_engine) as session:
                                aio = TableAio()
                                #time include MM DD HH MM SS milliseconds
                                aio.time = datetime.datetime.now()
                                for ch in range(NUM_CH_AI):
                                    setattr(aio, 'ai_raw_%d'%ch, int(self._aio.get_ai_data(ch)))
                                    setattr(aio, 'ai_phy_%d'%ch, float(self._aio.get_ai_data_calibed(ch)))
                                for ch in range(NUM_CH_AO):
                                    setattr(aio, 'ao_raw_%d'%ch, int(self._aio.get_ao_data(ch)))
                                session.add(aio)
                                session.commit()
                        except Exception as e:
                            print('Background: Failed to save data')
                            print(e)
                    next_time = ((base_time - time.time()) % interval) or interval
                    threading.Timer(next_time, lambda: self._msg_queue.put("receive")).start()
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

    def sync_ao(self, ch):
        data = int(self._aio.get_ao_data(ch))
        try:
            with self._modbus_client_lock:
                self._modbus_client.write_register(ch, data, slave=MODBUS_SLAVE_ADDRESS)
        except Exception as e:
            print('sync_ao, Failed to write')
            print(e)

    def __init__(self, master=None):
        super().__init__(master)
        self.pack()
        self.create_widgets()
        self.after(200, self.update)

        self.master.geometry("1920x1000")
        self.master.resizable(False, True)

    def update(self):
        ao = self._aio.get_ao_data_all()
        ai = self._aio.get_ai_data_all()
        aic = self._aio.get_ai_data_calibed_all()
        aoc = self._aio.get_ao_data_calibed_all()

        for ch in range(NUM_CH_AI):
            self._label_ai_raw_list[ch].config(text="%d"% ai[ch])
            _raw = ai[ch]
            _phy = aic[ch]
            if ch < int(NUM_CH_AI/2):
                _vlt = float(_raw)/32768.0/128.0/2*1E3*HX711_VOLTAGE
                _ust = float(_raw)/32768.0/128.0/2*1E6*2
                self._label_ai_vlt_list[ch].config(text=FMT_STRING_FLOAT%_vlt)
                self._label_ai_ust_list[ch].config(text=FMT_STRING_FLOAT%_ust)
            else:
                _vlt = float(_raw)/32768.0*6.144
                self._label_ai_vlt_list[ch].config(text=FMT_STRING_FLOAT%_vlt)
            self._label_ai_phy_list[ch].config(text=FMT_STRING_FLOAT%_phy)
        
        for ch in range(NUM_CH_AO):
            _raw = int(ao[ch])
            _phy = float(aoc[ch])
            self._label_ao_raw_list[ch].config(text=_raw)
            self._label_ao_phy_list[ch].config(text=FMT_STRING_FLOAT%_phy)
        
        # self._plot_pipe.send((float(time.time()), float(self._aio.get_ai_data(0))))
        # if self._plot_pipe.poll():
        #     _bio = self._plot_pipe.recv()
        #     _img = tk.PhotoImage(data=_bio)
        #     self._canvas.create_image(0, 0, image=_img, anchor='nw')
        #     self._canvas.image = _img

        self.after(200, self.update)

    def set_ao(self, ch, entry):
        try:
            _x = float(entry.get())
            _x = np.uint16(_x*1000)
            if _x < 0 or _x > 10000:
                raise ValueError('Invalid value')
            self._aio.set_ao_data(_x, ch)
            self.sync_ao(ch)
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

        _parent_frame = tk.LabelFrame(self, text='AnalogInput %d ch'%NUM_CH_AI, font=FONT_LARGE_BOLD)
        for ch in range(NUM_CH_AI):
            _text = 'CH %d (HX711-%d)'% (ch, ch) if ch < int(NUM_CH_AI/2) else 'CH %d (ADS1115-%d)'% (ch, (ch-8)//4)
            _lframe = tk.LabelFrame(_parent_frame, text=_text, font=FONT_BOLD)
            _lframe.grid(row=ch//int(NUM_CH_AI/2), column=ch%int(NUM_CH_AI/2), padx=3, pady=5, sticky='w')
            # Raw Value
            _make_type_label(_lframe, 'Raw', 0, 0)
            _label = _make_digit_label(_lframe)
            _label.grid(row=0, column=1)
            self._label_ai_raw_list.append(_label)
            _make_unit_label(_lframe, 'i16', 0, 2)
            ## Physical Value
            _make_type_label(_lframe, 'Phy', 1, 0)
            _label = _make_digit_label(_lframe)
            _label.grid(row=1, column=1)
            self._label_ai_phy_list.append(_label)
            _make_unit_label(_lframe, '___', 1, 2)
            # Voltage Value
            _make_type_label(_lframe, 'Vlt', 2, 0)
            _label = _make_digit_label(_lframe)
            _label.grid(row=2, column=1)
            self._label_ai_vlt_list.append(_label)
            if ch < int(NUM_CH_AI/2):
                _make_unit_label(_lframe, 'mV', 2, 2)
            else:
                _make_unit_label(_lframe, 'V', 2, 2)
            # micro strain
            if ch < int(NUM_CH_AI/2):
                _make_type_label(_lframe, 'μST', 3, 0)
                _label = _make_digit_label(_lframe)
                _label.grid(row=3, column=1)
                self._label_ai_ust_list.append(_label)
                _make_unit_label(_lframe, 'με', 3, 2)
        _parent_frame.pack(side=tk.TOP, padx=5)

        _parent_frame = tk.LabelFrame(self, text='AnalogOutput %d ch'%NUM_CH_AO, font=FONT_LARGE_BOLD)
        for ch in range(NUM_CH_AO):
            _state = 'disabled' if ch >= NUM_CH_AO_LIMIT else 'normal'
            _text = 'CH %d (GP8403-%d)'% (ch, ch//2)
            _lframe = tk.LabelFrame(_parent_frame, text=_text, font=FONT_BOLD)
            _lframe.grid(row=1, column=ch, padx=3, pady=5, sticky='w')
            # Raw Value
            _make_type_label(_lframe, 'Raw', 0, 0)
            _label = _make_digit_label_s(_lframe, _state)
            _label.grid(row=0, column=1)
            self._label_ao_raw_list.append(_label)
            _make_unit_label(_lframe, 'u16', 0, 2)
            # Physical Value
            _make_type_label(_lframe, 'Phy', 1, 0)
            _label = _make_digit_label_s(_lframe, _state)
            _label.grid(row=1, column=1)
            self._label_ao_phy_list.append(_label) 
            _make_unit_label(_lframe, 'V', 1, 2)
            # Set Value Entry and Button
            _make_type_label(_lframe, 'SetV', 2, 0)
            _entry = tk.Entry(_lframe, width=WIDTH_OF_DIGIT_LABEL, font=FONT_NORMAL, justify='right', state=_state)
            _entry.grid(row=2, column=1)
            _entry.insert(0, '0')
            tk.Button(_lframe, text='Set', font=FONT_SMALL, command=lambda ch=ch, entry=_entry: self.set_ao(ch, entry), state=_state).grid(row=2, column=2)
        _parent_frame.pack(side=tk.TOP, padx=5)

        _frame = tk.Frame(self, width=1900, relief='raised')
        if _frame:
            self._canvas = tk.Canvas(_frame, width = 512, height = 512)
            self._canvas.create_rectangle(0, 0, 512, 512, fill = 'green')
            self._canvas.pack(padx=10, pady=10)

            # self._plot_pipe, self._plotter_pipe = mp.Pipe()
            # self._plotter = ProcessPlotter()
            # self._plot_process = mp.Process(target=self._plotter, args=(self._plotter_pipe,), daemon=True)
            # self._plot_process.start()
        _frame.pack(side='left')

class ProcessPlotter:
    def __init__(self):
        self.x = []
        self.y = []

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
                self.x = []
                self.y = []
                plt.cla()
                plt.clf()
                #self.fig, self.ax = plt.subplots()
                self.fig = plt.figure(figsize=(1,1), tight_layout=True)
            else:
                
                for i in range(0, len(command), 2):
                    self.x.append(command[i])
                    self.y.append(command[i+1])
                plt.plot(self.x, self.y)
                #self.ax.plot(self.x, self.y)
                #self.ax.set_aspect('equal')
                self.fig.canvas.draw()
                _bio = io.BytesIO()
                print('...done')
                plt.savefig(_bio, format='png')
                _bio.seek(0)

                self.pipe.send(_bio.read())

            print('ProcessPlotter: done')

def main():
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

