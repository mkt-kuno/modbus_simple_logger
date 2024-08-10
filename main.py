import time
import copy
import tkinter as tk

import queue
import threading
import multiprocessing as mp

import numpy as np
import matplotlib.pyplot as plt

from pymodbus import FramerType
import pymodbus.client as ModbusClient

MODBUS_COM_PORT = 'COM11'
MODBUS_MODE = 'RTU'
MODBUS_BAUDRATE = 38400

NUM_CH_AI = 16
NUM_CH_AO = 8
NUM_CH_AO_LIMIT = 6
HX711_VOLTAGE = 4.2

class ThreadSafeAioData():
    def __init__(self):
        self._ai = np.array([0]*NUM_CH_AI, dtype=np.int16)
        self._ao = np.array([0]*NUM_CH_AO, dtype=np.uint16)
        self._lock = threading.Lock()
    
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

    def get_ao_data_all(self):
        with self._lock:
            return copy.deepcopy(self._ao)
    
    def get_ai_data_all(self):
        with self._lock:
            return copy.deepcopy(self._ai)
    
    def get_ai_data(self, ch:int):
        if ch < 0 or ch >= NUM_CH_AI:
            raise ValueError('Invalid channel')
        with self._lock:
            return copy.deepcopy(self._ai[ch])

# Create a new thread for ModbusRTU
class Application(tk.Frame):
    _aio_data = ThreadSafeAioData()
    _msg_queue = queue.Queue()
    _bg_thread = None

    _label_ai_raw_list = []
    _label_ai_vlt_list = []
    _label_ai_ust_list = []
    _label_ai_phy_list = []
    _label_ao_raw_list = []
    _label_ao_phy_list = []

    _calib_a_list = [0.0]*NUM_CH_AI
    _calib_b_list = [1.0]*NUM_CH_AI
    _calib_c_list = [0.0]*NUM_CH_AI

    def start_background_job(self):
        self._bg_thread = threading.Thread(target=self.modbus_thread, daemon=True)
        self._bg_thread.start()

    def stop_background_job(self):
        self._msg_queue.put('stop')
        self._bg_thread.join()

    def modbus_thread(self):
        print('ModbusRTU thread started')
        framer = FramerType.RTU if MODBUS_MODE == 'RTU' else FramerType.ASCII
        client = ModbusClient.ModbusSerialClient(port=MODBUS_COM_PORT, framer=framer, baudrate=MODBUS_BAUDRATE, timeout=0.5)
        client.connect()
        base_time = time.time()
        next_time = 0
        interval = 0.100

        while client.connected:
            msg = None
            if not self._msg_queue.empty():
                msg = self._msg_queue.get()
                if type(msg) is not str:
                    msg = None
            if msg is not None:
                if msg == 'stop':
                    print('ModbusRTU: Exiting thread')
                    break
                elif msg == 'send':
                    print('ModbusRTU: Sending data')
                    ao = self._aio_data.get_ao_data_all().tolist()[:NUM_CH_AO_LIMIT]
                    client.write_registers(0, ao, slave=1)

            rr = client.read_input_registers(0, NUM_CH_AI, slave=1)
            self._aio_data.set_ai_data_all(np.array(rr.registers, dtype=np.uint16).astype(np.int16))

            next_time = ((base_time - time.time()) % interval) or interval
            time.sleep(next_time)
        
        client.close()

    def __init__(self, master=None):
        super().__init__(master)
        self.pack()
        self.create_widgets()
        self.after(200, self.update)

        self.master.geometry("1920x1000")
        self.master.resizable(False, True)

    def update(self):
        FMT_STRING_FLOAT = '%.3f'

        ai = self._aio_data.get_ai_data_all()
        for ch in range(NUM_CH_AI):
            self._label_ai_raw_list[ch].config(text="%d"% ai[ch])
            _x = ai[ch]
            _a = self._calib_a_list[ch]
            _b = self._calib_b_list[ch]
            _c = self._calib_c_list[ch]
            _phy = _a**2*_x + _b*_x + _c
            if ch < int(NUM_CH_AI/2):
                self._label_ai_vlt_list[ch].config(text=FMT_STRING_FLOAT%(float(_x)/32768.0/128.0/2*1E3*HX711_VOLTAGE))
                self._label_ai_ust_list[ch].config(text=FMT_STRING_FLOAT%(float(_x)/32768.0/128.0/2*1E6*2))
            else:
                self._label_ai_vlt_list[ch].config(text=FMT_STRING_FLOAT%(float(_x)/32768.0*6.144))
            self._label_ai_phy_list[ch].config(text=FMT_STRING_FLOAT%_phy)
        for ch in range(NUM_CH_AO):
            _x = self._aio_data.get_ao_data(ch)
            self._label_ao_raw_list[ch].config(text=int(_x))
            self._label_ao_phy_list[ch].config(text=FMT_STRING_FLOAT% (float(_x)/1000.0))
            
        self.after(200, self.update)

    def set_ao(self, ch, entry):
        try:
            _x = float(entry.get())
            _x = np.uint16(_x*1000)
            if _x < 0 or _x > 10000:
                raise ValueError('Invalid value')
            self._aio_data.set_ao_data(_x, ch)
            self._msg_queue.put('send')
        except ValueError as e:
            print

    def set_calib_vlt_offset(self, ch):
        _x = self._aio_data.get_ai_data(ch)
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
            self.place(x=0, y=0)
            self._canvas.pack(side='left')
        _frame.pack()

def main():
    root = tk.Tk()
    app = Application(master=root)
    app.start_background_job()
    app.mainloop()
    app.stop_background_job()

if __name__ == "__main__":
    main()

