###############################################################################################################
###############################################################################################################
###############################################################################################################

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

###############################################################################################################
###############################################################################################################
###############################################################################################################

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

###############################################################################################################
###############################################################################################################
###############################################################################################################

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
