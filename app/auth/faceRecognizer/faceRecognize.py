#insightface from camera ，树莓派5B平台
import cv2
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import os
import insightface
from insightface.app import FaceAnalysis
import threading
import queue    
import matplotlib.pyplot as plt
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


# 创建 FaceAnalysis 对象，使用速度更快的模型
app = FaceAnalysis(det_name='scrfd')
# 准备模型，使用 GPU
app.prepare(ctx_id=0)
def creatNpy(path):
	 # 加载人脸图像，图像在./faces文件夹下
	faces = {}
	path1=os.path.join(path,'faces')
	for face in os.listdir(path1):
		img_pil = Image.open(os.path.join(path1, face))
		img_pil=np.array(img_pil)
		faces[face.split('.')[0]] = app.get(img_pil)[0].embedding
	np.save(os.path.join(path,'face_recognizer.npy'), faces)
	return "success"
def recognize(faceImg):
	if faceImg is None or not isinstance(faceImg, np.ndarray) or len(faceImg.shape) != 3:
		print("输入的 face 不是一个有效的图像数组")
		raise ValueError("输入的 face 不是一个有效的图像数组")

	path=os.path.join(os.getcwd(),"app","auth","faceRecognizer")
	#将faces中的人脸特征保存到face_recognizer.npy文件中
	if os.path.exists(os.path.join(path	,'./face_recognizer.npy')):
	    faces = np.load(os.path.join(path,'./face_recognizer.npy'), allow_pickle=True).item()
	else:
		creatnpy(path)
		faces = np.load(os.path.join(path,'face_recognizer.npy'), allow_pickle=True).item()
	faceImg=np.array(faceImg)
	# 人脸识别
	face = app.get(faceImg)
	if len(face)==0:
		return None
	#与faces中已知的人脸匹配
	distances={}
	for name, face_ in faces.items():
		# 计算欧式距离
		dist = np.sum(np.square(face[0].embedding - face_))
		distances[name] = dist
	# 找出最小的距离和key
	name = min(distances, key=distances.get)
	# 
	if distances[name] < 500:
		return name
	else:
		return None

		
		


	


