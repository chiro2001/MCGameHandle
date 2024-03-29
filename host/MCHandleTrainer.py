from tkinter import *
from tkinter import messagebox
from keras.layers import Dense
from keras.models import Sequential, load_model
import tensorflow as tf
import serial
import serial.tools.list_ports
import threading
from PIL import Image, ImageDraw, ImageTk
import numpy as np
import time
import multiprocessing
import queue

from host.BaseComm import BaseComm
from host.ui_logger import UiLogger


class MCHandleTrainer:
    ACTION_NONE = '无动作'
    ACTION_FORWARD = '前进'
    ACTION_JUMP = '起跳'
    ACTION_DOWN = '下降'
    ACTION_HIT = '打击'
    ACTION_PUT = '放置'
    ACTIONS = [ACTION_NONE, ACTION_FORWARD, ACTION_JUMP, ACTION_DOWN, ACTION_HIT, ACTION_PUT]

    def __init__(self, root=None):
        self.init_top = Tk()

        self.port_left = 'COM4'
        self.port_right = 'COM5'

        self.init_bps = StringVar()
        self.init_bps.set('115200')
        self.init_com_left = StringVar()
        self.init_com_left.set(self.port_left)
        self.init_com_right = StringVar()
        self.init_com_right.set(self.port_right)

        self.init_communication()

        self.bps = 115200
        self.comm = None
        self.n = 512
        self.select = 24
        self.frames = [[0 for i in range(12)] for j in range(self.n)]
        self.raw = [[[0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]] for j in range(self.n)]

        # 建立网络
        self.model_file = 'mc_actions.h5'

        # 建立网络的过程放在线程2

        # self.model = model
        # print(self.model.get_config())

        self.comm_left = BaseComm(self.init_com_left.get(), self.bps)
        self.comm_right = BaseComm(self.init_com_right.get(), self.bps)

        self.root = root
        if self.root is None:
            self.root = Tk()
        self.root.title("MC手柄训练器")

        self.panel = Label(self.root)
        self.panel.pack(side=TOP, expand=1, fill=X)

        frame = Frame(self.root)
        Button(frame, text='切换模式', command=self.predict_mode).grid(row=1, column=1, sticky=W + E)
        Button(frame, text='前进', command=self.action_forward).grid(row=1, column=2, sticky=W + E)
        Button(frame, text='上跳', command=self.action_jump).grid(row=1, column=3, sticky=W + E)
        Button(frame, text='下降', command=self.action_down).grid(row=1, column=4, sticky=W + E)
        Button(frame, text='打击', command=self.action_hit).grid(row=1, column=5, sticky=W + E)
        Button(frame, text='放置', command=self.action_put).grid(row=1, column=6, sticky=W + E)
        Button(frame, text='无动作', command=self.action_none).grid(row=1, column=7, sticky=W + E)
        Button(frame, text='保存模型', command=self.save_model).grid(row=1, column=8, sticky=W + E)
        Label(frame, text='正在训练:').grid(row=1, column=9, sticky=W + E)

        self.var_training = StringVar()
        self.var_training.set('...')
        Label(frame, textvariable=self.var_training).grid(row=1, column=10, sticky=W + E)

        frame.pack(side=BOTTOM, expand=1, fill=X)

        self.logger_test = UiLogger(self.root, title='程序日志', simplify=False, height=10)
        self.logger_test.logger().pack(side=BOTTOM, expand=1, fill=X)

        self.lock = threading.Lock()

        self.training = self.ACTION_NONE
        self.will_save_model = False
        self.train_mode = True

        self.t1 = 0
        self.t2 = 0

        t = threading.Thread(target=self.read_thread)
        t.setDaemon(True)
        t.start()
        t = threading.Thread(target=self.parse_thread)
        t.setDaemon(True)
        t.start()

    def predict_mode(self):
        if self.train_mode is True:
            self.train_mode = False
            self.logger_test.push(UiLogger.Item(UiLogger.LEVEL_WARNING, 'switch', '切换到预测模式'))
            self.t2 = 0
        else:
            self.train_mode = True
            self.logger_test.push(UiLogger.Item(UiLogger.LEVEL_WARNING, 'switch', '切换到训练模式'))
            self.t2 = 0

    def action_forward(self):
        if self.training == self.ACTION_FORWARD:
            self.training = self.ACTION_NONE
        else:
            self.training = self.ACTION_FORWARD

    def action_jump(self):
        if self.training == self.ACTION_JUMP:
            self.training = self.ACTION_NONE
        else:
            self.training = self.ACTION_JUMP

    def action_down(self):
        if self.training == self.ACTION_DOWN:
            self.training = self.ACTION_NONE
        else:
            self.training = self.ACTION_DOWN

    def action_hit(self):
        if self.training == self.ACTION_HIT:
            self.training = self.ACTION_NONE
        else:
            self.training = self.ACTION_HIT

    def action_put(self):
        if self.training == self.ACTION_PUT:
            self.training = self.ACTION_NONE
        else:
            self.training = self.ACTION_PUT

    def action_none(self):
        self.training = self.ACTION_NONE

    def save_model(self):
        self.will_save_model = True

    def init_communication(self):
        top = self.init_top
        frame = LabelFrame(top, text="连接设置")
        Label(frame, text="左手柄").grid(row=1, column=1)
        Entry(frame, textvariable=self.init_com_left).grid(row=1, column=2)
        Label(frame, text="右手柄").grid(row=2, column=1)
        Entry(frame, textvariable=self.init_com_right).grid(row=2, column=2)
        Label(frame, text="波特率").grid(row=3, column=1)
        Entry(frame, textvariable=self.init_bps).grid(row=3, column=2)
        frame.grid(row=1, columnspan=3, column=1)

        Button(top, text="测试", command=self.init_communication_test).grid(row=2, column=1, sticky=W+E)
        Button(top, text="刷新", command=self.init_communication_refresh).grid(row=2, column=2, sticky=W+E)
        Button(top, text="确定", command=self.init_communication_ok).grid(row=2, column=3, sticky=W+E)
        top.mainloop()

    def init_communication_ok(self):
        try:
            bps = int(self.init_bps.get())
        except ValueError:
            messagebox.showerror("错误", '数值错误！')
            return
        self.bps = bps
        self.port_left = self.init_com_left.get()
        self.port_right = self.init_com_right.get()
        if self.init_communication_test(show=False) is False:
            messagebox.showerror("错误", '手柄测试不通过！')
            return
        self.init_top.destroy()

    def mainloop(self):
        self.root.mainloop()

    def init_communication_test(self, show=True):
        try:
            bps = int(self.init_bps.get())
        except ValueError:
            messagebox.showerror("错误", '数值错误！')
            return
        res = True
        print('测试左手柄')
        comm = BaseComm(self.init_com_left.get(), bps)
        if not comm.test():
            if show is True:
                messagebox.showerror("错误", '测试左手柄失败')
            res = False
        comm.close()
        print('测试右手柄')
        comm = BaseComm(self.init_com_right.get(), bps)
        if not comm.test():
            if show is True:
                messagebox.showerror("错误", '测试右手柄失败')
            res = False
        comm.close()
        return res

    def init_communication_refresh(self):
        pass

    # 单个手柄数据读取
    def read_data(self, comm: BaseComm, q: queue.Queue):
        q.put(comm.read1epoch())

    # 第二个线程，负责读取
    def read_thread(self):
        while True:
            time.sleep(0.01)
            q_left = queue.Queue()
            q_right = queue.Queue()
            # data_left = self.comm_left.read1epoch()
            # data_right = self.comm_right.read1epoch()
            thread_left = threading.Thread(target=self.read_data, args=(self.comm_left, q_left))
            thread_right = threading.Thread(target=self.read_data, args=(self.comm_right, q_right))
            thread_left.setDaemon(True)
            thread_right.setDaemon(True)
            thread_left.start()
            thread_right.start()
            thread_left.join(5)
            thread_right.join(5)
            if q_left.empty() or q_right.empty():
                print('WARING: 数据读取失败!')
                continue
            data_left = q_left.get()
            data_right = q_right.get()
            self.lock.acquire()
            self.raw.append([data_left, data_right])
            if len(self.raw) > self.n:
                self.raw = self.raw[1:-1]
            self.lock.release()
            # frames添加数据
            ann = data_left[0:6]
            ann.extend(data_right[0:6])
            self.lock.acquire()
            self.frames.append(ann)
            if len(self.frames) > self.n:
                self.frames = self.frames[1:-1]
            self.lock.release()
            # print('ANN DATA:', ann)

    def parse_thread(self):
        # 建模
        try:
            model = load_model(self.model_file)
        except OSError:
            print("Can't find", self.model_file)
            model = Sequential()
            model.add(Dense(self.select * 12, activation='tanh', input_dim=self.select * 12))
            model.add(Dense(self.select * 24, activation='tanh'))
            model.add(Dense(self.select * 32, activation='tanh'))
            model.add(Dense(self.select * 48, activation='tanh'))
            model.add(Dense(self.select * 32, activation='tanh'))
            model.add(Dense(self.select * 24, activation='tanh'))
            model.add(Dense(self.select * 12, activation='tanh'))
            model.add(Dense(self.select, activation='tanh'))
            model.add(Dense(6, activation='softmax'))

            model.compile(loss='binary_crossentropy', optimizer='adam')

        start = time.time()

        while True:
            self.var_training.set(self.training)

            # 只需要MPU数据
            self.lock.acquire()
            data_left = self.raw[-1][0][:6]
            data_right = self.raw[-1][1][:6]
            self.lock.release()
            # data_left = self.comm_left.read1epoch()[:6]
            # data_right = self.comm_right.read1epoch()[:6]
            # print(data)
            data = data_left
            data.extend(data_right)
            # print(data)
            # self.lock.acquire()
            # self.frames.append(data)
            # if len(self.frames) > self.n:
            #     self.frames = self.frames[1:-1]
            # self.lock.release()
            if self.t1 == 5:
                im = self.draw()
                imp = ImageTk.PhotoImage(image=im)
                self.panel.configure(image=imp)
                self.panel.image = imp
                self.t1 = 0
            self.t1 += 1

            # 开始训练
            if self.t2 == 5 and self.train_mode is True:
                self.lock.acquire()
                x = np.array(self.frames[len(self.frames) - self.select:])
                self.lock.release()
                x = x.reshape((1, x.size))
                # print('X shape:', x.shape)
                one = [0 for i in range(6)]
                one[self.ACTIONS.index(self.training)] = 1
                y = np.array(one)
                y = y.reshape((1, 6))
                # print('Y shape:', y.shape)
                self.t2 = 0
                res = model.train_on_batch(x=x, y=y)
                # print('train:', res)
                self.logger_test.push(UiLogger.Item(UiLogger.LEVEL_INFO, 'training', '%s' % res))

            self.t2 += 1

            if self.will_save_model is True:
                print('保存模型...')
                self.lock.acquire()
                model.save(self.model_file)
                self.will_save_model = False
                self.lock.release()

            # 预测模式
            if self.t2 == 5 and self.train_mode is False:
                self.t2 = 0
                self.lock.acquire()
                x = np.array(self.frames[len(self.frames) - self.select:])
                self.lock.release()
                x = x.reshape((1, x.size))
                # print('X shape:', x.shape)
                # res = model.train_on_batch(x=x, y=y)
                predict = model.predict(x=x)[0]
                predict = predict.tolist()
                res = predict.index(max(predict))
                res = self.ACTIONS[res]
                # print('predict:', res)
                self.logger_test.push(UiLogger.Item(UiLogger.LEVEL_INFO, 'predict %.2f' % (time.time() - start), '%s' % res))

    def draw(self):
        width = 1
        height = 32
        colors = [
            'red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple',
            'red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple',
        ]

        size = (width * self.n, height * 6)
        im = Image.new("RGB", size, color='white')
        draw = ImageDraw.Draw(im)
        for i in range(self.n - 2):
            for j in range(12):
                draw.line((width * i, self.frames[i][j] + size[1] / 2,
                           width * (i + 1), self.frames[i + 1][j] + size[1] / 2), fill=colors[j])
        sx = size[0] - width * self.select
        draw.line((sx, 0, sx, size[1]), fill='red')
        return im


if __name__ == '__main__':
    multiprocessing.freeze_support()
    _trainer = MCHandleTrainer()
    # _trainer.init_communication()
    _trainer.mainloop()
