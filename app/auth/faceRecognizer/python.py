import cv2
import time
import numpy as np
import io
from PIL import ImageFont, ImageDraw, Image
import os
import insightface
from insightface.app import FaceAnalysis
import pyttsx3
import threading
engine = pyttsx3.init()
#设定pyttsx3中文播报
engine.setProperty('voice', 'zh')
engine.setProperty('rate', 150)

# 创建 FaceAnalysis 对象，使用速度更快的模型
app = FaceAnalysis(det_name='scrfd')
# 准备模型，使用 GPU
app.prepare(ctx_id=0)
class VideoCapture:
    def __init__(self, url):
        self.cap = cv2.VideoCapture(url)
        self.q = queue.Queue()
        t = threading.Thread(target=self._reader)
        t.daemon = True
        t.start()

    # 读取帧的线程
    def _reader(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            if not self.q.empty():
                try:
                    self.q.get_nowait()   # discard previous (unprocessed) frame
                except queue.Empty:
                    pass
            self.q.put(frame)

    def read(self):
        return self.q.get()
#获取rtsp视频流
rtsp='rtsp://192.168.240.228:8554/camera'
cap=cv2.VideoCapture(rtsp)
#读取npy文件
if os.path.exists('face_recognizer.npy'):
    faces = np.load('face_recognizer.npy', allow_pickle=True).item()
else:
    # 加载人脸图像，图像在./faces文件夹下
    faces = {}
    for face in os.listdir('./faces'):
        img_pil = Image.open(os.path.join('./faces', face))
        img_pil=np.array(img_pil)
        faces[face.split('.')[0]] = app.get(img_pil)[0].embedding
        np.save('face_recognizer.npy', faces)
# 无限循环

def puttext_chinese(img, text, point, color):
    # 图像从OpenCV格式转换成PIL格式
    img_PIL = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    # 字体
    font = ImageFont.truetype('msyh.ttf', 20, encoding="utf-8")
    # 绘制文字信息
    draw = ImageDraw.Draw(img_PIL)
    draw.text(point, text, color, font=font)
    # 转换回OpenCV格式
    img_OpenCV = cv2.cvtColor(np.asarray(img_PIL), cv2.COLOR_RGB2BGR)
    return img_OpenCV

while True:
    ret,frame=cap.read()
    if not ret:
        continue
    # 人脸检测
    faces_ = app.get(frame)
    #画框
    for idx, face in enumerate(faces_):
        bbox = face.bbox.astype(int)
        cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
        #画出关键点
        if face.landmark is not None:
            for i in range(5):
                cv2.circle(frame, (int(face.landmark[i][0]), int(face.landmark[i][1])), 1, (0, 0, 255), 2)
        #识别
        for name, embedding in faces.items():
            dist = np.sum(np.square(embedding - face.embedding))
            if dist < 500:
                
                # 语音播报
                engine.say(name)
                engine.runAndWait()
                frame = puttext_chinese(frame, name, (bbox[0], bbox[1] - 20), (0, 255, 0))
                break
    cv2.imshow('frame',frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break