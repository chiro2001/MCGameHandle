from tkinter import *
from tkinter import messagebox
from keras.layers import Dense
from keras.models import Sequential
import serial
import serial.tools.list_ports
import threading
from PIL import Image, ImageDraw, ImageTk

from host.BaseComm import BaseComm
from host.ui_logger import UiLogger


class MCHandleTrainer:
    ACTION_FORWARD = 0
    ACTION_JUMP = 1
    ACTION_DOWN = 2
    ACTION_HIT = 3
    ACTION_PUT = 4
    ACTION_NONE = 5

    def __init__(self, root=None):
        self.init_top = Tk()

        self.init_bps = StringVar()
        self.init_bps.set('115200')
        self.init_com_left = StringVar()
        self.init_com_left.set('COM4')
        self.init_com_right = StringVar()
        self.init_com_right.set('COM4')

        self.init_communication()

        self.port_left = 'COM4'
        self.port_right = 'COM4'
        self.bps = 115200
        self.comm = None
        self.n = 512
        self.frames = [[0 for i in range(6)] for j in range(self.n)]

        self.comm_left = BaseComm(self.init_com_left.get(), self.bps)
        # self.comm_right = BaseComm(self.init_com_right.get(), self.bps)

        self.root = root
        if self.root is None:
            self.root = Tk()
        self.root.title("MC手柄训练器")

        self.panel = Label(self.root)
        self.panel.pack(side=TOP, expand=1, fill=X)

        frame = Frame(self.root)
        Button(frame, text='预测模式').grid(row=1, column=1, sticky=W + E)
        Button(frame, text='前进').grid(row=1, column=2, sticky=W + E)
        Button(frame, text='上跳').grid(row=1, column=3, sticky=W + E)
        Button(frame, text='下降').grid(row=1, column=4, sticky=W + E)
        Button(frame, text='打击').grid(row=1, column=5, sticky=W + E)
        Button(frame, text='放置').grid(row=1, column=6, sticky=W + E)
        Button(frame, text='无动作').grid(row=1, column=7, sticky=W + E)
        Label(frame, text='正在训练:').grid(row=1, column=8, sticky=W + E)

        self.var_training = StringVar()
        self.var_training.set('...')
        Label(frame, textvariable=self.var_training).grid(row=1, column=9, sticky=W + E)

        frame.pack(side=BOTTOM, expand=1, fill=X)

        self.logger_test = UiLogger(self.root, title='测试结果', simplify=True, height=10)
        self.logger_test.logger().pack(side=BOTTOM, expand=1, fill=X)

        self.lock = threading.Lock()

        t = threading.Thread(target=self.read_thread)
        t.setDaemon(True)
        t.start()

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
        comm = BaseComm(self.init_com_left.get(), bps)
        if not comm.test():
            if show is True:
                messagebox.showerror("错误", '测试右手柄失败')
            res = False
        comm.close()
        return res

    def init_communication_refresh(self):
        pass

    def read_thread(self):
        while True:
            data = self.comm_left.read1epoch()
            # print(data)
            self.lock.acquire()
            self.frames.append(data)
            if len(self.frames) > self.n:
                self.frames = self.frames[1:-1]
            self.lock.release()
            im = self.draw()
            imp = ImageTk.PhotoImage(image=im)
            self.panel.configure(image=imp)
            self.panel.image = imp

    def draw(self):
        width = 1
        height = 32
        colors = [
            'red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple'
        ]

        size = (width * self.n, height * 6)
        im = Image.new("RGB", size, color='white')
        draw = ImageDraw.Draw(im)
        for i in range(self.n - 2):
            for j in range(6):
                draw.line((width * i, self.frames[i][j] + size[1] / 2,
                           width * (i + 1), self.frames[i + 1][j] + size[1] / 2), fill=colors[j])
        return im


if __name__ == '__main__':
    _trainer = MCHandleTrainer()
    # _trainer.init_communication()
    _trainer.mainloop()